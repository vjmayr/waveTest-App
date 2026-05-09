"""
scripts/auth_set_role.py — change a user's roles without touching their password
=================================================================================

Usage::

    python scripts/auth_set_role.py --username jdoe --role admin
    python scripts/auth_set_role.py --username jdoe --role analyst,admin

Multiple roles are comma-separated. The user's password and other fields
are untouched. Refresh the Streamlit page after running — the auth
helper re-reads ``auth/users.yaml`` on every page render.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import yaml  # noqa: E402

from wavetest_app.config import AUTH_USERS_PATH  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Change a user's roles in auth/users.yaml.",
    )
    parser.add_argument("--username", required=True)
    parser.add_argument(
        "--role", required=True,
        help="Single role or comma-separated list (e.g. 'admin' or "
             "'analyst,admin').",
    )
    args = parser.parse_args()

    if not AUTH_USERS_PATH.exists():
        print(f"ERROR: {AUTH_USERS_PATH} not found. "
              f"Bootstrap a user first via auth_add_user.py.",
              file=sys.stderr)
        return 1

    with AUTH_USERS_PATH.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    users = cfg.get("credentials", {}).get("usernames", {})
    if args.username not in users:
        print(f"ERROR: user `{args.username}` not found. "
              f"Existing: {sorted(users)}", file=sys.stderr)
        return 1

    new_roles = [r.strip() for r in args.role.split(",") if r.strip()]
    if not new_roles:
        print("ERROR: at least one role is required.", file=sys.stderr)
        return 1

    users[args.username]["roles"] = new_roles
    with AUTH_USERS_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False)

    print(f"✅ {args.username}: roles → {new_roles}")
    print("Refresh the Streamlit page to pick up the change "
          "(no restart needed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
