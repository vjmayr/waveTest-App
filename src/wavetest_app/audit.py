"""
wavetest_app.audit — Assessment-run audit logging
====================================================

One-line API used by every assessment page::

    record_run(
        project=project, module="data_quality",
        status="GOOD", status_color="ok",
        status_detail="Quality 92.4 / Article 10 compliant",
        duration_seconds=1.7,
    )

Each call appends one row to ``audit_log``. The session is opened, written,
and closed inside the helper so callers don't have to thread the DB through.
Until auth lands, ``actor`` defaults to the OS login (``$USER``); pages may
pass an explicit ``actor`` once that's available.
"""

from __future__ import annotations

import os
from typing import Literal, Optional, TYPE_CHECKING

from wavetest_app._time import utc_now
from wavetest_app.db.ids import next_id
from wavetest_app.db.models import AuditLog
from wavetest_app.db.session import get_session

if TYPE_CHECKING:  # avoid runtime cost / circular-import risk
    from wavetest_app.db.models import Project


ModuleName = Literal[
    "data_quality", "bias", "explainability",
    "logging", "monitoring", "combined",
]
StatusColor = Literal["ok", "warning", "critical", "info"]


def _current_actor() -> str:
    """Best-effort identity until real auth lands."""
    return (
        os.environ.get("USER")
        or os.environ.get("USERNAME")
        or "system"
    )


def record_run(
    *,
    project: "Project",
    module: ModuleName,
    status: str,
    status_color: StatusColor = "info",
    status_detail: str = "",
    duration_seconds: Optional[float] = None,
    actor: Optional[str] = None,
) -> str:
    """Append one audit-log entry. Returns the generated ``audit_id``.

    ``project`` may be a detached ORM instance (the picker hands those
    out) — only column attributes and ``project.client.*`` (eager-loaded)
    are read. No relationship loads happen here.
    """
    with get_session() as db:
        audit_id = next_id(db, AuditLog.audit_id, "AL")
        client_id = project.client.client_id if project.client else None
        client_name = project.client.company_name if project.client else ""
        db.add(AuditLog(
            audit_id=audit_id,
            project_id=project.project_id,
            project_name=project.project_name,
            client_id=client_id,
            client_name=client_name,
            module=module,
            run_at=utc_now(),
            status=status,
            status_color=status_color,
            status_detail=status_detail,
            duration_seconds=duration_seconds,
            actor=actor or _current_actor(),
        ))
    return audit_id
