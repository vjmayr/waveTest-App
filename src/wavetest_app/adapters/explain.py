"""Adapter: DB project → wavetest_explain.ExplainabilityAssessment."""

from __future__ import annotations

from typing import Optional

from wavetest_explain import ExplainabilityAssessment
from wavetest_explain.core.assessment import AssessmentConfig

from wavetest_app.adapters._common import load_project_snapshot


def make_explain_assessment(
    project_id: str,
    config: Optional[AssessmentConfig] = None,
) -> ExplainabilityAssessment:
    s = load_project_snapshot(project_id)
    return ExplainabilityAssessment(
        client_name=s.company_name,
        system_name=s.system_name,
        system_description=s.system_description,
        project_id=s.project_id,
        project_name=s.project_name,
        config=config,
        reports_path=s.reports_path,
        analysis_path=s.analysis_path,
        data_path=s.data_path,
        languages=s.languages,
    )
