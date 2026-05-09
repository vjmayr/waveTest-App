"""Tests for the voluntary sustainability estimator."""

from sqlalchemy import select

from wavetest_app.db.models import Client, Project, SustainabilityRecord
from wavetest_app.db.session import get_session
from wavetest_app.sustainability import (
    REGION_INTENSITIES_G_PER_KWH,
    annual_carbon_kg,
    carbon_kg,
    intensity_for,
    monthly_inference_kwh,
    region_options,
    training_carbon_kg,
)


# ---------------------------------------------------------------------------
# Pure-function helpers
# ---------------------------------------------------------------------------
class TestCarbonHelpers:
    def test_carbon_kg_basic(self):
        # 1000 kWh × 250 g/kWh / 1000 = 250 kg
        assert carbon_kg(1000, 250) == 250.0

    def test_carbon_kg_none_in_none_out(self):
        assert carbon_kg(None, 250) is None

    def test_training_override_wins(self):
        # override given → ignore the kWh × intensity calc
        assert training_carbon_kg(1000, 250, override_kg=42.5) == 42.5

    def test_training_falls_through_to_computed(self):
        assert training_carbon_kg(1000, 250) == 250.0

    def test_training_with_neither_returns_none(self):
        assert training_carbon_kg(None, 250) is None

    def test_monthly_inference_kwh(self):
        # 100_000 predictions × 0.5 kWh per 1k = 50 kWh
        assert monthly_inference_kwh(0.5, 100_000) == 50.0

    def test_annual_combines_training_and_inference(self):
        # Training 100 kg + 12 months × 50 kWh × 250 g/kWh / 1000 = 100 + 150 = 250
        assert annual_carbon_kg(100.0, 50.0, 250.0) == 250.0

    def test_annual_with_no_inputs_returns_none(self):
        assert annual_carbon_kg(None, None, 250.0) is None


# ---------------------------------------------------------------------------
# Region intensity table
# ---------------------------------------------------------------------------
def test_region_table_has_eu_average():
    assert "EU-Average" in REGION_INTENSITIES_G_PER_KWH
    assert REGION_INTENSITIES_G_PER_KWH["EU-Average"] > 0


def test_region_table_intensities_in_plausible_range():
    """Sanity-check: every value within 10–1500 g/kWh."""
    for region, value in REGION_INTENSITIES_G_PER_KWH.items():
        assert 10 <= value <= 1500, f"{region}={value} is implausible"


# ---------------------------------------------------------------------------
# codecarbon integration
# ---------------------------------------------------------------------------
class TestCodecarbonIntegration:
    def test_iso3_lookup_returns_published_value(self):
        # Germany's intensity in CodeCarbon's table — the *exact* value may
        # drift between releases, but it should be in the 200–500 ballpark
        # for a fossil-heavy grid.
        intensity = intensity_for("DEU")
        assert intensity is not None
        assert 200 <= intensity <= 500

    def test_unknown_iso_returns_none(self):
        assert intensity_for("XXX") is None

    def test_curated_aggregate_resolves(self):
        # EU-Average is curated, not from codecarbon
        assert intensity_for("EU-Average") == 250.0

    def test_region_options_includes_213_plus_curated(self):
        opts = region_options()
        # ≥ ~210 countries from CodeCarbon + 2 aggregates + 1 Custom slot
        assert len(opts) >= 200
        # Display labels are unique
        labels = [label for label, _ in opts]
        assert len(labels) == len(set(labels)), "duplicate region labels"
        # Aggregates appear at the top
        assert "European Union (avg)" in labels[:5]
        # Custom is the last entry
        assert opts[-1] == ("Custom (edit intensity below)", "Custom")


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def test_record_roundtrip(in_memory_db):
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(Project(project_id="PRJ0001", client_id="CLI0001",
                       project_name="X", project_type="Y"))
        db.add(SustainabilityRecord(
            record_id="SUS0001",
            project_id="PRJ0001",
            training_compute_kwh=1500.0,
            inference_kwh_per_1k_predictions=0.05,
            monthly_predictions=2_000_000,
            deployment_region="Germany",
            carbon_intensity_g_per_kwh=380.0,
            assumptions="A100 GPUs, batch 64",
        ))

    with get_session() as db:
        rec = db.scalars(select(SustainabilityRecord)).first()
        assert rec is not None
        assert rec.deployment_region == "Germany"
        assert rec.training_compute_kwh == 1500.0
        assert rec.monthly_predictions == 2_000_000


def test_one_record_per_project(in_memory_db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(Project(project_id="PRJ0001", client_id="CLI0001",
                       project_name="X", project_type="Y"))
        db.add(SustainabilityRecord(record_id="SUS0001", project_id="PRJ0001"))

    with pytest.raises(IntegrityError):
        with get_session() as db:
            db.add(SustainabilityRecord(record_id="SUS0002", project_id="PRJ0001"))


def test_project_delete_cascades(in_memory_db):
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(Project(project_id="PRJ0001", client_id="CLI0001",
                       project_name="X", project_type="Y"))
        db.add(SustainabilityRecord(record_id="SUS0001", project_id="PRJ0001"))

    with get_session() as db:
        db.delete(db.get(Project, "PRJ0001"))

    with get_session() as db:
        remaining = db.scalars(select(SustainabilityRecord)).all()
        assert remaining == []
