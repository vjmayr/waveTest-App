"""
wavetest_app.db.ids — sequential ID generator
================================================

The original console allocated IDs as ``CLI{count + 1:04d}`` which collides
after deletions. This helper looks at the maximum used numeric suffix and
returns the next available.

Race-safety: read-then-allocate is wrapped in a process-wide lock, so
concurrent form submissions inside a single Streamlit instance never
produce the same ID. **This is not enough for a multi-process deploy** —
two `streamlit run` instances pointed at the same SQLite file can still
collide. When that becomes a real concern, swap this for a DB-side
``id_sequences`` table with ``UPSERT … RETURNING`` for atomic allocation.
"""

from __future__ import annotations

import threading

from sqlalchemy import select
from sqlalchemy.orm import Session

_ID_LOCK = threading.Lock()


def next_id(
    db: Session,
    id_column,
    prefix: str,
    width: int = 4,
) -> str:
    """Return the next ``"{prefix}{NNNN}"`` ID not yet present in ``id_column``.

    Examples
    --------
    >>> next_id(db, Client.client_id, "CLI")
    'CLI0001'
    """
    with _ID_LOCK:
        rows = db.scalars(
            select(id_column).where(id_column.like(f"{prefix}%"))
        ).all()
        nums = []
        for r in rows:
            suffix = r[len(prefix):]
            if suffix.isdigit():
                nums.append(int(suffix))
        return f"{prefix}{(max(nums, default=0) + 1):0{width}d}"
