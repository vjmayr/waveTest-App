"""
wavetest_app.inputs — central per-project input store
==========================================================

Implements §Z of ``docs/INPUT_SPEC.md``: every assessment module loads
its input artefacts from one of seven canonical slots on the project,
instead of asking the analyst to upload the same CSV on every page.

Public API
----------

* :data:`SLOTS` — tuple of valid slot names.
* :data:`SLOT_KIND` — ``"file"`` or ``"value"`` per slot.
* :data:`SLOT_EXT` — file extension per file-based slot.
* :data:`SLOT_LABEL` — human-readable display label per slot.
* :func:`save_input` — upsert one slot. Replaces the previous value
  + writes ``audit_log``.
* :func:`load_input` — returns a ``Path`` (file slots) or ``str``
  (value slots), or ``None`` if not yet uploaded.
* :func:`list_inputs` — snapshot of every slot for UI display.
* :func:`delete_input` — remove a slot (and its file, if any).

Files live in ``<project.folder_path>/inputs/<slot><ext>``. The
``project.folder_path`` is set when the project is created; the
``inputs/`` subfolder is created lazily by :func:`save_input`.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Optional, Union

from sqlalchemy import select

from wavetest_app._time import utc_now
from wavetest_app.audit import record_run
from wavetest_app.db.ids import next_id
from wavetest_app.db.models import ProjectInput
from wavetest_app.db.session import get_session


# Order matters for the UI — slots render top-to-bottom in this order.
SLOTS: tuple[str, ...] = (
    "dataset",
    "dataset_train",
    "sklearn_model",
    "pytorch_model",
    "hf_model_id",
    "privileged_groups_json",
    "target_population_json",
)

SLOT_KIND: dict[str, str] = {
    "dataset":                  "file",
    "dataset_train":            "file",
    "sklearn_model":            "file",
    "pytorch_model":            "file",
    "hf_model_id":              "value",
    "privileged_groups_json":   "value",
    "target_population_json":   "value",
}

SLOT_EXT: dict[str, str] = {
    "dataset":       ".csv",
    "dataset_train": ".csv",
    "sklearn_model": ".pkl",
    "pytorch_model": ".pt",
}

SLOT_LABEL: dict[str, str] = {
    "dataset":                "📊 Canonical dataset (CSV)",
    "dataset_train":          "📊 Training dataset (CSV, optional)",
    "sklearn_model":          "🤖 Scikit-learn model (.pkl)",
    "pytorch_model":          "🔥 PyTorch model (.pt)",
    "hf_model_id":            "🤗 HuggingFace model id",
    "privileged_groups_json": "⚖️ Privileged groups (JSON)",
    "target_population_json": "🎯 Target population (JSON)",
}

SLOT_DESCRIPTION: dict[str, str] = {
    "dataset":
        "Canonical project dataset. Conventional columns: `y_true` (required), "
        "`y_pred`, `timestamp`, `confidence`, then arbitrary features. "
        "Consumed by Data Quality, Bias, Explainability, Performance "
        "Monitoring, Cybersecurity (ART) and Captum.",
    "dataset_train":
        "Optional training CSV — used by Explainability as SHAP's "
        "background distribution. Same column layout as `dataset`.",
    "sklearn_model":
        "Pickled scikit-learn classifier with `predict` + `predict_proba`. "
        "Consumed by Explainability and Cybersecurity (ART).",
    "pytorch_model":
        "Full pickled `nn.Module` (not a state dict). Consumed by Captum.",
    "hf_model_id":
        "Public HuggingFace model id, e.g. "
        "`distilbert-base-uncased-finetuned-sst-2-english`. Consumed by "
        "TextAttack.",
    "privileged_groups_json":
        "JSON dict mapping `column_name → privileged_value`. Consumed by "
        "Bias Detection.",
    "target_population_json":
        "JSON dict mapping `column_name → {category: proportion}`. "
        "Consumed by Data Quality (chi-square representativeness test).",
}


# ---------------------------------------------------------------------------
# Filesystem layout
# ---------------------------------------------------------------------------
def _inputs_dir(project: Any) -> Path:
    """Return ``<project.folder_path>/inputs/``, creating it lazily."""
    base = Path(project.folder_path) if project.folder_path else None
    if base is None:
        raise ValueError(
            f"Project {project.project_id} has no folder_path; cannot "
            "store file-based inputs. Re-create the project to populate "
            "folder_path."
        )
    inputs = base / "inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    return inputs


def _file_path_for(project: Any, slot: str) -> Path:
    if slot not in SLOT_EXT:
        raise ValueError(f"{slot} is not a file slot")
    return _inputs_dir(project) / f"{slot}{SLOT_EXT[slot]}"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def _audit_action(
    project: Any, slot: str, action: str, *,
    actor: str = "system", size: Optional[int] = None,
) -> None:
    detail = f"slot={slot}"
    if size is not None:
        detail += f" size={size}"
    record_run(
        project=project, module="project_inputs",
        status=f"{action} {slot}", status_color="info",
        status_detail=detail, actor=actor,
    )


def _validate_slot(slot: str) -> None:
    if slot not in SLOTS:
        raise ValueError(
            f"unknown slot {slot!r}; valid slots: {list(SLOTS)}"
        )


def save_input(
    project: Any,
    slot: str,
    *,
    file_bytes: Optional[bytes] = None,
    value: Optional[str] = None,
    content_type: str = "",
    actor: str = "system",
    notes: str = "",
) -> ProjectInput:
    """Upsert one slot on ``project``.

    Exactly one of ``file_bytes`` / ``value`` must be set — files for
    file-slots, plain strings for value-slots. Existing slot is replaced
    in-place (UNIQUE constraint on ``project_id, slot``).

    Returns the persisted :class:`ProjectInput` row (detached after save).
    """
    _validate_slot(slot)
    kind = SLOT_KIND[slot]
    if kind == "file":
        if file_bytes is None:
            raise ValueError(
                f"slot {slot!r} is a file slot — pass file_bytes"
            )
        target = _file_path_for(project, slot)
        target.write_bytes(file_bytes)
        size = len(file_bytes)
        stored_path = str(target)
        stored_value = None
    else:
        if value is None:
            raise ValueError(
                f"slot {slot!r} is a value slot — pass value"
            )
        size = len(value.encode("utf-8"))
        stored_path = None
        stored_value = value

    with get_session() as db:
        existing = db.scalars(
            select(ProjectInput).where(
                ProjectInput.project_id == project.project_id,
                ProjectInput.slot == slot,
            )
        ).first()
        if existing is None:
            existing = ProjectInput(
                input_id=next_id(db, ProjectInput.input_id, "PI"),
                project_id=project.project_id,
                slot=slot,
            )
            db.add(existing)
        existing.file_path = stored_path
        existing.value = stored_value
        existing.content_type = content_type
        existing.size_bytes = size
        existing.uploaded_by = actor or "system"
        existing.uploaded_at = utc_now()
        if notes:
            existing.notes = notes
        db.flush()
        db.refresh(existing)
        db.expunge(existing)

    _audit_action(project, slot, "SAVED", actor=actor, size=size)
    return existing


def load_input(project: Any, slot: str) -> Optional[Union[Path, str]]:
    """Return the slot's contents, or ``None`` if not yet uploaded.

    File slots → :class:`Path` to the file on disk.
    Value slots → :class:`str` of the stored value (verbatim).
    """
    _validate_slot(slot)
    with get_session() as db:
        row = db.scalars(
            select(ProjectInput).where(
                ProjectInput.project_id == project.project_id,
                ProjectInput.slot == slot,
            )
        ).first()
        if row is None:
            return None
        kind = SLOT_KIND[slot]
        if kind == "file":
            return Path(row.file_path) if row.file_path else None
        return row.value


def list_inputs(project: Any) -> dict[str, dict[str, Any]]:
    """Snapshot of every slot for UI display.

    Returns ``{slot: {...metadata...}}`` for every slot, with absent
    slots represented as ``{"present": False}`` so the page can render
    every row regardless of upload state.
    """
    out: dict[str, dict[str, Any]] = {
        slot: {"present": False, "kind": SLOT_KIND[slot]}
        for slot in SLOTS
    }
    with get_session() as db:
        rows = db.scalars(
            select(ProjectInput).where(
                ProjectInput.project_id == project.project_id,
            )
        ).all()
        for r in rows:
            out[r.slot] = {
                "present":      True,
                "kind":         SLOT_KIND[r.slot],
                "input_id":     r.input_id,
                "file_path":    r.file_path,
                "value":        r.value,
                "size_bytes":   r.size_bytes,
                "uploaded_by":  r.uploaded_by,
                "uploaded_at":  r.uploaded_at,
                "notes":        r.notes,
            }
    return out


def delete_input(project: Any, slot: str, *, actor: str = "system") -> bool:
    """Remove a slot. Returns True if it existed."""
    _validate_slot(slot)
    deleted = False
    with get_session() as db:
        row = db.scalars(
            select(ProjectInput).where(
                ProjectInput.project_id == project.project_id,
                ProjectInput.slot == slot,
            )
        ).first()
        if row is not None:
            if row.file_path:
                Path(row.file_path).unlink(missing_ok=True)
            db.delete(row)
            deleted = True
    if deleted:
        _audit_action(project, slot, "DELETED", actor=actor)
    return deleted
