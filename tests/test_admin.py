"""Tests for the admin helpers (ID generation + EU AI Act classifier)."""

from datetime import datetime

import pytest

from wavetest_app.classification import classify
from wavetest_app.db.ids import next_id
from wavetest_app.db.models import Client, Project, ProjectType, System
from wavetest_app.db.session import get_session


# ---------------------------------------------------------------------------
# next_id
# ---------------------------------------------------------------------------
class TestNextId:
    def test_first_id_in_empty_table(self, in_memory_db):
        with get_session() as db:
            assert next_id(db, Client.client_id, "CLI") == "CLI0001"

    def test_increments_after_insert(self, in_memory_db):
        with get_session() as db:
            db.add(Client(client_id="CLI0001", company_name="A"))
        with get_session() as db:
            assert next_id(db, Client.client_id, "CLI") == "CLI0002"

    def test_skips_to_max_plus_one_after_delete(self, in_memory_db):
        with get_session() as db:
            db.add(Client(client_id="CLI0001", company_name="A"))
            db.add(Client(client_id="CLI0002", company_name="B"))
            db.add(Client(client_id="CLI0003", company_name="C"))
        with get_session() as db:
            db.delete(db.get(Client, "CLI0002"))
        with get_session() as db:
            # Buggy "count + 1" would return CLI0003 (collision); correct is CLI0004
            assert next_id(db, Client.client_id, "CLI") == "CLI0004"

    def test_ignores_non_numeric_suffixes(self, in_memory_db):
        with get_session() as db:
            db.add(Client(client_id="CLI0005", company_name="A"))
            db.add(Client(client_id="CLIabc",  company_name="B"))  # garbage
        with get_session() as db:
            assert next_id(db, Client.client_id, "CLI") == "CLI0006"

    def test_works_for_each_table(self, in_memory_db):
        with get_session() as db:
            assert next_id(db, Client.client_id,        "CLI") == "CLI0001"
            assert next_id(db, System.system_id,        "SYS") == "SYS0001"
            assert next_id(db, Project.project_id,      "PRJ") == "PRJ0001"
            assert next_id(db, ProjectType.type_id,     "PT")  == "PT0001"

    def test_concurrent_calls_produce_unique_ids(self):
        """20 threads each allocate + insert a client; all IDs must be unique.

        Uses a single shared in-memory connection (StaticPool) so all threads
        see the same database. Without the module-level lock in next_id, the
        read-then-allocate pattern races and at least two threads compute the
        same ID, causing IntegrityError on the second insert.
        """
        from concurrent.futures import ThreadPoolExecutor

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import StaticPool

        from wavetest_app.db.session import Base

        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)

        n_threads = 20

        def worker(_idx: int) -> str:
            with SessionLocal() as db:
                cid = next_id(db, Client.client_id, "CLI")
                db.add(Client(client_id=cid, company_name=f"co_{_idx}"))
                db.commit()
                return cid

        with ThreadPoolExecutor(max_workers=n_threads) as ex:
            ids = list(ex.map(worker, range(n_threads)))

        assert len(ids) == n_threads
        assert len(set(ids)) == n_threads, f"duplicate IDs: {sorted(ids)}"


# ---------------------------------------------------------------------------
# classify
# ---------------------------------------------------------------------------
class TestClassify:
    def test_minimal_risk_default(self):
        r = classify({
            "entity_type": "Provider",
            "is_ai_system": "Yes",
            "high_risk_categories": ["None"],
            "prohibited_practices": ["None"],
            "significant_risk": "No",
            "transparency_requirements": ["None"],
        })
        assert r["overall_status"].startswith("MINIMAL-RISK")
        assert not r["high_risk"]
        assert not r["prohibited"]

    def test_high_risk_via_annex_iii(self):
        r = classify({
            "entity_type": "Provider",
            "high_risk_categories": ["Employment, workers management, and access to self-employment"],
            "prohibited_practices": ["None"],
            "significant_risk": "No",
            "transparency_requirements": ["None"],
        })
        assert r["high_risk"]
        assert r["overall_status"].startswith("HIGH-RISK")
        # Provider + high-risk should trigger the full Article 9–15 stack
        obs = r["entity_obligations"]
        assert any("Article 9" in o for o in obs)
        assert any("Article 15" in o for o in obs)

    def test_high_risk_via_significant_risk(self):
        r = classify({
            "entity_type": "Deployer",
            "high_risk_categories": ["None"],
            "prohibited_practices": ["None"],
            "significant_risk": "Yes",
            "transparency_requirements": ["None"],
        })
        assert r["high_risk"]
        assert r["overall_status"].startswith("HIGH-RISK")

    def test_prohibited_overrides_everything(self):
        r = classify({
            "entity_type": "Provider",
            "high_risk_categories": ["Law enforcement"],  # also high-risk
            "prohibited_practices": ["Social scoring"],
            "significant_risk": "Yes",
            "transparency_requirements": ["None"],
        })
        assert r["prohibited"]
        assert r["overall_status"].startswith("PROHIBITED")

    def test_limited_risk_via_transparency(self):
        r = classify({
            "entity_type": "Deployer",
            "high_risk_categories": ["None"],
            "prohibited_practices": ["None"],
            "significant_risk": "No",
            "transparency_requirements": ["Generating synthetic content (deepfakes)"],
        })
        assert not r["high_risk"]
        assert r["transparency_required"]
        assert r["overall_status"].startswith("LIMITED-RISK")

    def test_empty_payload_is_minimal(self):
        r = classify({})
        assert r["overall_status"].startswith("MINIMAL-RISK")
