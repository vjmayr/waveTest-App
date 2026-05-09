"""
pages/11_Risk_Management.py — Art. 9 Risk Register
======================================================

A per-project risk register: identify, score (severity × likelihood),
mitigate, score the residual, and track ownership + review dates.
Each create / update / delete writes one row to ``audit_log`` so the
admin can see who changed what.
"""

from __future__ import annotations

import csv
import io
from datetime import date

import pandas as pd
import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from wavetest_app._time import utc_now
from wavetest_app.audit import record_run
from wavetest_app.auth import current_username, require_login
from wavetest_app.db.ids import next_id
from wavetest_app.db.models import RiskEntry
from wavetest_app.db.session import get_session
from wavetest_app.risk import (
    LIKELIHOODS,
    MITIGATION_STATUSES,
    RISK_CATEGORIES,
    SEVERITIES,
    compute_residual_level,
    compute_risk_level,
    level_color,
)
from wavetest_app.ui import page_header, project_picker, risk_pill

st.set_page_config(
    page_title="Risk Register · waveTest",
    page_icon="🛡",
    layout="wide",
)

require_login()

page_header(
    "🛡 Risk Register",
    "EU AI Act Article 9 — identify, score, mitigate, monitor",
    articles=["9"],
)

project = project_picker()
if project is None:
    st.stop()

st.markdown(
    f"### Project: `{project.project_id}` — "
    f"{project.client.company_name} / {project.project_name}"
)

# ---------------------------------------------------------------------------
# Snapshot the project's risks inside the session — same pattern as the
# admin pages — so attribute access after exit is safe.
# ---------------------------------------------------------------------------
with get_session() as db:
    rows = [
        {
            "risk_id":             r.risk_id,
            "title":               r.title,
            "description":         r.description,
            "category":            r.category,
            "severity":            r.severity,
            "likelihood":          r.likelihood,
            "risk_level":          r.risk_level,
            "mitigation":          r.mitigation,
            "mitigation_status":   r.mitigation_status,
            "residual_severity":   r.residual_severity,
            "residual_likelihood": r.residual_likelihood,
            "residual_level":      r.residual_level,
            "owner":               r.owner,
            "next_review_date":    r.next_review_date,
            "created_by":          r.created_by,
            "created_at":          r.created_at,
            "updated_at":          r.updated_at,
            "notes":               r.notes,
        }
        for r in db.scalars(
            select(RiskEntry)
            .where(RiskEntry.project_id == project.project_id)
            .order_by(RiskEntry.created_at.desc())
        ).all()
    ]

# ---------------------------------------------------------------------------
# Summary pills
# ---------------------------------------------------------------------------
def _count(rs, key, value):
    return sum(1 for r in rs if r[key] == value)

n_total = len(rows)
n_critical = _count(rows, "risk_level", "CRITICAL")
n_high     = _count(rows, "risk_level", "HIGH")
n_open     = sum(
    1 for r in rows
    if r["mitigation_status"] in ("proposed", "in_progress")
)

pills = (
    risk_pill("Risks tracked", str(n_total),
              "info" if n_total else "ok") +
    risk_pill("Critical", str(n_critical),
              "critical" if n_critical else "ok") +
    risk_pill("High", str(n_high),
              "warning" if n_high else "ok") +
    risk_pill("Open mitigations", str(n_open),
              "warning" if n_open else "ok")
)
st.markdown(pills, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Add a new risk
# ---------------------------------------------------------------------------
with st.expander("➕ Add a risk", expanded=(n_total == 0)):
    with st.form("add_risk", clear_on_submit=True):
        c1, c2 = st.columns([3, 1])
        with c1:
            title = st.text_input("Title", help="Short name for the risk")
            description = st.text_area(
                "Description", height=80,
                help="What is the risk? In what scenario does it manifest?",
            )
        with c2:
            category = st.selectbox("Category", RISK_CATEGORIES)
            severity = st.selectbox("Severity", SEVERITIES, index=1)
            likelihood = st.selectbox("Likelihood", LIKELIHOODS, index=2)
            preview_level = compute_risk_level(severity, likelihood)
            st.caption(f"Computed level → **{preview_level}**")

        c3, c4 = st.columns(2)
        with c3:
            mitigation = st.text_area(
                "Mitigation plan", height=80,
                help="What's being done (or proposed) to address this risk?",
            )
            mitigation_status = st.selectbox(
                "Mitigation status", MITIGATION_STATUSES, index=0,
            )
        with c4:
            owner = st.text_input(
                "Owner", help="Name of the person accountable",
            )
            next_review_date = st.date_input(
                "Next review date",
                value=None,
                help="When should this risk be revisited?",
            )
            notes = st.text_area("Notes (optional)", height=80)

        if st.form_submit_button("Save risk", type="primary"):
            t = title.strip()
            if not t:
                st.error("Title is required.")
            else:
                with get_session() as db:
                    rid = next_id(db, RiskEntry.risk_id, "RR")
                    db.add(RiskEntry(
                        risk_id=rid,
                        project_id=project.project_id,
                        title=t,
                        description=description.strip(),
                        category=category,
                        severity=severity,
                        likelihood=likelihood,
                        risk_level=compute_risk_level(severity, likelihood),
                        mitigation=mitigation.strip(),
                        mitigation_status=mitigation_status,
                        owner=owner.strip(),
                        next_review_date=next_review_date,
                        created_by=current_username() or "system",
                        notes=notes.strip(),
                    ))
                record_run(
                    project=project, module="risk_management",
                    status=f"CREATED {rid}",
                    status_color=level_color(
                        compute_risk_level(severity, likelihood)
                    ),
                    status_detail=f"{t} ({category}, "
                                  f"{compute_risk_level(severity, likelihood)})",
                )
                st.success(f"Created risk `{rid}`.")
                st.rerun()

# ---------------------------------------------------------------------------
# Existing risks
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Existing risks")

if not rows:
    st.info(
        "No risks recorded yet. Add the first one above — Art. 9 expects "
        "the risk register to be maintained throughout the system's lifecycle."
    )
    st.stop()

# Filters
fc1, fc2, fc3 = st.columns(3)
with fc1:
    cat_filter = st.multiselect(
        "Category", RISK_CATEGORIES, default=[],
        help="Empty = all",
    )
with fc2:
    level_filter = st.multiselect(
        "Level", ["LOW", "MEDIUM", "HIGH", "CRITICAL"], default=[],
        help="Empty = all",
    )
with fc3:
    status_filter = st.multiselect(
        "Mitigation status", MITIGATION_STATUSES, default=[],
        help="Empty = all",
    )

filtered = rows
if cat_filter:    filtered = [r for r in filtered if r["category"] in cat_filter]
if level_filter:  filtered = [r for r in filtered if r["risk_level"] in level_filter]
if status_filter: filtered = [r for r in filtered if r["mitigation_status"] in status_filter]

st.caption(f"{len(filtered)} of {len(rows)} risks shown.")

for r in filtered:
    color = level_color(r["risk_level"])
    badge = (
        " <span style='background:#D62828; color:white; font-size:11px; "
        "padding:2px 6px; border-radius:6px;'>CRITICAL</span>"
        if r["risk_level"] == "CRITICAL"
        else " <span style='background:#F77F00; color:white; font-size:11px; "
             "padding:2px 6px; border-radius:6px;'>HIGH</span>"
        if r["risk_level"] == "HIGH"
        else ""
    )
    with st.expander(
        f"{r['risk_id']} — {r['title']} [{r['category']}, {r['risk_level']}]",
        expanded=False,
    ):
        st.markdown(f"**{r['title']}**{badge}", unsafe_allow_html=True)
        st.write(r["description"] or "_No description._")

        meta_cols = st.columns(4)
        meta_cols[0].markdown(f"**Severity**\n\n{r['severity']}")
        meta_cols[1].markdown(f"**Likelihood**\n\n{r['likelihood']}")
        meta_cols[2].markdown(f"**Owner**\n\n{r['owner'] or '—'}")
        meta_cols[3].markdown(
            f"**Next review**\n\n"
            + (r["next_review_date"].isoformat()
               if r["next_review_date"] else "—")
        )

        st.markdown("**Mitigation**")
        st.write(r["mitigation"] or "_No mitigation plan recorded._")
        st.caption(f"Status: **{r['mitigation_status']}**")

        if r["residual_level"]:
            st.markdown(
                f"**Residual** — severity `{r['residual_severity']}` × "
                f"likelihood `{r['residual_likelihood']}` = **{r['residual_level']}**"
            )
        else:
            st.caption("Residual risk not yet re-evaluated.")

        if r["notes"]:
            st.markdown("**Notes**")
            st.write(r["notes"])

        st.caption(
            f"Created by `{r['created_by']}` on "
            f"{r['created_at'].strftime('%Y-%m-%d %H:%M')} · "
            f"updated {r['updated_at'].strftime('%Y-%m-%d %H:%M')}"
        )

        # --- Edit form
        with st.form(f"edit_{r['risk_id']}"):
            st.markdown("##### Update")
            ec1, ec2 = st.columns(2)
            with ec1:
                new_status = st.selectbox(
                    "Mitigation status", MITIGATION_STATUSES,
                    index=MITIGATION_STATUSES.index(r["mitigation_status"]),
                    key=f"st_{r['risk_id']}",
                )
                new_owner = st.text_input(
                    "Owner", value=r["owner"], key=f"o_{r['risk_id']}",
                )
                new_review = st.date_input(
                    "Next review date",
                    value=r["next_review_date"],
                    key=f"d_{r['risk_id']}",
                )
            with ec2:
                st.markdown("**Residual** (after mitigation)")
                new_res_sev = st.selectbox(
                    "Residual severity",
                    [""] + SEVERITIES,
                    index=([""] + SEVERITIES).index(r["residual_severity"] or ""),
                    key=f"rs_{r['risk_id']}",
                )
                new_res_like = st.selectbox(
                    "Residual likelihood",
                    [""] + LIKELIHOODS,
                    index=([""] + LIKELIHOODS).index(r["residual_likelihood"] or ""),
                    key=f"rl_{r['risk_id']}",
                )

            new_notes = st.text_area(
                "Notes", value=r["notes"], key=f"n_{r['risk_id']}",
            )

            uc1, uc2 = st.columns([1, 1])
            saved = uc1.form_submit_button("Save changes")
            confirm = uc2.checkbox(
                "Confirm delete", key=f"cd_{r['risk_id']}",
            )
            deleted = uc1.form_submit_button(
                "Delete risk", disabled=not confirm,
            )

            if saved:
                residual_severity = new_res_sev or None
                residual_likelihood = new_res_like or None
                with get_session() as db:
                    target = db.get(RiskEntry, r["risk_id"])
                    if target:
                        target.mitigation_status = new_status
                        target.owner = new_owner.strip()
                        target.next_review_date = new_review
                        target.residual_severity = residual_severity
                        target.residual_likelihood = residual_likelihood
                        target.residual_level = compute_residual_level(
                            residual_severity, residual_likelihood,
                        )
                        target.notes = new_notes.strip()
                        target.updated_at = utc_now()
                record_run(
                    project=project, module="risk_management",
                    status=f"UPDATED {r['risk_id']}",
                    status_color=level_color(r["risk_level"]),
                    status_detail=f"status → {new_status}",
                )
                st.success(f"Updated `{r['risk_id']}`.")
                st.rerun()

            if deleted:
                with get_session() as db:
                    target = db.get(RiskEntry, r["risk_id"])
                    if target:
                        db.delete(target)
                record_run(
                    project=project, module="risk_management",
                    status=f"DELETED {r['risk_id']}",
                    status_color="info",
                    status_detail=r["title"],
                )
                st.success(f"Deleted `{r['risk_id']}`.")
                st.rerun()

# ---------------------------------------------------------------------------
# Risk matrix — counts per (severity × likelihood) cell
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Risk matrix")

matrix = {sev: {lk: 0 for lk in LIKELIHOODS} for sev in SEVERITIES}
for r in rows:
    if r["severity"] in matrix and r["likelihood"] in matrix[r["severity"]]:
        matrix[r["severity"]][r["likelihood"]] += 1

# Render as a small dataframe with severities as rows (CRITICAL on top)
matrix_rows = [
    {"Severity": sev, **{lk: matrix[sev][lk] for lk in LIKELIHOODS}}
    for sev in reversed(SEVERITIES)
]
st.dataframe(
    pd.DataFrame(matrix_rows).set_index("Severity"),
    use_container_width=True,
)
st.caption("Cells = number of risks at that severity × likelihood.")

# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------
buf = io.StringIO()
writer = csv.DictWriter(
    buf,
    fieldnames=[
        "risk_id", "title", "description", "category", "severity",
        "likelihood", "risk_level", "mitigation", "mitigation_status",
        "residual_severity", "residual_likelihood", "residual_level",
        "owner", "next_review_date", "created_by",
        "created_at", "updated_at", "notes",
    ],
)
writer.writeheader()
for r in rows:
    writer.writerow({
        **r,
        "next_review_date": r["next_review_date"].isoformat()
                            if r["next_review_date"] else "",
        "created_at": r["created_at"].isoformat(),
        "updated_at": r["updated_at"].isoformat(),
    })

st.download_button(
    "⬇ Export risk register as CSV",
    data=buf.getvalue(),
    file_name=f"risk_register_{project.project_id}.csv",
    mime="text/csv",
)
