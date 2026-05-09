"""
pages/16_Right_To_Explanation.py — Art. 86 right to explanation
====================================================================

Per-decision request log — different from the Explainability page,
which explains the *model*. This page captures one request per
affected person, drafts the customer-facing letter, and exports it
as Markdown.
"""

from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from wavetest_app._time import utc_now
from wavetest_app.audit import record_run
from wavetest_app.auth import current_username, require_login
from wavetest_app.db.ids import next_id
from wavetest_app.db.models import ExplanationRequest
from wavetest_app.db.session import get_session
from wavetest_app.explanations import (
    STATUSES,
    STATUS_COLOR,
    days_remaining,
    deadline_color,
    default_due_date,
    to_markdown,
)
from wavetest_app.ui import page_header, project_picker, risk_pill

st.set_page_config(
    page_title="Right to Explanation · waveTest",
    page_icon="📨",
    layout="wide",
)

require_login()

page_header(
    "📨 Right to Explanation",
    "EU AI Act Article 86 — explanations to affected persons about specific decisions",
    articles=["86"],
)

project = project_picker()
if project is None:
    st.stop()

st.markdown(
    f"### Project: `{project.project_id}` — "
    f"{project.client.company_name} / {project.project_name}"
)

# ---------------------------------------------------------------------------
# Snapshot existing requests
# ---------------------------------------------------------------------------
with get_session() as db:
    rows = [
        {
            "request_id":             r.request_id,
            "subject_reference":      r.subject_reference,
            "decision_date":          r.decision_date,
            "decision_outcome":       r.decision_outcome,
            "request_received_date":  r.request_received_date,
            "response_due_date":      r.response_due_date,
            "response_sent_date":     r.response_sent_date,
            "factors_text":           r.factors_text,
            "alternative_paths":      r.alternative_paths,
            "human_review_offered":   r.human_review_offered,
            "status":                 r.status,
            "created_by":             r.created_by,
            "created_at":             r.created_at,
            "updated_at":             r.updated_at,
            "notes":                  r.notes,
            "project_name":           r.project_name,
            "client_name":            r.client_name,
        }
        for r in db.scalars(
            select(ExplanationRequest)
            .where(ExplanationRequest.project_id == project.project_id)
            .order_by(ExplanationRequest.request_received_date.desc().nullslast())
        ).all()
    ]

# ---------------------------------------------------------------------------
# Summary pills
# ---------------------------------------------------------------------------
n_total = len(rows)
n_open = sum(1 for r in rows if r["status"] == "open")
n_overdue = sum(
    1 for r in rows
    if r["response_sent_date"] is None
    and (rem := days_remaining(r["response_due_date"])) is not None
    and rem < 0
)

pills = (
    risk_pill("Requests", str(n_total), "info" if n_total else "ok") +
    risk_pill("Open", str(n_open), "critical" if n_open else "ok") +
    risk_pill("Overdue", str(n_overdue), "critical" if n_overdue else "ok")
)
st.markdown(pills, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Add new request
# ---------------------------------------------------------------------------
with st.expander(
    "➕ Log a new explanation request", expanded=(n_total == 0),
):
    with st.form("add_request", clear_on_submit=True):
        a1, a2 = st.columns(2)
        with a1:
            subject_reference = st.text_input(
                "Customer / case reference",
                help="Use the deployer's case ID — DO NOT enter the "
                     "natural person's name. GDPR data minimisation.",
            )
            decision_date = st.date_input(
                "Date of decision", value=None,
            )
        with a2:
            request_received_date = st.date_input(
                "Date request received", value=None,
            )
            human_review_offered = st.checkbox(
                "Human review is offered",
                value=True,
                help="Most high-risk deployments offer this. Uncheck only "
                     "if not available for this specific decision.",
            )

        decision_outcome = st.text_area(
            "Decision outcome (plain language)",
            height=60,
            help="The actual decision in one sentence — e.g. "
                 "'Loan application declined.' or 'Hiring referral approved.'",
        )

        if st.form_submit_button("Log request", type="primary"):
            if not subject_reference.strip():
                st.error("Customer / case reference is required.")
            else:
                with get_session() as db:
                    rid = next_id(db, ExplanationRequest.request_id, "RTE")
                    db.add(ExplanationRequest(
                        request_id=rid,
                        project_id=project.project_id,
                        project_name=project.project_name,
                        client_name=project.client.company_name,
                        subject_reference=subject_reference.strip(),
                        decision_date=decision_date,
                        decision_outcome=decision_outcome.strip(),
                        request_received_date=request_received_date,
                        response_due_date=default_due_date(
                            request_received_date,
                        ),
                        human_review_offered=human_review_offered,
                        status="open",
                        created_by=current_username() or "system",
                    ))
                record_run(
                    project=project, module="right_to_explanation",
                    status=f"LOGGED {rid}",
                    status_color="info",
                    status_detail=f"Subject: {subject_reference}",
                )
                st.success(f"Logged request `{rid}`.")
                st.rerun()

# ---------------------------------------------------------------------------
# Existing requests
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Existing requests")

if not rows:
    st.info("No explanation requests for this project yet.")
    st.stop()

for r in rows:
    rem = days_remaining(r["response_due_date"])
    deadline_label = (
        "✓ sent" if r["response_sent_date"]
        else f"{rem} day(s) left" if rem is not None and rem >= 0
        else f"{abs(rem)} day(s) overdue" if rem is not None
        else "no due date"
    )

    expander_label = (
        f"{r['request_id']} — subject `{r['subject_reference']}` "
        f"[{r['status']}] · {deadline_label}"
    )

    with st.expander(expander_label, expanded=False):
        ipills = (
            risk_pill("Status", r["status"],
                      STATUS_COLOR.get(r["status"], "info")) +
            risk_pill("Deadline", deadline_label,
                      deadline_color(r["response_due_date"],
                                     r["response_sent_date"])) +
            risk_pill("Human review",
                      "offered" if r["human_review_offered"] else "not offered",
                      "ok" if r["human_review_offered"] else "warning")
        )
        st.markdown(ipills, unsafe_allow_html=True)

        meta_cols = st.columns(3)
        meta_cols[0].markdown(
            f"**Decision date**\n\n"
            f"{r['decision_date'].isoformat() if r['decision_date'] else '—'}"
        )
        meta_cols[1].markdown(
            f"**Request received**\n\n"
            f"{r['request_received_date'].isoformat() if r['request_received_date'] else '—'}"
        )
        meta_cols[2].markdown(
            f"**Response due**\n\n"
            f"{r['response_due_date'].isoformat() if r['response_due_date'] else '—'}"
        )

        st.markdown("**Decision outcome**")
        st.write(r["decision_outcome"] or "_Not provided._")

        # Edit form
        with st.form(f"edit_rte_{r['request_id']}"):
            st.markdown("##### Draft the explanation")
            new_factors = st.text_area(
                "Top factors (plain language; aim for 3 bullet points)",
                value=r["factors_text"],
                height=140,
                key=f"f_{r['request_id']}",
                help="Translate model features into language the affected "
                     "person will understand. No technical jargon.",
            )
            new_alts = st.text_area(
                "What could change the outcome",
                value=r["alternative_paths"],
                height=100,
                key=f"a_{r['request_id']}",
                help="Conditions under which the decision would change. "
                     "If the decision wouldn't change in any reasonable "
                     "scenario, say so.",
            )

            ec1, ec2 = st.columns(2)
            with ec1:
                new_status = st.selectbox(
                    "Status", STATUSES,
                    index=STATUSES.index(r["status"]),
                    key=f"st_{r['request_id']}",
                )
            with ec2:
                new_response_sent = st.date_input(
                    "Response sent date",
                    value=r["response_sent_date"],
                    key=f"rs_{r['request_id']}",
                )

            new_notes = st.text_area(
                "Internal notes (not in the customer letter)",
                value=r["notes"],
                key=f"n_{r['request_id']}",
            )

            saved = st.form_submit_button("Save changes")
            if saved:
                with get_session() as db:
                    target = db.get(ExplanationRequest, r["request_id"])
                    if target:
                        target.factors_text = new_factors.strip()
                        target.alternative_paths = new_alts.strip()
                        target.status = new_status
                        target.response_sent_date = new_response_sent
                        target.notes = new_notes.strip()
                        target.updated_at = utc_now()
                record_run(
                    project=project, module="right_to_explanation",
                    status=f"UPDATED {r['request_id']}",
                    status_color=STATUS_COLOR.get(new_status, "info"),
                    status_detail=f"status → {new_status}",
                )
                st.success(f"Updated `{r['request_id']}`.")
                st.rerun()

        # Letter preview + download
        st.markdown("##### Letter preview")
        md = to_markdown(r)
        with st.expander("Show letter Markdown", expanded=False):
            st.markdown(md)
        st.download_button(
            "⬇ Download letter (Markdown)",
            data=md,
            file_name=f"explanation_{r['request_id']}.md",
            mime="text/markdown",
            key=f"dl_{r['request_id']}",
        )
