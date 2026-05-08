"""
wavetest_app.db.ids — sequential ID generator
================================================

The original console allocated IDs as ``CLI{count + 1:04d}`` which collides
after deletions. This helper looks at the maximum used numeric suffix and
returns the next available.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session


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
    rows = db.scalars(
        select(id_column).where(id_column.like(f"{prefix}%"))
    ).all()
    nums = []
    for r in rows:
        suffix = r[len(prefix):]
        if suffix.isdigit():
            nums.append(int(suffix))
    return f"{prefix}{(max(nums, default=0) + 1):0{width}d}"
