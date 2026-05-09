"""
pages/7_Systems.py — AI system classification
================================================

Register an AI system against a client and classify it under the EU AI Act
questionnaire. The classification result (PROHIBITED / HIGH-RISK / LIMITED-RISK
/ MINIMAL-RISK) is stored alongside the raw answers as JSON.
"""

from __future__ import annotations

import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from wavetest_app._time import utc_now
from wavetest_app.auth import require_role
from wavetest_app.classification import (
    ENTITY_TYPES,
    HIGH_RISK_CATEGORIES,
    PROHIBITED_PRACTICES,
    TRANSPARENCY_REQUIREMENTS,
    classify,
)
from wavetest_app.db.ids import next_id
from wavetest_app.db.models import Client, System
from wavetest_app.db.session import get_session
from wavetest_app.ui import page_header

st.set_page_config(
    page_title="Systems · waveTest", page_icon="🤖", layout="wide",
)

require_role("admin")

page_header(
    "🤖 AI Systems",
    "Classify AI systems per the EU AI Act · SYS{NNNN} IDs auto-generated",
)

# ---------------------------------------------------------------------------
# Pre-flight: need at least one client
# ---------------------------------------------------------------------------
with get_session() as db:
    clients = db.scalars(select(Client).order_by(Client.company_name)).all()
    client_options = [(c.client_id, c.company_name) for c in clients]

if not client_options:
    st.warning(
        "No clients exist yet. Create a client on the **Clients** page first."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
with st.form("new_system", clear_on_submit=True):
    st.subheader("Classify new AI system")

    c1, c2 = st.columns(2)
    with c1:
        client_id = st.selectbox(
            "Client",
            options=[cid for cid, _ in client_options],
            format_func=lambda cid: f"{cid} — "
                                    + dict(client_options).get(cid, ""),
        )
        system_name = st.text_input("System name")
        system_description = st.text_area("Description", height=80)

    with c2:
        st.markdown("**Entity & system definition**")
        entity_type = st.radio("Entity type", ENTITY_TYPES, horizontal=True)
        is_ai_system = st.radio(
            "Is this an AI System per EU AI Act definition?",
            ["Yes", "No", "Uncertain"], horizontal=True,
        )
        significant_risk = st.radio(
            "Poses significant risk to health, safety, or fundamental rights?",
            ["Yes", "No", "Uncertain"], horizontal=True,
        )

    st.markdown("**High-risk areas (Annex III)**")
    high_risk_categories = st.multiselect(
        "Tick all that apply", HIGH_RISK_CATEGORIES, default=["None"],
    )

    st.markdown("**Prohibited practices**")
    prohibited_practices = st.multiselect(
        "Tick all that apply", PROHIBITED_PRACTICES, default=["None"],
    )

    st.markdown("**Transparency obligations**")
    transparency_requirements = st.multiselect(
        "Tick all that apply", TRANSPARENCY_REQUIREMENTS, default=["None"],
    )

    technical_details = st.text_area(
        "Technical details",
        placeholder="Model architecture, training data, deployment pipeline…",
        height=80,
    )
    use_case_details = st.text_area(
        "Use case details",
        placeholder="How is the system deployed and used?", height=80,
    )

    if st.form_submit_button("Classify and save", type="primary"):
        if not system_name.strip():
            st.error("System name is required.")
        else:
            classification_payload = {
                "entity_type":               entity_type,
                "is_ai_system":              is_ai_system,
                "high_risk_categories":      high_risk_categories,
                "prohibited_practices":      prohibited_practices,
                "significant_risk":          significant_risk,
                "transparency_requirements": transparency_requirements,
                "technical_details":         technical_details,
                "use_case_details":          use_case_details,
            }
            results = classify(classification_payload)

            with get_session() as db:
                system_id = next_id(db, System.system_id, "SYS")
                db.add(System(
                    system_id=system_id,
                    client_id=client_id,
                    system_name=system_name.strip(),
                    description=system_description.strip(),
                    classification_date=utc_now(),
                    classification_data={**classification_payload, "results": results},
                ))

            st.success(
                f"Created system `{system_id}` — **{results['overall_status']}**"
            )
            with st.expander("Detailed classification result", expanded=True):
                st.json(results)
            st.rerun()

# ---------------------------------------------------------------------------
# List + delete
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Existing systems")

with get_session() as db:
    systems = db.scalars(
        select(System)
        .options(joinedload(System.client))
        .order_by(System.classification_date.desc())
    ).all()
    rows = [
        {
            "ID":           s.system_id,
            "Name":         s.system_name,
            "Client":       f"{s.client_id} — {s.client.company_name}",
            "Status":       (s.classification_data.get("results", {}) or {})
                            .get("overall_status", "Not classified"),
            "Classified":   s.classification_date.strftime("%Y-%m-%d")
                            if s.classification_date else "—",
        }
        for s in systems
    ]

if not rows:
    st.info("No systems classified yet.")
else:
    st.dataframe(rows, hide_index=True, use_container_width=True)

    st.markdown("##### Delete system")
    delete_id = st.selectbox(
        "System to delete",
        [r["ID"] + " — " + r["Name"] for r in rows],
        key="del_sys_pick",
    )
    confirm = st.checkbox(
        f"Yes, permanently delete `{delete_id.split(' — ')[0]}`",
        key="del_sys_confirm",
    )
    if st.button("Delete", disabled=not confirm, key="del_sys_btn"):
        sid = delete_id.split(" — ")[0]
        with get_session() as db:
            sys_obj = db.get(System, sid)
            if sys_obj:
                db.delete(sys_obj)
        st.success(f"Deleted `{sid}`.")
        st.rerun()
