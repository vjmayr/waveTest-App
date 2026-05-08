"""Smoke tests for the persistence layer."""

from datetime import date, datetime

from wavetest_app.db.models import Client, Project, ProjectType, System
from wavetest_app.db.session import get_session


def test_client_roundtrip(in_memory_db):
    with get_session() as db:
        db.add(Client(
            client_id="CLI0001",
            company_name="ACME GmbH",
            country="Germany",
            languages=["en", "de"],
            folder_path="/tmp/CLI0001",
        ))

    with get_session() as db:
        client = db.get(Client, "CLI0001")
        assert client is not None
        assert client.company_name == "ACME GmbH"
        assert client.languages == ["en", "de"]


def test_full_object_graph(in_memory_db):
    with get_session() as db:
        pt = ProjectType(
            type_id="PT0001",
            type_name="Bias Detection",
            description="Bias diagnostics + remediation",
            standard_services=["screen", "diagnose", "mitigate"],
            is_default=True,
        )
        client = Client(
            client_id="CLI0001",
            company_name="ACME",
            languages=["en"],
        )
        system = System(
            system_id="SYS0001",
            client_id="CLI0001",
            system_name="HR-Bot",
            description="Hiring screener",
            classification_date=datetime(2026, 1, 1),
            classification_data={"high_risk": True},
        )
        project = Project(
            project_id="PRJ0001",
            client_id="CLI0001",
            project_type_id="PT0001",
            project_name="Audit",
            project_type="Bias Detection",
            start_date=date(2026, 5, 1),
            folder_path="/tmp/PRJ0001",
            status="active",
        )
        db.add_all([pt, client, system, project])

    with get_session() as db:
        client = db.get(Client, "CLI0001")
        assert len(client.systems) == 1
        assert client.systems[0].classification_data["high_risk"] is True
        assert len(client.projects) == 1

        project = db.get(Project, "PRJ0001")
        assert project.project_type_ref is not None
        assert project.project_type_ref.type_name == "Bias Detection"


def test_idempotent_upsert(in_memory_db):
    """Re-inserting the same client_id should be safe via merge-style updates."""
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME", languages=["en"]))

    with get_session() as db:
        existing = db.get(Client, "CLI0001")
        existing.company_name = "ACME GmbH"
        existing.languages = ["en", "de"]

    with get_session() as db:
        client = db.get(Client, "CLI0001")
        assert client.company_name == "ACME GmbH"
        assert "de" in client.languages


def test_classification_data_json_roundtrip(in_memory_db):
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(System(
            system_id="SYS0001",
            client_id="CLI0001",
            system_name="X",
            classification_data={
                "entity_type": "Provider",
                "high_risk_categories": ["Employment"],
                "results": {"high_risk": True, "overall_status": "HIGH-RISK"},
            },
        ))

    with get_session() as db:
        s = db.get(System, "SYS0001")
        assert s.classification_data["entity_type"] == "Provider"
        assert s.classification_data["results"]["high_risk"] is True
        assert s.classification_data["high_risk_categories"] == ["Employment"]
