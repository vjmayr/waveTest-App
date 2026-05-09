"""
pages/2_Bias_Detection.py
============================

Bias detection and fairness assessment for one project.
Wraps :mod:`wavetest_fairness` end-to-end.
"""

from __future__ import annotations

import json as _json
import time

import streamlit as st
from wavetest_fairness import FairnessVisualizer, generate_demo_data

from wavetest_app.adapters.fairness import make_fairness_assessment
from wavetest_app.audit import audit_assessment, record_run
from wavetest_app.auth import require_login
from wavetest_app.ui import (
    csv_uploader, page_header, project_picker, risk_pill, show_recommendations,
)

st.set_page_config(
    page_title="Bias Detection · waveTest",
    page_icon="⚖️",
    layout="wide",
)

require_login()

page_header(
    "⚖️ Bias Detection & Fairness",
    "EU AI Act Articles 10, 13, 61 — Disparate impact, statistical parity, equal opportunity",
    articles=["10", "13", "61"],
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
        st.markdown("**Data source**")
        source = st.radio(
            "Choose data",
            ["Demo data (synthetic)", "Upload CSV"],
            horizontal=True, key="bias_source",
        )
        uploaded_df = None
        if source == "Demo data (synthetic)":
            bias_level = st.selectbox(
                "Demo bias level",
                ["none", "low", "moderate", "high"], index=2, key="bias_level",
            )
            n_samples = st.number_input(
                "Sample count", 100, 50_000, 2000, 500, key="bias_n",
            )
        else:
            uploaded_df = csv_uploader(
                "Drop a CSV with predictions",
                key="bias_upload",
                required_columns=["y_true", "y_pred"],
                help=(
                    "Required columns: `y_true`, `y_pred`. Plus one column for each "
                    "key in the privileged-groups JSON below."
                ),
            )

    with c2:
        st.markdown("**Privileged groups**")
        priv_text = st.text_area(
            "JSON dict mapping protected attribute → privileged value",
            value=(
                '{\n'
                '  "geschlecht":   "M",\n'
                '  "alter_gruppe": "<30",\n'
                '  "nationalitaet": "DE",\n'
                '  "behinderung":  false\n'
                '}'
            ),
            height=140, key="bias_priv",
            help=(
                "These are the columns on which fairness metrics are computed. "
                "The value identifies the privileged group within each column."
            ),
        )

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if st.button("▶ Run assessment", type="primary", key="bias_run"):
    try:
        privileged_groups = _json.loads(priv_text)
    except _json.JSONDecodeError as exc:
        st.error(f"Privileged groups JSON is invalid: {exc}")
        st.stop()

    if source != "Demo data (synthetic)" and uploaded_df is None:
        st.error("Upload a CSV first or switch to demo data.")
        st.stop()

    with audit_assessment(project, "bias"):
        with st.spinner("Running assessment…"):
            if source == "Demo data (synthetic)":
                y_true, y_pred, sensitive_features, _full = generate_demo_data(
                    n_samples=int(n_samples), bias_level=bias_level,
                )
            else:
                missing = [c for c in privileged_groups if c not in uploaded_df.columns]
                if missing:
                    st.error(
                        f"Privileged-groups columns missing from CSV: {missing}\n\n"
                        f"CSV columns: {list(uploaded_df.columns)}"
                    )
                    st.stop()
                y_true = uploaded_df["y_true"]
                y_pred = uploaded_df["y_pred"]
                sensitive_features = uploaded_df[list(privileged_groups.keys())]

            assessment = make_fairness_assessment(
                project_id=project.project_id,
                privileged_groups=privileged_groups,
            )
            _t0 = time.perf_counter()
            results = assessment.run(
                y_true=y_true, y_pred=y_pred,
                sensitive_features=sensitive_features, verbose=False,
            )
            _dt = time.perf_counter() - _t0
            report_paths = assessment.generate_reports(formats=["json", "csv"])

        risk_v = assessment.overall_risk.value
        color = (
            "ok" if risk_v in ("NIEDRIG", "LOW") else
            "warning" if risk_v in ("MITTEL", "MEDIUM") else "critical"
        )
        record_run(
            project=project, module="bias",
            status=risk_v, status_color=color,
            status_detail=(
                f"{assessment.critical_count}/{len(results)} critical findings"
            ),
            duration_seconds=_dt,
        )

    st.session_state["bias_assessment"]   = assessment
    st.session_state["bias_results"]      = results
    st.session_state["bias_report_paths"] = report_paths
    st.session_state["bias_features"]     = sensitive_features
    # Snapshots for the Fairlearn complementary view
    st.session_state["bias_y_true"]       = y_true
    st.session_state["bias_y_pred"]       = y_pred

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if "bias_results" in st.session_state:
    assessment    = st.session_state["bias_assessment"]
    results       = st.session_state["bias_results"]
    report_paths  = st.session_state["bias_report_paths"]
    features_df   = st.session_state["bias_features"]

    st.divider()
    st.subheader("Results")

    overall_risk = assessment.overall_risk
    n_critical = assessment.critical_count
    n_total = len(results)
    risk_color = (
        "ok" if overall_risk.value in ("NIEDRIG", "LOW") else
        "warning" if overall_risk.value in ("MITTEL", "MEDIUM") else "critical"
    )

    pills = (
        risk_pill("Overall Risk", overall_risk.value, risk_color) +
        risk_pill("Critical findings", f"{n_critical} / {n_total}",
                  "critical" if n_critical else "ok") +
        risk_pill("Features analysed", str(n_total), "ok")
    )
    st.markdown(pills, unsafe_allow_html=True)

    # Metrics dataframe
    st.markdown("#### Per-feature fairness metrics")
    st.dataframe(
        assessment.results_dataframe, hide_index=True, use_container_width=True,
    )

    # Dashboard
    st.markdown("#### Dashboard")
    viz = FairnessVisualizer()
    fig, _ = viz.plot_assessment_dashboard(results, system_name=assessment.system_name)
    st.pyplot(fig, use_container_width=True)

    # Feature distributions
    st.markdown("#### Protected-attribute distributions")
    fig2, _ = viz.plot_feature_distributions(features_df)
    st.pyplot(fig2, use_container_width=True)

    # ---------------------------------------------------------------------
    # Fairlearn — complementary per-group metric breakdowns. AIF360 above
    # gives the risk classification; Fairlearn shows what the underlying
    # rates actually look like per group, which is what analysts need
    # for the client conversation.
    # ---------------------------------------------------------------------
    with st.expander(
        "📊 Per-group metrics (Fairlearn)", expanded=False,
    ):
        st.caption(
            "Selection rate, true-positive rate, false-positive rate per "
            "subgroup of each protected attribute, plus disparity summaries."
        )
        try:
            from fairlearn.metrics import (
                MetricFrame,
                demographic_parity_difference,
                equalized_odds_difference,
                false_positive_rate,
                selection_rate,
                true_positive_rate,
            )
            from sklearn.metrics import accuracy_score

            # Recover the same y/sensitive_features arrays the assessment used
            y_true_arr = st.session_state.get("bias_y_true")
            y_pred_arr = st.session_state.get("bias_y_pred")
            if y_true_arr is None or y_pred_arr is None:
                st.info(
                    "Re-run the assessment to enable Fairlearn — the "
                    "y_true/y_pred snapshot wasn't saved on the previous run."
                )
            else:
                metrics = {
                    "accuracy":        accuracy_score,
                    "selection_rate":  selection_rate,
                    "true_pos_rate":   true_positive_rate,
                    "false_pos_rate":  false_positive_rate,
                }
                # One MetricFrame per protected attribute → tabbed view.
                tab_labels = list(features_df.columns)
                tabs = st.tabs([f"`{c}`" for c in tab_labels])
                for tab, col in zip(tabs, tab_labels):
                    with tab:
                        mf = MetricFrame(
                            metrics=metrics,
                            y_true=y_true_arr,
                            y_pred=y_pred_arr,
                            sensitive_features=features_df[col],
                        )
                        st.dataframe(
                            mf.by_group, use_container_width=True,
                        )
                        dp = demographic_parity_difference(
                            y_true=y_true_arr, y_pred=y_pred_arr,
                            sensitive_features=features_df[col],
                        )
                        eo = equalized_odds_difference(
                            y_true=y_true_arr, y_pred=y_pred_arr,
                            sensitive_features=features_df[col],
                        )
                        st.caption(
                            f"**Demographic parity difference**: "
                            f"`{dp:+.3f}` (0 = perfectly equal selection "
                            f"rates) · "
                            f"**Equalized odds difference**: "
                            f"`{eo:+.3f}` (0 = perfectly equal TPR + FPR)"
                        )
        except Exception as exc:
            st.info(
                f"Fairlearn analysis not available "
                f"({type(exc).__name__}: {exc})."
            )

    # Recommendations via the unified report envelope
    from wavetest_report import ReportEnvelope
    envelope = ReportEnvelope.from_fairness(assessment, results)
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
            mime="application/json" if fmt == "json" else "text/csv",
            key=f"bias_dl_{fmt}",
        )
