"""
pages/14_Sustainability.py — voluntary carbon-footprint estimate
====================================================================

Captures training kWh + inference kWh per 1k predictions + monthly
volume + deployment region, derives training and annual operational
carbon. Voluntary; useful for CSRD / ISO 42001 reporting.
"""

from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from wavetest_app._time import utc_now
from wavetest_app.audit import record_run
from wavetest_app.auth import current_username, require_login
from wavetest_app.db.ids import next_id
from wavetest_app.db.models import SustainabilityRecord
from wavetest_app.db.session import get_session
from wavetest_app.sustainability import (
    REGION_INTENSITIES_G_PER_KWH,
    annual_carbon_kg,
    monthly_inference_kwh,
    to_markdown,
    training_carbon_kg,
)
from wavetest_app.ui import page_header, project_picker, risk_pill

st.set_page_config(
    page_title="Sustainability · waveTest",
    page_icon="🌱",
    layout="wide",
)

require_login()

page_header(
    "🌱 Sustainability",
    "Voluntary carbon footprint — useful for CSRD / ISO 42001 reporting",
)

project = project_picker()
if project is None:
    st.stop()

st.markdown(
    f"### Project: `{project.project_id}` — "
    f"{project.client.company_name} / {project.project_name}"
)

# ---------------------------------------------------------------------------
# Load existing record
# ---------------------------------------------------------------------------
with get_session() as db:
    existing = db.scalars(
        select(SustainabilityRecord)
        .where(SustainabilityRecord.project_id == project.project_id)
    ).first()
    if existing:
        record = {
            "record_id":                       existing.record_id,
            "training_compute_kwh":            existing.training_compute_kwh,
            "training_carbon_override_kg":     existing.training_carbon_override_kg,
            "inference_kwh_per_1k_predictions": existing.inference_kwh_per_1k_predictions,
            "monthly_predictions":             existing.monthly_predictions,
            "deployment_region":               existing.deployment_region,
            "carbon_intensity_g_per_kwh":      existing.carbon_intensity_g_per_kwh,
            "assumptions":                     existing.assumptions,
            "data_source":                     existing.data_source,
            "notes":                           existing.notes,
            "created_by":                      existing.created_by,
            "created_at":                      existing.created_at,
            "updated_at":                      existing.updated_at,
        }
    else:
        record = None

# ---------------------------------------------------------------------------
# Summary pills (computed)
# ---------------------------------------------------------------------------
if record is not None:
    intensity = record["carbon_intensity_g_per_kwh"]
    train_kg = training_carbon_kg(
        record["training_compute_kwh"],
        intensity,
        record["training_carbon_override_kg"],
    )
    m_kwh = monthly_inference_kwh(
        record["inference_kwh_per_1k_predictions"],
        record["monthly_predictions"],
    )
    annual_kg = annual_carbon_kg(train_kg, m_kwh, intensity)

    pills = (
        risk_pill(
            "Training",
            f"{train_kg:,.1f} kg" if train_kg is not None else "—",
            "info",
        ) +
        risk_pill(
            "Annual",
            f"{annual_kg:,.0f} kg" if annual_kg is not None else "—",
            "info",
        ) +
        risk_pill(
            "Region",
            record["deployment_region"],
            "info",
        ) +
        risk_pill(
            "Intensity",
            f"{intensity:.0f} g/kWh",
            "info",
        )
    )
    st.markdown(pills, unsafe_allow_html=True)
else:
    st.info(
        "No sustainability record yet. Fill in the form below — every "
        "field is optional, so partial data still produces a partial "
        "footprint estimate. Numbers are picked up live by CSRD / ISO "
        "42001 reports."
    )

# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------
defaults = record or {
    "training_compute_kwh":              None,
    "training_carbon_override_kg":       None,
    "inference_kwh_per_1k_predictions":  None,
    "monthly_predictions":               None,
    "deployment_region":                 "EU-Average",
    "carbon_intensity_g_per_kwh":        250.0,
    "assumptions":                       "",
    "data_source":                       "",
    "notes":                             "",
}

with st.form("sus_form"):
    st.markdown("### Training")
    c1, c2 = st.columns(2)
    with c1:
        training_compute_kwh = st.number_input(
            "Training energy (kWh)",
            min_value=0.0,
            value=float(defaults["training_compute_kwh"] or 0.0),
            step=10.0,
            help="Convert from GPU-hours: kWh ≈ GPU-hours × board-TDP-W / 1000. "
                 "Or pull directly from CodeCarbon / eco2AI logs.",
        )
    with c2:
        training_carbon_override_kg = st.number_input(
            "Direct CO₂eq override (kg, optional)",
            min_value=0.0,
            value=float(defaults["training_carbon_override_kg"] or 0.0),
            step=1.0,
            help="If the client measured training carbon directly with "
                 "CodeCarbon / eco2AI, enter it here. Overrides the "
                 "kWh × intensity calculation.",
        )

    st.markdown("### Inference")
    c3, c4 = st.columns(2)
    with c3:
        inference_kwh_per_1k = st.number_input(
            "Inference energy (kWh per 1 000 predictions)",
            min_value=0.0,
            value=float(defaults["inference_kwh_per_1k_predictions"] or 0.0),
            step=0.001,
            format="%.4f",
            help="Per-prediction energy × 1000. Typical ranges: small "
                 "tabular models 0.0001–0.001 kWh/1k; LLM serving "
                 "0.1–1.0 kWh/1k.",
        )
    with c4:
        monthly_predictions = st.number_input(
            "Monthly predictions (count)",
            min_value=0,
            value=int(defaults["monthly_predictions"] or 0),
            step=1000,
        )

    st.markdown("### Region")
    c5, c6 = st.columns(2)
    with c5:
        regions = list(REGION_INTENSITIES_G_PER_KWH.keys())
        try:
            region_idx = regions.index(defaults["deployment_region"])
        except ValueError:
            region_idx = regions.index("EU-Average")
        deployment_region = st.selectbox(
            "Deployment region",
            regions,
            index=region_idx,
        )
    with c6:
        # Default the intensity to the region's value the FIRST time,
        # but let the user override afterwards.
        intensity_default = (
            defaults["carbon_intensity_g_per_kwh"]
            if record is not None
            else REGION_INTENSITIES_G_PER_KWH[deployment_region]
        )
        carbon_intensity = st.number_input(
            "Carbon intensity (gCO₂eq / kWh)",
            min_value=0.0,
            value=float(intensity_default),
            step=10.0,
            help="Public 2024 baselines pre-filled per region; overwrite "
                 "with the customer's actual figure if they have one.",
        )

    st.markdown("### Notes")
    assumptions = st.text_area(
        "Assumptions",
        value=defaults["assumptions"],
        height=80,
        help="What's been assumed (e.g. PUE, GPU model, batch size, …)",
    )
    data_source = st.text_area(
        "Data source",
        value=defaults["data_source"],
        height=60,
        help="Where do these numbers come from? CodeCarbon log? Cloud "
             "billing? Estimated from architecture?",
    )
    notes = st.text_area("Other notes", value=defaults["notes"], height=60)

    if st.form_submit_button("Save record", type="primary"):
        with get_session() as db:
            target = db.scalars(
                select(SustainabilityRecord)
                .where(SustainabilityRecord.project_id == project.project_id)
            ).first()
            if target is None:
                rid = next_id(db, SustainabilityRecord.record_id, "SUS")
                target = SustainabilityRecord(
                    record_id=rid,
                    project_id=project.project_id,
                    created_by=current_username() or "system",
                )
                db.add(target)
            target.training_compute_kwh = training_compute_kwh or None
            target.training_carbon_override_kg = training_carbon_override_kg or None
            target.inference_kwh_per_1k_predictions = inference_kwh_per_1k or None
            target.monthly_predictions = int(monthly_predictions) or None
            target.deployment_region = deployment_region
            target.carbon_intensity_g_per_kwh = carbon_intensity
            target.assumptions = assumptions.strip()
            target.data_source = data_source.strip()
            target.notes = notes.strip()
            target.updated_at = utc_now()

        # Record the high-level annual total in the audit detail
        train_kg_now = training_carbon_kg(
            training_compute_kwh or None,
            carbon_intensity,
            training_carbon_override_kg or None,
        )
        m_kwh_now = monthly_inference_kwh(
            inference_kwh_per_1k or None,
            int(monthly_predictions) or None,
        )
        annual_kg_now = annual_carbon_kg(train_kg_now, m_kwh_now, carbon_intensity)
        record_run(
            project=project, module="sustainability",
            status=f"{annual_kg_now:,.0f} kg/yr"
            if annual_kg_now is not None else "incomplete",
            status_color="info",
            status_detail=f"region {deployment_region}, "
                          f"intensity {carbon_intensity:.0f} g/kWh",
        )
        st.success("Sustainability record saved.")
        st.rerun()

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
if record is not None:
    st.divider()
    md = to_markdown(
        record,
        project_label=f"{project.client.company_name} / {project.project_name}",
    )
    st.download_button(
        "⬇ Download sustainability estimate (Markdown)",
        data=md,
        file_name=f"sustainability_{project.project_id}.md",
        mime="text/markdown",
    )
