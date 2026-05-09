"""
pages/4_Logging_Framework.py
===============================

Article 12 logging-framework evaluation for one project.
Wraps :mod:`wavetest_logging`: gap analysis + tailored framework design +
a downloadable standalone Python file the client can drop into their
codebase.
"""

from __future__ import annotations

import time

import streamlit as st
from wavetest_logging import (
    CurrentLoggingState,
    GapVisualizer,
    SystemProfile,
)

from wavetest_app.adapters.logging import make_logging_assessment
from wavetest_app.audit import record_run
from wavetest_app.ui import page_header, project_picker, risk_pill, show_recommendations

st.set_page_config(
    page_title="Logging Framework · waveTest",
    page_icon="📝",
    layout="wide",
)

page_header(
    "📝 Logging Framework Evaluation",
    "EU AI Act Articles 12, 72 — Record-keeping · Generates a compliant logger",
    articles=["12", "72"],
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
        st.markdown("**Current logging state** (interview the client)")
        has_logging         = st.checkbox("Has any logging today",                key="lg_h")
        logs_inputs         = st.checkbox("Logs inputs",                          key="lg_in")
        logs_outputs        = st.checkbox("Logs outputs / decisions",             key="lg_out")
        logs_timestamps     = st.checkbox("Logs timestamps",                      key="lg_ts")
        logs_user_info      = st.checkbox("Logs user information",                key="lg_user")
        logs_model_version  = st.checkbox("Logs model / system version",          key="lg_ver")
        logs_confidence     = st.checkbox("Logs confidence scores",               key="lg_conf")
        structured_format   = st.checkbox("Logs are in a structured format (JSON)", key="lg_struct")

        logging_method = st.selectbox(
            "Storage method", ["none", "file", "database", "cloud"], key="lg_method",
        )
        retention_period_days = st.number_input(
            "Current retention (days)", 0, 3650, 0, 30, key="lg_ret",
        )

    with c2:
        st.markdown("**System profile**")
        system_type = st.selectbox(
            "System type",
            ["classification", "regression", "recommendation", "nlp", "vision"],
            key="lg_stype",
        )
        deployment = st.selectbox(
            "Deployment", ["api", "batch", "embedded", "web_app"], key="lg_dep",
        )
        throughput = st.selectbox(
            "Throughput", ["low", "medium", "high"], index=1, key="lg_tput",
        )
        latency_requirements = st.selectbox(
            "Latency requirements", ["strict", "moderate", "relaxed"], index=1,
            key="lg_lat",
        )
        contains_personal_data = st.checkbox(
            "Processes personal data (GDPR)", value=True, key="lg_pii",
        )
        high_risk_classification = st.checkbox(
            "Classified as high-risk (EU AI Act)", value=True, key="lg_hr",
        )

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if st.button("▶ Run assessment", type="primary", key="lg_run"):
    current = CurrentLoggingState(
        has_logging=has_logging,
        logging_method=logging_method,
        logs_inputs=logs_inputs,
        logs_outputs=logs_outputs,
        logs_timestamps=logs_timestamps,
        logs_user_info=logs_user_info,
        logs_model_version=logs_model_version,
        logs_confidence=logs_confidence,
        retention_period_days=int(retention_period_days),
        structured_format=structured_format,
    )
    profile = SystemProfile(
        system_type=system_type,
        deployment=deployment,
        throughput=throughput,
        latency_requirements=latency_requirements,
        contains_personal_data=contains_personal_data,
        high_risk_classification=high_risk_classification,
    )

    with st.spinner("Analysing gaps and generating framework…"):
        assessment = make_logging_assessment(
            project_id=project.project_id,
            current_logging=current,
            system_profile=profile,
        )
        _t0 = time.perf_counter()
        results = assessment.run(verbose=False)
        _dt = time.perf_counter() - _t0
        report_paths = assessment.generate_reports(formats=["json", "csv", "guide"])

    pct = results.summary["compliance_percent"]
    color = "ok" if pct == 100 else "warning" if pct >= 50 else "critical"
    record_run(
        project=project, module="logging",
        status=f"{pct}%", status_color=color,
        status_detail=(
            f"{results.summary['total_gaps']} gaps "
            f"({results.summary['critical_gaps']} critical) · Art.12 "
            f"{'compliant' if results.article_12_compliant else 'gaps'}"
        ),
        duration_seconds=_dt,
    )

    st.session_state["lg_assessment"]   = assessment
    st.session_state["lg_results"]      = results
    st.session_state["lg_report_paths"] = report_paths

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if "lg_results" in st.session_state:
    assessment   = st.session_state["lg_assessment"]
    results      = st.session_state["lg_results"]
    report_paths = st.session_state["lg_report_paths"]

    st.divider()
    st.subheader("Results")

    s = results.summary
    compliance_pct = s["compliance_percent"]
    pct_color = (
        "ok" if compliance_pct == 100 else
        "warning" if compliance_pct >= 50 else "critical"
    )
    art12_color = "ok" if results.article_12_compliant else "critical"
    test_color = (
        "ok" if results.tests_total and results.tests_passed == results.tests_total
        else "warning"
    )

    pills = (
        risk_pill("Compliance", f"{compliance_pct}%", pct_color) +
        risk_pill("Open gaps", str(s["total_gaps"]),
                  "ok" if s["total_gaps"] == 0 else "critical") +
        risk_pill("Critical gaps", str(s["critical_gaps"]),
                  "ok" if s["critical_gaps"] == 0 else "critical") +
        risk_pill("Smoke tests",
                  f"{results.tests_passed}/{results.tests_total}", test_color) +
        risk_pill("Article 12",
                  "Compliant" if results.article_12_compliant else "Gaps",
                  art12_color)
    )
    st.markdown(pills, unsafe_allow_html=True)

    # Gap chart
    st.markdown("#### Gap analysis")
    viz = GapVisualizer(system_name=assessment.system_name)
    fig, _ = viz.gap_chart(results.gaps)
    st.pyplot(fig, use_container_width=True)

    # Schema
    st.markdown("#### Designed logging schema")
    st.dataframe(
        results.design.schema_dataframe(), hide_index=True, use_container_width=True,
    )
    st.caption(
        f"Storage: **{results.design.storage_method.upper()}** · "
        f"Format: **{results.design.format_type.upper()}** · "
        f"Retention: **{results.design.retention_days} days**"
    )

    # Smoke tests
    st.markdown("#### Smoke tests on the generated logger")
    st.dataframe(
        [{"Test": t, "Passed": "✓" if ok else "❌"}
         for t, ok in results.test_results.items()],
        hide_index=True, use_container_width=True,
    )

    # Recommendations
    st.markdown("#### Recommendations")
    show_recommendations(assessment.build_recommendations(results))

    # Downloads
    st.markdown("#### Exports")
    cols = st.columns(len(report_paths) + 1)
    for col, (fmt, path) in zip(cols, report_paths.items()):
        mime = (
            "application/json" if fmt == "json"
            else "text/csv" if fmt == "csv"
            else "text/markdown"
        )
        col.download_button(
            f"⬇ Download {fmt.upper()}",
            data=path.read_bytes(),
            file_name=path.name,
            mime=mime,
            key=f"lg_dl_{fmt}",
        )
    # Generated standalone Python file
    if results.code_path is not None:
        cols[-1].download_button(
            "⬇ Standalone .py",
            data=results.code_path.read_bytes(),
            file_name=results.code_path.name,
            mime="text/x-python",
            key="lg_dl_code",
            help="Self-contained AISystemLogger module the client drops into their codebase.",
        )
