"""
wavetest_app.explanations — Art. 86 right-to-explanation helpers
=====================================================================

Article 86 is *the affected person's* right — distinct from the model-
level transparency in the Explainability page. The deliverable here is
a plain-language letter to the individual, not a notified-body packet.

Tone guidance for the letter (baked into the Markdown renderer):

* No jargon. "Your application was declined because…", not
  "The classifier output 0 with confidence 0.83."
* Top 3 factors only. Long lists hide the message.
* Always offer a path: how to ask for human review, what evidence would
  change the outcome.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

STATUSES: list[str] = ["open", "in_progress", "sent", "closed"]
STATUS_COLOR = {
    "open":         "critical",
    "in_progress":  "warning",
    "sent":         "ok",
    "closed":       "ok",
}

# Art. 86 doesn't fix a Union-wide deadline — national implementations
# vary. 30 days mirrors the GDPR Art. 12 cadence and is a defensible
# default; analysts can override per request.
DEFAULT_RESPONSE_WINDOW_DAYS = 30


def default_due_date(received: Optional[date]) -> Optional[date]:
    """Returns ``received + 30 days`` or None if no received date set."""
    if received is None:
        return None
    return received + timedelta(days=DEFAULT_RESPONSE_WINDOW_DAYS)


def days_remaining(
    due: Optional[date],
    today: Optional[date] = None,
) -> Optional[int]:
    if due is None:
        return None
    today = today or date.today()
    return (due - today).days


def deadline_color(
    due: Optional[date],
    sent: Optional[date],
) -> str:
    if sent is not None:
        return "ok"
    rem = days_remaining(due)
    if rem is None:
        return "info"
    if rem < 0:
        return "critical"
    if rem <= 5:
        return "warning"
    return "ok"


def to_markdown(request: dict) -> str:
    """Render a customer-facing letter explaining the decision."""
    lines = [
        f"# Your decision — explanation request {request['request_id']}",
        "",
        f"_Filed under your right to an explanation under EU AI Act Article 86._",
        "",
        f"**Request reference**: `{request['request_id']}`  ",
        f"**Customer reference**: `{request.get('subject_reference') or '—'}`  ",
        f"**Date of decision**: "
        f"{request['decision_date'].isoformat() if request.get('decision_date') else '—'}  ",
        f"**Date of response**: "
        f"{request['response_sent_date'].isoformat() if request.get('response_sent_date') else '_to be sent_'}",
        "",
        "## What was decided",
        "",
        request.get("decision_outcome") or "_The decision details will appear here._",
        "",
        "## How an AI system was involved",
        "",
        "An AI system was used as part of the decision-making process. "
        "The system reviews the information you provided and produces a "
        "recommendation that informs the final decision.",
        "",
        "## Main factors that drove your decision",
        "",
        request.get("factors_text") or
        "_The top factors that drove this specific decision will be listed "
        "here in plain language._",
        "",
        "## What could change the outcome",
        "",
        request.get("alternative_paths") or
        "_The conditions under which the decision would change will be "
        "described here, where they exist._",
        "",
        "## Your right to human review",
        "",
        (
            "If you would like a human to review this decision, please reply "
            "to this letter or contact us using the details below."
            if request.get("human_review_offered")
            else "Human review is not currently offered for this decision. "
                 "If you wish to challenge the outcome, please contact us "
                 "to discuss your options."
        ),
        "",
        "## Notes",
        "",
        request.get("notes") or "_None._",
        "",
        "---",
        "",
        f"_This letter was prepared by waveImpact GmbH on behalf of "
        f"{request.get('client_name') or 'the deployer'}. "
        f"Reference our internal record `{request['request_id']}` "
        "in any follow-up._",
    ]
    return "\n".join(lines)
