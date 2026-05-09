"""Tests for the Article 15(5) cybersecurity plan."""

from sqlalchemy import select

from wavetest_app.cybersecurity import (
    CHECKPOINTS,
    compute_compliance_percent,
    status_color,
)
from wavetest_app.db.models import Client, CybersecurityPlan, Project
from wavetest_app.db.session import get_session


def test_full_yes_is_100_percent():
    answers = {f: "yes" for f, _, _, _ in CHECKPOINTS}
    assert compute_compliance_percent(answers) == 100.0


def test_full_no_is_zero():
    answers = {f: "no" for f, _, _, _ in CHECKPOINTS}
    assert compute_compliance_percent(answers) == 0.0


def test_eight_checkpoints():
    """Exactly 8 checkpoints — change deliberately, schema is per-field."""
    assert len(CHECKPOINTS) == 8


def test_status_color_thresholds():
    assert status_color(100) == "ok"
    assert status_color(99.9) == "warning"
    assert status_color(50.0) == "warning"
    assert status_color(49.9) == "critical"


def test_plan_roundtrip(in_memory_db):
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(Project(project_id="PRJ0001", client_id="CLI0001",
                       project_name="X", project_type="Y"))
        db.add(CybersecurityPlan(
            plan_id="CSP0001",
            project_id="PRJ0001",
            threat_model_documented="yes",
            sbom_maintained="partial",
            pentest_performed="no",
            data_poisoning_controls="partial",
            adversarial_input_controls="no",
            privacy_attack_controls="no",
            access_controls_documented="yes",
            incident_response_playbook="partial",
            threat_model_notes="STRIDE doc owned by SecOps",
            mitigation_plan="Schedule pentest Q3, add ART evaluation",
            compliance_percent=37.5,
        ))

    with get_session() as db:
        plan = db.scalars(select(CybersecurityPlan)).first()
        assert plan is not None
        assert plan.threat_model_documented == "yes"
        assert plan.privacy_attack_controls == "no"
        assert plan.compliance_percent == 37.5


def test_one_plan_per_project(in_memory_db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(Project(project_id="PRJ0001", client_id="CLI0001",
                       project_name="X", project_type="Y"))
        db.add(CybersecurityPlan(plan_id="CSP0001", project_id="PRJ0001"))

    with pytest.raises(IntegrityError):
        with get_session() as db:
            db.add(CybersecurityPlan(plan_id="CSP0002", project_id="PRJ0001"))


def test_project_delete_cascades(in_memory_db):
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(Project(project_id="PRJ0001", client_id="CLI0001",
                       project_name="X", project_type="Y"))
        db.add(CybersecurityPlan(plan_id="CSP0001", project_id="PRJ0001"))

    with get_session() as db:
        db.delete(db.get(Project, "PRJ0001"))

    with get_session() as db:
        remaining = db.scalars(select(CybersecurityPlan)).all()
        assert remaining == []
