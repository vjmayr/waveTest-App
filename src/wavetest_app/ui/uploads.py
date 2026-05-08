"""
wavetest_app.ui.uploads — File upload helpers
==================================================

Small wrappers around ``st.file_uploader`` that parse + validate CSVs and
pickled models, returning ready-to-use objects (or ``None`` if the user
hasn't uploaded yet). Used by the assessment pages to accept real client
data alongside the demo-data path.
"""

from __future__ import annotations

import io
import pickle
from typing import Any, List, Optional, Sequence

import pandas as pd
import streamlit as st


def csv_uploader(
    label: str,
    *,
    required_columns: Sequence[str] = (),
    parse_dates: Sequence[str] = (),
    key: str,
    help: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """Upload a CSV; return the parsed DataFrame, or ``None`` if not yet uploaded.

    Validates that ``required_columns`` are all present (case-sensitive) and
    parses any ``parse_dates`` columns as datetimes. Failures surface as
    ``st.error`` and return ``None`` so the page can ``st.stop()``.
    """
    file = st.file_uploader(label, type=["csv"], key=key, help=help)
    if file is None:
        return None

    try:
        df = pd.read_csv(
            io.BytesIO(file.getvalue()),
            parse_dates=list(parse_dates) if parse_dates else None,
        )
    except Exception as exc:
        st.error(f"❌ Could not parse `{file.name}`: {exc}")
        return None

    missing = [c for c in required_columns if c not in df.columns]
    if missing:
        st.error(
            f"❌ `{file.name}` is missing required columns: {missing}\n\n"
            f"Got columns: {list(df.columns)}"
        )
        return None

    st.caption(
        f"✓ Loaded `{file.name}` — {len(df):,} rows × {len(df.columns)} columns"
    )
    return df


def model_uploader(
    label: str,
    *,
    key: str,
    help: Optional[str] = None,
    required_methods: Sequence[str] = ("predict",),
) -> Optional[Any]:
    """Upload a pickled scikit-learn-style model.

    Validates that the unpickled object exposes ``required_methods``
    (e.g. ``predict``, ``predict_proba``). Returns the model or ``None``.
    """
    file = st.file_uploader(label, type=["pkl", "pickle", "joblib"],
                            key=key, help=help)
    if file is None:
        return None

    try:
        # joblib uses a pickle-compatible format; loading via pickle works
        # for the common scikit-learn estimator case
        model = pickle.loads(file.getvalue())
    except Exception as exc:
        st.error(f"❌ Could not unpickle `{file.name}`: {exc}")
        return None

    missing = [m for m in required_methods if not hasattr(model, m)]
    if missing:
        st.error(
            f"❌ Uploaded model is missing required methods: {missing}\n\n"
            f"Got class: {type(model).__name__}"
        )
        return None

    st.caption(f"✓ Loaded model: `{type(model).__name__}` from `{file.name}`")
    return model


def array_csv_uploader(
    label: str,
    *,
    key: str,
    help: Optional[str] = None,
    require_no_target: bool = False,
):
    """Upload a CSV intended to be used as a feature matrix.

    Returns ``(np.ndarray, list[str])`` of (X, feature_names) or ``None``.
    If ``require_no_target=True``, drops a ``target`` / ``y`` column if present.
    """
    df = csv_uploader(label, key=key, help=help)
    if df is None:
        return None
    if require_no_target:
        for tcol in ("target", "y", "label"):
            if tcol in df.columns:
                df = df.drop(columns=[tcol])
    return df.to_numpy(), df.columns.tolist()
