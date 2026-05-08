"""
wavetest_app.classification — EU AI Act risk classifier
==========================================================

Pure-data classification of an AI system based on the questionnaire fields
captured by the Systems page. Ported from the original waveImpact Console.
"""

from __future__ import annotations

from typing import Any, Dict, List


# Annex III high-risk categories (EU AI Act, current text)
HIGH_RISK_CATEGORIES = [
    "None",
    "Biometrics",
    "Critical infrastructure",
    "Educational and vocational training",
    "Employment, workers management, and access to self-employment",
    "Access to essential private/public services",
    "Law enforcement",
    "Migration, asylum, and border control management",
    "Administration of justice and democratic processes",
]

PROHIBITED_PRACTICES = [
    "None",
    "Subliminal techniques, manipulation, and deception",
    "Exploiting vulnerabilities",
    "Biometric categorisation",
    "Social scoring",
    "Predictive policing",
    "Expanding facial recognition databases",
    "Emotion recognition in workplace/education",
    "Real-time remote biometrics",
]

TRANSPARENCY_REQUIREMENTS = [
    "None",
    "Interacting directly with people",
    "Generating synthetic content (deepfakes)",
    "Emotion recognition or biometric categorisation",
    "Generating text for public information",
]

ENTITY_TYPES = [
    "Provider",
    "Deployer",
    "Distributor",
    "Importer",
    "Product Manufacturer",
    "Authorised Representative",
]


# ---------------------------------------------------------------------------
def _has_real_value(values: List[str]) -> bool:
    """True if the list contains at least one non-'None' value."""
    return bool(values) and "None" not in values


def get_entity_obligations(entity_type: str, is_high_risk: bool) -> List[str]:
    """Article-tagged obligations triggered by the entity type + high-risk flag."""
    obligations: List[str] = []

    if entity_type == "Provider":
        obligations.append("AI Literacy (Article 4)")
        if is_high_risk:
            obligations.extend([
                "Risk Management System (Article 9)",
                "Data Governance (Article 10)",
                "Technical Documentation (Article 11)",
                "Record-Keeping (Article 12)",
                "Transparency (Article 13)",
                "Human Oversight (Article 14)",
                "Accuracy, Robustness, Cybersecurity (Article 15)",
            ])
    elif entity_type == "Deployer":
        obligations.append("AI Literacy (Article 4)")
        if is_high_risk:
            obligations.extend([
                "Use instructions compliance (Article 26)",
                "Human oversight during use",
                "Input data monitoring",
                "Fundamental Rights Impact Assessment (if applicable)",
            ])
    # Distributor / Importer / Product Manufacturer / Authorised Representative
    # share the AI Literacy baseline; specific obligations depend on context
    # and are out of scope for this classifier.
    elif entity_type:
        obligations.append("AI Literacy (Article 4)")

    return obligations


def classify(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Classify an AI system based on the questionnaire payload.

    Parameters
    ----------
    payload : dict
        Questionnaire fields: ``entity_type``, ``is_ai_system``,
        ``high_risk_categories``, ``prohibited_practices``,
        ``significant_risk``, ``transparency_requirements``.

    Returns
    -------
    dict
        ``{prohibited, high_risk, transparency_required, entity_obligations,
        overall_status}``.
    """
    prohibited = _has_real_value(payload.get("prohibited_practices", []))

    high_risk_cats = payload.get("high_risk_categories", [])
    significant_risk = payload.get("significant_risk", "No") == "Yes"
    high_risk = _has_real_value(high_risk_cats) or significant_risk

    transparency_required = _has_real_value(
        payload.get("transparency_requirements", [])
    )

    entity_obligations = get_entity_obligations(
        payload.get("entity_type", ""), high_risk,
    )

    if prohibited:
        overall_status = "PROHIBITED - System cannot be deployed"
    elif high_risk:
        overall_status = "HIGH-RISK - Strict compliance requirements"
    elif transparency_required:
        overall_status = "LIMITED-RISK - Transparency obligations"
    else:
        overall_status = "MINIMAL-RISK - Basic requirements"

    return {
        "prohibited":            prohibited,
        "high_risk":             high_risk,
        "transparency_required": transparency_required,
        "entity_obligations":    entity_obligations,
        "overall_status":        overall_status,
    }
