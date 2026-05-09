"""
wavetest_app.db.ids — sequential ID generator
================================================

The original console allocated IDs as ``CLI{count + 1:04d}`` which collides
after deletions. This helper looks at the maximum used numeric suffix and
returns the next available.

Race-safety: a process-wide lock serialises Python-level interleaving
of the read+compute step. **This is not a complete fix.** The sessions
of two concurrent callers each establish their own read snapshot before
the lock is taken, so under heavy concurrent submissions you can still
hit ``IntegrityError`` on the second commit. The proper fix is a DB-side
``id_sequences`` table with atomic ``INSERT … ON CONFLICT … RETURNING``
— left as a follow-up in HANDOVER. For ≤10 analysts on localhost the
realistic collision window is tiny; if it bites in practice, the user
sees the Streamlit error and retries.
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
