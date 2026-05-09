"""
pages/6_Clients.py — Client administration
==============================================

Create, list, and delete client organisations.
Replaces the original console's Clients tab.
"""

from __future__ import annotations

import streamlit as st
from sqlalchemy import select

from wavetest_app._time import utc_now
from wavetest_app.auth import require_login
from wavetest_app.db.ids import next_id
from wavetest_app.db.models import Client
from wavetest_app.db.session import get_session
from wavetest_app.ui import page_header

st.set_page_config(
    page_title="Clients · waveTest", page_icon="🏢", layout="wide",
)

require_login()

page_header(
    "🏢 Clients",
    "Create and manage client organisations · CLI{NNNN} IDs auto-generated",
)

# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
COUNTRIES = [
    "Germany", "Austria", "Switzerland", "Netherlands", "France",
    "Belgium", "Other EU", "Non-EU",
]
LANGUAGES = ["en", "de", "fr", "nl", "es", "it"]

with st.form("new_client", clear_on_submit=True):
    st.subheader("Register new client")

    c1, c2 = st.columns(2)
    with c1:
        company_name = st.text_input("Company name")
        country      = st.selectbox("Country", COUNTRIES)
    with c2:
        languages = st.multiselect(
            "Languages", LANGUAGES, default=["en"],
            help="Reports are generated in every selected language. 'en' is always included.",
        )

    if st.form_submit_button("Create client", type="primary"):
        if not company_name.strip():
            st.error("Company name is required.")
        else:
            langs = list(languages)
            if "en" not in langs:
                langs.insert(0, "en")
            with get_session() as db:
                client_id = next_id(db, Client.client_id, "CLI")
                db.add(Client(
                    client_id=client_id,
                    company_name=company_name.strip(),
                    country=country,
                    languages=langs,
                    created_date=utc_now(),
                ))
            st.success(f"Created client `{client_id}` — {company_name}")
            st.rerun()

# ---------------------------------------------------------------------------
# List + delete
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Existing clients")

with get_session() as db:
    clients = db.scalars(
        select(Client).order_by(Client.created_date.desc())
    ).all()
    rows = [
        {
            "ID":          c.client_id,
            "Company":     c.company_name,
            "Country":     c.country or "—",
            "Languages":   ", ".join(c.languages or []),
            "Systems":     len(c.systems),
            "Projects":    len(c.projects),
            "Created":     c.created_date.strftime("%Y-%m-%d") if c.created_date else "—",
        }
        for c in clients
    ]

if not rows:
    st.info("No clients yet. Use the form above to create one.")
else:
    st.dataframe(rows, hide_index=True, use_container_width=True)

    st.markdown("##### Delete client")
    st.caption(
        "⚠ Deleting a client cascades to all of its systems and projects. "
        "Generated artefacts on disk are **not** removed."
    )
    delete_id = st.selectbox(
        "Client to delete",
        [c["ID"] + " — " + c["Company"] for c in rows],
        key="del_client_pick",
    )
    confirm = st.checkbox(
        f"Yes, permanently delete `{delete_id.split(' — ')[0]}` and all its systems + projects",
        key="del_client_confirm",
    )
    if st.button("Delete", type="secondary", disabled=not confirm, key="del_client_btn"):
        cid = delete_id.split(" — ")[0]
        with get_session() as db:
            client = db.get(Client, cid)
            if client:
                db.delete(client)
        st.success(f"Deleted `{cid}`.")
        st.rerun()
