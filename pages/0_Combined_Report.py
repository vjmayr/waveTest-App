"""
pages/0_Combined_Report.py — Run all 5 assessments and emit one PDF
=======================================================================

Orchestrates DataQuality + Bias + Explainability + Logging + Monitoring,
combines the resulting envelopes via :func:`wavetest_report.ReportEnvelope.combined`,
and renders a single branded PDF for the customer presentation.

PDF rendering uses the reportlab fallback (zero system deps); the PDF
also writes alongside an HTML version and the combined JSON envelope.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from wavetest_app.adapters.dataquality import make_dataquality_assessment
from wavetest_app.adapters.fairness    import make_fairness_assessment
from wavetest_app.adapters.explain     import make_explain_assessment
from wavetest_app.adapters.logging     import make_logging_assessment
from wavetest_app.adapters.monitoring  import make_monitoring_assessment
from wavetest_app.config import project_artifacts_dir
from wavetest_app.ui import page_header, project_picker, risk_pill, show_recommendations

st.set_page_config(
    page_title="Combined Report · waveTest",
    page_icon="🧾",
    layout="wide",
)

page_header(
    "🧾 Combined Compliance Report",
    "All five assessments → one branded PDF for the customer presentation",
    articles=["10", "12", "13", "15", "61", "72"],
)

project = project_picker()
if project is None:
    st.stop()

st.markdown(
    f"### Project: `{project.project_id}` — "
    f"{project.client.company_name} / {project.project_name}"
)

# ---------------------------------------------------------------------------
# Configure (collapsed by default — sensible demo defaults work out-of-box)
# ---------------------------------------------------------------------------
with st.expander("⚙️ Demo-data settings (advanced)", expanded=False):
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Data Quality**")
        dq_quality = st.selectbox(
            "Quality level", ["clean", "moderate", "poor"], index=1,
            key="cb_dq_q",
        )
        dq_n = st.number_input("Samples", 500, 20_000, 3000, 500, key="cb_dq_n")

        st.markdown("**Bias**")
        bias_level = st.selectbox(
            "Bias level", ["none", "low", "moderate", "high"], index=2,
            key="cb_bias_l",
        )
        bias_n = st.number_input("Samples", 500, 20_000, 2000, 500, key="cb_bias_n")
        priv_text = st.text_area(
            "Privileged groups (JSON)",
            value=(
                '{"geschlecht":"M","alter_gruppe":"<30",'
                '"nationalitaet":"DE","behinderung":false}'
            ),
            height=80, key="cb_priv",
        )

    with c2:
        st.markdown("**Explainability**")
        exp_n_demo = st.number_input(
            "Demo samples", 200, 5000, 800, 100, key="cb_exp_n",
        )
        exp_n_features = st.number_input(
            "Demo features", 5, 30, 8, 1, key="cb_exp_f",
        )
        exp_n_explanations = st.number_input(
            "Explanation samples", 10, 200, 30, 5, key="cb_exp_e",
        )

        st.markdown("**Monitoring**")
        mon_drift = st.selectbox(
            "Drift level", ["none", "moderate", "high"], index=1, key="cb_mon_d",
        )
        mon_n = st.number_input("Samples", 200, 5000, 800, 100, key="cb_mon_n")

    st.markdown("**Logging — current-state assumptions**")
    c3, c4 = st.columns(2)
    with c3:
        lg_has = st.checkbox("Has any logging today", key="cb_lg_h")
        lg_in  = st.checkbox("Logs inputs",  key="cb_lg_i")
        lg_out = st.checkbox("Logs outputs", value=True, key="cb_lg_o")
        lg_ts  = st.checkbox("Logs timestamps", value=True, key="cb_lg_t")
    with c4:
        lg_struct = st.checkbox("Structured (JSON)",   key="cb_lg_s")
        lg_personal = st.checkbox(
            "Processes personal data", value=True, key="cb_lg_p",
        )
        lg_high_risk = st.checkbox(
            "High-risk classification", value=True, key="cb_lg_r",
        )
        lg_retention = st.number_input(
            "Retention days", 0, 3650, 90, 30, key="cb_lg_ret",
        )

# ---------------------------------------------------------------------------
# Module toggles
# ---------------------------------------------------------------------------
st.markdown("**Modules to include in the combined report:**")
mc1, mc2, mc3, mc4, mc5 = st.columns(5)
inc_dq    = mc1.checkbox("📊 Data Quality",  value=True, key="cb_inc_dq")
inc_bias  = mc2.checkbox("⚖️ Bias",          value=True, key="cb_inc_bias")
inc_exp   = mc3.checkbox("🔍 Explain",       value=True, key="cb_inc_exp")
inc_lg    = mc4.checkbox("📝 Logging",       value=True, key="cb_inc_lg")
inc_mon   = mc5.checkbox("📈 Monitoring",    value=True, key="cb_inc_mon")

# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------
if st.button("▶ Run all and generate combined PDF", type="primary", key="cb_run"):
    selected = sum([inc_dq, inc_bias, inc_exp, inc_lg, inc_mon])
    if selected == 0:
        st.error("Select at least one module to include.")
        st.stop()

    progress = st.progress(0.0, text="Initialising…")
    envelopes = []
    panel_status = {}
    step_box = [0]

    def _bump(label: str) -> None:
        step_box[0] += 1
        progress.progress(step_box[0] / (selected + 1), text=label)

    # --- 1. Data Quality
    if inc_dq:
        _bump("Running Data Quality…")
        from wavetest_dataquality import generate_demo_data
        from wavetest_report import ReportEnvelope
        a = make_dataquality_assessment(
            project.project_id,
            target_population={"gender": {"M": 0.49, "F": 0.51}},
        )
        df = generate_demo_data(n_samples=int(dq_n), quality_level=dq_quality)
        r = a.run(df, verbose=False)
        envelopes.append(ReportEnvelope.from_dataquality(a, r))
        panel_status["📊 Data Quality"] = (
            r.metrics.quality_classification,
            "ok" if r.article_10_compliant else "warning",
        )

    # --- 2. Bias
    if inc_bias:
        _bump("Running Bias…")
        from wavetest_fairness import generate_demo_data as bias_demo
        from wavetest_report import ReportEnvelope
        try:
            priv = json.loads(priv_text)
        except json.JSONDecodeError as exc:
            st.error(f"Privileged-groups JSON is invalid: {exc}")
            st.stop()
        a = make_fairness_assessment(project.project_id, privileged_groups=priv)
        y_true, y_pred, sf, _ = bias_demo(
            n_samples=int(bias_n), bias_level=bias_level,
        )
        r = a.run(y_true, y_pred, sf, verbose=False)
        envelopes.append(ReportEnvelope.from_fairness(a, r))
        risk_v = a.overall_risk.value
        panel_status["⚖️ Bias"] = (
            risk_v,
            "ok" if risk_v in ("NIEDRIG", "LOW") else "critical",
        )

    # --- 3. Explainability
    if inc_exp:
        _bump("Running Explainability (training demo model + SHAP)…")
        from wavetest_explain.core.assessment import AssessmentConfig
        from wavetest_explain.data.demo import generate_demo_model
        from wavetest_report import ReportEnvelope
        cfg = AssessmentConfig(
            n_explanation_samples=int(exp_n_explanations),
        )
        a = make_explain_assessment(project.project_id, config=cfg)
        bundle = generate_demo_model(
            n_samples=int(exp_n_demo), n_features=int(exp_n_features),
        )
        r = a.run(
            bundle.model, bundle.X_test, bundle.y_test,
            bundle.feature_names, bundle.X_train, verbose=False,
        )
        envelopes.append(ReportEnvelope.from_explainability(a, r))
        panel_status["🔍 Explain"] = (
            f"{r.accuracy:.1%}",
            "ok" if r.accuracy >= 0.85 else "warning",
        )

    # --- 4. Logging
    if inc_lg:
        _bump("Running Logging assessment…")
        from wavetest_logging import CurrentLoggingState, SystemProfile
        from wavetest_report import ReportEnvelope
        a = make_logging_assessment(
            project.project_id,
            current_logging=CurrentLoggingState(
                has_logging=lg_has,
                logs_inputs=lg_in,
                logs_outputs=lg_out,
                logs_timestamps=lg_ts,
                structured_format=lg_struct,
                retention_period_days=int(lg_retention),
            ),
            system_profile=SystemProfile(
                contains_personal_data=lg_personal,
                high_risk_classification=lg_high_risk,
            ),
        )
        r = a.run(verbose=False)
        envelopes.append(ReportEnvelope.from_logging(a, r))
        panel_status["📝 Logging"] = (
            f"{r.summary['compliance_percent']}%",
            "ok" if r.article_12_compliant else "warning",
        )

    # --- 5. Monitoring
    if inc_mon:
        _bump("Running Monitoring…")
        from wavetest_monitoring import generate_demo_monitoring_data
        from wavetest_report import ReportEnvelope
        a = make_monitoring_assessment(project.project_id)
        df = generate_demo_monitoring_data(
            n_samples=int(mon_n), drift_level=mon_drift,
        )
        r = a.run(df, verbose=False)
        envelopes.append(ReportEnvelope.from_monitoring(a, r))
        compliant = a.is_article_15_compliant(r)
        panel_status["📈 Monitoring"] = (
            f"{r.overall_metrics.accuracy:.1%}",
            "ok" if compliant else "critical",
        )

    # --- Combine + render
    progress.progress((selected) / (selected + 1), text="Combining envelopes + rendering PDF…")
    from wavetest_report import ReportEnvelope, HTMLRenderer, JSONRenderer, PDFRenderer
    combined = ReportEnvelope.combined(*envelopes)

    artifacts = project_artifacts_dir(
        project.client.client_id, project.client.company_name,
        project.project_id, project.project_name,
    )
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_client = project.client.company_name.replace(" ", "_")
    base_name = f"combined_report_{safe_client}_{project.project_id}_{ts}"

    pdf_path  = artifacts / "reports" / f"{base_name}.pdf"
    html_path = artifacts / "reports" / f"{base_name}.html"
    json_path = artifacts / "reports" / f"{base_name}.json"

    # JSON
    JSONRenderer().render(combined, output_path=json_path)
    # HTML (will render envelope sections that have templates; the rest emit
    # comments — fine as a preview)
    HTMLRenderer(language=project.client.languages[0] if project.client.languages else "de") \
        .render(combined, output_path=html_path)
    # PDF (reportlab fallback covers all five module types)
    PDFRenderer(engine="reportlab").render(combined, output_path=pdf_path)

    progress.progress(1.0, text="Done.")
    st.session_state["cb_combined"]      = combined
    st.session_state["cb_panel_status"]  = panel_status
    st.session_state["cb_pdf_path"]      = pdf_path
    st.session_state["cb_html_path"]     = html_path
    st.session_state["cb_json_path"]     = json_path

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
if "cb_combined" in st.session_state:
    combined      = st.session_state["cb_combined"]
    panel_status  = st.session_state["cb_panel_status"]
    pdf_path      = st.session_state["cb_pdf_path"]
    html_path     = st.session_state["cb_html_path"]
    json_path     = st.session_state["cb_json_path"]

    st.divider()
    st.subheader("Combined report — overview")

    # Per-module status pills
    pills = ""
    for label, (value, status) in panel_status.items():
        pills += risk_pill(label, value, status)
    st.markdown(pills, unsafe_allow_html=True)

    # Combined summary
    st.markdown("#### Executive summary")
    st.markdown(
        f"**Overall status:** {combined.summary.overall_status}  \n"
        f"**Modules included:** {len(panel_status)} of 5"
    )

    if combined.summary.key_findings:
        with st.expander(
            f"Key findings ({len(combined.summary.key_findings)})", expanded=False,
        ):
            for f in combined.summary.key_findings:
                st.markdown(f"- {f}")

    # Recommendations
    st.markdown("#### Recommendations")
    show_recommendations(combined.summary.recommendations)

    # Downloads
    st.markdown("#### Downloads")
    cols = st.columns(3)
    cols[0].download_button(
        "⬇ Combined PDF",
        data=pdf_path.read_bytes(),
        file_name=pdf_path.name,
        mime="application/pdf",
        type="primary",
        key="cb_dl_pdf",
        help="Branded single-document report covering every selected module.",
    )
    cols[1].download_button(
        "⬇ HTML preview",
        data=html_path.read_bytes(),
        file_name=html_path.name,
        mime="text/html",
        key="cb_dl_html",
    )
    cols[2].download_button(
        "⬇ Combined JSON",
        data=json_path.read_bytes(),
        file_name=json_path.name,
        mime="application/json",
        key="cb_dl_json",
    )

    st.caption(
        f"Saved to `{pdf_path.relative_to(Path.cwd()) if pdf_path.is_relative_to(Path.cwd()) else pdf_path}`"
    )
