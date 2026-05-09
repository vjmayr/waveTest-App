"""
pages/13_Cybersecurity.py — Art. 15(5) cybersecurity questionnaire
======================================================================

One cybersecurity plan per project. Eight yes/partial/no checkpoints
covering threat modelling, SBOM hygiene, penetration testing, AI-
specific attack vectors (data poisoning, adversarial inputs, privacy
attacks), access controls, and incident response. Markdown export for
the customer file.
"""

from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from wavetest_app._time import utc_now
from wavetest_app.audit import record_run
from wavetest_app.auth import current_username, require_login
from wavetest_app.cybersecurity import (
    ANSWERS,
    CHECKPOINTS,
    compute_compliance_percent,
    status_color,
    to_markdown,
)
from wavetest_app.db.ids import next_id
from wavetest_app.db.models import CybersecurityPlan
from wavetest_app.db.session import get_session
from wavetest_app.ui import (
    page_header, project_picker, risk_pill, show_recommendations,
)

st.set_page_config(
    page_title="Cybersecurity · waveTest",
    page_icon="🔐",
    layout="wide",
)

require_login()

page_header(
    "🔐 Cybersecurity Plan",
    "EU AI Act Article 15(5) — resilience against attempts to alter use, outputs, or performance",
    articles=["15"],
)

project = project_picker()
if project is None:
    st.stop()

st.markdown(
    f"### Project: `{project.project_id}` — "
    f"{project.client.company_name} / {project.project_name}"
)

# ---------------------------------------------------------------------------
# Load existing plan
# ---------------------------------------------------------------------------
with get_session() as db:
    existing = db.scalars(
        select(CybersecurityPlan)
        .where(CybersecurityPlan.project_id == project.project_id)
    ).first()
    if existing:
        plan = {
            "plan_id":                     existing.plan_id,
            "threat_model_documented":     existing.threat_model_documented,
            "sbom_maintained":             existing.sbom_maintained,
            "pentest_performed":           existing.pentest_performed,
            "data_poisoning_controls":     existing.data_poisoning_controls,
            "adversarial_input_controls":  existing.adversarial_input_controls,
            "privacy_attack_controls":     existing.privacy_attack_controls,
            "access_controls_documented":  existing.access_controls_documented,
            "incident_response_playbook":  existing.incident_response_playbook,
            "pentest_last_date":           existing.pentest_last_date,
            "threat_model_notes":          existing.threat_model_notes,
            "open_findings":               existing.open_findings,
            "mitigation_plan":             existing.mitigation_plan,
            "next_review_date":            existing.next_review_date,
            "compliance_percent":          existing.compliance_percent,
            "created_by":                  existing.created_by,
            "created_at":                  existing.created_at,
            "updated_at":                  existing.updated_at,
        }
    else:
        plan = None

# ---------------------------------------------------------------------------
# Status pills
# ---------------------------------------------------------------------------
if plan is not None:
    pct = plan["compliance_percent"]
    pills = (
        risk_pill("Compliance", f"{pct:.0f}%", status_color(pct)) +
        risk_pill(
            "Last pentest",
            plan["pentest_last_date"].isoformat()
            if plan["pentest_last_date"] else "—",
            "info" if plan["pentest_last_date"] else "warning",
        ) +
        risk_pill(
            "Last updated",
            plan["updated_at"].strftime("%Y-%m-%d"),
            "info",
        )
    )
    st.markdown(pills, unsafe_allow_html=True)
else:
    st.info(
        "No cybersecurity plan recorded for this project yet. The "
        "questions below cover Article 15(5) — both classical infosec "
        "hygiene and AI-specific attacks (data poisoning, adversarial "
        "inputs, privacy attacks)."
    )

# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------
defaults = plan or {
    "threat_model_documented":    "no",
    "sbom_maintained":            "no",
    "pentest_performed":          "no",
    "data_poisoning_controls":    "no",
    "adversarial_input_controls": "no",
    "privacy_attack_controls":    "no",
    "access_controls_documented": "no",
    "incident_response_playbook": "no",
    "pentest_last_date":          None,
    "threat_model_notes":         "",
    "open_findings":              "",
    "mitigation_plan":            "",
    "next_review_date":           None,
}

with st.form("cybersec_form"):
    st.markdown("### Article 15(5) checkpoints")

    answers: dict[str, str] = {}
    for field, label, ref, helptext in CHECKPOINTS:
        idx = ANSWERS.index(defaults.get(field, "no"))
        answers[field] = st.radio(
            f"**{label}** — _Art. {ref}_",
            ANSWERS,
            index=idx,
            horizontal=True,
            key=f"cs_{field}",
            help=helptext,
            format_func=lambda x: {
                "yes":     "✅ Yes",
                "partial": "🟡 Partial",
                "no":      "❌ No",
            }[x],
        )

    st.markdown("### Threat model + dates")
    cc1, cc2 = st.columns(2)
    with cc1:
        threat_model_notes = st.text_area(
            "Threat-model notes",
            value=defaults["threat_model_notes"],
            height=120,
            help="Top assets, top adversaries, top attack surfaces. "
                 "Reference the project's STRIDE / LINDDUN doc if any.",
        )
        pentest_last_date = st.date_input(
            "Last pentest date",
            value=defaults["pentest_last_date"],
        )
    with cc2:
        open_findings = st.text_area(
            "Open findings",
            value=defaults["open_findings"],
            height=120,
        )
        next_review_date = st.date_input(
            "Next review date",
            value=defaults["next_review_date"],
        )

    mitigation_plan = st.text_area(
        "Mitigation plan",
        value=defaults["mitigation_plan"],
        height=100,
    )

    if st.form_submit_button("Save plan", type="primary"):
        new_pct = compute_compliance_percent(answers)
        with get_session() as db:
            target = db.scalars(
                select(CybersecurityPlan)
                .where(CybersecurityPlan.project_id == project.project_id)
            ).first()
            if target is None:
                pid = next_id(db, CybersecurityPlan.plan_id, "CSP")
                target = CybersecurityPlan(
                    plan_id=pid,
                    project_id=project.project_id,
                    created_by=current_username() or "system",
                )
                db.add(target)
            for field in (
                "threat_model_documented", "sbom_maintained",
                "pentest_performed", "data_poisoning_controls",
                "adversarial_input_controls", "privacy_attack_controls",
                "access_controls_documented", "incident_response_playbook",
            ):
                setattr(target, field, answers[field])
            target.pentest_last_date = pentest_last_date
            target.threat_model_notes = threat_model_notes.strip()
            target.open_findings = open_findings.strip()
            target.mitigation_plan = mitigation_plan.strip()
            target.next_review_date = next_review_date
            target.compliance_percent = new_pct
            target.updated_at = utc_now()

        record_run(
            project=project, module="cybersecurity",
            status=f"{new_pct:.0f}%",
            status_color=status_color(new_pct),
            status_detail="Art. 15(5) cybersecurity plan saved",
        )
        st.success(f"Plan saved — Art. 15(5) compliance: **{new_pct:.0f}%**")
        st.rerun()

# ---------------------------------------------------------------------------
# Recommendations + download
# ---------------------------------------------------------------------------
if plan is not None:
    st.divider()
    st.subheader("Recommendations")
    recs = []
    for field, label, ref, _help in CHECKPOINTS:
        a = plan[field]
        if a == "no":
            recs.append(
                f"❌ **{label}** (Art. {ref}) is missing — flag this as a "
                f"high-risk gap and assign an owner."
            )
        elif a == "partial":
            recs.append(
                f"🟡 **{label}** (Art. {ref}) is partial — document the "
                f"gap and the upgrade path."
            )
    if not recs:
        st.success(
            "All Article 15(5) checkpoints are at YES — full v0 compliance. "
            "Active adversarial testing (ART-based FGSM/PGD/etc.) is the "
            "next layer; tracked in HANDOVER."
        )
    else:
        show_recommendations(recs)

    st.divider()
    st.subheader("Export")
    md = to_markdown(
        plan,
        project_label=f"{project.client.company_name} / {project.project_name}",
    )
    st.download_button(
        "⬇ Download cybersecurity plan (Markdown)",
        data=md,
        file_name=f"cybersecurity_plan_{project.project_id}.md",
        mime="text/markdown",
    )
