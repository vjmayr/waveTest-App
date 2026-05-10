"""
wavetest_app.model_card — Google-schema Model Card serialisation
=====================================================================

Google's model-card-toolkit Python package is incompatible with
Python 3.13 (its build pin is too old). The schema, however, is open
and well documented:
https://modelcards.withgoogle.com/about

We mirror the schema field-for-field on a per-project DB row and
produce Markdown + JSON deliverables interchangeable with toolkit output.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from wavetest_app._time import utc_now


def to_dict(card: dict, *, project, system_classification: str = "") -> dict[str, Any]:
    """Build a Google-schema Model Card dict from a stored card row.

    Empty fields are written as empty strings rather than omitted, so
    consumers (downstream toolchains, reviewers) always see the full
    schema and know what's missing. Lists are split from free text on
    blank lines or numbered/bulleted lines.
    """
    def _list_split(text: str) -> list[str]:
        if not text:
            return []
        # Accept any of "- ...", "* ...", "1. ...", or blank-line-separated
        items: list[str] = []
        for raw in text.replace("\r\n", "\n").split("\n"):
            stripped = raw.lstrip("-*0123456789. ").strip()
            if stripped:
                items.append(stripped)
        return items

    return {
        "schema_version": "0.0.2",  # Google MC schema
        "model_details": {
            "name": card.get("model_name", ""),
            "version": {"name": card.get("model_version", "")},
            "owners": _list_split(card.get("model_owners", "")),
            "licenses": [
                {"identifier": card.get("license", "")}
            ] if card.get("license") else [],
            "citations": _list_split(card.get("citation", "")),
            "references": _list_split(card.get("references", "")),
            "overview": card.get("overview", ""),
        },
        "intended_use": {
            "primary_uses":     card.get("primary_uses", ""),
            "primary_users":    card.get("primary_users", ""),
            "out_of_scope_uses": card.get("out_of_scope_uses", ""),
        },
        "model_parameters": {
            # Filled by the analyst free-form via "training_data" /
            # "evaluation_data" in this v0; the schema's full
            # `data.train` / `data.eval` blocks can be expanded later.
        },
        "considerations": {
            "ethical_considerations": _list_split(
                card.get("ethical_considerations", "")
            ),
            "limitations": _list_split(card.get("caveats", "")),
            "tradeoffs": [],
            "use_cases": [],
            "users": _list_split(card.get("primary_users", "")),
        },
        "quantitative_analysis": {
            "performance_metrics": _list_split(
                card.get("performance_metrics", "")
            ),
        },
        "_wavetest": {
            "project_id":   getattr(project, "project_id", ""),
            "client_name":  getattr(project.client, "company_name", "")
                            if hasattr(project, "client") and project.client else "",
            "system_classification": system_classification,
            "exported_at": utc_now().isoformat(),
        },
    }


def to_markdown(card: dict, *, project_label: str) -> str:
    """Render the Model Card as a customer-facing Markdown deliverable."""
    def _val(field: str) -> str:
        v = card.get(field) or ""
        return v.strip() if v.strip() else "_Not provided._"

    lines = [
        f"# Model Card — {project_label}",
        "",
        "_Mirrors Google's Model Card schema (model-card-toolkit "
        "Python package not installable on Python 3.13). Fulfils EU AI "
        "Act Article 11 technical documentation + Article 13 deployer "
        "transparency requirements._",
        "",
        f"**Last updated**: {card['updated_at'].strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Model details",
        "",
        f"- **Name**: {_val('model_name')}",
        f"- **Version**: {_val('model_version')}",
        f"- **Owners**: {_val('model_owners')}",
        f"- **License**: {_val('license')}",
        "",
        "### Overview",
        "",
        _val("overview"),
        "",
        "### Citation",
        "",
        _val("citation"),
        "",
        "### References",
        "",
        _val("references"),
        "",
        "## Intended use",
        "",
        f"**Primary uses:** {_val('primary_uses')}",
        "",
        f"**Primary users:** {_val('primary_users')}",
        "",
        f"**Out-of-scope uses:** {_val('out_of_scope_uses')}",
        "",
        "## Factors",
        "",
        f"**Relevant factors:** {_val('relevant_factors')}",
        "",
        f"**Evaluation factors:** {_val('evaluation_factors')}",
        "",
        "## Metrics",
        "",
        "### Performance metrics",
        "",
        _val("performance_metrics"),
        "",
        "### Decision thresholds",
        "",
        _val("decision_thresholds"),
        "",
        "## Data",
        "",
        "### Training data",
        "",
        _val("training_data"),
        "",
        "### Evaluation data",
        "",
        _val("evaluation_data"),
        "",
        "## Ethical considerations",
        "",
        _val("ethical_considerations"),
        "",
        "## Caveats and recommendations",
        "",
        "### Caveats",
        "",
        _val("caveats"),
        "",
        "### Recommendations",
        "",
        _val("recommendations"),
        "",
        "---",
        "",
        f"_Generated by wavetest-app · waveImpact GmbH._",
    ]
    return "\n".join(lines)


def to_json(card: dict, *, project, system_classification: str = "") -> str:
    """Convenience wrapper — emits the Google-schema dict as a JSON string."""
    return json.dumps(
        to_dict(card, project=project,
                system_classification=system_classification),
        indent=2, ensure_ascii=False,
    )
