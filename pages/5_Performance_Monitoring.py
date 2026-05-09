"""
pages/5_Performance_Monitoring.py
====================================

Article 15 performance monitoring for one project.
Wraps :mod:`wavetest_monitoring`: accuracy + drift + outliers + dashboard.
"""

from __future__ import annotations

import time

import streamlit as st
from wavetest_monitoring import (
    MonitoringConfig,
    MonitoringDashboard,
    MonitoringSystemProfile,
    generate_demo_monitoring_data,
)

from wavetest_app.adapters.monitoring import make_monitoring_assessment
from wavetest_app.audit import record_run
from wavetest_app.ui import (
    csv_uploader, page_header, project_picker, risk_pill, show_recommendations,
)

st.set_page_config(
    page_title="Performance Monitoring · waveTest",
    page_icon="📈",
    layout="wide",
)

page_header(
    "📈 Performance Monitoring",
    "EU AI Act Articles 15, 72 — Accuracy, drift detection, outlier rates",
    articles=["15", "72"],
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
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Performance thresholds**")
        accuracy_threshold = st.slider(
            "Min accuracy", 0.5, 0.99, 0.85, 0.01, key="mn_acc",
        )
        accuracy_degradation_tolerance = st.slider(
            "Degradation tolerance", 0.0, 0.20, 0.05, 0.01, key="mn_tol",
        )
        confidence_threshold = st.slider(
            "Min confidence", 0.5, 0.99, 0.70, 0.01, key="mn_conf",
        )
        error_rate_threshold = st.slider(
            "Max error rate", 0.0, 0.50, 0.10, 0.01, key="mn_err",
        )

    with c2:
        st.markdown("**Drift / outlier thresholds**")
        drift_significance_level = st.slider(
            "Drift p-value cutoff", 0.001, 0.10, 0.05, 0.005, key="mn_p",
        )
        drift_critical_threshold = st.slider(
            "Critical drift (KS statistic)", 0.05, 0.50, 0.10, 0.01,
            key="mn_dc",
        )
        outlier_threshold_std = st.slider(
            "Outlier Z-score cutoff", 2.0, 5.0, 3.0, 0.1, key="mn_z",
        )
        max_outlier_rate = st.slider(
            "Max outlier rate per feature", 0.01, 0.20, 0.05, 0.01, key="mn_or",
        )

    with c3:
        st.markdown("**System profile + demo data**")
        task_type = st.selectbox(
            "Task type", ["classification", "regression", "ranking"],
            key="mn_task",
        )
        high_risk = st.checkbox(
            "High-risk classification", value=True, key="mn_hr",
        )
        deployment = st.selectbox(
            "Deployment", ["development", "staging", "production"],
            index=2, key="mn_dep",
        )
        st.markdown("---")
        source = st.radio(
            "Data source",
            ["Demo data (synthetic)", "Upload CSV"],
            horizontal=True, key="mn_src",
        )
        uploaded_df = None
        if source == "Demo data (synthetic)":
            drift_level = st.selectbox(
                "Demo drift level", ["none", "moderate", "high"], index=1,
                key="mn_dl",
            )
            n_samples = st.number_input(
                "Demo samples", 100, 10_000, 1000, 100, key="mn_n",
            )
        else:
            uploaded_df = csv_uploader(
                "Drop a CSV with monitoring data",
                key="mn_upload",
                required_columns=["timestamp", "y_true", "y_pred"],
                parse_dates=["timestamp"],
                help=(
                    "Required columns: `timestamp`, `y_true`, `y_pred`. "
                    "Optional: `confidence`. Any other numeric / categorical "
                    "columns will be analysed for drift and outliers."
                ),
            )

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if st.button("▶ Run assessment", type="primary", key="mn_run"):
    cfg = MonitoringConfig(
        accuracy_threshold=accuracy_threshold,
        accuracy_degradation_tolerance=accuracy_degradation_tolerance,
        confidence_threshold=confidence_threshold,
        drift_significance_level=drift_significance_level,
        drift_critical_threshold=drift_critical_threshold,
        outlier_threshold_std=outlier_threshold_std,
        max_outlier_rate=max_outlier_rate,
        error_rate_threshold=error_rate_threshold,
    )
    profile = MonitoringSystemProfile(
        task_type=task_type, high_risk=high_risk, deployment=deployment,
    )

    if source != "Demo data (synthetic)" and uploaded_df is None:
        st.error("Upload a CSV first or switch to demo data.")
        st.stop()

    with st.spinner("Running assessment…"):
        if source == "Demo data (synthetic)":
            df = generate_demo_monitoring_data(
                n_samples=int(n_samples), drift_level=drift_level,
            )
        else:
            df = uploaded_df
        assessment = make_monitoring_assessment(
            project_id=project.project_id,
            config=cfg, system_profile=profile,
        )
        _t0 = time.perf_counter()
        results = assessment.run(df, verbose=False)
        _dt = time.perf_counter() - _t0
        report_paths = assessment.generate_reports(formats=["json", "csv"])

    status = results.overall_metrics.status(
        cfg.accuracy_threshold, cfg.accuracy_degradation_tolerance,
    )
    color = {"GOOD": "ok", "WARNING": "warning", "CRITICAL": "critical"}[status]
    record_run(
        project=project, module="monitoring",
        status=status, status_color=color,
        status_detail=(
            f"Accuracy {results.overall_metrics.accuracy:.2%} · "
            f"drift {results.drift_count}/{len(results.drift_results)} · "
            f"Art.15 "
            f"{'compliant' if assessment.is_article_15_compliant(results) else 'gaps'}"
        ),
        duration_seconds=_dt,
    )

    st.session_state["mn_df"]            = df
    st.session_state["mn_assessment"]    = assessment
    st.session_state["mn_results"]       = results
    st.session_state["mn_report_paths"]  = report_paths

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if "mn_results" in st.session_state:
    df            = st.session_state["mn_df"]
    assessment    = st.session_state["mn_assessment"]
    results       = st.session_state["mn_results"]
    report_paths  = st.session_state["mn_report_paths"]
    m             = results.overall_metrics
    cfg           = assessment.config

    st.divider()
    st.subheader("Results")

    status = m.status(cfg.accuracy_threshold, cfg.accuracy_degradation_tolerance)
    status_color = {"GOOD": "ok", "WARNING": "warning", "CRITICAL": "critical"}[status]
    drift_color = "ok" if results.drift_count == 0 else "warning"
    out_color   = "ok" if results.critical_outlier_count == 0 else "warning"
    art15_color = "ok" if assessment.is_article_15_compliant(results) else "critical"

    pills = (
        risk_pill("Accuracy", f"{m.accuracy:.2%}", status_color) +
        risk_pill("Status", status, status_color) +
        risk_pill("Drift",
                  f"{results.drift_count}/{len(results.drift_results)}", drift_color) +
        risk_pill("Critical outliers",
                  f"{results.critical_outlier_count}/{len(results.outlier_results)}",
                  out_color) +
        risk_pill("Article 15",
                  "Compliant" if assessment.is_article_15_compliant(results) else "Gaps",
                  art15_color)
    )
    st.markdown(pills, unsafe_allow_html=True)

    # Dashboard
    st.markdown("#### Dashboard")
    viz = MonitoringDashboard(system_name=assessment.system_name)
    fig, _ = viz.render(df, results, cfg)
    st.pyplot(fig, use_container_width=True)

    # Detail tables
    cols = st.columns(2)
    with cols[0]:
        st.markdown("#### Drift detection")
        if results.drift_results:
            st.dataframe(
                [r.to_dict() for r in results.drift_results.values()],
                hide_index=True, use_container_width=True,
            )
        else:
            st.info("No features available for drift analysis.")

    with cols[1]:
        st.markdown("#### Outlier rates")
        if results.outlier_results:
            st.dataframe(
                [r.to_dict() for r in results.outlier_results.values()],
                hide_index=True, use_container_width=True,
            )
        else:
            st.info("No features available for outlier analysis.")

    # Daily metrics
    if len(results.daily_metrics) > 0:
        st.markdown("#### Daily metrics (rolling)")
        st.dataframe(
            results.daily_metrics.tail(14),
            hide_index=True, use_container_width=True,
        )
        if results.trend is not None:
            arrow = "📈" if results.trend > 0 else "📉" if results.trend < 0 else "➡️"
            st.caption(f"Performance trend: {arrow} **{results.trend:+.2%}** "
                       "(last 3 days vs first 3 days)")

    # Recommendations
    st.markdown("#### Recommendations")
    show_recommendations(assessment.build_recommendations(results))

    # Downloads
    st.markdown("#### Exports")
    cols = st.columns(len(report_paths))
    for col, (fmt, path) in zip(cols, report_paths.items()):
        col.download_button(
            f"⬇ Download {fmt.upper()}",
            data=path.read_bytes(),
            file_name=path.name,
            mime="application/json" if fmt == "json" else "text/csv",
            key=f"mn_dl_{fmt}",
        )
