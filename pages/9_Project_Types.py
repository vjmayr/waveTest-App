"""
pages/9_Project_Types.py — Project type catalogue
======================================================

Manage reusable bundles of standard services (e.g. "Bias Detection &
Mitigation"). Every project picks one of these; the standard services
copy through to the project at creation time.
"""

from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from wavetest_app._time import utc_now
from wavetest_app.db.ids import next_id
from wavetest_app.db.models import ProjectType
from wavetest_app.db.session import get_session
from wavetest_app.ui import page_header

st.set_page_config(
    page_title="Project Types · waveTest", page_icon="🗂", layout="wide",
)

page_header(
    "🗂 Project Types",
    "Reusable service bundles · PT{NNNN} IDs auto-generated",
)

# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
with st.form("new_pt", clear_on_submit=True):
    st.subheader("Create new project type")
    type_name = st.text_input("Type name")
    description = st.text_area(
        "Description", height=80,
        placeholder="Short summary surfaced to consultants picking this type.",
    )
    services_text = st.text_area(
        "Standard services (one per line)", height=120,
        placeholder="Regulatory scope mapping\n"
                    "Risk classification review\n"
                    "Compliance gap analysis\n"
                    "Remediation roadmap workshop",
    )

    if st.form_submit_button("Save project type", type="primary"):
        name = type_name.strip()
        if not name:
            st.error("Type name is required.")
        else:
            services = [
                line.strip() for line in services_text.splitlines() if line.strip()
            ]
            with get_session() as db:
                # Reject duplicate names (case-insensitive)
                existing = db.scalar(
                    select(ProjectType).where(
                        ProjectType.type_name.ilike(name)
                    )
                )
                if existing:
                    st.warning(f"A project type named '{name}' already exists.")
                    st.stop()

                type_id = next_id(db, ProjectType.type_id, "PT")
                db.add(ProjectType(
                    type_id=type_id,
                    type_name=name,
                    description=description.strip(),
                    standard_services=services,
                    is_default=False,
                    created_date=utc_now(),
                    updated_date=utc_now(),
                ))
            st.success(f"Created project type `{type_id}` — {name}")
            st.rerun()

# ---------------------------------------------------------------------------
# List + delete
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Existing project types")

with get_session() as db:
    # Snapshot to plain dicts inside the session — accessing ORM column
    # attributes after the with block exits would raise
    # DetachedInstanceError (the implicit commit() expires attributes).
    types = [
        {
            "type_id":           pt.type_id,
            "type_name":         pt.type_name,
            "description":       pt.description,
            "standard_services": list(pt.standard_services or []),
            "is_default":        pt.is_default,
        }
        for pt in db.scalars(
            select(ProjectType).order_by(ProjectType.type_name)
        ).all()
    ]

if not types:
    st.info("No project types yet.")
else:
    for pt in types:
        default_badge = (
            " <span style='background:#eef1f9; color:#445; font-size:11px; "
            "padding:2px 6px; border-radius:6px; margin-left:6px;'>default</span>"
            if pt["is_default"] else ""
        )
        with st.expander(
            f"{pt['type_id']} — {pt['type_name']}", expanded=False,
        ):
            st.markdown(
                f"**{pt['type_name']}**{default_badge}",
                unsafe_allow_html=True,
            )
            st.write(pt["description"] or "_No description._")
            if pt["standard_services"]:
                st.markdown(
                    "**Standard services**\n"
                    + "\n".join(f"- {svc}" for svc in pt["standard_services"])
                )

            if pt["is_default"]:
                st.caption("⚠ Default project types cannot be deleted.")
            else:
                if st.button(
                    "Delete", key=f"del_pt_{pt['type_id']}",
                    help=f"Delete project type {pt['type_id']}",
                ):
                    with get_session() as db:
                        target = db.get(ProjectType, pt["type_id"])
                        if target:
                            db.delete(target)
                    st.success(f"Deleted `{pt['type_id']}`.")
                    st.rerun()
