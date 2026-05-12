"""
pages/20_Project_Inputs.py — central per-project input store
=================================================================

Implements §Z of ``docs/INPUT_SPEC.md``. Per project, the analyst uploads
seven canonical input artefacts once; the assessment pages then offer
"Use project inputs" as a source option (instead of re-uploading per run).

Slots are listed in :data:`wavetest_app.inputs.SLOTS`.
"""

from __future__ import annotations

import streamlit as st

from wavetest_app.auth import current_username, require_login
from wavetest_app.inputs import (
    SLOT_DESCRIPTION,
    SLOT_EXT,
    SLOT_KIND,
    SLOT_LABEL,
    SLOTS,
    delete_input,
    list_inputs,
    save_input,
)
from wavetest_app.ui import page_header, project_picker, risk_pill

st.set_page_config(
    page_title="Project Inputs · waveTest",
    page_icon="📥",
    layout="wide",
)

require_login()

page_header(
    "📥 Project Inputs",
    "Upload the canonical artefacts once per project; "
    "every assessment page picks them up.",
)

project = project_picker()
if project is None:
    st.stop()

st.markdown(
    f"### Project: `{project.project_id}` — "
    f"{project.client.company_name} / {project.project_name}"
)

st.caption(
    "Each slot is overwrite-style — saving replaces the previous value. "
    "File slots write to `<project.folder_path>/inputs/<slot>.<ext>`; "
    "value slots store the string verbatim in the DB. Every change is "
    "recorded in the audit log under module `project_inputs`."
)

# ---------------------------------------------------------------------------
# Status pills
# ---------------------------------------------------------------------------
status = list_inputs(project)
present_count = sum(1 for v in status.values() if v["present"])

st.markdown(
    risk_pill(
        "Slots filled", f"{present_count} / {len(SLOTS)}",
        "ok" if present_count == len(SLOTS)
        else "warning" if present_count else "critical",
    ),
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Per-slot rows
# ---------------------------------------------------------------------------
def _format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:,.1f} KB"
    return f"{n / 1024 / 1024:,.2f} MB"


for slot in SLOTS:
    info = status[slot]
    kind = SLOT_KIND[slot]

    with st.expander(
        SLOT_LABEL[slot]
        + ("  ✅" if info["present"] else "  ⚪"),
        expanded=False,
    ):
        st.markdown(SLOT_DESCRIPTION[slot])

        if info["present"]:
            meta_cols = st.columns(3)
            meta_cols[0].caption(
                f"Size: **{_format_bytes(info['size_bytes'])}**"
            )
            meta_cols[1].caption(
                f"Uploaded by: **{info['uploaded_by']}**"
            )
            meta_cols[2].caption(
                "Uploaded: "
                f"**{info['uploaded_at'].strftime('%Y-%m-%d %H:%M')}**"
            )
            if kind == "value":
                st.code(info["value"], language="json"
                        if "json" in slot else "text")

        st.divider()

        # --- Upload / value input
        if kind == "file":
            ext = SLOT_EXT[slot].lstrip(".")
            uploaded = st.file_uploader(
                f"Replace {slot}{SLOT_EXT[slot]}"
                if info["present"]
                else f"Upload {slot}{SLOT_EXT[slot]}",
                type=[ext, "pickle", "joblib"] if ext == "pkl" else [ext],
                key=f"pi_upload_{slot}",
            )
            if uploaded is not None and st.button(
                f"Save {slot}", key=f"pi_save_{slot}", type="primary",
            ):
                save_input(
                    project, slot,
                    file_bytes=uploaded.getvalue(),
                    content_type=uploaded.type or "",
                    actor=current_username() or "system",
                )
                st.success(
                    f"Saved `{slot}` "
                    f"({_format_bytes(len(uploaded.getvalue()))})."
                )
                st.rerun()
        else:
            default = info["value"] or ""
            new_value = st.text_area(
                f"Value for `{slot}`",
                value=default,
                height=120 if "json" in slot else 60,
                key=f"pi_value_{slot}",
                help="JSON slots must be valid JSON (see INPUT_SPEC.md §2.4)."
                if "json" in slot else None,
            )
            if st.button(
                f"Save {slot}", key=f"pi_save_{slot}", type="primary",
                disabled=(not new_value.strip()),
            ):
                # Light validation: JSON slots should parse
                if "json" in slot:
                    import json as _json
                    try:
                        _json.loads(new_value)
                    except _json.JSONDecodeError as exc:
                        st.error(f"Not valid JSON: {exc}")
                        st.stop()
                save_input(
                    project, slot,
                    value=new_value.strip(),
                    actor=current_username() or "system",
                )
                st.success(f"Saved `{slot}`.")
                st.rerun()

        # --- Reset / delete
        if info["present"]:
            confirm = st.checkbox(
                f"Confirm reset of `{slot}`",
                key=f"pi_confirm_{slot}",
            )
            if st.button(
                f"Reset {slot}",
                key=f"pi_reset_{slot}",
                disabled=not confirm,
            ):
                delete_input(
                    project, slot,
                    actor=current_username() or "system",
                )
                st.success(f"Removed `{slot}`.")
                st.rerun()
