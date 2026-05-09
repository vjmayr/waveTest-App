"""
pages/13_Cybersecurity.py — Art. 15(5) cybersecurity questionnaire
======================================================================

One cybersecurity plan per project. Eight yes/partial/no checkpoints
covering threat modelling, SBOM hygiene, penetration testing, AI-
specific attack vectors (data poisoning, adversarial inputs, privacy
attacks), access controls, and incident response. Markdown export for
the customer file.
"""

from __future__ import annotations

import streamlit as st
import io
import pickle
import time

import numpy as np
import pandas as pd
from sqlalchemy import select

from wavetest_app._time import utc_now
from wavetest_app.audit import record_run
from wavetest_app.auth import current_username, require_login
from wavetest_app.cybersecurity import (
    ANSWERS,
    CHECKPOINTS,
    compute_compliance_percent,
    status_color,
    to_markdown,
)
from wavetest_app.db.ids import next_id
from wavetest_app.db.models import CybersecurityPlan
from wavetest_app.db.session import get_session
from wavetest_app.ui import (
    page_header, project_picker, risk_pill, show_recommendations,
)

st.set_page_config(
    page_title="Cybersecurity · waveTest",
    page_icon="🔐",
    layout="wide",
)

require_login()

page_header(
    "🔐 Cybersecurity Plan",
    "EU AI Act Article 15(5) — resilience against attempts to alter use, outputs, or performance",
    articles=["15"],
)

project = project_picker()
if project is None:
    st.stop()

st.markdown(
    f"### Project: `{project.project_id}` — "
    f"{project.client.company_name} / {project.project_name}"
)

# ---------------------------------------------------------------------------
# Load existing plan
# ---------------------------------------------------------------------------
with get_session() as db:
    existing = db.scalars(
        select(CybersecurityPlan)
        .where(CybersecurityPlan.project_id == project.project_id)
    ).first()
    if existing:
        plan = {
            "plan_id":                     existing.plan_id,
            "threat_model_documented":     existing.threat_model_documented,
            "sbom_maintained":             existing.sbom_maintained,
            "pentest_performed":           existing.pentest_performed,
            "data_poisoning_controls":     existing.data_poisoning_controls,
            "adversarial_input_controls":  existing.adversarial_input_controls,
            "privacy_attack_controls":     existing.privacy_attack_controls,
            "access_controls_documented":  existing.access_controls_documented,
            "incident_response_playbook":  existing.incident_response_playbook,
            "pentest_last_date":           existing.pentest_last_date,
            "threat_model_notes":          existing.threat_model_notes,
            "open_findings":               existing.open_findings,
            "mitigation_plan":             existing.mitigation_plan,
            "next_review_date":            existing.next_review_date,
            "compliance_percent":          existing.compliance_percent,
            "created_by":                  existing.created_by,
            "created_at":                  existing.created_at,
            "updated_at":                  existing.updated_at,
        }
    else:
        plan = None

# ---------------------------------------------------------------------------
# Status pills
# ---------------------------------------------------------------------------
if plan is not None:
    pct = plan["compliance_percent"]
    pills = (
        risk_pill("Compliance", f"{pct:.0f}%", status_color(pct)) +
        risk_pill(
            "Last pentest",
            plan["pentest_last_date"].isoformat()
            if plan["pentest_last_date"] else "—",
            "info" if plan["pentest_last_date"] else "warning",
        ) +
        risk_pill(
            "Last updated",
            plan["updated_at"].strftime("%Y-%m-%d"),
            "info",
        )
    )
    st.markdown(pills, unsafe_allow_html=True)
else:
    st.info(
        "No cybersecurity plan recorded for this project yet. The "
        "questions below cover Article 15(5) — both classical infosec "
        "hygiene and AI-specific attacks (data poisoning, adversarial "
        "inputs, privacy attacks)."
    )

# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------
defaults = plan or {
    "threat_model_documented":    "no",
    "sbom_maintained":            "no",
    "pentest_performed":          "no",
    "data_poisoning_controls":    "no",
    "adversarial_input_controls": "no",
    "privacy_attack_controls":    "no",
    "access_controls_documented": "no",
    "incident_response_playbook": "no",
    "pentest_last_date":          None,
    "threat_model_notes":         "",
    "open_findings":              "",
    "mitigation_plan":            "",
    "next_review_date":           None,
}

with st.form("cybersec_form"):
    st.markdown("### Article 15(5) checkpoints")

    answers: dict[str, str] = {}
    for field, label, ref, helptext in CHECKPOINTS:
        idx = ANSWERS.index(defaults.get(field, "no"))
        answers[field] = st.radio(
            f"**{label}** — _Art. {ref}_",
            ANSWERS,
            index=idx,
            horizontal=True,
            key=f"cs_{field}",
            help=helptext,
            format_func=lambda x: {
                "yes":     "✅ Yes",
                "partial": "🟡 Partial",
                "no":      "❌ No",
            }[x],
        )

    st.markdown("### Threat model + dates")
    cc1, cc2 = st.columns(2)
    with cc1:
        threat_model_notes = st.text_area(
            "Threat-model notes",
            value=defaults["threat_model_notes"],
            height=120,
            help="Top assets, top adversaries, top attack surfaces. "
                 "Reference the project's STRIDE / LINDDUN doc if any.",
        )
        pentest_last_date = st.date_input(
            "Last pentest date",
            value=defaults["pentest_last_date"],
        )
    with cc2:
        open_findings = st.text_area(
            "Open findings",
            value=defaults["open_findings"],
            height=120,
        )
        next_review_date = st.date_input(
            "Next review date",
            value=defaults["next_review_date"],
        )

    mitigation_plan = st.text_area(
        "Mitigation plan",
        value=defaults["mitigation_plan"],
        height=100,
    )

    if st.form_submit_button("Save plan", type="primary"):
        new_pct = compute_compliance_percent(answers)
        with get_session() as db:
            target = db.scalars(
                select(CybersecurityPlan)
                .where(CybersecurityPlan.project_id == project.project_id)
            ).first()
            if target is None:
                pid = next_id(db, CybersecurityPlan.plan_id, "CSP")
                target = CybersecurityPlan(
                    plan_id=pid,
                    project_id=project.project_id,
                    created_by=current_username() or "system",
                )
                db.add(target)
            for field in (
                "threat_model_documented", "sbom_maintained",
                "pentest_performed", "data_poisoning_controls",
                "adversarial_input_controls", "privacy_attack_controls",
                "access_controls_documented", "incident_response_playbook",
            ):
                setattr(target, field, answers[field])
            target.pentest_last_date = pentest_last_date
            target.threat_model_notes = threat_model_notes.strip()
            target.open_findings = open_findings.strip()
            target.mitigation_plan = mitigation_plan.strip()
            target.next_review_date = next_review_date
            target.compliance_percent = new_pct
            target.updated_at = utc_now()

        record_run(
            project=project, module="cybersecurity",
            status=f"{new_pct:.0f}%",
            status_color=status_color(new_pct),
            status_detail="Art. 15(5) cybersecurity plan saved",
        )
        st.success(f"Plan saved — Art. 15(5) compliance: **{new_pct:.0f}%**")
        st.rerun()

# ---------------------------------------------------------------------------
# Recommendations + download
# ---------------------------------------------------------------------------
if plan is not None:
    st.divider()
    st.subheader("Recommendations")
    recs = []
    for field, label, ref, _help in CHECKPOINTS:
        a = plan[field]
        if a == "no":
            recs.append(
                f"❌ **{label}** (Art. {ref}) is missing — flag this as a "
                f"high-risk gap and assign an owner."
            )
        elif a == "partial":
            recs.append(
                f"🟡 **{label}** (Art. {ref}) is partial — document the "
                f"gap and the upgrade path."
            )
    if not recs:
        st.success(
            "All Article 15(5) checkpoints are at YES — full v0 compliance. "
            "Active adversarial testing (ART-based FGSM/PGD/etc.) is the "
            "next layer; tracked in HANDOVER."
        )
    else:
        show_recommendations(recs)

    st.divider()
    st.subheader("Export")
    md = to_markdown(
        plan,
        project_label=f"{project.client.company_name} / {project.project_name}",
    )
    st.download_button(
        "⬇ Download cybersecurity plan (Markdown)",
        data=md,
        file_name=f"cybersecurity_plan_{project.project_id}.md",
        mime="text/markdown",
    )

# ---------------------------------------------------------------------------
# Active adversarial testing — IBM ART HopSkipJump (decision-based,
# blackbox; works on any classifier with .predict() — no gradient access
# required, no PyTorch / TF needed for a sklearn pipeline).
# ---------------------------------------------------------------------------
st.divider()
with st.expander(
    "🎯 Active adversarial testing (IBM ART)", expanded=False,
):
    st.caption(
        "Wraps the uploaded model with `art.estimators.SklearnClassifier` "
        "and runs **HopSkipJump** — a decision-based, blackbox evasion "
        "attack — against a sample of the test set. Reports how much the "
        "accuracy drops and the L2 perturbation magnitude needed to flip "
        "predictions. This is the active-testing layer the v0 questionnaire "
        "above asks the team about (`adversarial_input_controls`)."
    )

    art_cols = st.columns(2)
    with art_cols[0]:
        art_model_file = st.file_uploader(
            "Pickled model (.pkl / .joblib) — must implement `predict`",
            type=["pkl", "pickle", "joblib"],
            key="art_model",
        )
        art_target = st.text_input(
            "Target column", value="target", key="art_target",
        )
    with art_cols[1]:
        art_csv_file = st.file_uploader(
            "Test CSV (features + target)", type=["csv"], key="art_csv",
        )
        art_n_samples = st.number_input(
            "Samples to attack", 1, 50, 10, 1, key="art_n",
            help="Each sample needs many model queries — stay small "
                 "while exploring.",
        )

    if st.button(
        "Run HopSkipJump attack",
        type="primary",
        key="art_run",
        disabled=(art_model_file is None or art_csv_file is None),
    ):
        try:
            from art.attacks.evasion import HopSkipJump
            from art.estimators.classification import SklearnClassifier
            from sklearn.metrics import accuracy_score

            model = pickle.loads(art_model_file.getvalue())
            test_df = pd.read_csv(io.BytesIO(art_csv_file.getvalue()))
            if art_target not in test_df.columns:
                st.error(
                    f"Target column `{art_target}` not in CSV. "
                    f"Got: {list(test_df.columns)}"
                )
                st.stop()

            feature_cols = [c for c in test_df.columns if c != art_target]
            X = test_df[feature_cols].head(int(art_n_samples)).to_numpy()
            y = test_df[art_target].head(int(art_n_samples)).to_numpy()

            with st.spinner("Wrapping model + running HopSkipJump…"):
                clip_lo = float(np.min(X))
                clip_hi = float(np.max(X))
                clf = SklearnClassifier(
                    model=model, clip_values=(clip_lo, clip_hi),
                )
                attack = HopSkipJump(
                    classifier=clf,
                    max_iter=10,
                    max_eval=200,
                    init_eval=20,
                    init_size=20,
                    targeted=False,
                )
                t0 = time.time()
                X_adv = attack.generate(x=X.astype(float))
                duration = time.time() - t0

            orig_pred = model.predict(X)
            adv_pred = model.predict(X_adv)
            orig_acc = accuracy_score(y, orig_pred)
            adv_acc = accuracy_score(y, adv_pred)
            success_rate = float(np.mean(orig_pred != adv_pred))
            mean_l2 = float(np.linalg.norm(X_adv - X, axis=1).mean())

            from wavetest_app.ui import risk_pill

            attack_color = (
                "ok" if success_rate < 0.20 else
                "warning" if success_rate < 0.50 else "critical"
            )
            pills = (
                risk_pill(
                    "Original accuracy", f"{orig_acc:.0%}", "info",
                ) +
                risk_pill(
                    "Adversarial accuracy", f"{adv_acc:.0%}", attack_color,
                ) +
                risk_pill(
                    "Attack success rate", f"{success_rate:.0%}",
                    attack_color,
                ) +
                risk_pill(
                    "Mean L2 perturbation", f"{mean_l2:.3f}",
                    "info",
                )
            )
            st.markdown(pills, unsafe_allow_html=True)
            st.caption(
                f"{int(art_n_samples)} samples attacked in {duration:.1f}s. "
                f"`success_rate >= 50%` is critical — the model's "
                f"decision boundary is highly exploitable. "
                f"Recommend adversarial training, input filtering, or "
                f"defensive distillation."
            )
            record_run(
                project=project, module="cybersecurity",
                status=f"ART attack: {success_rate:.0%} success",
                status_color=attack_color,
                status_detail=(
                    f"HopSkipJump on {int(art_n_samples)} samples; "
                    f"acc {orig_acc:.0%} → {adv_acc:.0%}, "
                    f"L2 {mean_l2:.2f}"
                ),
                duration_seconds=duration,
            )
        except Exception as exc:
            st.error(
                f"ART attack failed: {type(exc).__name__}: {exc}"
            )
