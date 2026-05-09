"""
pages/12_Human_Oversight.py — Art. 14 oversight plan
========================================================

One oversight plan per project: the six Art. 14.4 (a)–(e) checkpoints,
operator profile, gaps, mitigation plan, next review date. Save to
upsert. Download as Markdown for the customer file.
"""

from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from wavetest_app._time import utc_now
from wavetest_app.audit import record_run
from wavetest_app.auth import current_username, require_login
from wavetest_app.db.ids import next_id
from wavetest_app.db.models import OversightPlan
from wavetest_app.db.session import get_session
from wavetest_app.oversight import (
    ANSWERS,
    CHECKPOINTS,
    compute_compliance_percent,
    status_color,
    to_markdown,
)
from wavetest_app.ui import (
    page_header, project_picker, risk_pill, show_recommendations,
)

st.set_page_config(
    page_title="Human Oversight · waveTest",
    page_icon="👁",
    layout="wide",
)

require_login()

page_header(
    "👁 Human Oversight Plan",
    "EU AI Act Article 14 — designed to support effective human oversight",
    articles=["14"],
)

project = project_picker()
if project is None:
    st.stop()

st.markdown(
    f"### Project: `{project.project_id}` — "
    f"{project.client.company_name} / {project.project_name}"
)

# ---------------------------------------------------------------------------
# Load existing plan (if any) inside the session
# ---------------------------------------------------------------------------
with get_session() as db:
    existing = db.scalars(
        select(OversightPlan)
        .where(OversightPlan.project_id == project.project_id)
    ).first()
    if existing:
        plan = {
            "plan_id":                     existing.plan_id,
            "operator_profile":            existing.operator_profile,
            "has_documentation":           existing.has_documentation,
            "automation_bias_training":    existing.automation_bias_training,
            "outputs_include_uncertainty": existing.outputs_include_uncertainty,
            "override_mechanism":          existing.override_mechanism,
            "override_logged":             existing.override_logged,
            "stop_mechanism":              existing.stop_mechanism,
            "gaps":                        existing.gaps,
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
            "Last updated",
            plan["updated_at"].strftime("%Y-%m-%d"),
            "info",
        ) +
        risk_pill(
            "Next review",
            plan["next_review_date"].isoformat()
            if plan["next_review_date"] else "—",
            "info" if plan["next_review_date"] else "warning",
        )
    )
    st.markdown(pills, unsafe_allow_html=True)
else:
    st.info(
        "No oversight plan recorded for this project yet. Fill in the form "
        "below to create one — the questions follow Article 14.4(a)–(e)."
    )

# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------
defaults = plan or {
    "operator_profile": "",
    "has_documentation": "no",
    "automation_bias_training": "no",
    "outputs_include_uncertainty": "no",
    "override_mechanism": "no",
    "override_logged": "no",
    "stop_mechanism": "no",
    "gaps": "",
    "mitigation_plan": "",
    "next_review_date": None,
}

with st.form("oversight_form"):
    st.markdown("### Operator profile")
    operator_profile = st.text_area(
        "Who oversees the system, and how are they trained?",
        value=defaults["operator_profile"],
        height=80,
        help="Roles, headcount, required training / certification, decision authority "
             "(advisory vs binding), time per decision.",
    )

    st.markdown("### Article 14.4 checkpoints")
    answers: dict[str, str] = {}
    for field, label, ref in CHECKPOINTS:
        idx = ANSWERS.index(defaults.get(field, "no"))
        answers[field] = st.radio(
            f"**{label}** — _Art. {ref}_",
            ANSWERS,
            index=idx,
            horizontal=True,
            key=f"oa_{field}",
            format_func=lambda x: {
                "yes":     "✅ Yes",
                "partial": "🟡 Partial",
                "no":      "❌ No",
            }[x],
        )

    st.markdown("### Gaps + remediation")
    gaps = st.text_area(
        "Identified gaps",
        value=defaults["gaps"],
        height=100,
        help="What's currently missing or insufficient?",
    )
    mitigation_plan = st.text_area(
        "Mitigation plan",
        value=defaults["mitigation_plan"],
        height=100,
        help="What will be done, by whom, and by when?",
    )
    next_review_date = st.date_input(
        "Next review date",
        value=defaults["next_review_date"],
        help="Art. 14 oversight should be reviewed regularly — pick a date.",
    )

    if st.form_submit_button("Save plan", type="primary"):
        new_pct = compute_compliance_percent(answers)
        with get_session() as db:
            target = db.scalars(
                select(OversightPlan)
                .where(OversightPlan.project_id == project.project_id)
            ).first()
            if target is None:
                pid = next_id(db, OversightPlan.plan_id, "HOP")
                target = OversightPlan(
                    plan_id=pid,
                    project_id=project.project_id,
                    created_by=current_username() or "system",
                )
                db.add(target)
            target.operator_profile = operator_profile.strip()
            for field in ("has_documentation", "automation_bias_training",
                          "outputs_include_uncertainty", "override_mechanism",
                          "override_logged", "stop_mechanism"):
                setattr(target, field, answers[field])
            target.gaps = gaps.strip()
            target.mitigation_plan = mitigation_plan.strip()
            target.next_review_date = next_review_date
            target.compliance_percent = new_pct
            target.updated_at = utc_now()

        record_run(
            project=project, module="human_oversight",
            status=f"{new_pct:.0f}%",
            status_color=status_color(new_pct),
            status_detail=f"Art. 14 oversight plan saved",
        )
        st.success(f"Plan saved — Art. 14 compliance: **{new_pct:.0f}%**")
        st.rerun()

# ---------------------------------------------------------------------------
# Recommendations + download
# ---------------------------------------------------------------------------
if plan is not None:
    st.divider()
    st.subheader("Recommendations")
    recs = []
    for field, label, ref in CHECKPOINTS:
        a = plan[field]
        if a == "no":
            recs.append(
                f"❌ **{label}** (Art. {ref}) is missing. Treat this as a "
                f"blocker for high-risk deployment."
            )
        elif a == "partial":
            recs.append(
                f"🟡 **{label}** (Art. {ref}) is partial — define the gap "
                f"and remediation in the plan above."
            )
    if not recs:
        st.success("All Article 14.4 checkpoints are at YES — full compliance.")
    else:
        show_recommendations(recs)

    st.divider()
    st.subheader("Export")
    md = to_markdown(
        plan,
        project_label=f"{project.client.company_name} / {project.project_name}",
    )
    st.download_button(
        "⬇ Download oversight plan (Markdown)",
        data=md,
        file_name=f"oversight_plan_{project.project_id}.md",
        mime="text/markdown",
    )
