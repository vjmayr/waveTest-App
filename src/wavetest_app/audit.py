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

import logging
import os
import time
from contextlib import contextmanager
from typing import Iterator, Literal, Optional, TYPE_CHECKING

from wavetest_app._time import utc_now
from wavetest_app.db.ids import next_id
from wavetest_app.db.models import AuditLog
from wavetest_app.db.session import get_session

_log = logging.getLogger(__name__)

if TYPE_CHECKING:  # avoid runtime cost / circular-import risk
    from wavetest_app.db.models import Project


ModuleName = Literal[
    "data_quality", "bias", "explainability",
    "logging", "monitoring", "combined",
]
StatusColor = Literal["ok", "warning", "critical", "info"]


def _current_actor() -> str:
    """Identity of the analyst running the assessment.

    Resolution order:
    1. The authenticated Streamlit user (set by ``wavetest_app.auth``).
    2. The OS login (``$USER`` / ``$USERNAME``) — only meaningful for CLI
       scripts that bypass the UI; pre-auth pages used to fall back here.
    3. ``"system"`` if nothing else is available.
    """
    try:
        from wavetest_app.auth import current_username
        username = current_username()
        if username:
            return username
    except Exception:
        # Streamlit not running (CLI tests/scripts), auth.yaml missing, etc.
        pass
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

    Audit-write failures are logged but never raised — a broken DB write
    must not break the assessment that triggered it.
    """
    try:
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
    except Exception:
        _log.exception("Failed to write audit_log entry for module=%s", module)
        return ""


@contextmanager
def audit_assessment(
    project: "Project",
    module: ModuleName,
) -> Iterator[None]:
    """Wrap an assessment block; on exception, write a FAILED audit row + re-raise.

    Usage::

        with audit_assessment(project, "data_quality"):
            results = assessment.run(df, verbose=False)
            record_run(project=project, module="data_quality",
                       status="GOOD", ...)

    On success the context manager does nothing — the inner ``record_run``
    call records the outcome. On exception, an audit entry with
    ``status="FAILED"`` is written before the exception propagates so the
    operator-visible Streamlit error is still preserved.
    """
    t0 = time.perf_counter()
    try:
        yield
    except Exception as exc:
        record_run(
            project=project,
            module=module,
            status="FAILED",
            status_color="critical",
            status_detail=f"{type(exc).__name__}: {exc}"[:500],
            duration_seconds=time.perf_counter() - t0,
        )
        raise
