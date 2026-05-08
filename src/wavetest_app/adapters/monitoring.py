"""Adapter: DB project → wavetest_monitoring.MonitoringAssessment."""

from __future__ import annotations

from typing import Optional

from wavetest_monitoring import (
    MonitoringAssessment,
    MonitoringConfig,
    MonitoringSystemProfile,
)

from wavetest_app.adapters._common import load_project_snapshot


def make_monitoring_assessment(
    project_id: str,
    config: Optional[MonitoringConfig] = None,
    system_profile: Optional[MonitoringSystemProfile] = None,
) -> MonitoringAssessment:
    s = load_project_snapshot(project_id)
    return MonitoringAssessment(
        client_name=s.company_name,
        system_name=s.system_name,
        system_description=s.system_description,
        project_id=s.project_id,
        project_name=s.project_name,
        config=config,
        system_profile=system_profile,
        reports_path=s.reports_path,
        analysis_path=s.analysis_path,
        documentation_path=s.documentation_path,
        data_path=s.data_path,
        languages=s.languages,
    )
