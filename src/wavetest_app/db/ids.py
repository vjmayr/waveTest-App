"""
wavetest_app.db.ids — atomic ID allocation
=================================================

Returns the next ``{prefix}{NNNN}`` id for a given prefix via a single
atomic UPSERT against the ``id_sequences`` table. Replaces the original
read-then-allocate scheme which raced under concurrent submissions
(two callers could both observe the same MAX and write the same PK,
with the second insert dying on the UNIQUE constraint).

The SQL we run is portable across SQLite 3.35+ and PostgreSQL 9.5+::

    INSERT INTO id_sequences (prefix, next_value) VALUES (:p, 1)
    ON CONFLICT(prefix) DO UPDATE SET next_value = next_value + 1
    RETURNING next_value;

The ``id_column`` argument is accepted for backwards compatibility with
older call sites but is no longer consulted — the canonical counter
lives in ``id_sequences``. Seed values were written by the Alembic
migration that created the table, so the first allocation per prefix
is contiguous with whatever IDs already existed at upgrade time.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


# A single SQL statement: insert a fresh row if the prefix is new (1) or
# increment the existing one (+1), and return the resulting value in either
# case. Atomic at the DB level — no application-side lock needed.
_NEXT_ID_SQL = text(
    """
    INSERT INTO id_sequences (prefix, next_value) VALUES (:p, 1)
    ON CONFLICT (prefix) DO UPDATE SET next_value = id_sequences.next_value + 1
    RETURNING next_value
    """
)


def next_id(
    db: Session,
    id_column=None,           # kept for backwards compat; unused
    prefix: str = "",
    width: int = 4,
) -> str:
    """Atomically allocate the next ``"{prefix}{NNNN}"`` id.

    Examples
    --------
    >>> next_id(db, Client.client_id, "CLI")
    'CLI0001'
    """
    if not prefix:
        raise ValueError("prefix is required")
    # scalar_one() expresses the invariant that this UPSERT always
    # returns exactly one value — it raises if the DB returns nothing
    # or more than one row, which would indicate a deeper schema issue.
    n = int(db.execute(_NEXT_ID_SQL, {"p": prefix}).scalar_one())
    return f"{prefix}{n:0{width}d}"
