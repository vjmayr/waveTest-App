"""
scripts/import_console_json.py — One-shot JSON → SQLite migration
====================================================================

Reads the four JSON databases the original waveImpact Console maintained
(``clients_database.json``, ``systems_database.json``, ``projects_database.json``,
``project_types_database.json``) and writes their contents into the new SQLite
database.

Idempotent: re-running the script updates existing rows in place. Safe to use
during development to refresh the DB after manual edits to the JSON files.

Usage:
    python scripts/import_console_json.py [--toolchain PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

# Make src/ importable when running the script directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wavetest_app._time import utc_now  # noqa: E402
from wavetest_app.config import DEFAULT_TOOLCHAIN_ROOT  # noqa: E402
from wavetest_app.db.models import (  # noqa: E402
    Client, Project, ProjectType, System,
)
from wavetest_app.db.session import get_session, init_db  # noqa: E402


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _load_json(path: Path) -> dict:
    if not path.exists():
        print(f"  ⚠️  Missing: {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _import_project_types(data: dict, db, dry_run: bool) -> int:
    n = 0
    for type_id, info in data.items():
        existing = db.get(ProjectType, type_id)
        attrs = dict(
            type_id=type_id,
            type_name=info.get("type_name", type_id),
            description=info.get("description", "") or "",
            standard_services=info.get("standard_services", []),
            is_default=bool(info.get("is_default", False)),
            created_date=_parse_dt(info.get("created_date")) or utc_now(),
            updated_date=_parse_dt(info.get("updated_date")) or utc_now(),
        )
        if existing:
            for k, v in attrs.items():
                setattr(existing, k, v)
        elif not dry_run:
            db.add(ProjectType(**attrs))
        n += 1
    return n


def _import_clients(data: dict, db, dry_run: bool) -> int:
    n = 0
    for client_id, info in data.items():
        attrs = dict(
            client_id=client_id,
            company_name=info.get("company_name", client_id),
            country=info.get("country"),
            languages=info.get("languages", ["en"]),
            folder_path=info.get("folder_path"),
            created_date=_parse_dt(info.get("created_date")) or utc_now(),
        )
        existing = db.get(Client, client_id)
        if existing:
            for k, v in attrs.items():
                setattr(existing, k, v)
        elif not dry_run:
            db.add(Client(**attrs))
        n += 1
    return n


def _import_systems(data: dict, db, dry_run: bool) -> int:
    n = 0
    for system_id, info in data.items():
        # Strip the dynamic fields into classification_data
        stable = {"system_id", "client_id", "system_name", "description",
                  "classification_date"}
        classification_data = {k: v for k, v in info.items() if k not in stable}
        attrs = dict(
            system_id=system_id,
            client_id=info.get("client_id"),
            system_name=info.get("system_name", system_id),
            description=info.get("description", "") or "",
            classification_date=_parse_dt(info.get("classification_date")),
            classification_data=classification_data,
        )
        if not attrs["client_id"]:
            print(f"  ⚠️  System {system_id} has no client_id — skipping")
            continue
        existing = db.get(System, system_id)
        if existing:
            for k, v in attrs.items():
                setattr(existing, k, v)
        elif not dry_run:
            db.add(System(**attrs))
        n += 1
    return n


def _import_projects(data: dict, db, dry_run: bool) -> int:
    n = 0
    for project_id, info in data.items():
        attrs = dict(
            project_id=project_id,
            client_id=info.get("client_id"),
            project_type_id=info.get("project_type_id"),
            project_name=info.get("project_name", project_id),
            project_type=info.get("project_type", ""),
            project_type_description=info.get("project_type_description", "") or "",
            standard_services=info.get("standard_services", []),
            description=info.get("description", "") or "",
            start_date=_parse_date(info.get("start_date")),
            folder_path=info.get("folder_path"),
            status=info.get("status", "active"),
            created_date=_parse_dt(info.get("created_date")) or utc_now(),
        )
        if not attrs["client_id"]:
            print(f"  ⚠️  Project {project_id} has no client_id — skipping")
            continue
        existing = db.get(Project, project_id)
        if existing:
            for k, v in attrs.items():
                setattr(existing, k, v)
        elif not dry_run:
            db.add(Project(**attrs))
        n += 1
    return n


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--toolchain", type=Path, default=DEFAULT_TOOLCHAIN_ROOT,
        help=f"Path to the RAI-TOOLCHAIN checkout "
             f"(default: {DEFAULT_TOOLCHAIN_ROOT})",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Read and validate the JSON files without writing.")
    args = parser.parse_args()

    console = args.toolchain / "waveImpact_ClientManagement"
    if not console.exists():
        print(f"❌ waveImpact_ClientManagement not found at: {console}")
        return 1

    print(f"Reading from: {console}")
    if args.dry_run:
        print("(dry run — no DB writes)")

    init_db()
    files = {
        "project_types": _load_json(console / "project_types_database.json"),
        "clients":       _load_json(console / "clients_database.json"),
        "systems":       _load_json(console / "systems_database.json"),
        "projects":      _load_json(console / "projects_database.json"),
    }

    with get_session() as db:
        n_pt   = _import_project_types(files["project_types"], db, args.dry_run)
        n_cli  = _import_clients(      files["clients"],       db, args.dry_run)
        n_sys  = _import_systems(      files["systems"],       db, args.dry_run)
        n_prj  = _import_projects(     files["projects"],      db, args.dry_run)

    print()
    print(f"  ✓ Project types: {n_pt}")
    print(f"  ✓ Clients:       {n_cli}")
    print(f"  ✓ Systems:       {n_sys}")
    print(f"  ✓ Projects:      {n_prj}")
    print(f"\n✅ Import {'simulated' if args.dry_run else 'complete'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
