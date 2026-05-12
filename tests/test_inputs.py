"""Tests for the central per-project input store (INPUT_SPEC §Z)."""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from wavetest_app.db.models import Client, Project, ProjectInput
from wavetest_app.db.session import get_session
from wavetest_app.inputs import (
    SLOT_EXT,
    SLOT_KIND,
    SLOTS,
    delete_input,
    list_inputs,
    load_input,
    save_input,
)


# ---------------------------------------------------------------------------
# Slot tables
# ---------------------------------------------------------------------------
class TestSlotTables:
    def test_seven_canonical_slots(self):
        assert len(SLOTS) == 7
        assert set(SLOTS) == {
            "dataset", "dataset_train", "sklearn_model", "pytorch_model",
            "hf_model_id", "privileged_groups_json", "target_population_json",
        }

    def test_every_slot_has_a_kind(self):
        for s in SLOTS:
            assert SLOT_KIND[s] in {"file", "value"}

    def test_file_slots_have_extensions(self):
        file_slots = [s for s in SLOTS if SLOT_KIND[s] == "file"]
        for s in file_slots:
            assert s in SLOT_EXT
            assert SLOT_EXT[s].startswith(".")


# ---------------------------------------------------------------------------
# Helper round-trips
# ---------------------------------------------------------------------------
def _make_project(tmp_path: Path) -> tuple[str, str]:
    """Create a Client + Project with a writable folder_path under tmp_path.
    Returns (project_id, folder_path) for follow-up loads.
    """
    folder = tmp_path / "proj_artifacts"
    folder.mkdir(parents=True, exist_ok=True)
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(Project(
            project_id="PRJ0001",
            client_id="CLI0001",
            project_name="X",
            project_type="Y",
            folder_path=str(folder),
        ))
    return "PRJ0001", str(folder)


def _fetch_project(project_id: str):
    """Return a detached Project (mirrors the picker pattern)."""
    from sqlalchemy.orm import joinedload
    with get_session() as db:
        proj = db.scalars(
            select(Project)
            .options(joinedload(Project.client))
            .where(Project.project_id == project_id)
        ).first()
        db.expunge_all()
    return proj


def test_save_and_load_file_slot(in_memory_db, tmp_path):
    pid, _ = _make_project(tmp_path)
    proj = _fetch_project(pid)

    csv = b"y_true,y_pred\n1,1\n0,0\n"
    save_input(proj, "dataset", file_bytes=csv,
               content_type="text/csv", actor="test")

    loaded = load_input(proj, "dataset")
    assert isinstance(loaded, Path)
    assert loaded.exists()
    assert loaded.read_bytes() == csv

    info = list_inputs(proj)["dataset"]
    assert info["present"] is True
    assert info["size_bytes"] == len(csv)
    assert info["uploaded_by"] == "test"


def test_save_and_load_value_slot(in_memory_db, tmp_path):
    pid, _ = _make_project(tmp_path)
    proj = _fetch_project(pid)

    save_input(
        proj, "hf_model_id",
        value="distilbert-base-uncased-finetuned-sst-2-english",
        actor="test",
    )
    loaded = load_input(proj, "hf_model_id")
    assert isinstance(loaded, str)
    assert loaded.startswith("distilbert")


def test_load_missing_slot_returns_none(in_memory_db, tmp_path):
    pid, _ = _make_project(tmp_path)
    proj = _fetch_project(pid)
    assert load_input(proj, "pytorch_model") is None


def test_save_replaces_existing(in_memory_db, tmp_path):
    pid, _ = _make_project(tmp_path)
    proj = _fetch_project(pid)

    save_input(proj, "hf_model_id", value="first", actor="a")
    save_input(proj, "hf_model_id", value="second", actor="b")

    with get_session() as db:
        rows = db.scalars(
            select(ProjectInput).where(
                ProjectInput.project_id == pid,
                ProjectInput.slot == "hf_model_id",
            )
        ).all()
        assert len(rows) == 1, "save_input should upsert, not insert"
        assert rows[0].value == "second"
        assert rows[0].uploaded_by == "b"


def test_unknown_slot_raises(in_memory_db, tmp_path):
    pid, _ = _make_project(tmp_path)
    proj = _fetch_project(pid)
    with pytest.raises(ValueError, match="unknown slot"):
        save_input(proj, "garbage_slot", value="x")
    with pytest.raises(ValueError, match="unknown slot"):
        load_input(proj, "garbage_slot")


def test_file_slot_requires_file_bytes(in_memory_db, tmp_path):
    pid, _ = _make_project(tmp_path)
    proj = _fetch_project(pid)
    with pytest.raises(ValueError, match="file slot"):
        save_input(proj, "dataset", value="not a file")


def test_value_slot_requires_value(in_memory_db, tmp_path):
    pid, _ = _make_project(tmp_path)
    proj = _fetch_project(pid)
    with pytest.raises(ValueError, match="value slot"):
        save_input(proj, "hf_model_id", file_bytes=b"x")


def test_delete_returns_true_when_existed(in_memory_db, tmp_path):
    pid, _ = _make_project(tmp_path)
    proj = _fetch_project(pid)

    save_input(proj, "dataset", file_bytes=b"x,y\n1,2\n")
    assert delete_input(proj, "dataset") is True
    assert delete_input(proj, "dataset") is False  # already gone
    assert load_input(proj, "dataset") is None


def test_delete_removes_file_from_disk(in_memory_db, tmp_path):
    pid, folder = _make_project(tmp_path)
    proj = _fetch_project(pid)
    save_input(proj, "dataset", file_bytes=b"x,y\n1,2\n")
    on_disk = Path(folder) / "inputs" / "dataset.csv"
    assert on_disk.exists()
    delete_input(proj, "dataset")
    assert not on_disk.exists()


def test_list_inputs_returns_every_slot(in_memory_db, tmp_path):
    pid, _ = _make_project(tmp_path)
    proj = _fetch_project(pid)
    snap = list_inputs(proj)
    assert set(snap.keys()) == set(SLOTS)
    for v in snap.values():
        assert v["present"] is False
    save_input(proj, "hf_model_id", value="x")
    snap = list_inputs(proj)
    assert snap["hf_model_id"]["present"] is True
    assert snap["dataset"]["present"] is False


# ---------------------------------------------------------------------------
# Constraints
# ---------------------------------------------------------------------------
def test_unique_constraint_on_project_slot(in_memory_db, tmp_path):
    """Cannot insert two ProjectInput rows for the same (project, slot)."""
    pid, _ = _make_project(tmp_path)
    # Insert one directly via SQLAlchemy, then try to insert a duplicate
    with get_session() as db:
        db.add(ProjectInput(
            input_id="PI0001",
            project_id=pid, slot="dataset",
            file_path="x", size_bytes=1,
        ))
    with pytest.raises(IntegrityError):
        with get_session() as db:
            db.add(ProjectInput(
                input_id="PI0002",
                project_id=pid, slot="dataset",
                file_path="y", size_bytes=1,
            ))


def test_project_delete_cascades(in_memory_db, tmp_path):
    pid, _ = _make_project(tmp_path)
    proj = _fetch_project(pid)
    save_input(proj, "dataset", file_bytes=b"x,y\n1,2\n")
    save_input(proj, "hf_model_id", value="m")

    with get_session() as db:
        db.delete(db.get(Project, pid))

    with get_session() as db:
        remaining = db.scalars(select(ProjectInput)).all()
        assert remaining == []
