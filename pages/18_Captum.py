"""
pages/18_Captum.py — PyTorch attribution via Captum
========================================================

The website matrix lists Captum as the primary tool for **Quality
Inspection** systems (Industry 4.0 / CV). This page is the v0:
tabular IntegratedGradients on a user-uploaded PyTorch classifier.

The same algorithm extends to image input — we just load the tensor,
compute attribution per pixel, and visualise. That CV-specific UI is
a tracked follow-up.
"""

from __future__ import annotations

import io
import time

import numpy as np
import pandas as pd
import streamlit as st

from wavetest_app.audit import record_run
from wavetest_app.auth import require_login
from wavetest_app.ui import page_header, project_picker, risk_pill

st.set_page_config(
    page_title="Captum · waveTest",
    page_icon="🖼",
    layout="wide",
)

require_login()

page_header(
    "🖼 Captum — PyTorch Attribution",
    "Integrated Gradients for any differentiable PyTorch classifier · "
    "complements SHAP / LIME on the Explainability page",
    articles=["13"],
)

project = project_picker()
if project is None:
    st.stop()

st.markdown(
    f"### Project: `{project.project_id}` — "
    f"{project.client.company_name} / {project.project_name}"
)

st.info(
    "Upload a **full pickled PyTorch model** (saved with `torch.save(model, ...)`, "
    "not just a state dict) plus a **numeric test CSV** (no target column needed). "
    "The page wraps the model with Captum's `IntegratedGradients` and reports "
    "per-feature attribution for a chosen test row."
)

# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------
c1, c2 = st.columns(2)
with c1:
    model_file = st.file_uploader(
        "PyTorch model (.pt / .pth — full module, not a state dict)",
        type=["pt", "pth"],
        key="cap_model",
    )
with c2:
    csv_file = st.file_uploader(
        "Test CSV (numeric columns only)",
        type=["csv"],
        key="cap_csv",
    )

target_class = st.number_input(
    "Target class index for attribution",
    min_value=0, value=1, step=1, key="cap_class",
    help="Captum attributes the prediction toward this class label. "
         "For binary classification, 1 = positive class.",
)
n_steps = st.slider(
    "Integration steps (more = smoother attribution, slower)",
    min_value=10, max_value=200, value=50, step=10, key="cap_steps",
)

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if st.button(
    "Compute attribution",
    type="primary",
    key="cap_run",
    disabled=(model_file is None or csv_file is None),
):
    try:
        import torch
        from captum.attr import IntegratedGradients

        with st.spinner("Loading model + computing IntegratedGradients…"):
            # Load the model on CPU; Captum wraps any differentiable
            # nn.Module. weights_only=False permits the legacy
            # torch.save(model) format.
            model = torch.load(
                io.BytesIO(model_file.getvalue()),
                map_location="cpu",
                weights_only=False,
            )
            model.eval()

            df = pd.read_csv(io.BytesIO(csv_file.getvalue()))
            feature_names = list(df.columns)
            X = torch.tensor(
                df.to_numpy(), dtype=torch.float32, requires_grad=True,
            )

            # Predict + IntegratedGradients on every row.
            t0 = time.time()
            with torch.no_grad():
                preds = model(X)
            ig = IntegratedGradients(model)
            attributions = ig.attribute(
                X,
                target=int(target_class),
                n_steps=int(n_steps),
            )
            duration = time.time() - t0

        # Aggregate across rows + per-row drill-down
        attr_np = attributions.detach().cpu().numpy()
        global_importance = pd.DataFrame(
            {
                "Feature":         feature_names,
                "Mean |attr|":     np.abs(attr_np).mean(axis=0),
                "Mean attr":       attr_np.mean(axis=0),
            }
        ).sort_values("Mean |attr|", ascending=False)

        st.markdown("#### Global feature importance (Integrated Gradients)")
        st.dataframe(
            global_importance, hide_index=True, use_container_width=True,
        )

        # Per-row inspection
        st.markdown("#### Per-row attribution")
        row_idx = st.number_input(
            "Row index",
            min_value=0, max_value=len(df) - 1, value=0, step=1,
            key="cap_row",
        )
        per_row = pd.DataFrame(
            {
                "Feature":     feature_names,
                "Value":       df.iloc[int(row_idx)].to_numpy(),
                "Attribution": attr_np[int(row_idx)],
            }
        )
        st.dataframe(per_row, hide_index=True, use_container_width=True)
        st.caption(
            f"Predicted logits for row {int(row_idx)}: "
            f"{preds[int(row_idx)].detach().tolist()}"
        )

        st.markdown(
            risk_pill(
                "Captum",
                f"{len(df)} rows in {duration:.1f}s",
                "info",
            ),
            unsafe_allow_html=True,
        )
        record_run(
            project=project, module="captum",
            status=f"IG {len(df)} rows",
            status_color="info",
            status_detail=(
                f"target_class={int(target_class)} steps={int(n_steps)}"
            ),
            duration_seconds=duration,
        )
    except Exception as exc:
        st.error(
            f"Captum attribution failed: {type(exc).__name__}: {exc}"
        )
