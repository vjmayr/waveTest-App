"""
pages/0_Combined_Report.py — Run all 5 assessments and emit one PDF
=======================================================================

Orchestrates DataQuality + Bias + Explainability + Logging + Monitoring,
combines the resulting envelopes via :func:`wavetest_report.ReportEnvelope.combined`,
and renders a single branded PDF for the customer presentation.

Each module independently accepts either demo data or a client upload
(CSV / pickled model), so the same page works for an internal smoke
test and for the live customer presentation.

PDF rendering uses the reportlab fallback (zero system deps); the PDF
also writes alongside an HTML version and the combined JSON envelope.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import streamlit as st
from pypdf import PdfWriter

from wavetest_app.adapters.dataquality import make_dataquality_assessment
from wavetest_app.adapters.fairness    import make_fairness_assessment
from wavetest_app.adapters.explain     import make_explain_assessment
from wavetest_app.adapters.logging     import make_logging_assessment
from wavetest_app.adapters.monitoring  import make_monitoring_assessment
from wavetest_app.branding import render_cover
from wavetest_app.config import project_artifacts_dir
from wavetest_app.ui import (
    csv_uploader,
    model_uploader,
    page_header,
    project_picker,
    risk_pill,
    show_recommendations,
)

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
# Module toggles — pick first so users only configure what they include
# ---------------------------------------------------------------------------
st.markdown("**Modules to include in the combined report:**")
mc1, mc2, mc3, mc4, mc5 = st.columns(5)
inc_dq    = mc1.checkbox("📊 Data Quality",  value=True, key="cb_inc_dq")
inc_bias  = mc2.checkbox("⚖️ Bias",          value=True, key="cb_inc_bias")
inc_exp   = mc3.checkbox("🔍 Explain",       value=True, key="cb_inc_exp")
inc_lg    = mc4.checkbox("📝 Logging",       value=True, key="cb_inc_lg")
inc_mon   = mc5.checkbox("📈 Monitoring",    value=True, key="cb_inc_mon")

# ---------------------------------------------------------------------------
# Per-module configuration (demo data or upload, plus assessment knobs)
# ---------------------------------------------------------------------------
with st.expander("⚙️ Per-module configuration", expanded=True):
    c1, c2 = st.columns(2)

    # --- Data Quality
    with c1:
        st.markdown("**📊 Data Quality**")
        dq_src = st.radio(
            "Data source",
            ["Demo data (synthetic)", "Upload CSV"],
            horizontal=True, key="cb_dq_src",
            disabled=not inc_dq,
        )
        dq_upload = None
        if dq_src == "Demo data (synthetic)":
            dq_quality = st.selectbox(
                "Quality level", ["clean", "moderate", "poor"], index=1,
                key="cb_dq_q", disabled=not inc_dq,
            )
            dq_n = st.number_input(
                "Samples", 500, 20_000, 3000, 500,
                key="cb_dq_n", disabled=not inc_dq,
            )
        else:
            dq_upload = csv_uploader(
                "Drop a CSV with the dataset to assess",
                key="cb_dq_upload",
                help=(
                    "Any tabular CSV. Columns named in the target population "
                    "JSON below will be tested for representativeness; columns "
                    "whose names match GDPR Art. 9 keywords are flagged."
                ),
            )

        st.divider()

        # --- Bias
        st.markdown("**⚖️ Bias**")
        bias_src = st.radio(
            "Data source",
            ["Demo data (synthetic)", "Upload CSV"],
            horizontal=True, key="cb_bias_src",
            disabled=not inc_bias,
        )
        bias_upload = None
        if bias_src == "Demo data (synthetic)":
            bias_level = st.selectbox(
                "Bias level", ["none", "low", "moderate", "high"], index=2,
                key="cb_bias_l", disabled=not inc_bias,
            )
            bias_n = st.number_input(
                "Samples", 500, 20_000, 2000, 500,
                key="cb_bias_n", disabled=not inc_bias,
            )
        else:
            bias_upload = csv_uploader(
                "Drop a CSV with predictions",
                key="cb_bias_upload",
                required_columns=["y_true", "y_pred"],
                help=(
                    "Required columns: `y_true`, `y_pred`. Plus one column "
                    "for each key in the privileged-groups JSON below."
                ),
            )
        priv_text = st.text_area(
            "Privileged groups (JSON)",
            value=(
                '{"geschlecht":"M","alter_gruppe":"<30",'
                '"nationalitaet":"DE","behinderung":false}'
            ),
            height=80, key="cb_priv", disabled=not inc_bias,
        )

    # --- Explainability + Monitoring
    with c2:
        st.markdown("**🔍 Explainability**")
        exp_src = st.radio(
            "Source",
            ["Demo model (synthetic)", "Upload client model"],
            horizontal=True, key="cb_exp_src",
            disabled=not inc_exp,
        )
        exp_model = None
        exp_test_df = None
        exp_train_df = None
        exp_target_col = "target"
        if exp_src == "Demo model (synthetic)":
            exp_n_demo = st.number_input(
                "Demo samples", 200, 5000, 800, 100,
                key="cb_exp_n", disabled=not inc_exp,
            )
            exp_n_features = st.number_input(
                "Demo features", 5, 30, 8, 1,
                key="cb_exp_f", disabled=not inc_exp,
            )
        else:
            exp_model = model_uploader(
                "Model file (.pkl / .joblib)",
                key="cb_exp_model",
                required_methods=["predict", "predict_proba"],
            )
            exp_target_col = st.text_input(
                "Target column name in the test CSV",
                value="target", key="cb_exp_target",
                disabled=not inc_exp,
            )
            exp_test_df = csv_uploader(
                "Test CSV (features + target column)",
                key="cb_exp_test_csv",
                help="One row per test sample. Feature columns will be passed "
                     "to the model in the order they appear in the CSV.",
            )
            exp_train_df = csv_uploader(
                "Training CSV (optional — improves SHAP background sampling)",
                key="cb_exp_train_csv",
                help="Same column layout as the test CSV. If omitted, SHAP "
                     "uses the test data as background.",
            )
        exp_n_explanations = st.number_input(
            "Explanation samples", 10, 200, 30, 5,
            key="cb_exp_e", disabled=not inc_exp,
        )

        st.divider()

        # --- Monitoring
        st.markdown("**📈 Monitoring**")
        mon_src = st.radio(
            "Data source",
            ["Demo data (synthetic)", "Upload CSV"],
            horizontal=True, key="cb_mon_src",
            disabled=not inc_mon,
        )
        mon_upload = None
        if mon_src == "Demo data (synthetic)":
            mon_drift = st.selectbox(
                "Drift level", ["none", "moderate", "high"], index=1,
                key="cb_mon_d", disabled=not inc_mon,
            )
            mon_n = st.number_input(
                "Samples", 200, 5000, 800, 100,
                key="cb_mon_n", disabled=not inc_mon,
            )
        else:
            mon_upload = csv_uploader(
                "Drop a CSV with monitoring data",
                key="cb_mon_upload",
                required_columns=["timestamp", "y_true", "y_pred"],
                parse_dates=["timestamp"],
                help=(
                    "Required columns: `timestamp`, `y_true`, `y_pred`. "
                    "Optional: `confidence`."
                ),
            )

    # --- Logging — interview-only, no uploads
    st.divider()
    st.markdown("**📝 Logging — current-state assumptions**")
    c3, c4 = st.columns(2)
    with c3:
        lg_has = st.checkbox(
            "Has any logging today", key="cb_lg_h", disabled=not inc_lg,
        )
        lg_in  = st.checkbox(
            "Logs inputs",  key="cb_lg_i", disabled=not inc_lg,
        )
        lg_out = st.checkbox(
            "Logs outputs", value=True, key="cb_lg_o", disabled=not inc_lg,
        )
        lg_ts  = st.checkbox(
            "Logs timestamps", value=True, key="cb_lg_t", disabled=not inc_lg,
        )
    with c4:
        lg_struct = st.checkbox(
            "Structured (JSON)", key="cb_lg_s", disabled=not inc_lg,
        )
        lg_personal = st.checkbox(
            "Processes personal data", value=True,
            key="cb_lg_p", disabled=not inc_lg,
        )
        lg_high_risk = st.checkbox(
            "High-risk classification", value=True,
            key="cb_lg_r", disabled=not inc_lg,
        )
        lg_retention = st.number_input(
            "Retention days", 0, 3650, 90, 30,
            key="cb_lg_ret", disabled=not inc_lg,
        )

# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------
if st.button("▶ Run all and generate combined PDF", type="primary", key="cb_run"):
    selected = sum([inc_dq, inc_bias, inc_exp, inc_lg, inc_mon])
    if selected == 0:
        st.error("Select at least one module to include.")
        st.stop()

    # Validate uploads up front so we don't half-run the pipeline
    if inc_dq and dq_src != "Demo data (synthetic)" and dq_upload is None:
        st.error("Data Quality: upload a CSV or switch to demo data.")
        st.stop()
    if inc_bias and bias_src != "Demo data (synthetic)" and bias_upload is None:
        st.error("Bias: upload a CSV or switch to demo data.")
        st.stop()
    if inc_exp and exp_src != "Demo model (synthetic)":
        if exp_model is None:
            st.error("Explainability: upload a model file or switch to the demo model.")
            st.stop()
        if exp_test_df is None:
            st.error("Explainability: upload a test CSV or switch to the demo model.")
            st.stop()
        if not exp_target_col or exp_target_col not in exp_test_df.columns:
            st.error(
                f"Explainability: target column `{exp_target_col}` not found "
                f"in test CSV. Available: {list(exp_test_df.columns)}"
            )
            st.stop()
    if inc_mon and mon_src != "Demo data (synthetic)" and mon_upload is None:
        st.error("Monitoring: upload a CSV or switch to demo data.")
        st.stop()

    # Bias privileged-groups JSON parses + validates against upload columns
    privileged_groups = None
    if inc_bias:
        try:
            privileged_groups = json.loads(priv_text)
        except json.JSONDecodeError as exc:
            st.error(f"Privileged-groups JSON is invalid: {exc}")
            st.stop()
        if bias_src != "Demo data (synthetic)":
            missing = [c for c in privileged_groups if c not in bias_upload.columns]
            if missing:
                st.error(
                    f"Bias: privileged-groups columns missing from CSV: {missing}\n\n"
                    f"CSV columns: {list(bias_upload.columns)}"
                )
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
        if dq_src == "Demo data (synthetic)":
            df = generate_demo_data(n_samples=int(dq_n), quality_level=dq_quality)
        else:
            df = dq_upload
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
        a = make_fairness_assessment(
            project.project_id, privileged_groups=privileged_groups,
        )
        if bias_src == "Demo data (synthetic)":
            y_true, y_pred, sf, _ = bias_demo(
                n_samples=int(bias_n), bias_level=bias_level,
            )
        else:
            y_true = bias_upload["y_true"]
            y_pred = bias_upload["y_pred"]
            sf = bias_upload[list(privileged_groups.keys())]
        r = a.run(y_true, y_pred, sf, verbose=False)
        envelopes.append(ReportEnvelope.from_fairness(a, r))
        risk_v = a.overall_risk.value
        panel_status["⚖️ Bias"] = (
            risk_v,
            "ok" if risk_v in ("NIEDRIG", "LOW") else "critical",
        )

    # --- 3. Explainability
    if inc_exp:
        from wavetest_explain.core.assessment import AssessmentConfig
        from wavetest_explain.data.demo import generate_demo_model
        from wavetest_report import ReportEnvelope
        cfg = AssessmentConfig(
            n_explanation_samples=int(exp_n_explanations),
        )
        a = make_explain_assessment(project.project_id, config=cfg)

        if exp_src == "Demo model (synthetic)":
            _bump("Running Explainability (training demo model + SHAP)…")
            bundle = generate_demo_model(
                n_samples=int(exp_n_demo), n_features=int(exp_n_features),
            )
            model = bundle.model
            X_test = bundle.X_test
            y_test = bundle.y_test
            feature_names = bundle.feature_names
            X_train = bundle.X_train
        else:
            _bump("Running Explainability (uploaded model + SHAP)…")
            feature_names = [
                c for c in exp_test_df.columns if c != exp_target_col
            ]
            X_test = exp_test_df[feature_names].to_numpy()
            y_test = exp_test_df[exp_target_col].to_numpy()
            model = exp_model
            if exp_train_df is not None:
                train_missing = [
                    c for c in feature_names + [exp_target_col]
                    if c not in exp_train_df.columns
                ]
                if train_missing:
                    st.error(
                        f"Explainability: training CSV is missing columns: {train_missing}"
                    )
                    st.stop()
                X_train = exp_train_df[feature_names].to_numpy()
            else:
                X_train = None

        X_test = np.asarray(X_test)
        y_test = np.asarray(y_test)
        if X_train is not None:
            X_train = np.asarray(X_train)

        r = a.run(
            model, X_test, y_test,
            feature_names, X_train, verbose=False,
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
        if mon_src == "Demo data (synthetic)":
            df = generate_demo_monitoring_data(
                n_samples=int(mon_n), drift_level=mon_drift,
            )
        else:
            df = mon_upload
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

    # PDF — render the report body first, then prepend a branded cover page.
    # The toolchain's PDFRenderer is left untouched (working-directory rule);
    # we just merge two PDFs together with pypdf.
    body_pdf  = pdf_path.with_name(f"{base_name}__body.pdf")
    cover_pdf = pdf_path.with_name(f"{base_name}__cover.pdf")
    PDFRenderer(engine="reportlab").render(combined, output_path=body_pdf)
    render_cover(
        cover_pdf,
        project_id=project.project_id,
        project_name=project.project_name,
        client_name=project.client.company_name,
        modules_included=list(panel_status.keys()),
    )
    writer = PdfWriter()
    writer.append(str(cover_pdf))
    writer.append(str(body_pdf))
    with pdf_path.open("wb") as f:
        writer.write(f)
    writer.close()
    body_pdf.unlink(missing_ok=True)
    cover_pdf.unlink(missing_ok=True)

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
