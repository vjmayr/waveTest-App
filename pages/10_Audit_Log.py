"""
pages/10_Audit_Log.py — Assessment-run audit log
====================================================

Read-only view over the ``audit_log`` table. Filter by project, module,
and severity; export the filtered slice as CSV. One row per assessment
run, written by every assessment page on completion (see
:mod:`wavetest_app.audit`).
"""

from __future__ import annotations

import csv
import io

import streamlit as st
from sqlalchemy import select

from wavetest_app.db.models import AuditLog
from wavetest_app.db.session import get_session
from wavetest_app.ui import page_header

st.set_page_config(
    page_title="Audit Log · waveTest", page_icon="📜", layout="wide",
)

page_header(
    "📜 Audit Log",
    "Every assessment run — who, when, which project, summary status",
)

MODULES = [
    ("data_quality",   "📊 Data Quality"),
    ("bias",           "⚖️ Bias"),
    ("explainability", "🔍 Explain"),
    ("logging",        "📝 Logging"),
    ("monitoring",     "📈 Monitoring"),
    ("combined",       "🧾 Combined"),
]
MODULE_LABEL = dict(MODULES)
COLOR_LABEL = {
    "ok":       "🟢 ok",
    "warning":  "🟡 warning",
    "critical": "🔴 critical",
    "info":     "⚪ info",
}

# ---------------------------------------------------------------------------
# Load + snapshot inside the session (so attribute access after exit is safe)
# ---------------------------------------------------------------------------
with get_session() as db:
    rows = [
        {
            "audit_id":         r.audit_id,
            "run_at":           r.run_at,
            "module":           r.module,
            "project_id":       r.project_id or "—",
            "project_name":     r.project_name,
            "client_name":      r.client_name,
            "status":           r.status,
            "status_color":     r.status_color,
            "status_detail":    r.status_detail,
            "actor":            r.actor,
            "duration_seconds": r.duration_seconds,
        }
        for r in db.scalars(
            select(AuditLog).order_by(AuditLog.run_at.desc())
        ).all()
    ]

if not rows:
    st.info(
        "No audit entries yet. Run any assessment from the other pages — "
        "each completed run appends a row here automatically."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
all_projects = sorted({r["project_name"] for r in rows})
all_clients  = sorted({r["client_name"] for r in rows if r["client_name"]})

f1, f2, f3, f4 = st.columns([2, 2, 2, 1])
with f1:
    proj_filter = st.multiselect(
        "Projects", all_projects, default=[],
        help="Empty = include all projects",
    )
with f2:
    mod_filter = st.multiselect(
        "Modules",
        [code for code, _ in MODULES],
        default=[],
        format_func=lambda c: MODULE_LABEL.get(c, c),
        help="Empty = include all modules",
    )
with f3:
    color_filter = st.multiselect(
        "Severity",
        ["ok", "warning", "critical", "info"],
        default=[],
        format_func=lambda c: COLOR_LABEL.get(c, c),
        help="Empty = include all",
    )
with f4:
    limit = st.number_input("Show N most recent", 10, 5000, 200, 10)

filtered = rows
if proj_filter:
    filtered = [r for r in filtered if r["project_name"] in proj_filter]
if mod_filter:
    filtered = [r for r in filtered if r["module"] in mod_filter]
if color_filter:
    filtered = [r for r in filtered if r["status_color"] in color_filter]
filtered = filtered[: int(limit)]

st.caption(f"{len(filtered):,} of {len(rows):,} rows match the filters.")

# ---------------------------------------------------------------------------
# Table
# ---------------------------------------------------------------------------
if not filtered:
    st.warning("No rows match the current filters.")
    st.stop()

table_rows = [
    {
        "When":       r["run_at"].strftime("%Y-%m-%d %H:%M"),
        "Module":     MODULE_LABEL.get(r["module"], r["module"]),
        "Project":    f"{r['project_id']} — {r['project_name']}",
        "Client":     r["client_name"] or "—",
        "Status":     f"{COLOR_LABEL.get(r['status_color'], '⚪')} {r['status']}",
        "Detail":     r["status_detail"],
        "Actor":      r["actor"],
        "Duration":   f"{r['duration_seconds']:.2f} s"
                      if r["duration_seconds"] is not None else "—",
        "ID":         r["audit_id"],
    }
    for r in filtered
]
st.dataframe(table_rows, hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
buf = io.StringIO()
writer = csv.DictWriter(
    buf,
    fieldnames=[
        "audit_id", "run_at", "module", "project_id", "project_name",
        "client_name", "status", "status_color", "status_detail",
        "actor", "duration_seconds",
    ],
)
writer.writeheader()
for r in filtered:
    writer.writerow({**r, "run_at": r["run_at"].isoformat()})

st.download_button(
    "⬇ Export filtered as CSV",
    data=buf.getvalue(),
    file_name="audit_log.csv",
    mime="text/csv",
)
