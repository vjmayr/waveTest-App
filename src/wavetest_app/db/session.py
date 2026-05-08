"""
wavetest_app.db.session — Engine + session factory
=====================================================

Single source of truth for SQLAlchemy engine creation. All DB code goes
through ``get_session()`` so we can swap SQLite for Postgres later by
changing the URL only.

Run as a module to bootstrap an empty database::

    python -m wavetest_app.db.session --init
"""

import argparse
import sys
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from wavetest_app.config import DB_URL


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""


_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker[Session]] = None


def init_engine(db_url: str = DB_URL, echo: bool = False) -> Engine:
    """Configure the global engine + session factory. Called lazily."""
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(db_url, echo=echo, future=True)
        _SessionLocal = sessionmaker(
            bind=_engine, autoflush=False, future=True,
        )
    return _engine


def get_engine() -> Engine:
    return init_engine()


@contextmanager
def get_session() -> Iterator[Session]:
    """Context-managed session that commits on success, rolls back on error."""
    init_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(db_url: str = DB_URL) -> None:
    """Create all tables. Idempotent: skips tables that already exist."""
    # Importing models registers them on Base.metadata
    from wavetest_app.db import models  # noqa: F401

    engine = init_engine(db_url)
    Base.metadata.create_all(engine)
    print(f"✅ Database initialised at: {db_url}")


def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialise the wavetest_app SQLite database.",
    )
    parser.add_argument("--init", action="store_true",
                        help="Create all tables (idempotent).")
    parser.add_argument("--db-url", default=DB_URL,
                        help=f"SQLAlchemy URL (default: {DB_URL}).")
    args = parser.parse_args()

    if args.init:
        init_db(args.db_url)
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(_main())
