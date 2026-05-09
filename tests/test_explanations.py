"""Tests for the Article 86 right-to-explanation module."""

from datetime import date

from sqlalchemy import select

from wavetest_app.db.models import Client, ExplanationRequest, Project
from wavetest_app.db.session import get_session
from wavetest_app.explanations import (
    DEFAULT_RESPONSE_WINDOW_DAYS,
    days_remaining,
    deadline_color,
    default_due_date,
    to_markdown,
)


# ---------------------------------------------------------------------------
# Deadline helpers
# ---------------------------------------------------------------------------
class TestDeadlines:
    def test_default_window_is_30_days(self):
        assert DEFAULT_RESPONSE_WINDOW_DAYS == 30

    def test_default_due_adds_30(self):
        received = date(2026, 5, 1)
        assert default_due_date(received) == date(2026, 5, 31)

    def test_default_due_none_in_none_out(self):
        assert default_due_date(None) is None

    def test_days_remaining_after_due(self):
        due = date(2026, 5, 1)
        today = date(2026, 4, 25)
        assert days_remaining(due, today=today) == 6

    def test_days_remaining_overdue(self):
        due = date(2026, 5, 1)
        today = date(2026, 5, 10)
        assert days_remaining(due, today=today) == -9

    def test_deadline_color_already_sent(self):
        assert deadline_color(date(2026, 5, 1), date(2026, 4, 30)) == "ok"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def test_request_roundtrip(in_memory_db):
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(Project(project_id="PRJ0001", client_id="CLI0001",
                       project_name="X", project_type="Y"))
        db.add(ExplanationRequest(
            request_id="RTE0001",
            project_id="PRJ0001",
            project_name="X",
            client_name="ACME",
            subject_reference="CASE-12345",
            decision_outcome="Application declined.",
            human_review_offered=True,
        ))

    with get_session() as db:
        rec = db.get(ExplanationRequest, "RTE0001")
        assert rec is not None
        assert rec.subject_reference == "CASE-12345"
        assert rec.human_review_offered is True


def test_project_delete_preserves_request(in_memory_db):
    """SET NULL on FK — explanation requests outlive engagements."""
    with get_session() as db:
        db.add(Client(client_id="CLI0001", company_name="ACME"))
        db.add(Project(project_id="PRJ0001", client_id="CLI0001",
                       project_name="Audit", project_type="Y"))
        db.add(ExplanationRequest(
            request_id="RTE0001",
            project_id="PRJ0001",
            project_name="Audit",
            client_name="ACME",
            subject_reference="X",
        ))

    with get_session() as db:
        db.delete(db.get(Project, "PRJ0001"))

    with get_session() as db:
        rows = db.scalars(select(ExplanationRequest)).all()
        assert len(rows) == 1
        assert rows[0].project_id is None
        assert rows[0].project_name == "Audit"


# ---------------------------------------------------------------------------
# Letter rendering
# ---------------------------------------------------------------------------
def test_letter_avoids_jargon_section_headers():
    md = to_markdown({
        "request_id": "RTE0001",
        "subject_reference": "CASE-99",
        "client_name": "ACME",
        "decision_date": date(2026, 5, 1),
        "decision_outcome": "Application declined.",
        "factors_text": "Income below threshold; existing debt.",
        "alternative_paths": "Reapplying after debt is reduced.",
        "human_review_offered": True,
        "response_sent_date": None,
        "notes": "",
    })
    # Must contain plain-language sections
    assert "## What was decided" in md
    assert "## Main factors that drove your decision" in md
    assert "## What could change the outcome" in md
    assert "## Your right to human review" in md
    # Reference and customer ID present
    assert "RTE0001" in md
    assert "CASE-99" in md
    # Mentions Art. 86
    assert "Article 86" in md


def test_letter_handles_no_human_review():
    md = to_markdown({
        "request_id": "RTE0002",
        "subject_reference": "X",
        "client_name": "ACME",
        "decision_date": None,
        "decision_outcome": "",
        "factors_text": "",
        "alternative_paths": "",
        "human_review_offered": False,
        "response_sent_date": None,
        "notes": "",
    })
    # Different language when human review is not offered
    assert "Human review is not currently offered" in md
