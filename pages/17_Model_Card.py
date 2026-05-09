"""
pages/17_Model_Card.py — Google-schema Model Card per project
=================================================================

Article 11 (technical documentation) + Article 13 (transparency to
deployers) overlap heavily with Google's published Model Card schema.
Google's `model-card-toolkit` Python package isn't installable on 3.13;
we mirror its schema field-for-field and emit Markdown + JSON
deliverables interchangeable with the official toolkit.
"""

from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from wavetest_app._time import utc_now
from wavetest_app.audit import record_run
from wavetest_app.auth import current_username, require_login
from wavetest_app.db.ids import next_id
from wavetest_app.db.models import ModelCard
from wavetest_app.db.session import get_session
from wavetest_app.model_card import to_json, to_markdown
from wavetest_app.ui import page_header, project_picker, risk_pill

st.set_page_config(
    page_title="Model Card · waveTest",
    page_icon="📇",
    layout="wide",
)

require_login()

page_header(
    "📇 Model Card",
    "Google-schema model card · EU AI Act Articles 11 + 13",
    articles=["11", "13"],
)

project = project_picker()
if project is None:
    st.stop()

st.markdown(
    f"### Project: `{project.project_id}` — "
    f"{project.client.company_name} / {project.project_name}"
)

# ---------------------------------------------------------------------------
# Load existing card
# ---------------------------------------------------------------------------
with get_session() as db:
    existing = db.scalars(
        select(ModelCard).where(ModelCard.project_id == project.project_id)
    ).first()
    if existing:
        card = {
            "card_id":                existing.card_id,
            "model_name":             existing.model_name,
            "model_version":          existing.model_version,
            "model_owners":           existing.model_owners,
            "license":                existing.license,
            "citation":               existing.citation,
            "references":             existing.references,
            "overview":               existing.overview,
            "primary_uses":           existing.primary_uses,
            "primary_users":          existing.primary_users,
            "out_of_scope_uses":      existing.out_of_scope_uses,
            "relevant_factors":       existing.relevant_factors,
            "evaluation_factors":     existing.evaluation_factors,
            "performance_metrics":    existing.performance_metrics,
            "decision_thresholds":    existing.decision_thresholds,
            "training_data":          existing.training_data,
            "evaluation_data":        existing.evaluation_data,
            "ethical_considerations": existing.ethical_considerations,
            "caveats":                existing.caveats,
            "recommendations":        existing.recommendations,
            "created_by":             existing.created_by,
            "created_at":             existing.created_at,
            "updated_at":             existing.updated_at,
        }
    else:
        card = None

# ---------------------------------------------------------------------------
# Status pill
# ---------------------------------------------------------------------------
if card is not None:
    pills = (
        risk_pill("Model name", card["model_name"] or "—", "info") +
        risk_pill("Version", card["model_version"] or "—", "info") +
        risk_pill(
            "Last updated",
            card["updated_at"].strftime("%Y-%m-%d"),
            "info",
        )
    )
    st.markdown(pills, unsafe_allow_html=True)
else:
    st.info(
        "No Model Card recorded for this project yet. The schema below "
        "follows Google's published Model Card spec and satisfies EU AI "
        "Act Articles 11 (technical documentation) and 13 (deployer "
        "transparency) when the fields are filled in."
    )

# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------
defaults = card or {
    "model_name": "", "model_version": "", "model_owners": "",
    "license": "", "citation": "", "references": "", "overview": "",
    "primary_uses": "", "primary_users": "", "out_of_scope_uses": "",
    "relevant_factors": "", "evaluation_factors": "",
    "performance_metrics": "", "decision_thresholds": "",
    "training_data": "", "evaluation_data": "",
    "ethical_considerations": "", "caveats": "", "recommendations": "",
}

with st.form("model_card"):
    st.markdown("### Model details")
    c1, c2 = st.columns(2)
    with c1:
        model_name = st.text_input(
            "Model name", value=defaults["model_name"]
        )
        model_version = st.text_input(
            "Version", value=defaults["model_version"]
        )
        license_ = st.text_input(
            "License", value=defaults["license"],
            help="e.g. MIT, Apache-2.0, Proprietary",
        )
    with c2:
        model_owners = st.text_area(
            "Owners (one per line)",
            value=defaults["model_owners"], height=80,
        )
        citation = st.text_area(
            "Citation", value=defaults["citation"], height=80,
        )

    overview = st.text_area(
        "Overview", value=defaults["overview"], height=100,
        help="One-paragraph description of what the model does.",
    )
    references = st.text_area(
        "References", value=defaults["references"], height=80,
        help="Papers, datasets, design docs (one per line).",
    )

    st.markdown("### Intended use")
    primary_uses = st.text_area(
        "Primary uses", value=defaults["primary_uses"], height=80,
    )
    primary_users = st.text_area(
        "Primary users", value=defaults["primary_users"], height=80,
    )
    out_of_scope_uses = st.text_area(
        "Out-of-scope uses",
        value=defaults["out_of_scope_uses"], height=80,
        help="Where the model SHOULD NOT be used. Crucial for "
             "downstream-deployer transparency under Art. 13.",
    )

    st.markdown("### Factors")
    f1, f2 = st.columns(2)
    with f1:
        relevant_factors = st.text_area(
            "Relevant factors",
            value=defaults["relevant_factors"], height=80,
            help="Subgroups, environments, or instrumentation conditions "
                 "the model's behaviour might depend on.",
        )
    with f2:
        evaluation_factors = st.text_area(
            "Evaluation factors",
            value=defaults["evaluation_factors"], height=80,
            help="Which of the relevant factors were evaluated, and "
                 "any that weren't.",
        )

    st.markdown("### Metrics")
    m1, m2 = st.columns(2)
    with m1:
        performance_metrics = st.text_area(
            "Performance metrics",
            value=defaults["performance_metrics"], height=120,
            help="One metric per line. Pull headline numbers from the "
                 "Performance Monitoring + Bias Detection runs.",
        )
    with m2:
        decision_thresholds = st.text_area(
            "Decision thresholds",
            value=defaults["decision_thresholds"], height=120,
        )

    st.markdown("### Data")
    d1, d2 = st.columns(2)
    with d1:
        training_data = st.text_area(
            "Training data",
            value=defaults["training_data"], height=120,
        )
    with d2:
        evaluation_data = st.text_area(
            "Evaluation data",
            value=defaults["evaluation_data"], height=120,
        )

    st.markdown("### Ethical considerations + caveats")
    ethical_considerations = st.text_area(
        "Ethical considerations",
        value=defaults["ethical_considerations"], height=100,
        help="Risks, harms, dual-use, mitigations.",
    )
    cv1, cv2 = st.columns(2)
    with cv1:
        caveats = st.text_area(
            "Caveats / limitations",
            value=defaults["caveats"], height=100,
        )
    with cv2:
        recommendations = st.text_area(
            "Recommendations to users",
            value=defaults["recommendations"], height=100,
        )

    if st.form_submit_button("Save model card", type="primary"):
        with get_session() as db:
            target = db.scalars(
                select(ModelCard)
                .where(ModelCard.project_id == project.project_id)
            ).first()
            if target is None:
                cid = next_id(db, ModelCard.card_id, "MC")
                target = ModelCard(
                    card_id=cid, project_id=project.project_id,
                    created_by=current_username() or "system",
                )
                db.add(target)
            for f, v in {
                "model_name": model_name, "model_version": model_version,
                "model_owners": model_owners, "license": license_,
                "citation": citation, "references": references,
                "overview": overview,
                "primary_uses": primary_uses, "primary_users": primary_users,
                "out_of_scope_uses": out_of_scope_uses,
                "relevant_factors": relevant_factors,
                "evaluation_factors": evaluation_factors,
                "performance_metrics": performance_metrics,
                "decision_thresholds": decision_thresholds,
                "training_data": training_data,
                "evaluation_data": evaluation_data,
                "ethical_considerations": ethical_considerations,
                "caveats": caveats, "recommendations": recommendations,
            }.items():
                setattr(target, f, (v or "").strip())
            target.updated_at = utc_now()
        record_run(
            project=project, module="model_card",
            status=f"SAVED {model_name or 'model'} v{model_version or 'unversioned'}",
            status_color="info",
            status_detail="Art. 11 + 13 model card updated",
        )
        st.success("Model card saved.")
        st.rerun()

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
if card is not None:
    st.divider()
    st.subheader("Export")
    md = to_markdown(
        card,
        project_label=f"{project.client.company_name} / {project.project_name}",
    )
    js = to_json(
        card, project=project,
    )
    cols = st.columns(2)
    cols[0].download_button(
        "⬇ Download Model Card (Markdown)",
        data=md,
        file_name=f"model_card_{project.project_id}.md",
        mime="text/markdown",
    )
    cols[1].download_button(
        "⬇ Download Model Card (JSON, Google schema)",
        data=js,
        file_name=f"model_card_{project.project_id}.json",
        mime="application/json",
    )
