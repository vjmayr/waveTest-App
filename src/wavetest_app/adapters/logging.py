"""Adapter: DB project → wavetest_logging.LoggingAssessment."""

from __future__ import annotations

from typing import Optional

from wavetest_logging import (
    CurrentLoggingState,
    LoggingAssessment,
    SystemProfile,
)

from wavetest_app.adapters._common import load_project_snapshot


def make_logging_assessment(
    project_id: str,
    current_logging: Optional[CurrentLoggingState] = None,
    system_profile: Optional[SystemProfile] = None,
) -> LoggingAssessment:
    s = load_project_snapshot(project_id)
    return LoggingAssessment(
        client_name=s.company_name,
        system_name=s.system_name,
        system_description=s.system_description,
        project_id=s.project_id,
        project_name=s.project_name,
        current_logging=current_logging,
        system_profile=system_profile,
        reports_path=s.reports_path,
        analysis_path=s.analysis_path,
        documentation_path=s.documentation_path,
        data_path=s.data_path,
        languages=s.languages,
    )
