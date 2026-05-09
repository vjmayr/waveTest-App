"""Tests for the Google-schema Model Card module."""

import json

from sqlalchemy import select

from wavetest_app.db.models import Client, ModelCard, Project
from wavetest_app.db.session import get_session
from wavetest_app.model_card import to_dict, to_json, to_markdown


def test_card_roundtrip(in_memory_db):
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(Project(project_id="PRJ0001", client_id="CLI0001",
                       project_name="X", project_type="Y"))
        db.add(ModelCard(
            card_id="MC0001",
            project_id="PRJ0001",
            model_name="Cardio v2",
            model_version="2.1.0",
            license="MIT",
            primary_uses="Triage cardiac MRI scans",
            out_of_scope_uses="Diagnosis without clinician review",
        ))

    with get_session() as db:
        card = db.scalars(select(ModelCard)).first()
        assert card is not None
        assert card.model_name == "Cardio v2"
        assert card.license == "MIT"


def test_one_card_per_project(in_memory_db):
    import pytest
    from sqlalchemy.exc import IntegrityError

    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(Project(project_id="PRJ0001", client_id="CLI0001",
                       project_name="X", project_type="Y"))
        db.add(ModelCard(card_id="MC0001", project_id="PRJ0001"))

    with pytest.raises(IntegrityError):
        with get_session() as db:
            db.add(ModelCard(card_id="MC0002", project_id="PRJ0001"))


def test_project_delete_cascades(in_memory_db):
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(Project(project_id="PRJ0001", client_id="CLI0001",
                       project_name="X", project_type="Y"))
        db.add(ModelCard(card_id="MC0001", project_id="PRJ0001"))

    with get_session() as db:
        db.delete(db.get(Project, "PRJ0001"))

    with get_session() as db:
        assert db.scalars(select(ModelCard)).all() == []


def test_to_markdown_renders_all_sections():
    import datetime
    card = {
        "model_name": "Cardio v2",
        "model_version": "2.1.0",
        "model_owners": "Asha Patel\nThomas Müller",
        "license": "MIT",
        "citation": "Patel et al., 2026",
        "references": "https://example.com/paper",
        "overview": "Detects ST-elevation MI from 12-lead ECG.",
        "primary_uses": "Triage cardiac MRI scans",
        "primary_users": "Cardiologists",
        "out_of_scope_uses": "Diagnosis without clinician review",
        "relevant_factors": "Age, gender, ethnicity",
        "evaluation_factors": "Age, gender",
        "performance_metrics": "Accuracy 0.87\nAUC 0.91",
        "decision_thresholds": "0.5 (operating point)",
        "training_data": "Internal multi-site cohort",
        "evaluation_data": "External validation cohort",
        "ethical_considerations": "Risk of demographic disparity in TPR",
        "caveats": "Low pediatric coverage",
        "recommendations": "Always pair with clinician review",
        "updated_at": datetime.datetime(2026, 5, 9, 14, 30),
    }
    md = to_markdown(card, project_label="ACME / Cardio Audit")
    assert "Model Card — ACME / Cardio Audit" in md
    assert "## Model details" in md
    assert "## Intended use" in md
    assert "## Factors" in md
    assert "## Metrics" in md
    assert "## Data" in md
    assert "## Ethical considerations" in md
    assert "## Caveats and recommendations" in md
    assert "Cardio v2" in md
    assert "Article 11" in md
    assert "Article 13" in md


def test_to_dict_follows_google_schema():
    card = {
        "model_name": "Cardio v2",
        "model_version": "2.1.0",
        "model_owners": "Asha Patel\nThomas Müller",
        "license": "MIT",
        "citation": "Patel et al., 2026",
        "references": "",
        "overview": "x",
        "primary_uses": "x", "primary_users": "Cardiologists",
        "out_of_scope_uses": "x",
        "relevant_factors": "", "evaluation_factors": "",
        "performance_metrics": "Accuracy 0.87\nAUC 0.91",
        "decision_thresholds": "",
        "training_data": "", "evaluation_data": "",
        "ethical_considerations": "Risk A\nRisk B",
        "caveats": "Limit 1\nLimit 2", "recommendations": "",
    }

    class _Project:
        project_id = "PRJ0001"
        class _C: company_name = "ACME"
        client = _C()

    d = to_dict(card, project=_Project())
    assert d["schema_version"] == "0.0.2"
    assert d["model_details"]["name"] == "Cardio v2"
    assert d["model_details"]["version"]["name"] == "2.1.0"
    assert d["model_details"]["owners"] == ["Asha Patel", "Thomas Müller"]
    assert d["model_details"]["licenses"] == [{"identifier": "MIT"}]
    # Lists are split from free text
    assert d["considerations"]["ethical_considerations"] == ["Risk A", "Risk B"]
    assert d["considerations"]["limitations"] == ["Limit 1", "Limit 2"]
    assert d["quantitative_analysis"]["performance_metrics"] == [
        "Accuracy 0.87", "AUC 0.91",
    ]
    # JSON is well-formed
    js = to_json(card, project=_Project())
    json.loads(js)  # no exception
