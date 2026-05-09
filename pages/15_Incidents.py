"""
pages/15_Incidents.py — Art. 73 incident reporting
======================================================

Multiple incidents per project. Each one tracks: severity, dates
(occurred / detected / reported), root cause, corrective action,
authority-notification metadata. Generates a Markdown packet for the
notified body.
"""

from __future__ import annotations

from datetime import date

import streamlit as st
from sqlalchemy import select

from wavetest_app._time import utc_now
from wavetest_app.audit import record_run
from wavetest_app.auth import current_username, require_login
from wavetest_app.db.ids import next_id
from wavetest_app.db.models import IncidentReport
from wavetest_app.db.session import get_session
from wavetest_app.incidents import (
    SEVERITIES,
    STATUS_COLOR,
    STATUSES,
    days_remaining,
    deadline_color,
    to_markdown,
)
from wavetest_app.ui import page_header, project_picker, risk_pill

st.set_page_config(
    page_title="Incidents · waveTest",
    page_icon="🚨",
    layout="wide",
)

require_login()

page_header(
    "🚨 Incident Reports",
    "EU AI Act Article 73 — serious-incident reporting (2-day deadline for "
    "death/health, 15 days otherwise)",
    articles=["73"],
)

project = project_picker()
if project is None:
    st.stop()

st.markdown(
    f"### Project: `{project.project_id}` — "
    f"{project.client.company_name} / {project.project_name}"
)

# ---------------------------------------------------------------------------
# Snapshot the project's incidents inside the session
# ---------------------------------------------------------------------------
with get_session() as db:
    rows = [
        {
            "incident_id":         r.incident_id,
            "title":               r.title,
            "summary":             r.summary,
            "description":         r.description,
            "severity":            r.severity,
            "affected_persons":    r.affected_persons,
            "date_occurred":       r.date_occurred,
            "date_detected":       r.date_detected,
            "date_reported":       r.date_reported,
            "root_cause":          r.root_cause,
            "corrective_action":   r.corrective_action,
            "status":              r.status,
            "authority_notified":  r.authority_notified,
            "authority_name":      r.authority_name,
            "authority_reference": r.authority_reference,
            "created_by":          r.created_by,
            "created_at":          r.created_at,
            "updated_at":          r.updated_at,
            "notes":               r.notes,
            "project_id":          r.project_id,
            "project_name":        r.project_name,
            "client_name":         r.client_name,
        }
        for r in db.scalars(
            select(IncidentReport)
            .where(IncidentReport.project_id == project.project_id)
            .order_by(IncidentReport.date_detected.desc().nullslast())
        ).all()
    ]

# ---------------------------------------------------------------------------
# Summary pills
# ---------------------------------------------------------------------------
n_total = len(rows)
n_open = sum(1 for r in rows if r["status"] == "open")
n_overdue = sum(
    1 for r in rows
    if r["date_reported"] is None
    and (rem := days_remaining(r["severity"], r["date_detected"])) is not None
    and rem < 0
)
n_unreported = sum(1 for r in rows if r["date_reported"] is None)

pills = (
    risk_pill("Reports", str(n_total), "info" if n_total else "ok") +
    risk_pill("Open", str(n_open), "critical" if n_open else "ok") +
    risk_pill("Overdue", str(n_overdue), "critical" if n_overdue else "ok") +
    risk_pill("Unreported", str(n_unreported),
              "warning" if n_unreported else "ok")
)
st.markdown(pills, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Add new incident
# ---------------------------------------------------------------------------
with st.expander("➕ Log a new incident", expanded=(n_total == 0)):
    with st.form("add_incident", clear_on_submit=True):
        a1, a2 = st.columns([3, 1])
        with a1:
            title = st.text_input("Title")
            summary = st.text_area("Summary (one paragraph)", height=80)
        with a2:
            severity = st.selectbox(
                "Severity",
                list(SEVERITIES.keys()),
                format_func=lambda s: SEVERITIES[s][0],
                index=3,  # near_miss default
            )
            affected = st.number_input(
                "Affected persons", min_value=0, value=0, step=1,
            )

        b1, b2, b3 = st.columns(3)
        with b1:
            date_occurred = st.date_input(
                "Date occurred", value=None,
            )
        with b2:
            date_detected = st.date_input(
                "Date detected", value=date.today(),
            )
        with b3:
            initial_status = st.selectbox(
                "Initial status", STATUSES, index=0,
            )

        description = st.text_area(
            "Detailed description", height=120,
            help="Sequence of events; what the system did; what the operator "
                 "did; immediate effect.",
        )

        if st.form_submit_button("Log incident", type="primary"):
            t = title.strip()
            if not t:
                st.error("Title is required.")
            else:
                with get_session() as db:
                    iid = next_id(db, IncidentReport.incident_id, "INC")
                    db.add(IncidentReport(
                        incident_id=iid,
                        project_id=project.project_id,
                        project_name=project.project_name,
                        client_name=project.client.company_name,
                        title=t,
                        summary=summary.strip(),
                        description=description.strip(),
                        severity=severity,
                        affected_persons=int(affected),
                        date_occurred=date_occurred,
                        date_detected=date_detected,
                        status=initial_status,
                        created_by=current_username() or "system",
                    ))
                record_run(
                    project=project, module="incidents",
                    status=f"LOGGED {iid}",
                    status_color=SEVERITIES[severity][2],
                    status_detail=f"{t} ({SEVERITIES[severity][0]})",
                )
                st.success(f"Logged incident `{iid}`.")
                st.rerun()

# ---------------------------------------------------------------------------
# Existing incidents
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Existing incidents")

if not rows:
    st.info("No incidents logged for this project yet.")
    st.stop()

for r in rows:
    sev_label, deadline_d, sev_color = SEVERITIES.get(
        r["severity"], (r["severity"], 15, "info"),
    )
    rem = days_remaining(r["severity"], r["date_detected"])
    deadline_label = (
        "✓ reported" if r["date_reported"]
        else f"{rem} day(s) left" if rem is not None and rem >= 0
        else f"{abs(rem)} day(s) overdue" if rem is not None
        else "no detection date"
    )
    status_badge_color = STATUS_COLOR.get(r["status"], "info")

    expander_label = (
        f"{r['incident_id']} — {r['title']} "
        f"[{sev_label}, {r['status']}] · {deadline_label}"
    )

    with st.expander(expander_label, expanded=False):
        # Pills
        ipills = (
            risk_pill("Severity", sev_label, sev_color) +
            risk_pill("Status", r["status"], status_badge_color) +
            risk_pill(
                "Deadline",
                deadline_label,
                deadline_color(
                    r["severity"], r["date_detected"], r["date_reported"],
                ),
            )
        )
        st.markdown(ipills, unsafe_allow_html=True)

        st.markdown("**Summary**")
        st.write(r["summary"] or "_None._")

        m_cols = st.columns(3)
        m_cols[0].markdown(
            f"**Occurred**\n\n{r['date_occurred'].isoformat() if r['date_occurred'] else '—'}"
        )
        m_cols[1].markdown(
            f"**Detected**\n\n{r['date_detected'].isoformat() if r['date_detected'] else '—'}"
        )
        m_cols[2].markdown(
            f"**Reported**\n\n{r['date_reported'].isoformat() if r['date_reported'] else '—'}"
        )

        st.markdown("**Description**")
        st.write(r["description"] or "_Not provided._")

        if r["root_cause"]:
            st.markdown("**Root cause**")
            st.write(r["root_cause"])
        if r["corrective_action"]:
            st.markdown("**Corrective action**")
            st.write(r["corrective_action"])

        # Edit form
        with st.form(f"edit_inc_{r['incident_id']}"):
            st.markdown("##### Update")
            c1, c2 = st.columns(2)
            with c1:
                new_status = st.selectbox(
                    "Status", STATUSES,
                    index=STATUSES.index(r["status"]),
                    key=f"st_{r['incident_id']}",
                )
                new_root_cause = st.text_area(
                    "Root cause", value=r["root_cause"],
                    key=f"rc_{r['incident_id']}",
                )
            with c2:
                new_corrective = st.text_area(
                    "Corrective action", value=r["corrective_action"],
                    key=f"ca_{r['incident_id']}",
                )
                new_date_reported = st.date_input(
                    "Date reported to authority",
                    value=r["date_reported"],
                    key=f"dr_{r['incident_id']}",
                )

            ac1, ac2 = st.columns(2)
            with ac1:
                new_authority_notified = st.checkbox(
                    "Authority notified",
                    value=r["authority_notified"],
                    key=f"an_{r['incident_id']}",
                )
                new_authority_name = st.text_input(
                    "Authority name",
                    value=r["authority_name"],
                    key=f"aname_{r['incident_id']}",
                )
            with ac2:
                new_authority_reference = st.text_input(
                    "Authority reference / case number",
                    value=r["authority_reference"],
                    key=f"aref_{r['incident_id']}",
                )

            new_notes = st.text_area(
                "Notes", value=r["notes"],
                key=f"n_{r['incident_id']}",
            )

            saved = st.form_submit_button("Save changes")

            if saved:
                with get_session() as db:
                    target = db.get(IncidentReport, r["incident_id"])
                    if target:
                        target.status = new_status
                        target.root_cause = new_root_cause.strip()
                        target.corrective_action = new_corrective.strip()
                        target.date_reported = new_date_reported
                        target.authority_notified = new_authority_notified
                        target.authority_name = new_authority_name.strip()
                        target.authority_reference = new_authority_reference.strip()
                        target.notes = new_notes.strip()
                        target.updated_at = utc_now()
                record_run(
                    project=project, module="incidents",
                    status=f"UPDATED {r['incident_id']}",
                    status_color=STATUS_COLOR.get(new_status, "info"),
                    status_detail=f"status → {new_status}",
                )
                st.success(f"Updated `{r['incident_id']}`.")
                st.rerun()

        # Markdown export per-incident (notified-body packet)
        md = to_markdown(r)
        st.download_button(
            "⬇ Notified-body packet (Markdown)",
            data=md,
            file_name=f"incident_{r['incident_id']}.md",
            mime="text/markdown",
            key=f"dl_{r['incident_id']}",
        )
