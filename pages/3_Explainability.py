"""
pages/3_Explainability.py
============================

SHAP-based explainability assessment for one project.
Wraps :mod:`wavetest_explain` end-to-end. The current page only supports
demo models; client model upload is a future feature.
"""

from __future__ import annotations

import streamlit as st
from wavetest_explain import ExplainabilityVisualizer
from wavetest_explain.core.assessment import AssessmentConfig
from wavetest_explain.data.demo import generate_demo_model

from wavetest_app.adapters.explain import make_explain_assessment
from wavetest_app.ui import page_header, project_picker, risk_pill, show_recommendations

st.set_page_config(
    page_title="Explainability · waveTest",
    page_icon="🔍",
    layout="wide",
)

page_header(
    "🔍 SHAP Explainability",
    "EU AI Act Article 13 — Transparency · Global + local explanations + consistency",
    articles=["13"],
)

project = project_picker()
if project is None:
    st.stop()

st.markdown(
    f"### Project: `{project.project_id}` — "
    f"{project.client.company_name} / {project.project_name}"
)

# ---------------------------------------------------------------------------
# Configure
# ---------------------------------------------------------------------------
with st.expander("⚙️ Configure", expanded=True):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Analysis configuration**")
        risk_level = st.selectbox(
            "Risk level (EU AI Act)",
            ["high-risk", "limited-risk", "minimal-risk"], index=0, key="exp_risk",
        )
        confidence_threshold = st.slider(
            "Confidence threshold (borderline cases below)",
            0.50, 0.99, 0.85, 0.01, key="exp_conf",
        )
        consistency_threshold = st.slider(
            "Consistency threshold (cosine similarity)",
            0.10, 0.99, 0.70, 0.05, key="exp_cons",
        )

    with c2:
        st.markdown("**Sampling**")
        n_background_samples = st.number_input(
            "Background samples (SHAP init)", 10, 1000, 100, 10, key="exp_bg",
        )
        n_explanation_samples = st.number_input(
            "Explanation samples (SHAP value count)", 5, 500, 50, 5, key="exp_n",
        )
        n_consistency_pairs = st.number_input(
            "Consistency pair count", 5, 200, 20, 5, key="exp_pairs",
        )

    st.markdown("**Demo model**")
    st.caption(
        "Real model upload is a future feature; for now this page trains a "
        "RandomForest on synthetic data with a known ground truth."
    )
    c3, c4 = st.columns(2)
    with c3:
        n_demo_samples = st.number_input(
            "Demo samples", 100, 10_000, 1000, 100, key="exp_dn",
        )
    with c4:
        n_demo_features = st.number_input(
            "Demo features", 3, 30, 10, 1, key="exp_df",
        )

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if st.button("▶ Run assessment", type="primary", key="exp_run"):
    cfg = AssessmentConfig(
        risk_level=risk_level,
        confidence_threshold=confidence_threshold,
        consistency_threshold=consistency_threshold,
        n_background_samples=int(n_background_samples),
        n_explanation_samples=int(n_explanation_samples),
        n_consistency_pairs=int(n_consistency_pairs),
    )

    with st.spinner("Training demo model and running SHAP analysis…"):
        bundle = generate_demo_model(
            n_samples=int(n_demo_samples), n_features=int(n_demo_features),
        )
        assessment = make_explain_assessment(
            project_id=project.project_id, config=cfg,
        )
        results = assessment.run(
            model=bundle.model,
            X_test=bundle.X_test,
            y_test=bundle.y_test,
            feature_names=bundle.feature_names,
            X_train=bundle.X_train,
            verbose=False,
        )
        report_paths = assessment.generate_reports(formats=["json"])

    st.session_state["exp_assessment"]   = assessment
    st.session_state["exp_results"]      = results
    st.session_state["exp_report_paths"] = report_paths
    st.session_state["exp_bundle"]       = bundle

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if "exp_results" in st.session_state:
    assessment   = st.session_state["exp_assessment"]
    results      = st.session_state["exp_results"]
    report_paths = st.session_state["exp_report_paths"]
    bundle       = st.session_state["exp_bundle"]

    st.divider()
    st.subheader("Results")

    accuracy_color = (
        "ok" if results.accuracy >= 0.85 else
        "warning" if results.accuracy >= 0.70 else "critical"
    )
    cons = results.consistency
    cons_color = "ok" if cons and cons.mean_consistency >= 0.70 else "warning"
    comp = results.compliance
    comp_color = (
        "ok" if comp and comp.overall_status == "ERFÜLLT" else "warning"
    )

    pills = (
        risk_pill("Accuracy", f"{results.accuracy:.2%}", accuracy_color) +
        (risk_pill("Consistency",
                   f"{cons.mean_consistency:.2%}" if cons else "—",
                   cons_color)) +
        (risk_pill("Compliance",
                   comp.overall_status if comp else "—",
                   comp_color))
    )
    st.markdown(pills, unsafe_allow_html=True)

    # Global feature importance table
    st.markdown("#### Global feature importance")
    if results.global_explanation:
        st.dataframe(
            results.global_explanation.importance_df.head(15),
            hide_index=True, use_container_width=True,
        )
        st.caption(
            f"Top-3 features account for "
            f"**{results.global_explanation.top_n_concentration:.1f}%** of total importance."
        )

    # SHAP summary plot
    if results.shap_values_positive is not None:
        st.markdown("#### SHAP summary")
        viz = ExplainabilityVisualizer(feature_names=bundle.feature_names)
        try:
            fig, _ = viz.plot_shap_bar(
                results.shap_values_positive,
                bundle.X_test[: len(results.shap_values_positive)],
            )
            st.pyplot(fig, use_container_width=True)
        except Exception as exc:
            st.warning(f"Could not render SHAP plot: {exc}")

    # Local case explanations
    if results.local_analysis and results.local_analysis.explanations:
        st.markdown("#### Local case explanations")
        st.dataframe(
            [
                {
                    "Index":      e.index,
                    "Category":   e.category.value,
                    "True":       e.true_label,
                    "Predicted":  e.predicted_label,
                    "Confidence": f"{e.confidence:.3f}",
                    "Borderline": "⚠️" if e.is_borderline else "",
                }
                for e in results.local_analysis.explanations
            ],
            hide_index=True, use_container_width=True,
        )
        st.caption(
            f"{results.local_analysis.n_borderline} of "
            f"{len(results.local_analysis.explanations)} cases were flagged "
            f"as borderline (confidence < "
            f"{assessment.config.confidence_threshold:.2f})."
        )

    # Compliance checklist
    if comp:
        st.markdown("#### EU AI Act Article 13 compliance")
        st.dataframe(
            [
                {
                    "Article":     item.article,
                    "Title":       item.title,
                    "Status":      item.status,
                    "Requirement": item.requirement,
                }
                for item in comp.items
            ],
            hide_index=True, use_container_width=True,
        )

    # Recommendations via unified envelope
    from wavetest_report import ReportEnvelope
    envelope = ReportEnvelope.from_explainability(assessment, results)
    st.markdown("#### Recommendations")
    show_recommendations(envelope.summary.recommendations)

    # Downloads
    st.markdown("#### Exports")
    cols = st.columns(len(report_paths))
    for col, (fmt, path) in zip(cols, report_paths.items()):
        col.download_button(
            f"⬇ Download {fmt.upper()}",
            data=path.read_bytes(),
            file_name=path.name,
            mime="application/json",
            key=f"exp_dl_{fmt}",
        )
