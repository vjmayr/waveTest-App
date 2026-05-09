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


@st.cache_resource
def get_authenticator() -> stauth.Authenticate:
    """Build (or return the cached) Authenticate from auth/users.yaml.

    Cached for the lifetime of the Streamlit process. If you edit the YAML
    (add a user, rotate a password) restart the Streamlit server so the
    cache picks the new file up.
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
