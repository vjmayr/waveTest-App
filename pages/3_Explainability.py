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

import numpy as np

from wavetest_app.adapters.explain import make_explain_assessment
from wavetest_app.ui import (
    csv_uploader, model_uploader, page_header, project_picker,
    risk_pill, show_recommendations,
)

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

    st.markdown("**Model + data**")
    source = st.radio(
        "Source",
        ["Demo model (synthetic)", "Upload client model"],
        horizontal=True, key="exp_src",
    )

    uploaded_model = None
    uploaded_test_df = None
    uploaded_train_df = None
    target_col = None

    if source == "Demo model (synthetic)":
        c3, c4 = st.columns(2)
        with c3:
            n_demo_samples = st.number_input(
                "Demo samples", 100, 10_000, 1000, 100, key="exp_dn",
            )
        with c4:
            n_demo_features = st.number_input(
                "Demo features", 3, 30, 10, 1, key="exp_df",
            )
    else:
        st.caption(
            "Upload a pickled scikit-learn-style model with `predict()` and "
            "`predict_proba()`, plus a test CSV containing the features and the "
            "target column."
        )
        uploaded_model = model_uploader(
            "Model file (.pkl / .joblib)",
            key="exp_model",
            required_methods=["predict", "predict_proba"],
        )
        target_col = st.text_input(
            "Target column name in the test CSV",
            value="target", key="exp_target",
        )
        uploaded_test_df = csv_uploader(
            "Test CSV (features + target column)",
            key="exp_test_csv",
            help="One row per test sample. Feature columns will be passed to "
                 "the model in the order they appear in the CSV.",
        )
        uploaded_train_df = csv_uploader(
            "Training CSV (optional — improves SHAP background sampling)",
            key="exp_train_csv",
            help="Same column layout as the test CSV. If omitted, SHAP uses the "
                 "test data as background.",
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

    if source == "Demo model (synthetic)":
        with st.spinner("Training demo model and running SHAP analysis…"):
            bundle = generate_demo_model(
                n_samples=int(n_demo_samples), n_features=int(n_demo_features),
            )
            model = bundle.model
            X_test = bundle.X_test
            y_test = bundle.y_test
            feature_names = bundle.feature_names
            X_train = bundle.X_train
    else:
        if uploaded_model is None:
            st.error("Upload a model file first.")
            st.stop()
        if uploaded_test_df is None:
            st.error("Upload a test CSV first.")
            st.stop()
        if not target_col or target_col not in uploaded_test_df.columns:
            st.error(
                f"Target column `{target_col}` not found in test CSV. "
                f"Available: {list(uploaded_test_df.columns)}"
            )
            st.stop()

        feature_names = [c for c in uploaded_test_df.columns if c != target_col]
        X_test = uploaded_test_df[feature_names].to_numpy()
        y_test = uploaded_test_df[target_col].to_numpy()
        if uploaded_train_df is not None:
            train_missing = [c for c in feature_names + [target_col]
                             if c not in uploaded_train_df.columns]
            if train_missing:
                st.error(f"Training CSV is missing columns: {train_missing}")
                st.stop()
            X_train = uploaded_train_df[feature_names].to_numpy()
        else:
            X_train = None
        model = uploaded_model

        with st.spinner("Running SHAP analysis on uploaded model…"):
            pass

    # Cast to ndarray to be safe (some uploaders give pandas)
    X_test = np.asarray(X_test)
    y_test = np.asarray(y_test)
    if X_train is not None:
        X_train = np.asarray(X_train)

    with st.spinner("Computing SHAP values + compliance mapping…"):
        assessment = make_explain_assessment(
            project_id=project.project_id, config=cfg,
        )
        results = assessment.run(
            model=model,
            X_test=X_test, y_test=y_test,
            feature_names=feature_names,
            X_train=X_train,
            verbose=False,
        )
        report_paths = assessment.generate_reports(formats=["json"])

    st.session_state["exp_assessment"]   = assessment
    st.session_state["exp_results"]      = results
    st.session_state["exp_report_paths"] = report_paths
    # Store enough for the downstream visuals (kept generic — no DemoBundle)
    st.session_state["exp_X_test"]       = X_test
    st.session_state["exp_feature_names"] = feature_names

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if "exp_results" in st.session_state:
    assessment    = st.session_state["exp_assessment"]
    results       = st.session_state["exp_results"]
    report_paths  = st.session_state["exp_report_paths"]
    X_test        = st.session_state["exp_X_test"]
    feature_names = st.session_state["exp_feature_names"]

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
        viz = ExplainabilityVisualizer(feature_names=feature_names)
        try:
            fig, _ = viz.plot_shap_bar(
                results.shap_values_positive,
                X_test[: len(results.shap_values_positive)],
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
