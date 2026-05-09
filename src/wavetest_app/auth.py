"""
wavetest_app.auth — Authentication gate
==========================================

Thin wrapper around `streamlit-authenticator` so each page can call
``require_login()`` once at the top and trust ``current_username()``
afterwards. The credentials YAML lives at ``auth/users.yaml`` (gitignored);
add users via ``scripts/auth_add_user.py``.
"""

from __future__ import annotations

from typing import Optional

import streamlit as st
import streamlit_authenticator as stauth
import yaml

from wavetest_app.config import AUTH_USERS_PATH


def get_authenticator() -> stauth.Authenticate:
    """Build a fresh Authenticate from ``auth/users.yaml``.

    Not cached: ``streamlit-authenticator`` 0.4 instantiates a Streamlit
    cookie-manager component inside ``Authenticate.__init__``, and
    Streamlit refuses to create widgets inside ``@st.cache_resource``.
    The YAML parse is cheap and edits to the file pick up on the next
    rerun without a server restart.
    """
    if not AUTH_USERS_PATH.exists():
        raise FileNotFoundError(
            f"Auth file not found at {AUTH_USERS_PATH}. "
            "Bootstrap one with `python scripts/auth_add_user.py`."
        )
    with AUTH_USERS_PATH.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    return stauth.Authenticate(
        credentials=cfg["credentials"],
        cookie_name=cfg["cookie"]["name"],
        cookie_key=cfg["cookie"]["key"],
        cookie_expiry_days=float(cfg["cookie"]["expiry_days"]),
        auto_hash=False,  # passwords are pre-hashed by the bootstrap script
    )


def require_login() -> None:
    """Block page execution until the user is logged in.

    Reads the auth cookie (without rendering a form) and falls back to a
    redirect-to-Home prompt if the cookie is missing or the session is
    invalidated. On success also drops a "Signed in as …" caption and a
    logout button into the sidebar so identity is visible from every
    assessment page.

    Call once near the top of every page that should be behind auth.
    Home.py is the exception — it renders the login form itself.
    """
    authenticator = get_authenticator()
    authenticator.login(location="unrendered")

    if not st.session_state.get("authentication_status"):
        st.warning(
            "🔒 Please log in via the **Home** page to use this assessment."
        )
        st.stop()

    # Identity + logout in the sidebar — consistent across every gated page
    with st.sidebar:
        st.caption(f"Signed in as **{st.session_state.get('name', '')}**")
        authenticator.logout(location="sidebar", key="logout_sidebar")


def current_username() -> Optional[str]:
    """Return the authenticated username, or None if not logged in."""
    if not st.session_state.get("authentication_status"):
        return None
    return st.session_state.get("username")


def current_display_name() -> Optional[str]:
    """Return the authenticated user's display name, or None."""
    if not st.session_state.get("authentication_status"):
        return None
    return st.session_state.get("name")


def current_user_roles() -> list[str]:
    """Return the authenticated user's role list, or ``[]`` if not logged in.

    Roles are stored in ``auth/users.yaml`` per user; we re-read the file
    here (cheap, ~10-user file) so role grants take effect on the next
    page render without a Streamlit restart.
    """
    if not st.session_state.get("authentication_status"):
        return []
    username = st.session_state.get("username")
    if not username or not AUTH_USERS_PATH.exists():
        return []
    with AUTH_USERS_PATH.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    user = (
        cfg.get("credentials", {})
           .get("usernames", {})
           .get(username, {})
    )
    return list(user.get("roles", []) or [])


def require_role(role: str) -> None:
    """Block page execution unless the authenticated user has ``role``.

    Calls :func:`require_login` first (so the login gate + sidebar widgets
    still run), then checks the role list. Failure shows a polite error
    + ``st.stop()`` so the rest of the page doesn't render.
    """
    require_login()
    if role not in current_user_roles():
        st.error(
            f"⛔ This page requires the **{role}** role. "
            "Ask an admin to grant it (edit `auth/users.yaml` or re-run "
            "`python scripts/auth_add_user.py --force --role admin --username YOU`)."
        )
        st.stop()
