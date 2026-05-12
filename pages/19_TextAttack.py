"""
pages/19_TextAttack.py — NLP robustness via TextAttack
==========================================================

The website matrix lists TextAttack as the secondary tool for **Chatbots
(German)** alongside the Custom German NLP Bias Probes. This page
loads a HuggingFace text-classification model, runs an evasion attack
recipe (TextFoolerJin2019 by default) on a small text sample, and
reports the attack success rate.

Heavy: pulls in transformers + nltk + flair via the textattack package.
The first run downloads the chosen HuggingFace model (~250 MB for the
default DistilBERT sentiment model).
"""

from __future__ import annotations

import io
import time

import pandas as pd
import streamlit as st

from wavetest_app.audit import record_run
from wavetest_app.auth import require_login
from wavetest_app.inputs import load_input
from wavetest_app.ui import page_header, project_picker, risk_pill

st.set_page_config(
    page_title="TextAttack · waveTest",
    page_icon="📝",
    layout="wide",
)

require_login()

page_header(
    "📝 TextAttack — NLP Robustness",
    "Adversarial evasion against a HuggingFace text classifier",
    articles=["15", "52"],
)

project = project_picker()
if project is None:
    st.stop()

st.markdown(
    f"### Project: `{project.project_id}` — "
    f"{project.client.company_name} / {project.project_name}"
)

st.info(
    "Loads a HuggingFace text-classification model and runs an evasion "
    "attack against it. The first run downloads the model (~250 MB for "
    "the default DistilBERT sentiment checkpoint). Each attacked sample "
    "may take several seconds — keep N small while exploring."
)

# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
# Pre-fill the HF model id from the project's `hf_model_id` slot if set.
# The analyst can still edit before running.
project_hf = load_input(project, "hf_model_id")
if project_hf:
    st.caption(
        f"Pre-filled from the project's `hf_model_id` slot. "
        "Manage in **Project Inputs**."
    )
model_name = st.text_input(
    "HuggingFace model id",
    value=project_hf or "distilbert-base-uncased-finetuned-sst-2-english",
    help="A `transformers` text-classification checkpoint. The default "
         "is binary sentiment (POSITIVE / NEGATIVE).",
)

attack_choice = st.selectbox(
    "Attack recipe",
    [
        "TextFoolerJin2019",
        "DeepWordBugGao2018",
        "BAEGarg2019",
    ],
    help="TextFooler is the most-cited tabular benchmark; DeepWordBug "
         "and BAE are alternatives.",
)

ta_csv_file = st.file_uploader(
    "Optional: CSV with `text` + `label` columns (numeric label). "
    "Leave empty to use a small demo sample.",
    type=["csv"],
    key="ta_csv",
)

n_samples = st.number_input(
    "Samples to attack",
    min_value=1, max_value=20, value=3, step=1, key="ta_n",
    help="Each sample needs many model queries — stay small while exploring. "
         "5–10 is usually enough to demonstrate vulnerability.",
)

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if st.button(
    "Run attack", type="primary", key="ta_run",
):
    try:
        # NLTK depends on SSL-fetched corpora that may have failed at install
        # time on some Macs; ensure they're loaded under a relaxed cert.
        import ssl as _ssl
        _ssl._create_default_https_context = _ssl._create_unverified_context
        import nltk
        for _pkg in ("stopwords", "wordnet", "averaged_perceptron_tagger"):
            try:
                nltk.data.find(f"corpora/{_pkg}")
            except LookupError:
                nltk.download(_pkg, quiet=True)

        from textattack.attack_recipes import (
            BAEGarg2019,
            DeepWordBugGao2018,
            TextFoolerJin2019,
        )
        from textattack.datasets import Dataset
        from textattack.models.wrappers import HuggingFaceModelWrapper
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
        )

        # --- Load HF model + tokenizer
        with st.spinner(f"Loading `{model_name}` (cached after first run)…"):
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSequenceClassification.from_pretrained(
                model_name
            )
            wrapper = HuggingFaceModelWrapper(model, tokenizer)

        # --- Build dataset
        if ta_csv_file is not None:
            df = pd.read_csv(io.BytesIO(ta_csv_file.getvalue()))
            if "text" not in df.columns or "label" not in df.columns:
                st.error(
                    f"CSV must have `text` and `label` columns. "
                    f"Got: {list(df.columns)}"
                )
                st.stop()
            samples = list(zip(
                df["text"].head(int(n_samples)).tolist(),
                df["label"].head(int(n_samples)).astype(int).tolist(),
            ))
        else:
            samples = [
                ("This product is absolutely fantastic and I love it.", 1),
                ("Worst experience I have ever had with a service.", 0),
                ("The food was decent but the wait was long.", 0),
                ("Highly recommend, the team went above and beyond!", 1),
                ("It is what it is. Nothing special.", 0),
            ][: int(n_samples)]

        dataset = Dataset(samples)

        # --- Build the attack
        recipe_cls = {
            "TextFoolerJin2019":  TextFoolerJin2019,
            "DeepWordBugGao2018": DeepWordBugGao2018,
            "BAEGarg2019":        BAEGarg2019,
        }[attack_choice]
        attack = recipe_cls.build(wrapper)

        # --- Run
        with st.spinner(f"Running {attack_choice} on {len(samples)} samples…"):
            t0 = time.time()
            results = []
            for i, (text, label) in enumerate(samples):
                result = attack.attack(text, label)
                results.append((i, text, label, result))
            duration = time.time() - t0

        # --- Aggregate
        n_success = sum(
            1 for _, _, _, r in results
            if type(r).__name__ == "SuccessfulAttackResult"
        )
        n_skipped = sum(
            1 for _, _, _, r in results
            if type(r).__name__ == "SkippedAttackResult"
        )
        success_rate = n_success / max(len(results) - n_skipped, 1)

        attack_color = (
            "ok" if success_rate < 0.20 else
            "warning" if success_rate < 0.50 else "critical"
        )
        pills = (
            risk_pill(
                "Samples", str(len(results)), "info",
            ) +
            risk_pill(
                "Successful attacks",
                f"{n_success} / {len(results) - n_skipped}",
                attack_color,
            ) +
            risk_pill(
                "Success rate", f"{success_rate:.0%}", attack_color,
            ) +
            risk_pill(
                "Skipped (already wrong)", str(n_skipped), "info",
            )
        )
        st.markdown(pills, unsafe_allow_html=True)

        # --- Per-sample details
        st.markdown("#### Per-sample results")
        rows = []
        for i, original, label, r in results:
            kind = type(r).__name__
            adv_text = (
                getattr(getattr(r, "perturbed_result", None),
                        "attacked_text", None)
            )
            adv_str = (
                str(adv_text.text) if adv_text else "—"
            )
            rows.append({
                "#":            i,
                "Outcome":      kind.replace("AttackResult", ""),
                "Label":        label,
                "Original":     (original[:80] + "…")
                                if len(original) > 80 else original,
                "Adversarial":  (adv_str[:80] + "…")
                                if len(adv_str) > 80 else adv_str,
            })
        st.dataframe(rows, hide_index=True, use_container_width=True)

        st.caption(
            f"Attack: **{attack_choice}** · "
            f"Total runtime: {duration:.1f}s. "
            f"`success_rate >= 50%` is critical — the model can be "
            f"flipped by minor word substitutions. Recommend "
            f"adversarial training, input perturbation defenses, or "
            f"ensembling."
        )
        record_run(
            project=project, module="textattack",
            status=f"{attack_choice} {success_rate:.0%}",
            status_color=attack_color,
            status_detail=(
                f"{n_success}/{len(results) - n_skipped} successful, "
                f"{n_skipped} skipped"
            ),
            duration_seconds=duration,
        )
    except Exception as exc:
        st.error(
            f"TextAttack run failed: {type(exc).__name__}: {exc}"
        )
