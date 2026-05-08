"""Shared pytest fixtures for wavetest-app."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from wavetest_app.db import session as session_mod
from wavetest_app.db.session import Base


@pytest.fixture
def in_memory_db(monkeypatch):
    """Replace the global engine + sessionmaker with an in-memory SQLite."""
    engine = create_engine("sqlite:///:memory:", future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)

    # Importing models registers them on the metadata
    from wavetest_app.db import models  # noqa: F401
    Base.metadata.create_all(engine)

    monkeypatch.setattr(session_mod, "_engine", engine)
    monkeypatch.setattr(session_mod, "_SessionLocal", SessionLocal)
    yield engine
