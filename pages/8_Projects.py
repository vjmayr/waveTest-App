"""
pages/8_Projects.py — Project administration
=================================================

Create, list, and delete consultancy projects bound to a client and a
project type. The auto-generated artefacts directory is created lazily
the first time an assessment runs against the project.
"""

from __future__ import annotations

from datetime import date

import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from wavetest_app._time import utc_now
from wavetest_app.auth import require_login
from wavetest_app.config import project_artifacts_dir
from wavetest_app.db.ids import next_id
from wavetest_app.db.models import Client, Project, ProjectType
from wavetest_app.db.session import get_session
from wavetest_app.ui import page_header

st.set_page_config(
    page_title="Projects · waveTest", page_icon="📋", layout="wide",
)

require_login()

page_header(
    "📋 Projects",
    "Engagements bound to a client + project type · PRJ{NNNN} IDs auto-generated",
)

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
with get_session() as db:
    clients = db.scalars(select(Client).order_by(Client.company_name)).all()
    project_types = db.scalars(
        select(ProjectType).order_by(ProjectType.type_name)
    ).all()
    client_options = [(c.client_id, c.company_name) for c in clients]
    type_options = [
        (pt.type_id, pt.type_name, pt.description, pt.standard_services or [])
        for pt in project_types
    ]

if not client_options:
    st.warning("No clients exist yet. Create a client on the **Clients** page first.")
    st.stop()
if not type_options:
    st.warning(
        "No project types defined yet. Create one on the **Project Types** page first."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
with st.form("new_project", clear_on_submit=False):
    st.subheader("Create new project")

    c1, c2 = st.columns(2)
    with c1:
        client_id = st.selectbox(
            "Client",
            [cid for cid, _ in client_options],
            format_func=lambda cid: f"{cid} — "
                                    + dict([(cid_, n) for cid_, n in client_options]).get(cid, ""),
        )
        project_name = st.text_input("Project name")
        start_date = st.date_input("Start date", value=date.today())

    with c2:
        type_id = st.selectbox(
            "Project type",
            [t[0] for t in type_options],
            format_func=lambda t: f"{t} — "
                                  + dict([(tid, name) for tid, name, *_ in type_options]).get(t, ""),
        )
        # Show selected type's description + standard services
        sel = next((t for t in type_options if t[0] == type_id), None)
        if sel:
            _, _, desc, services = sel
            st.caption(f"_{desc or 'No description provided.'}_")
            if services:
                st.markdown(
                    "Standard services:\n"
                    + "\n".join(f"  - {svc}" for svc in services)
                )

    description = st.text_area(
        "Project description / scope notes", height=80,
    )

    if st.form_submit_button("Create project", type="primary"):
        if not project_name.strip():
            st.error("Project name is required.")
        else:
            sel = next((t for t in type_options if t[0] == type_id), None)
            type_name = sel[1] if sel else type_id
            type_description = sel[2] if sel else ""
            services = sel[3] if sel else []

            with get_session() as db:
                project_id = next_id(db, Project.project_id, "PRJ")
                # Compute the artefacts root so we can record its path —
                # actual mkdir happens when the first assessment runs.
                client = db.get(Client, client_id)
                folder = project_artifacts_dir(
                    client.client_id, client.company_name,
                    project_id, project_name.strip(),
                )
                db.add(Project(
                    project_id=project_id,
                    client_id=client_id,
                    project_type_id=type_id,
                    project_name=project_name.strip(),
                    project_type=type_name,
                    project_type_description=type_description,
                    standard_services=services,
                    description=description.strip(),
                    start_date=start_date,
                    folder_path=str(folder),
                    status="active",
                    created_date=utc_now(),
                ))
            st.success(f"Created project `{project_id}` — {project_name}")
            st.rerun()

# ---------------------------------------------------------------------------
# List + delete + status toggle
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Existing projects")

with get_session() as db:
    projects = db.scalars(
        select(Project)
        .options(joinedload(Project.client))
        .order_by(Project.created_date.desc())
    ).all()
    rows = [
        {
            "ID":         p.project_id,
            "Name":       p.project_name,
            "Client":     f"{p.client_id} — {p.client.company_name}",
            "Type":       p.project_type or "—",
            "Status":     p.status,
            "Started":    p.start_date.isoformat() if p.start_date else "—",
            "Folder":     p.folder_path or "—",
        }
        for p in projects
    ]

if not rows:
    st.info("No projects yet.")
else:
    st.dataframe(rows, hide_index=True, use_container_width=True)

    st.markdown("##### Update project")
    target = st.selectbox(
        "Project",
        [r["ID"] + " — " + r["Name"] for r in rows],
        key="upd_proj_pick",
    )
    pid = target.split(" — ")[0]
    new_status = st.selectbox(
        "Status", ["active", "on_hold", "completed", "archived"],
        key="upd_proj_status",
    )
    if st.button("Update status", key="upd_proj_btn"):
        with get_session() as db:
            p = db.get(Project, pid)
            if p:
                p.status = new_status
        st.success(f"`{pid}` status set to `{new_status}`.")
        st.rerun()

    st.markdown("##### Delete project")
    confirm = st.checkbox(
        f"Yes, permanently delete `{pid}`",
        key="del_proj_confirm",
    )
    if st.button("Delete", disabled=not confirm, key="del_proj_btn"):
        with get_session() as db:
            p = db.get(Project, pid)
            if p:
                db.delete(p)
        st.success(f"Deleted `{pid}`.")
        st.rerun()
