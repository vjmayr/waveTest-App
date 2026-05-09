"""
scripts/auth_add_user.py — bootstrap or add an analyst to auth/users.yaml
=============================================================================

Run interactively to add a user::

    python scripts/auth_add_user.py
    Username: jdoe
    Email:    jdoe@example.com
    Name:     John Doe
    Password: ********

Or non-interactively::

    python scripts/auth_add_user.py --username jdoe --email jdoe@example.com \\
        --name "John Doe" --password 's3cr3t'

The first run creates ``auth/users.yaml`` with a freshly-generated random
``cookie.key``; subsequent runs append to it.
"""

from __future__ import annotations

import argparse
import getpass
import secrets
import sys
from pathlib import Path

# Make src/ importable when running the script directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import streamlit_authenticator as stauth  # noqa: E402
import yaml  # noqa: E402

from wavetest_app.config import AUTH_USERS_PATH  # noqa: E402


def _new_cookie_block() -> dict:
    return {
        "name": "wavetest_auth",
        "key": secrets.token_hex(32),
        "expiry_days": 30,
    }


def _load_or_init() -> dict:
    if AUTH_USERS_PATH.exists():
        with AUTH_USERS_PATH.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}
    cfg.setdefault("cookie", _new_cookie_block())
    cfg.setdefault("credentials", {"usernames": {}})
    cfg["credentials"].setdefault("usernames", {})
    return cfg


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Add a user to auth/users.yaml."
    )
    parser.add_argument("--username")
    parser.add_argument("--email")
    parser.add_argument(
        "--name",
        help="Display name. Will be split on whitespace into first/last.",
    )
    parser.add_argument(
        "--password",
        help=(
            "Plaintext password. If omitted, you'll be prompted "
            "(prompt is hidden)."
        ),
    )
    parser.add_argument(
        "--role", default="analyst",
        help="Role label stored alongside the user (default: analyst).",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite the user if they already exist.",
    )
    args = parser.parse_args()

    username = args.username or input("Username: ").strip()
    email = args.email or input("Email:    ").strip()
    name = args.name or input("Name:     ").strip()
    password = args.password or getpass.getpass("Password: ")

    if not (username and email and name and password):
        print("ERROR: username, email, name, and password are all required.",
              file=sys.stderr)
        return 1

    cfg = _load_or_init()
    users = cfg["credentials"]["usernames"]
    if username in users and not args.force:
        print(f"ERROR: user `{username}` already exists. "
              f"Pass --force to overwrite.", file=sys.stderr)
        return 1

    parts = name.split(maxsplit=1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    users[username] = {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "password": stauth.Hasher.hash(password),
        "logged_in": False,
        "failed_login_attempts": 0,
        "roles": [args.role],
    }

    AUTH_USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUTH_USERS_PATH.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False)

    AUTH_USERS_PATH.chmod(0o600)
    print(f"✅ User `{username}` saved to {AUTH_USERS_PATH}")
    print("Restart Streamlit so the cached authenticator picks up the change.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
