"""Adapter: DB project → wavetest_fairness.FairnessAssessment."""

from __future__ import annotations

from typing import Any, Dict, Optional

from wavetest_fairness import FairnessAssessment
from wavetest_fairness.core.risk import RiskThresholds

from wavetest_app.adapters._common import load_project_snapshot


def make_fairness_assessment(
    project_id: str,
    privileged_groups: Optional[Dict[str, Any]] = None,
    risk_thresholds: Optional[RiskThresholds] = None,
) -> FairnessAssessment:
    s = load_project_snapshot(project_id)
    return FairnessAssessment(
        client_name=s.company_name,
        system_name=s.system_name,
        system_description=s.system_description,
        project_id=s.project_id,
        project_name=s.project_name,
        privileged_groups=privileged_groups,
        risk_thresholds=risk_thresholds,
        reports_path=s.reports_path,
        analysis_path=s.analysis_path,
        data_path=s.data_path,
        languages=s.languages,
    )
