"""
wavetest_app.sustainability — voluntary carbon-footprint estimator
=======================================================================

Backed by `CodeCarbon <https://codecarbon.io>`_'s ``global_energy_mix.json``
(213 countries, kept up to date by the upstream project) for region
carbon-intensity values. The page collects four inputs (training kWh,
inference kWh per 1k predictions, deployment region, monthly prediction
volume) and produces training + annual operational carbon estimates.

For *live* training-time tracking the analyst should run CodeCarbon's
``EmissionsTracker`` inside the customer's training script — that's the
authoritative path. This module accepts the resulting kWh / kg numbers
back as form inputs and assembles the deliverable.

Not an EU AI Act requirement (voluntary under Art. 95 + the AI Pact /
codes of conduct), but useful for CSRD / ISO 42001 reporting.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional


# A small set of curated multi-country aggregates kept on top of the
# CodeCarbon country list. CodeCarbon doesn't ship "EU average" — useful
# when the customer can't pin down a single member state.
_CURATED_AGGREGATES: dict[str, tuple[str, float]] = {
    "EU-Average":     ("European Union (avg)",  250.0),
    "Global-Average": ("Global average",        475.0),
}


@lru_cache(maxsize=1)
def _codecarbon_data() -> dict[str, dict]:
    """Load CodeCarbon's ``global_energy_mix.json`` (cached for the process).

    Falls back to an empty dict if the file moves between codecarbon
    releases — we still keep the curated aggregates above.
    """
    try:
        import codecarbon  # type: ignore
    except ImportError:
        return {}
    data_path = (
        Path(codecarbon.__file__).parent
        / "data" / "private_infra" / "global_energy_mix.json"
    )
    if not data_path.exists():
        return {}
    with data_path.open(encoding="utf-8") as f:
        return json.load(f)


def region_options() -> list[tuple[str, str]]:
    """Return ``[(display_label, intensity_key), ...]`` sorted alphabetically.

    The intensity_key is what we store in the DB column. Aggregates come
    first, then individual countries.
    """
    items: list[tuple[str, str]] = []
    for key, (label, _) in _CURATED_AGGREGATES.items():
        items.append((label, key))
    countries = sorted(
        (
            (entry.get("country_name", iso), iso)
            for iso, entry in _codecarbon_data().items()
            if "carbon_intensity" in entry
        ),
        key=lambda t: t[0],
    )
    items.extend(countries)
    items.append(("Custom (edit intensity below)", "Custom"))
    return items


def intensity_for(region_key: str) -> Optional[float]:
    """Look up gCO₂eq/kWh for an aggregate or ISO3 country code.

    Returns ``None`` if the key is unknown — the page falls back to the
    user-entered intensity in that case.
    """
    if region_key in _CURATED_AGGREGATES:
        return _CURATED_AGGREGATES[region_key][1]
    entry = _codecarbon_data().get(region_key)
    if entry and "carbon_intensity" in entry:
        return float(entry["carbon_intensity"])
    return None


def carbon_kg(kwh: Optional[float], intensity_g_per_kwh: float) -> Optional[float]:
    """``kWh × g/kWh / 1000 = kg``. Returns None if no kWh given."""
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


# Backwards-compat: the old hard-coded dict is still importable so the
# existing tests continue to pass without forcing a wholesale rewrite.
# It now derives from the codecarbon source plus the curated aggregates.
def _legacy_intensity_table() -> dict[str, float]:
    table: dict[str, float] = {
        label: intensity for label, (_, intensity) in _CURATED_AGGREGATES.items()
    }
    # Add a few common Western European labels under their human names —
    # mirrors the previous v0 keys so legacy DB rows resolve.
    name_aliases = {
        "Germany": "DEU", "France": "FRA", "Sweden": "SWE", "Norway": "NOR",
        "Poland": "POL", "Spain": "ESP", "Italy": "ITA",
        "Netherlands": "NLD", "Austria": "AUT", "Switzerland": "CHE",
        "UK": "GBR", "USA-Average": "USA", "China-Average": "CHN",
        "India-Average": "IND",
    }
    for name, iso in name_aliases.items():
        i = intensity_for(iso)
        if i is not None:
            table[name] = i
    table.setdefault("Custom", 250.0)
    return table


REGION_INTENSITIES_G_PER_KWH: dict[str, float] = _legacy_intensity_table()


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
        "_Voluntary disclosure — not a legal requirement under the EU AI "
        "Act, but useful for CSRD / ISO 42001 reporting._",
        "",
        f"**Region**: {record.get('deployment_region', 'Custom')}  ",
        f"**Carbon intensity**: {intensity:.0f} gCO₂eq/kWh "
        "(source: CodeCarbon `global_energy_mix.json`)  ",
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
        "## How to capture training emissions live",
        "",
        "For an authoritative training-time number, run "
        "[CodeCarbon's](https://codecarbon.io) `EmissionsTracker` inside "
        "the customer's training script::",
        "",
        "    from codecarbon import EmissionsTracker",
        "    with EmissionsTracker(project_name='cardio-v2', "
        "country_iso_code='DEU') as tracker:",
        "        train_model(...)",
        "    # tracker writes emissions.csv with kWh + kg CO₂eq",
        "",
        "Then enter the kWh and kg numbers above as the override.",
        "",
        "---",
        "",
        f"_Generated by wavetest-app · waveImpact GmbH._",
    ]
    return "\n".join(lines)
