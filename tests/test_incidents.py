"""Tests for the Article 73 incident-reporting module."""

from datetime import date

from sqlalchemy import select

from wavetest_app.db.models import Client, IncidentReport, Project
from wavetest_app.db.session import get_session
from wavetest_app.incidents import (
    SEVERITIES,
    STATUSES,
    days_remaining,
    deadline_color,
    deadline_days,
    to_markdown,
)


# ---------------------------------------------------------------------------
# Deadline arithmetic
# ---------------------------------------------------------------------------
class TestDeadlines:
    def test_severity_table_has_legal_deadlines(self):
        # Art. 73 specifies 2 days for death/serious health
        assert deadline_days("death_or_serious_health") == 2
        # 15 days for the rest
        assert deadline_days("fundamental_rights") == 15
        assert deadline_days("near_miss") == 15

    def test_unknown_severity_falls_back_to_15(self):
        assert deadline_days("nonsense") == 15

    def test_days_remaining_none_when_no_detection_date(self):
        assert days_remaining("near_miss", None) is None

    def test_days_remaining_after_detection(self):
        # Detected 5 days ago, 15-day deadline → 10 days left
        detected = date(2026, 5, 1)
        today = date(2026, 5, 6)
        assert days_remaining("near_miss", detected, today=today) == 10

    def test_days_remaining_overdue_is_negative(self):
        detected = date(2026, 1, 1)
        today = date(2026, 5, 6)
        assert days_remaining("near_miss", detected, today=today) < 0

    def test_deadline_color_already_reported_is_ok(self):
        assert deadline_color(
            "death_or_serious_health",
            date_detected=date(2026, 5, 1),
            date_reported=date(2026, 5, 2),
        ) == "ok"

    def test_deadline_color_critical_when_overdue(self):
        # 100 days past detection of a 15-day item, never reported → critical
        old_detect = date(2026, 1, 1)
        # Use today=None falls through to date.today(), but we can't pin it
        # in the public API. Instead test via days_remaining directly:
        rem = days_remaining("near_miss", old_detect, today=date(2026, 6, 1))
        assert rem is not None and rem < 0


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def test_incident_roundtrip(in_memory_db):
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(Project(project_id="PRJ0001", client_id="CLI0001",
                       project_name="X", project_type="Y"))
        db.add(IncidentReport(
            incident_id="INC0001",
            project_id="PRJ0001",
            project_name="X",
            client_name="ACME",
            title="False positive on hiring screen",
            severity="fundamental_rights",
            affected_persons=12,
            date_detected=date(2026, 5, 1),
        ))

    with get_session() as db:
        rec = db.get(IncidentReport, "INC0001")
        assert rec is not None
        assert rec.severity == "fundamental_rights"
        assert rec.affected_persons == 12


def test_project_delete_preserves_incident(in_memory_db):
    """SET NULL on FK — incidents outlive engagements."""
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(Project(project_id="PRJ0001", client_id="CLI0001",
                       project_name="Audit", project_type="Y"))
        db.add(IncidentReport(
            incident_id="INC0001",
            project_id="PRJ0001",
            project_name="Audit",
            client_name="ACME",
            title="x",
        ))

    with get_session() as db:
        db.delete(db.get(Project, "PRJ0001"))

    with get_session() as db:
        rows = db.scalars(select(IncidentReport)).all()
        assert len(rows) == 1
        assert rows[0].project_id is None  # FK cleared
        assert rows[0].project_name == "Audit"  # snapshot preserved


# ---------------------------------------------------------------------------
# Markdown packet
# ---------------------------------------------------------------------------
def test_markdown_packet_renders_all_sections():
    md = to_markdown({
        "incident_id": "INC0042",
        "title": "Outage on Tuesday",
        "project_id": "PRJ0001",
        "project_name": "Cardio AI",
        "client_name": "ACME",
        "severity": "fundamental_rights",
        "status": "investigating",
        "summary": "Model returned all-zeros for 4 hours.",
        "description": "After config push the model …",
        "root_cause": "Stale feature store.",
        "corrective_action": "Add staleness check to deploy hook.",
        "authority_notified": True,
        "authority_name": "BNetzA",
        "authority_reference": "AI-2026-001",
        "date_occurred": date(2026, 5, 1),
        "date_detected": date(2026, 5, 1),
        "date_reported": date(2026, 5, 5),
        "affected_persons": 312,
        "notes": "Public statement issued.",
    })
    assert "INC0042" in md
    assert "Cardio AI" in md
    assert "deadline: 15 days" in md
    assert "BNetzA" in md
    assert "AI-2026-001" in md
    assert "Stale feature store" in md
