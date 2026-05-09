"""
wavetest_app.sustainability — voluntary carbon-footprint estimator
=======================================================================

Not an EU AI Act requirement (those are voluntary under Art. 95 + the
AI Pact / codes of conduct), but customers reporting under CSRD or
ISO/IEC 42001 ask for these numbers anyway. The page collects four
inputs (training kWh, inference kWh per 1k predictions, deployment
region, monthly prediction volume) and produces training + annual
operational carbon estimates.

Numbers in this module are public 2024 grid-intensity baselines. Edit
in-place from the form if a customer has a more accurate figure.
"""

from __future__ import annotations

from typing import Optional

# Public regional electricity carbon intensity, gCO2eq/kWh, ~2024.
# Sources mixed (Ember, IEA, Our World in Data) — figures are coarse on
# purpose so analysts override with the customer's own number.
REGION_INTENSITIES_G_PER_KWH: dict[str, float] = {
    "EU-Average":       250,
    "Germany":          380,
    "France":            60,
    "Sweden":            30,
    "Norway":            25,
    "Poland":           700,
    "Spain":            150,
    "Italy":            260,
    "Netherlands":      280,
    "Austria":           90,
    "Switzerland":       40,
    "UK":               180,
    "USA-Average":      380,
    "China-Average":    580,
    "India-Average":    700,
    "Global-Average":   475,
    "Custom":           250,  # placeholder — user edits the number
}


def carbon_kg(kwh: Optional[float], intensity_g_per_kwh: float) -> Optional[float]:
    """``kWh × g_per_kWh / 1000 = kg``. Returns None if no kWh given."""
    if kwh is None:
        return None
    return round(kwh * intensity_g_per_kwh / 1000.0, 2)


def training_carbon_kg(
    compute_kwh: Optional[float],
    intensity_g_per_kwh: float,
    override_kg: Optional[float] = None,
) -> Optional[float]:
    """Override > computed. Returns None if neither path is filled."""
    if override_kg is not None:
        return round(override_kg, 2)
    return carbon_kg(compute_kwh, intensity_g_per_kwh)


def monthly_inference_kwh(
    inference_kwh_per_1k: Optional[float],
    monthly_predictions: Optional[int],
) -> Optional[float]:
    """``predictions / 1000 × kWh-per-1k``. None if either input is missing."""
    if inference_kwh_per_1k is None or monthly_predictions is None:
        return None
    return round(monthly_predictions / 1000.0 * inference_kwh_per_1k, 4)


def annual_carbon_kg(
    training_kg: Optional[float],
    monthly_inference_kwh_value: Optional[float],
    intensity_g_per_kwh: float,
) -> Optional[float]:
    """Training (one-shot) + 12 × monthly inference carbon."""
    parts: list[float] = []
    if training_kg is not None:
        parts.append(training_kg)
    if monthly_inference_kwh_value is not None:
        parts.append(
            12 * monthly_inference_kwh_value * intensity_g_per_kwh / 1000.0
        )
    if not parts:
        return None
    return round(sum(parts), 2)


def to_markdown(record: dict, *, project_label: str) -> str:
    """Render the carbon estimate as a Markdown deliverable."""
    intensity = record.get("carbon_intensity_g_per_kwh", 250.0)
    train_kg = training_carbon_kg(
        record.get("training_compute_kwh"),
        intensity,
        record.get("training_carbon_override_kg"),
    )
    monthly_kwh = monthly_inference_kwh(
        record.get("inference_kwh_per_1k_predictions"),
        record.get("monthly_predictions"),
    )
    annual_kg = annual_carbon_kg(train_kg, monthly_kwh, intensity)

    def _fmt(v, unit: str = "") -> str:
        if v is None:
            return "_not provided_"
        return f"{v:,.2f} {unit}".rstrip()

    lines = [
        f"# Sustainability Estimate — {project_label}",
        "",
        "_Voluntary disclosure — not a legal requirement under the EU AI Act, but useful for CSRD / ISO 42001 reporting._",
        "",
        f"**Region**: {record.get('deployment_region', 'Custom')}  ",
        f"**Carbon intensity**: {intensity:.0f} gCO₂eq/kWh  ",
        f"**Last updated**: {record['updated_at'].strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Footprint",
        "",
        "| Item | Value |",
        "| --- | --- |",
        f"| Training energy | {_fmt(record.get('training_compute_kwh'), 'kWh')} |",
        f"| Training carbon | {_fmt(train_kg, 'kg CO₂eq')} |",
        f"| Inference energy / 1 000 predictions | "
        f"{_fmt(record.get('inference_kwh_per_1k_predictions'), 'kWh')} |",
        f"| Monthly predictions | "
        f"{record.get('monthly_predictions') or '_not provided_'} |",
        f"| Monthly inference energy | {_fmt(monthly_kwh, 'kWh')} |",
        f"| **Annual operational footprint** | "
        f"**{_fmt(annual_kg, 'kg CO₂eq')}** |",
        "",
        "## Assumptions",
        "",
        record.get("assumptions") or "_None recorded._",
        "",
        "## Data source",
        "",
        record.get("data_source") or "_None recorded._",
        "",
        "## Notes",
        "",
        record.get("notes") or "_None recorded._",
        "",
        "---",
        "",
        f"_Generated by wavetest-app · waveImpact GmbH._",
    ]
    return "\n".join(lines)
