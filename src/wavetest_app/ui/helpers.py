"""
wavetest_app.ui.helpers — Shared Streamlit components
========================================================

Small functions reused across pages so individual page files stay tight.
"""

from __future__ import annotations

from typing import Iterable, Optional

import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from wavetest_app.db.models import Project
from wavetest_app.db.session import get_session


# ---------------------------------------------------------------------------
def page_header(title: str, subtitle: str = "", articles: Optional[list[str]] = None) -> None:
    """Standard page header with branded gradient + EU AI Act tags."""
    article_html = ""
    if articles:
        chips = " ".join(
            f'<span style="background:#eef1f9; color:#445; font-size:11px; '
            f'padding:2px 8px; border-radius:8px; margin-right:6px;">'
            f'EU AI Act Art. {a}</span>'
            for a in articles
        )
        article_html = f'<div style="margin-top:8px;">{chips}</div>'

    st.markdown(
        f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 18px 24px; border-radius: 10px; margin-bottom: 20px;">
            <h1 style="color: white; margin: 0; font-size: 22px;">{title}</h1>
            <p style="color: white; margin: 4px 0 0 0; opacity: 0.9; font-size: 13px;">{subtitle}</p>
            {article_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
def project_picker(
    label: str = "Project",
    key: str = "project_picker",
) -> Optional[Project]:
    """Sidebar dropdown listing all projects (joined with their client).

    Returns the selected ``Project`` or ``None`` if the DB is empty.
    """
    with get_session() as db:
        rows = db.scalars(
            select(Project)
            .options(joinedload(Project.client))
            .order_by(Project.created_date.desc())
        ).all()
        # Detach Projects AND their joinedload-loaded Clients before the
        # context manager's commit() expires them. expunge() is per-instance
        # and does not cascade through relationships, so per-row expunge()
        # would leave Clients attached → DetachedInstanceError on first
        # access of p.client.* after the session closes.
        db.expunge_all()

    if not rows:
        st.sidebar.warning(
            "No projects in the database. Run "
            "`python scripts/import_console_json.py` to seed from your existing "
            "waveImpact_ClientManagement folder, or add one via the Admin page."
        )
        return None

    options = {
        f"{p.project_id} — {p.client.company_name} / {p.project_name}": p
        for p in rows
    }
    chosen = st.sidebar.selectbox(label, list(options.keys()), key=key)
    return options[chosen] if chosen else None


# ---------------------------------------------------------------------------
def risk_pill(label: str, value: str, status: str = "ok") -> str:
    """HTML chip used in summary rows (matches wavetest_report colours)."""
    color = {
        "ok": "#06A77D", "warning": "#F77F00", "critical": "#D62828",
    }.get(status, "#999")
    return (
        f'<div style="display:inline-block; padding:8px 14px; border-radius:8px; '
        f'background:{color}; color:white; margin-right:8px; margin-bottom:8px;">'
        f'<div style="font-size:11px; opacity:0.85;">{label}</div>'
        f'<div style="font-size:18px; font-weight:600;">{value}</div>'
        f'</div>'
    )


# ---------------------------------------------------------------------------
def show_recommendations(recs: Iterable[str]) -> None:
    """Render a recommendation list as a callout block."""
    if not recs:
        return
    items = "".join(f"<li>{r}</li>" for r in recs)
    st.markdown(
        f"""
        <div style="background:#fff8ec; border-left:4px solid #F77F00;
                    padding:14px 18px; border-radius:6px;">
            <strong>Recommendations</strong>
            <ol style="margin:8px 0 0 16px;">{items}</ol>
        </div>
        """,
        unsafe_allow_html=True,
    )
