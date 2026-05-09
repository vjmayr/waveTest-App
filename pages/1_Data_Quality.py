"""
pages/1_Data_Quality.py
==========================

Article 10 + GDPR Art. 9 data-quality assessment for one project.
Wraps :mod:`wavetest_dataquality` end-to-end:

    pick project → tune parameters → run → dashboard + recommendations + exports
"""

from __future__ import annotations

import time

import streamlit as st
from wavetest_dataquality import (
    DataQualityVisualizer,
    QualityThresholds,
    generate_demo_data,
)

from wavetest_app.adapters.dataquality import make_dataquality_assessment
from wavetest_app.audit import record_run
from wavetest_app.auth import require_login
from wavetest_app.ui import (
    csv_uploader, page_header, project_picker, risk_pill, show_recommendations,
)

st.set_page_config(
    page_title="Data Quality · waveTest",
    page_icon="📊",
    layout="wide",
)

require_login()

page_header(
    "📊 Data Quality Assessment",
    "EU AI Act Article 10 — Data governance · GDPR Article 9 detection",
    articles=["10", "61"],
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
        st.markdown("**Quality thresholds**")
        missing_max = st.number_input(
            "Max missing values per column", 0.0, 1.0, 0.05, 0.01,
            help="Article 10 default: 5%",
        )
        outlier_max = st.number_input(
            "Max outliers per numeric column", 0.0, 1.0, 0.05, 0.01,
        )
        min_sample_size = st.number_input(
            "Minimum sample size", 100, 1_000_000, 1000, 100,
        )

    with c2:
        st.markdown("**Data source**")
        source = st.radio(
            "Choose data",
            ["Demo data (synthetic)", "Upload CSV"],
            horizontal=True,
            help="Demo data is generated with controllable quality issues.",
        )
        uploaded_df = None
        if source == "Demo data (synthetic)":
            quality_level = st.selectbox(
                "Demo quality level",
                ["clean", "moderate", "poor"], index=1,
            )
            n_samples = st.number_input(
                "Sample count", 100, 50_000, 5000, 500,
            )
        else:
            uploaded_df = csv_uploader(
                "Drop a CSV with the dataset to assess",
                key="dq_upload",
                help=(
                    "Any tabular CSV. Columns named in the target population JSON below "
                    "will be tested for representativeness; columns whose names match "
                    "GDPR Art. 9 keywords (race, health, religion, …) are flagged "
                    "automatically."
                ),
            )

    st.markdown("**Target population (chi-square representativeness)**")
    target_pop_text = st.text_area(
        "JSON dict of feature → category proportions",
        value=(
            '{\n'
            '  "gender":      {"M": 0.49, "F": 0.51},\n'
            '  "age_group":   {"18-30": 0.25, "31-45": 0.35, "46-60": 0.28, "60+": 0.12},\n'
            '  "nationality": {"DE": 0.85, "EU": 0.12, "Non-EU": 0.03}\n'
            '}'
        ),
        height=140,
    )

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
run_clicked = st.button("▶ Run assessment", type="primary")

if run_clicked:
    import json as _json
    try:
        target_population = _json.loads(target_pop_text) if target_pop_text.strip() else None
    except _json.JSONDecodeError as exc:
        st.error(f"Target population JSON is invalid: {exc}")
        st.stop()

    thresholds = QualityThresholds(
        missing_values_max=missing_max,
        outlier_max=outlier_max,
        min_sample_size=int(min_sample_size),
    )

    if source != "Demo data (synthetic)" and uploaded_df is None:
        st.error("Upload a CSV first or switch to demo data.")
        st.stop()

    with st.spinner("Running assessment…"):
        if source == "Demo data (synthetic)":
            df = generate_demo_data(
                n_samples=int(n_samples), quality_level=quality_level,
            )
        else:
            df = uploaded_df

        assessment = make_dataquality_assessment(
            project_id=project.project_id,
            target_population=target_population,
            thresholds=thresholds,
        )
        _t0 = time.perf_counter()
        results = assessment.run(df, verbose=False)
        _dt = time.perf_counter() - _t0
        report_paths = assessment.generate_reports(formats=["json", "csv"])

    score = results.metrics.overall_quality_score
    color = "ok" if score >= 90 else "warning" if score >= 75 else "critical"
    record_run(
        project=project, module="data_quality",
        status=results.metrics.quality_classification,
        status_color=color,
        status_detail=(
            f"Quality {score:.1f} · Art.10 "
            f"{'compliant' if results.article_10_compliant else 'gaps'}"
        ),
        duration_seconds=_dt,
    )

    # Cache results in session state so re-renders don't lose them
    st.session_state["dq_df"]            = df
    st.session_state["dq_results"]       = results
    st.session_state["dq_assessment"]    = assessment
    st.session_state["dq_report_paths"]  = report_paths

# ---------------------------------------------------------------------------
# Results (rendered if present in session state)
# ---------------------------------------------------------------------------
if "dq_results" in st.session_state:
    df            = st.session_state["dq_df"]
    results       = st.session_state["dq_results"]
    assessment    = st.session_state["dq_assessment"]
    report_paths  = st.session_state["dq_report_paths"]
    m             = results.metrics

    st.divider()
    st.subheader("Results")

    quality_color = (
        "ok" if m.overall_quality_score >= 90 else
        "warning" if m.overall_quality_score >= 75 else "critical"
    )
    art10_color = "ok" if results.article_10_compliant else "critical"

    pills = (
        risk_pill("Quality Score", f"{m.overall_quality_score:.1f}", quality_color) +
        risk_pill("Classification", m.quality_classification, quality_color) +
        risk_pill("Missing", f"{m.missing_values_pct:.2f}%",
                  "ok" if m.missing_values_pct < 5 else "warning") +
        risk_pill("Duplicates", f"{m.duplicate_rows_pct:.2f}%",
                  "ok" if m.duplicate_rows_pct < 1 else "warning") +
        risk_pill("Article 10",
                  "Compliant" if results.article_10_compliant else "Gaps",
                  art10_color)
    )
    st.markdown(pills, unsafe_allow_html=True)

    # Dashboard
    st.markdown("#### Dashboard")
    viz = DataQualityVisualizer(
        system_name=assessment.system_name,
        min_subgroup_size=assessment.thresholds.min_subgroup_size,
    )
    fig, _ = viz.dashboard(df, m)
    st.pyplot(fig, use_container_width=True)

    # GDPR + representativeness
    cols = st.columns(2)
    with cols[0]:
        st.markdown("#### GDPR Article 9")
        if results.sensitive_columns:
            st.warning(
                f"⚠️ Sensitive columns: " +
                ", ".join(f"`{c}`" for c in results.sensitive_columns.keys())
            )
            st.write({c: kws for c, kws in results.sensitive_columns.items()})
        else:
            st.success("No GDPR Art. 9 sensitive columns detected.")
        if results.direct_identifiers:
            st.warning(
                f"Direct identifiers detected: "
                + ", ".join(f"`{c}`" for c in results.direct_identifiers)
            )

    with cols[1]:
        st.markdown("#### Representativeness")
        if results.representativeness:
            st.dataframe(
                [
                    {
                        "Feature":       r.feature,
                        "χ²":            f"{r.chi2_statistic:.2f}",
                        "p-value":       f"{r.p_value:.4f}",
                        "Result":        r.result,
                        "Sample size":   r.sample_size,
                    }
                    for r in results.representativeness.values()
                ],
                hide_index=True, use_container_width=True,
            )
        else:
            st.info("No target population was supplied.")

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
        )
