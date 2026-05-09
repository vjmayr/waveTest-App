"""
wavetest_app.risk — risk-level matrix helpers
================================================

Article 9 of the EU AI Act requires a risk management system that
identifies, analyses, evaluates, and monitors risks throughout the
lifecycle of a high-risk AI system. This module is the small lookup
table that maps a (severity, likelihood) pair to an overall level.

Pre-mitigation level lives on every ``RiskEntry``; the same lookup
re-runs against (residual_severity, residual_likelihood) to produce a
post-mitigation residual level.
"""

from __future__ import annotations

from typing import Literal, Optional

Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
Likelihood = Literal["RARE", "UNLIKELY", "POSSIBLE", "LIKELY", "ALMOST_CERTAIN"]
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

SEVERITIES: list[Severity] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
LIKELIHOODS: list[Likelihood] = [
    "RARE", "UNLIKELY", "POSSIBLE", "LIKELY", "ALMOST_CERTAIN",
]
RISK_CATEGORIES = [
    "data_quality", "bias", "security", "oversight",
    "performance", "governance", "other",
]
MITIGATION_STATUSES = ["proposed", "in_progress", "implemented", "verified"]


# Severity rows (LOW→CRITICAL) × likelihood cols (RARE→ALMOST_CERTAIN).
# Read as: this is the level when severity=row, likelihood=col.
_MATRIX: dict[Severity, dict[Likelihood, RiskLevel]] = {
    "LOW": {
        "RARE": "LOW", "UNLIKELY": "LOW", "POSSIBLE": "LOW",
        "LIKELY": "MEDIUM", "ALMOST_CERTAIN": "MEDIUM",
    },
    "MEDIUM": {
        "RARE": "LOW", "UNLIKELY": "MEDIUM", "POSSIBLE": "MEDIUM",
        "LIKELY": "HIGH", "ALMOST_CERTAIN": "HIGH",
    },
    "HIGH": {
        "RARE": "MEDIUM", "UNLIKELY": "HIGH", "POSSIBLE": "HIGH",
        "LIKELY": "CRITICAL", "ALMOST_CERTAIN": "CRITICAL",
    },
    "CRITICAL": {
        "RARE": "HIGH", "UNLIKELY": "HIGH", "POSSIBLE": "CRITICAL",
        "LIKELY": "CRITICAL", "ALMOST_CERTAIN": "CRITICAL",
    },
}


def compute_risk_level(severity: str, likelihood: str) -> RiskLevel:
    """Look up the risk level for a (severity, likelihood) pair.

    Unknown labels fall through to ``"MEDIUM"`` so the form-driven UI
    never crashes on a typo.
    """
    return _MATRIX.get(severity, {}).get(likelihood, "MEDIUM")  # type: ignore[return-value]


def compute_residual_level(
    residual_severity: Optional[str],
    residual_likelihood: Optional[str],
) -> Optional[RiskLevel]:
    """Same as :func:`compute_risk_level` but returns ``None`` if either
    residual coordinate is missing — reflects "not yet re-evaluated".
    """
    if not residual_severity or not residual_likelihood:
        return None
    return compute_risk_level(residual_severity, residual_likelihood)


_LEVEL_COLOR = {
    "LOW":      "ok",
    "MEDIUM":   "warning",
    "HIGH":     "warning",
    "CRITICAL": "critical",
}


def level_color(level: Optional[str]) -> str:
    """Map a risk level to the app's ok/warning/critical/info palette."""
    if not level:
        return "info"
    return _LEVEL_COLOR.get(level, "info")
