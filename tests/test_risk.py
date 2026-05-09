"""Tests for the Article 9 risk register."""

from sqlalchemy import select

from wavetest_app.db.models import Client, Project, RiskEntry
from wavetest_app.db.session import get_session
from wavetest_app.risk import (
    compute_residual_level,
    compute_risk_level,
    level_color,
)


# ---------------------------------------------------------------------------
# Risk-level lookup
# ---------------------------------------------------------------------------
class TestRiskLevel:
    def test_low_x_rare_is_low(self):
        assert compute_risk_level("LOW", "RARE") == "LOW"

    def test_critical_x_likely_is_critical(self):
        assert compute_risk_level("CRITICAL", "LIKELY") == "CRITICAL"

    def test_high_x_unlikely_is_high(self):
        assert compute_risk_level("HIGH", "UNLIKELY") == "HIGH"

    def test_unknown_input_falls_back_to_medium(self):
        # form-driven UI should never crash on a typo
        assert compute_risk_level("nonsense", "alsoBad") == "MEDIUM"

    def test_residual_returns_none_when_either_axis_missing(self):
        assert compute_residual_level(None, "RARE") is None
        assert compute_residual_level("LOW", None) is None
        assert compute_residual_level(None, None) is None
        assert compute_residual_level("LOW", "RARE") == "LOW"


class TestLevelColor:
    def test_palette_mapping(self):
        assert level_color("LOW") == "ok"
        assert level_color("MEDIUM") == "warning"
        assert level_color("HIGH") == "warning"
        assert level_color("CRITICAL") == "critical"
        assert level_color(None) == "info"
        assert level_color("") == "info"


# ---------------------------------------------------------------------------
# RiskEntry persistence
# ---------------------------------------------------------------------------
def test_risk_entry_roundtrip(in_memory_db):
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME", languages=["en"]))
        db.add(Project(
            project_id="PRJ0001", client_id="CLI0001",
            project_name="Audit", project_type="Bias",
        ))
        db.add(RiskEntry(
            risk_id="RR0001",
            project_id="PRJ0001",
            title="Drift on age feature",
            description="Age distribution shifts under new marketing channel.",
            category="performance",
            severity="HIGH",
            likelihood="LIKELY",
            risk_level="CRITICAL",
            mitigation="Quarterly retraining pipeline",
            mitigation_status="proposed",
            owner="Asha Patel",
            created_by="testuser",
        ))

    with get_session() as db:
        risk = db.get(RiskEntry, "RR0001")
        assert risk is not None
        assert risk.title == "Drift on age feature"
        assert risk.risk_level == "CRITICAL"
        assert risk.project.project_name == "Audit"


def test_project_delete_cascades_to_risks(in_memory_db):
    """Risk register is per-engagement: delete project → risks gone."""
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME", languages=["en"]))
        db.add(Project(
            project_id="PRJ0001", client_id="CLI0001",
            project_name="Audit", project_type="Bias",
        ))
        db.add(RiskEntry(
            risk_id="RR0001", project_id="PRJ0001",
            title="X", severity="LOW", likelihood="RARE", risk_level="LOW",
        ))
        db.add(RiskEntry(
            risk_id="RR0002", project_id="PRJ0001",
            title="Y", severity="HIGH", likelihood="LIKELY", risk_level="CRITICAL",
        ))

    with get_session() as db:
        db.delete(db.get(Project, "PRJ0001"))

    with get_session() as db:
        remaining = db.scalars(select(RiskEntry)).all()
        assert remaining == [], "FK CASCADE should have removed both risks"
