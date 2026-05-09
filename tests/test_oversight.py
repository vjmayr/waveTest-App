"""Tests for the Article 14 human-oversight plan."""

from sqlalchemy import select

from wavetest_app.db.models import Client, OversightPlan, Project
from wavetest_app.db.session import get_session
from wavetest_app.oversight import (
    CHECKPOINTS,
    compute_compliance_percent,
    status_color,
    to_markdown,
)


def test_full_yes_is_100_percent():
    answers = {f: "yes" for f, _, _ in CHECKPOINTS}
    assert compute_compliance_percent(answers) == 100.0


def test_full_no_is_zero():
    answers = {f: "no" for f, _, _ in CHECKPOINTS}
    assert compute_compliance_percent(answers) == 0.0


def test_partial_scoring():
    # 6 checkpoints × 3 max = 18; one yes (3) + rest no (0) = 3 / 18 ≈ 16.7
    answers = {f: "no" for f, _, _ in CHECKPOINTS}
    answers[CHECKPOINTS[0][0]] = "yes"
    pct = compute_compliance_percent(answers)
    assert 16.0 <= pct <= 17.0


def test_status_color_thresholds():
    assert status_color(100) == "ok"
    assert status_color(99.9) == "warning"
    assert status_color(50.0) == "warning"
    assert status_color(49.9) == "critical"
    assert status_color(0.0) == "critical"


def test_oversight_plan_roundtrip(in_memory_db):
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME", languages=["en"]))
        db.add(Project(
            project_id="PRJ0001", client_id="CLI0001",
            project_name="Audit", project_type="X",
        ))
        db.add(OversightPlan(
            plan_id="HOP0001",
            project_id="PRJ0001",
            operator_profile="3 senior analysts; OWASP-trained",
            has_documentation="yes",
            automation_bias_training="partial",
            outputs_include_uncertainty="yes",
            override_mechanism="yes",
            override_logged="yes",
            stop_mechanism="yes",
            gaps="Bias training material is dated.",
            mitigation_plan="Refresh training Q3 2026.",
            compliance_percent=88.9,
            created_by="testuser",
        ))

    with get_session() as db:
        plan = db.scalars(
            select(OversightPlan).where(
                OversightPlan.project_id == "PRJ0001"
            )
        ).first()
        assert plan is not None
        assert plan.has_documentation == "yes"
        assert plan.automation_bias_training == "partial"
        assert plan.compliance_percent == 88.9


def test_one_plan_per_project_uniqueness(in_memory_db):
    """The unique constraint on project_id forbids two plans for the same engagement."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(Project(project_id="PRJ0001", client_id="CLI0001",
                       project_name="X", project_type="Y"))
        db.add(OversightPlan(plan_id="HOP0001", project_id="PRJ0001"))

    with pytest.raises(IntegrityError):
        with get_session() as db:
            db.add(OversightPlan(plan_id="HOP0002", project_id="PRJ0001"))


def test_project_delete_cascades(in_memory_db):
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(Project(project_id="PRJ0001", client_id="CLI0001",
                       project_name="X", project_type="Y"))
        db.add(OversightPlan(plan_id="HOP0001", project_id="PRJ0001"))

    with get_session() as db:
        db.delete(db.get(Project, "PRJ0001"))

    with get_session() as db:
        remaining = db.scalars(select(OversightPlan)).all()
        assert remaining == []


def test_to_markdown_renders_checkpoints():
    plan = {
        "compliance_percent": 88.9,
        "operator_profile": "3 analysts",
        "has_documentation": "yes",
        "automation_bias_training": "partial",
        "outputs_include_uncertainty": "yes",
        "override_mechanism": "yes",
        "override_logged": "yes",
        "stop_mechanism": "yes",
        "gaps": "Training is dated",
        "mitigation_plan": "Refresh Q3",
        "next_review_date": None,
        "updated_at": __import__("datetime").datetime(2026, 5, 9, 14, 30),
    }
    md = to_markdown(plan, project_label="ACME / Audit")
    assert "Human Oversight Plan — ACME / Audit" in md
    assert "89%" in md  # 88.9 rounds to 89 via :.0f
    assert "Art. 14.4(a)" in md
    assert "❌" not in md  # no "no" answers in this plan
