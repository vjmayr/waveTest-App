"""
wavetest_app.adapters._common — Shared snapshot helper
=========================================================

Loads a project + its client + first system in a single query, snapshots
everything needed by an orchestrator into a plain dataclass, and computes
the canonical artifacts directory. All five module-specific adapters
share this helper so they stay 5–10 lines each.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from wavetest_app.config import project_artifacts_dir
from wavetest_app.db.models import Project
from wavetest_app.db.session import get_session


@dataclass(frozen=True)
class ProjectSnapshot:
    """Detached, read-only view of a project plus its client and primary system."""
    client_id: str
    company_name: str
    languages: list[str]
    system_name: str
    system_description: str
    project_id: str
    project_name: str
    artifacts_root: Path  # the per-project artefacts directory (subdirs already created)

    @property
    def reports_path(self) -> Path:       return self.artifacts_root / "reports"
    @property
    def analysis_path(self) -> Path:      return self.artifacts_root / "analysis"
    @property
    def documentation_path(self) -> Path: return self.artifacts_root / "documentation"
    @property
    def data_path(self) -> Path:          return self.artifacts_root / "data"


def load_project_snapshot(project_id: str) -> ProjectSnapshot:
    """Read one project + its primary system from the DB and detach it."""
    with get_session() as db:
        project = db.scalar(
            select(Project)
            .options(joinedload(Project.client))
            .where(Project.project_id == project_id)
        )
        if project is None:
            raise ValueError(f"Project '{project_id}' not found.")

        client = project.client
        primary_system = client.systems[0] if client.systems else None

        snapshot_kwargs = dict(
            client_id=client.client_id,
            company_name=client.company_name,
            languages=list(client.languages or ["en"]),
            system_name=(
                primary_system.system_name if primary_system else "AI System"
            ),
            system_description=(
                primary_system.description if primary_system else ""
            ),
            project_id=project.project_id,
            project_name=project.project_name,
        )

    artifacts_root = project_artifacts_dir(
        snapshot_kwargs["client_id"], snapshot_kwargs["company_name"],
        snapshot_kwargs["project_id"], snapshot_kwargs["project_name"],
    )
    return ProjectSnapshot(**snapshot_kwargs, artifacts_root=artifacts_root)
