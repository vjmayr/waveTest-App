"""Tiny clock helper — drop-in replacement for the deprecated datetime.utcnow().

Returns a *naive* UTC datetime, matching the on-disk format of existing
SQLite rows (DateTime columns without timezone). Switching the columns
themselves to ``DateTime(timezone=True)`` is a separate, larger change.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
