"""
Home.py — wavetest-app landing page + login gate
====================================================

Routes the unauthenticated user to a sign-in form and, on success, shows
the operator console (toolchain status banner + client/project tree).
Run with::

    streamlit run Home.py
"""

import importlib
from typing import Any

import streamlit as st
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from wavetest_app.auth import get_authenticator
from wavetest_app.db.models import Client, Project, ProjectType, System
from wavetest_app.db.session import get_session, init_db
from wavetest_app.ui import page_header

st.set_page_config(
    page_title="waveTest | Home",
    page_icon="🌊",
    layout="wide",
)

# Make sure tables exist on first launch
init_db()

# ---------------------------------------------------------------------------
# Login gate — every other page also calls require_login(), but the form
# itself only renders here on the Home page.
# ---------------------------------------------------------------------------
authenticator = get_authenticator()
authenticator.login(location="main")

auth_status = st.session_state.get("authentication_status")

if auth_status is False:
    st.error("Username or password is incorrect.")
    st.stop()

if auth_status is None:
    page_header(
        "🌊 waveTest — Operator Console",
        "Sign in to continue",
    )
    st.info(
        "Sign in to access the EU AI Act assessment toolchain. "
        "Need an account? Ask an admin to run "
        "`python scripts/auth_add_user.py`."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Authenticated — render dashboard
# ---------------------------------------------------------------------------
authenticator.logout(location="sidebar")
st.sidebar.caption(f"Signed in as **{st.session_state.get('name', '')}**")

page_header(
    "🌊 waveTest — Operator Console",
    "Technical Compliance Toolkit for high-risk AI systems · "
    "covers Art. 10, 12 fully and 13 / 15 / 61 / 72 partially "
    "(see README for scope)",
)

# ---------------------------------------------------------------------------
# Toolchain status banner
# ---------------------------------------------------------------------------
TOOLCHAIN_PACKAGES = [
    ("wavetest_fairness",    "Bias Detection (Art. 10 / 13 / 61)"),
    ("wavetest_explain",     "SHAP Explainability (Art. 13)"),
    ("wavetest_dataquality", "Data Governance (Art. 10 + GDPR Art. 9)"),
    ("wavetest_logging",     "Record-keeping (Art. 12)"),
    ("wavetest_monitoring",  "Accuracy & Robustness (Art. 15)"),
    ("wavetest_report",      "Standardised report envelope (HTML/PDF)"),
]


def _toolchain_status() -> list[dict[str, Any]]:
    rows = []
    for pkg, label in TOOLCHAIN_PACKAGES:
        try:
            mod = importlib.import_module(pkg)
            rows.append({
                "Package": pkg, "Module": label,
                "Installed": "✓",
                "Version": getattr(mod, "__version__", "?"),
            })
        except ImportError as e:
            rows.append({
                "Package": pkg, "Module": label,
                "Installed": "❌",
                "Version": str(e),
            })
    return rows


with st.expander("Toolchain status", expanded=False):
    rows = _toolchain_status()
    st.dataframe(rows, hide_index=True, use_container_width=True)
    if any(r["Installed"] == "❌" for r in rows):
        st.warning(
            "One or more wavetest_* packages are missing. Run "
            "`./scripts/install_toolchain.sh` to install them editable from "
            "your RAI-TOOLCHAIN checkout."
        )

# ---------------------------------------------------------------------------
# Database overview
# ---------------------------------------------------------------------------
with get_session() as db:
    counts = {
        "clients":       db.scalar(select(func.count()).select_from(Client))      or 0,
        "systems":       db.scalar(select(func.count()).select_from(System))      or 0,
        "projects":      db.scalar(select(func.count()).select_from(Project))     or 0,
        "project_types": db.scalar(select(func.count()).select_from(ProjectType)) or 0,
    }
    clients = db.scalars(
        select(Client)
        .options(joinedload(Client.systems), joinedload(Client.projects))
        .order_by(Client.created_date.desc())
    ).unique().all()
    # Detach Client rows + their joinedload-loaded systems/projects so the
    # iteration below survives the implicit commit (see helpers.py for the
    # same fix in project_picker).
    db.expunge_all()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Clients",       counts["clients"])
c2.metric("Systems",       counts["systems"])
c3.metric("Projects",      counts["projects"])
c4.metric("Project types", counts["project_types"])

st.divider()

# ---------------------------------------------------------------------------
# Client / project tree
# ---------------------------------------------------------------------------
if not clients:
    st.info(
        "**Database is empty.** Seed it from your existing waveImpact Console:\n\n"
        "```bash\n"
        "python scripts/import_console_json.py\n"
        "```\n\n"
        "Then refresh this page."
    )
else:
    st.subheader("Clients & projects")
    for client in clients:
        with st.expander(
            f"🏢 {client.company_name} ({client.client_id}) · "
            f"{len(client.systems)} system(s) · {len(client.projects)} project(s)",
            expanded=False,
        ):
            cols = st.columns([1, 2, 2])
            cols[0].markdown(f"**Country**\n\n{client.country or '—'}")
            cols[1].markdown(
                f"**Languages**\n\n{', '.join(client.languages) if client.languages else '—'}"
            )
            cols[2].markdown(
                f"**Folder**\n\n`{client.folder_path or '—'}`"
            )

            if client.systems:
                st.markdown("**Systems:**")
                st.dataframe(
                    [
                        {
                            "ID": s.system_id,
                            "Name": s.system_name,
                            "Description": s.description[:80] or "—",
                            "Classified": s.classification_date.strftime("%Y-%m-%d")
                                          if s.classification_date else "—",
                        }
                        for s in client.systems
                    ],
                    hide_index=True, use_container_width=True,
                )

            if client.projects:
                st.markdown("**Projects:**")
                st.dataframe(
                    [
                        {
                            "ID": p.project_id,
                            "Name": p.project_name,
                            "Type": p.project_type or "—",
                            "Status": p.status,
                            "Started": p.start_date.isoformat() if p.start_date else "—",
                        }
                        for p in client.projects
                    ],
                    hide_index=True, use_container_width=True,
                )

st.divider()
st.caption(
    "Use the page navigation on the left to run individual assessments. "
    "Each assessment writes its artefacts to `artifacts/<client>/<project>/` and "
    "stays linked to the project in the database."
)
