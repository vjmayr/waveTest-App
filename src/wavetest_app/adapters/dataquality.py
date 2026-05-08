"""
wavetest_app.adapters.dataquality
====================================

Build a ``DataQualityAssessment`` from a project ID. The adapter owns its
own DB read so callers don't need to manage SQLAlchemy session lifecycles.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload
from wavetest_dataquality import DataQualityAssessment, QualityThresholds

from wavetest_app.config import project_artifacts_dir
from wavetest_app.db.models import Project
from wavetest_app.db.session import get_session


def make_dataquality_assessment(
    project_id: str,
    target_population: Optional[dict] = None,
    thresholds: Optional[QualityThresholds] = None,
) -> DataQualityAssessment:
    """Instantiate a DataQualityAssessment for the given project.

    Reads the project plus its client and the client's first system in one
    query, so the orchestrator carries no SQLAlchemy state.
    """
    with get_session() as db:
        project = db.scalar(
            select(Project)
            .options(
                joinedload(Project.client),
            )
            .where(Project.project_id == project_id)
        )
        if project is None:
            raise ValueError(f"Project '{project_id}' not found.")

        client = project.client
        primary_system = client.systems[0] if client.systems else None

        # Snapshot all attributes we need before the session closes
        snapshot = {
            "client_id":           client.client_id,
            "company_name":        client.company_name,
            "languages":           list(client.languages or ["en"]),
            "system_name":         primary_system.system_name if primary_system else "AI System",
            "system_description":  primary_system.description if primary_system else "",
            "project_id":          project.project_id,
            "project_name":        project.project_name,
        }

    artifacts = project_artifacts_dir(
        snapshot["client_id"], snapshot["company_name"],
        snapshot["project_id"], snapshot["project_name"],
    )

    return DataQualityAssessment(
        client_name=snapshot["company_name"],
        system_name=snapshot["system_name"],
        system_description=snapshot["system_description"],
        project_id=snapshot["project_id"],
        project_name=snapshot["project_name"],
        target_population=target_population,
        thresholds=thresholds,
        reports_path=artifacts / "reports",
        analysis_path=artifacts / "analysis",
        documentation_path=artifacts / "documentation",
        data_path=artifacts / "data",
        languages=snapshot["languages"],
    )
