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
    """``next_id`` now allocates from a per-prefix counter row in
    ``id_sequences`` via an atomic UPSERT-and-RETURN. Semantics changed
    from "MAX(suffix)+1 over the target table" to "increment the counter":

    * Monotonic — deleting a row does NOT make its ID available again.
    * Independent of the target table — the counter increments even if
      the caller never actually inserts using the returned ID.
    * Race-safe across processes — the DB serialises the UPSERT.

    These three invariants are what the tests below pin.
    """

    def test_first_call_returns_one(self, in_memory_db):
        with get_session() as db:
            assert next_id(db, Client.client_id, "CLI") == "CLI0001"

    def test_consecutive_calls_increment(self, in_memory_db):
        with get_session() as db:
            assert next_id(db, Client.client_id, "CLI") == "CLI0001"
            assert next_id(db, Client.client_id, "CLI") == "CLI0002"
            assert next_id(db, Client.client_id, "CLI") == "CLI0003"

    def test_each_prefix_has_its_own_counter(self, in_memory_db):
        with get_session() as db:
            assert next_id(db, Client.client_id,    "CLI") == "CLI0001"
            assert next_id(db, System.system_id,    "SYS") == "SYS0001"
            assert next_id(db, Project.project_id,  "PRJ") == "PRJ0001"
            assert next_id(db, ProjectType.type_id, "PT")  == "PT0001"
            # Counters are independent — calling CLI again jumps past 0001
            assert next_id(db, Client.client_id, "CLI") == "CLI0002"

    def test_counter_is_monotonic_across_delete(self, in_memory_db):
        """ID is never reused, even if the row holding it goes away.

        This is the *desired* behaviour with a sequence table: deleted
        IDs stay burned. Audit traces that reference an old `CLI0003`
        always point at the same logical record.
        """
        with get_session() as db:
            cid1 = next_id(db, Client.client_id, "CLI")
            db.add(Client(client_id=cid1, company_name="A"))
            cid2 = next_id(db, Client.client_id, "CLI")
            db.add(Client(client_id=cid2, company_name="B"))
        with get_session() as db:
            db.delete(db.get(Client, cid2))
        with get_session() as db:
            cid3 = next_id(db, Client.client_id, "CLI")
            # Counter is at 3 even though the table only has CLI0001
            assert cid3 == "CLI0003"

    def test_concurrent_callers_get_unique_ids(self, tmp_path):
        """20 threads each allocate an ID; every result must be unique.

        Uses a file-backed SQLite DB so each thread gets its own
        connection. With the old read-then-allocate scheme this test
        failed (`IntegrityError` on the second insert). With the atomic
        UPSERT, every caller observes its own monotonic value.
        """
        from concurrent.futures import ThreadPoolExecutor

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from wavetest_app.db.session import Base

        db_path = tmp_path / "concurrency.db"
        engine = create_engine(f"sqlite:///{db_path}", future=True)
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)

        N = 20

        def worker(_idx: int) -> str:
            with SessionLocal() as db:
                cid = next_id(db, Client.client_id, "CLI")
                db.add(Client(client_id=cid, company_name=f"co_{_idx}"))
                db.commit()
                return cid

        with ThreadPoolExecutor(max_workers=N) as ex:
            ids = list(ex.map(worker, range(N)))

        assert len(ids) == N
        assert len(set(ids)) == N, f"duplicate IDs: {sorted(ids)}"


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
