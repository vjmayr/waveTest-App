# Input Data Specification

Companion to [AUDIT_MANUAL.md](AUDIT_MANUAL.md). The manual tells the analyst
**how** to run an assessment; this document is the rigorous **contract** for
the input data each module accepts — column names, value ranges, file
formats, validation rules — so a client knows exactly what to ship before
the engagement starts.

Section [§Z](#z-feasibility-central-project-level-input-store) at the end
analyses how we could centralise these inputs at the Customer → Project
level (one upload, all modules pick it up).

---

## Table of contents

1. At-a-glance matrix
2. Cross-cutting conventions
3. Data Quality (Art. 10 + GDPR Art. 9)
4. Bias Detection (Art. 10 / 13 / 61)
5. Explainability (Art. 13)
6. Logging Framework (Art. 12 / 72)
7. Performance Monitoring (Art. 15 / 72)
8. Cybersecurity — active ART testing (Art. 15(5))
9. Captum (Art. 13, CV / PyTorch)
10. TextAttack (Art. 15, NLP)
11. Sustainability (voluntary)
12. Combined Report (orchestrates 1–7)
13. Pure-questionnaire modules — no inputs
14. **Feasibility: central Project-level input store** — see [§Z](#z-feasibility-central-project-level-input-store)

---

## 1. At-a-glance matrix

Every cell is one upload widget on the corresponding page today.

| Module | Tabular CSV | Pickled sklearn model | PyTorch model | HF model id | JSON config |
| --- | --- | --- | --- | --- | --- |
| Data Quality | ✅ any tabular | — | — | — | optional **target_population.json** |
| Bias Detection | ✅ `y_true`, `y_pred` + privileged-group columns | — | — | — | **privileged_groups.json** |
| Explainability | ✅ test CSV (features + target); optional training CSV | ✅ `.pkl` / `.joblib` | — | — | — |
| Logging Framework | — | — | — | — | — |
| Performance Monitoring | ✅ `timestamp`, `y_true`, `y_pred`, optional `confidence` + arbitrary features | — | — | — | — |
| Cybersecurity (ART panel) | ✅ test CSV (features + target) | ✅ `.pkl` / `.joblib` | — | — | — |
| Captum | ✅ numeric features only | — | ✅ `.pt` / `.pth` (full pickled module) | — | — |
| TextAttack | ✅ optional `text`, `label` | — | — | ✅ HF model id (string) | — |
| Sustainability | — | — | — | — | — (only numeric form fields) |
| Risk Register, Human Oversight, Cybersecurity (questionnaire), Incidents, Right to Explanation, Model Card | — | — | — | — | — |

---

## 2. Cross-cutting conventions

These apply to **every** upload across every module unless an individual
section says otherwise.

### 2.1 CSV

- **Encoding**: UTF-8. The CSV uploader uses `pandas.read_csv` with default
  encoding; non-UTF-8 files fail with `UnicodeDecodeError`. Re-export from
  Excel with *Save as → CSV UTF-8*.
- **Delimiter**: comma (`,`). Semicolon-delimited European CSVs need to be
  re-exported.
- **Header row**: required. The first non-empty line is treated as the column
  names. Column names are **case-sensitive** — `y_true` ≠ `Y_True`.
- **Missing values**: encoded as empty cells, `NA`, `NaN`, or `null`.
  Don't use sentinel numbers like `-1` or `999` — they're invisible to the
  missing-value checks.
- **Decimal separator**: dot (`.`). Comma-decimal European CSVs need
  re-export.
- **Date columns**: ISO 8601 (`YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS`). The
  Monitoring page passes the `timestamp` column through `parse_dates`; other
  pages leave date columns as strings.
- **Maximum recommended size**: ~50 MB. Streamlit's default upload limit is
  200 MB; above ~50 MB Pandas / SHAP / Fairlearn start being noticeably slow.

### 2.2 Pickled scikit-learn models

- **File extension**: `.pkl`, `.pickle`, or `.joblib`. The uploader treats
  all three identically (uses Python's `pickle.loads`).
- **What gets pickled**: the **fitted estimator**, not a state dict. Example
  in the customer's training script:
  ```python
  import pickle
  with open("model.pkl", "wb") as f:
      pickle.dump(model, f)
  ```
- **Required methods**: `.predict()` is universal; **`predict_proba()`** is
  required by Explainability, Cybersecurity (ART), and LIME.
- **Python / scikit-learn version**: a pickle created with scikit-learn
  X.Y must be loaded with scikit-learn X.Y (or close — sklearn's pickle
  compatibility is "best-effort across minor versions"). Mismatches surface as
  cryptic `AttributeError` or `ModuleNotFoundError`.
- **Pipelines work**: a `sklearn.pipeline.Pipeline(...)` ending in a
  classifier is a valid upload.

### 2.3 PyTorch models

- **File extension**: `.pt` or `.pth`.
- **Format**: **full pickled `nn.Module`** (saved via `torch.save(model, path)`),
  **NOT** a state dict (`torch.save(model.state_dict(), path)`). If the file
  only contains state-dict weights, the Captum page has no module to call.
- **Architecture**: must be a `torch.nn.Module` subclass. Any layers / loss
  functions are fine.
- **Device**: the page loads to CPU regardless of where the model was
  trained — `torch.load(path, map_location="cpu")`.

### 2.4 JSON configuration blocks

Two pages need a small JSON document pasted into a text area
(target_population on Data Quality, privileged_groups on Bias). Both expect
**valid JSON**, not a Python dict literal. The distinction matters:

| ✅ Valid JSON | ❌ Python literal |
| --- | --- |
| `{"M": 0.49}` | `{"M": 0.49,}` (trailing comma) |
| `{"M": 0.49, "F": 0.51}` | `{'M': 0.49}` (single quotes) |
| `{"x": false}` | `{"x": False}` (capitalised bool) |
| `{"x": null}` | `{"x": None}` |

The pages run `json.loads(...)` and surface `JSONDecodeError` inline.

### 2.5 Audit trail

Every successful run writes one row to `audit_log` with the actor's
username, the module, the run duration, and a short status detail.
Failed runs (when wrapped in `audit_assessment(...)`) write a `FAILED`
entry. See §6 of the Audit Manual for how to read the Audit Log page.

---

## 3. Data Quality — Art. 10 + GDPR Art. 9

**Page**: [pages/1_Data_Quality.py](../pages/1_Data_Quality.py)
**Toolchain**: `wavetest_dataquality`
**EU AI Act**: Article 10 (data governance) + GDPR Article 9 (special-category data)

### 3.1 Required inputs

| Input | Type | Notes |
| --- | --- | --- |
| Dataset | CSV (any tabular) | No required columns — every column is analysed. |
| Target population | JSON (optional) | Drives the chi-square representativeness test. If omitted, only the missingness / outlier / duplicate checks run. |

### 3.2 Dataset schema

There is no fixed schema. The module ingests whatever columns are present:

- **Any column** is checked for missing-value rate, outlier rate (numeric
  columns only, via Z-score), and contribution to duplicate rows.
- **Column names matching GDPR Art. 9 keywords** are flagged automatically.
  The keyword list (from `wavetest_dataquality`) includes — case-insensitive:
  `race`, `ethnic`, `religion`, `political`, `union`, `genetic`, `biometric`,
  `health`, `sex life`, `sexual orientation`, plus German variants
  (`herkunft`, `religion`, `gesundheit`, `weltanschauung`, …).
- **Direct identifiers** (column names like `name`, `email`, `phone`,
  `address`, `ssn`, `passport`) are flagged separately as a privacy risk
  in their own right.

### 3.3 target_population.json

A nested JSON dict mapping **column name → category → expected proportion**.
Proportions per column must sum to ≈ 1.0 (the page is tolerant of small
rounding errors).

```json
{
  "gender":      {"M": 0.49, "F": 0.51},
  "age_group":   {"18-30": 0.25, "31-45": 0.35, "46-60": 0.28, "60+": 0.12},
  "nationality": {"DE": 0.85, "EU": 0.12, "Non-EU": 0.03}
}
```

For each key in this dict:
- The matching column in the dataset is identified.
- A chi-square test is run against the expected proportions.
- The page surfaces χ², p-value, sample size, and a REPRESENTATIVE /
  NOT REPRESENTATIVE verdict (`p > 0.05` = representative).

If a key in the JSON has no matching column in the dataset, that key is
silently skipped (and recorded as a recommendation to capture).

### 3.4 Example dataset

```csv
record_id,age,gender,nationality,health_status,credit_score,income,outcome
A001,34,M,DE,Healthy,720,42000,APPROVED
A002,29,F,EU,Healthy,680,38000,APPROVED
A003,55,M,DE,Chronic,640,29000,REJECTED
```

What the module will flag here:
- `health_status` → GDPR Art. 9 hit (the substring `health` matches).
- `record_id` → direct-identifier hit.
- If `target_population.json` includes a `gender` block, a chi-square test
  runs on the M/F split.

### 3.5 Extended profiling

Two opt-in expanders below the main report (notebook 04 uses both):

- **ydata-profiling**: full automatic dataset profile as a downloadable
  HTML report. Sampled to keep runtime sensible; the page shows a sample-
  size slider (default 2 000 rows).
- **Great Expectations validation**: runs a canned suite (≥95 % non-null on
  every column, every numeric column within its observed min/max). Returns
  per-expectation pass/fail.

Neither requires any extra upload — they consume the dataset that was
already loaded above.

### 3.6 Validation rules / common errors

| Error | Cause | Fix |
| --- | --- | --- |
| `❌ Could not parse <file>.csv: <pandas error>` | Encoding / delimiter mismatch | Re-export as UTF-8 with comma delimiter |
| `Target population JSON is invalid` | Trailing comma, Python-style bool/None, single quotes | See §2.4 |
| Empty representativeness table | No target_population provided **or** none of its keys match a column | Either add the JSON block or rename columns |

---

## 4. Bias Detection — Art. 10 / 13 / 61

**Page**: [pages/2_Bias_Detection.py](../pages/2_Bias_Detection.py)
**Toolchain**: `wavetest_fairness` (AIF360) + in-page Fairlearn panel
**EU AI Act**: Articles 10 (data), 13 (transparency), 61 (post-market)

### 4.1 Required inputs

| Input | Type | Notes |
| --- | --- | --- |
| Predictions CSV | CSV | Must contain `y_true`, `y_pred`, plus one column per protected attribute. |
| Privileged groups | JSON | Defines which value of each protected attribute is *privileged*. |

### 4.2 Predictions CSV schema

| Column | Type | Required | Range / notes |
| --- | --- | --- | --- |
| `y_true` | int or string | ✅ | Ground-truth labels. Binary classification typically `0` / `1`; multi-class as integers; string labels OK as long as they match `y_pred`. |
| `y_pred` | int or string | ✅ | Model predictions, same domain as `y_true`. |
| `<protected_attr>` | str / bool / numeric | ✅ (per key in privileged_groups) | One column per key in privileged_groups.json. Values are the group identifiers (e.g. `M`, `F`, `D` for gender). |
| any other column | any | optional | Ignored by Bias; useful for traceability. |

`y_true` and `y_pred` must have **the same type** (don't mix string and
integer labels). If `y_pred` contains values not seen in `y_true`,
AIF360's metric computation may emit warnings but won't crash.

### 4.3 privileged_groups.json

```json
{
  "geschlecht":     "M",
  "alter_gruppe":   "<30",
  "nationalitaet":  "DE",
  "behinderung":    false
}
```

- The **keys** are column names in the CSV. The page validates that every
  key has a matching column.
- The **value** is the *privileged* category. Everything else in that
  column is *unprivileged* (the binary split is unavoidable in AIF360's
  metric definitions; multi-valued attributes are split as
  `value == privileged` vs not).
- Boolean values (`true` / `false`) must use lowercase JSON form.

### 4.4 Example predictions CSV

```csv
case_id,y_true,y_pred,geschlecht,alter_gruppe,nationalitaet,behinderung
B001,1,1,M,<30,DE,false
B002,0,1,W,30-60,DE,false
B003,1,0,M,>60,Non-EU,true
B004,0,0,W,30-60,EU,false
```

For the page, the matching `privileged_groups.json` would treat males
under 30 with German nationality and no disability as the privileged
intersection.

### 4.5 What the page computes

For each protected attribute (one row in the per-feature dataframe):

- **Disparate Impact (DI)** — `P(pred=1 | unprivileged) / P(pred=1 | privileged)`. 1.0 = parity; <0.8 trips the "four-fifths rule".
- **Statistical Parity Difference** — `P(pred=1 | unpriv) − P(pred=1 | priv)`. 0 = parity.
- **Equal Opportunity Difference** — difference in true-positive rates.
- **Average Odds Difference** — half-sum of FPR + TPR differences.

Each metric maps to a per-attribute risk level (LOW / MEDIUM / HIGH).
The worst attribute drives the page's **Overall Risk** pill.

**Fairlearn complementary panel** — tabbed view per protected attribute
showing accuracy / selection rate / TPR / FPR via `MetricFrame.by_group`,
plus `demographic_parity_difference` and `equalized_odds_difference`. No
extra upload — same y_true / y_pred / sensitive_features.

### 4.6 Common errors

| Error | Cause | Fix |
| --- | --- | --- |
| `Privileged-groups columns missing from CSV: [...]` | Key in JSON has no matching CSV column | Rename either side to match |
| `Privileged groups JSON is invalid` | Python-style JSON | See §2.4 |
| Empty / all-LOW results | All groups in a protected attribute have the same `y_pred` rate | Sanity-check the `y_pred` column; this often means the model isn't actually using the attribute |

---

## 5. Explainability — Art. 13

**Page**: [pages/3_Explainability.py](../pages/3_Explainability.py)
**Toolchain**: `wavetest_explain` (SHAP) + in-page LIME panel
**EU AI Act**: Article 13 (model-level transparency)

### 5.1 Required inputs

| Input | Type | Notes |
| --- | --- | --- |
| Model | `.pkl` / `.joblib` | Pickled scikit-learn-style classifier. Must expose `predict` **and** `predict_proba`. |
| Test CSV | CSV | Features + a target column (name configurable). |
| Training CSV | CSV (optional) | Same column layout as the test CSV. Used as SHAP's background distribution; improves explanation accuracy. |
| Target column name | text (form field) | Default `target`. Must match a column in the test (and training) CSV exactly. |

### 5.2 Test / Training CSV schema

- One row per sample.
- Feature columns in **the same order the model was trained on**. SHAP and
  scikit-learn don't read column names — they consume positional arrays.
  Re-ordering columns silently misaligns explanations.
- A single target column (any name; specified via the text input).
- All feature columns must be numeric (or one-hot encoded). Categorical
  string columns must be encoded before upload — the page passes the raw
  array straight into `model.predict_proba(...)`, which fails on strings
  unless your pipeline handles them.

### 5.3 Example test CSV

```csv
age,income_eur,debt_ratio,prior_defaults,target
34,42000,0.18,0,1
29,38000,0.22,0,1
55,29000,0.41,2,0
67,55000,0.05,0,1
```

With `target_col = "target"`, the model is asked for `predict_proba(X_test)`
where `X_test` is the four feature columns in that order.

### 5.4 Configuration knobs

| Setting | Default | Effect |
| --- | --- | --- |
| Risk level | `high-risk` | Drives strictness of the Article 13 compliance mapping |
| Confidence threshold | 0.85 | Predictions below are flagged borderline |
| Consistency threshold | 0.70 | Min cosine similarity between similar-case explanations |
| Background samples | 100 | SHAP kernel/tree explainer base |
| Explanation samples | 30 | Test rows that get detailed local SHAP |
| Consistency pair count | 20 | How many similar-case pairs to compare |

### 5.5 LIME panel

Optional expander below the SHAP local-cases table. Reuses the same
`X_test` + `X_train` + model that the page already loaded. Picks up to
3 borderline cases (or the first 3 if none are borderline) and renders
each one as a (feature-range, weight) table. Requires `predict_proba`.

### 5.6 Common errors

| Error | Cause | Fix |
| --- | --- | --- |
| `Uploaded model is missing required methods: ['predict_proba']` | Pickled a regressor or a classifier without proba support | Wrap the model so it exposes proba, or use a different model |
| `Target column 'target' not found` | Column name mismatch | Adjust the *Target column* form field |
| `Training CSV is missing columns: [...]` | Training CSV has different schema than test | Re-export both with identical column order |
| Cryptic `AttributeError` on load | sklearn version mismatch | Match the customer's sklearn version in your `.venv` |

---

## 6. Logging Framework — Art. 12 / 72

**Page**: [pages/4_Logging_Framework.py](../pages/4_Logging_Framework.py)
**Toolchain**: `wavetest_logging`
**Inputs**: **none — pure interview**.

The page is a structured questionnaire about the customer's current
logging state and system profile. No uploads. Outputs a generated
`AISystemLogger` Python module, a gap-analysis CSV, and an implementation
guide Markdown.

The fields the analyst fills in are listed in [Audit Manual §4.4](AUDIT_MANUAL.md);
this spec has nothing to add.

---

## 7. Performance Monitoring — Art. 15 / 72

**Page**: [pages/5_Performance_Monitoring.py](../pages/5_Performance_Monitoring.py)
**Toolchain**: `wavetest_monitoring` (scipy) + in-page Evidently AI panel
**EU AI Act**: Articles 15 (accuracy & robustness), 72 (post-market monitoring)

### 7.1 Required inputs

| Input | Type | Notes |
| --- | --- | --- |
| Monitoring CSV | CSV | One row per inference / prediction, timestamped. |

### 7.2 Monitoring CSV schema

| Column | Type | Required | Range / notes |
| --- | --- | --- | --- |
| `timestamp` | ISO 8601 date or datetime | ✅ | Parsed via `pandas.to_datetime`. Mixed timezones get coerced to naive UTC. |
| `y_true` | int / string | ✅ | Ground-truth label. May be missing for unlabelled rows; rows with missing y_true are excluded from accuracy. |
| `y_pred` | int / string | ✅ | Model prediction. |
| `confidence` | float in [0,1] | optional | Per-prediction confidence. Used for the *confidence below threshold* metric. |
| Any other numeric / categorical column | any | optional | Analysed for drift (KS for numeric, chi-square for categorical) and outliers (Z-score). |

The order of columns doesn't matter — `wavetest_monitoring` accesses by
name, not position.

### 7.3 Example monitoring CSV

```csv
timestamp,y_true,y_pred,confidence,age,region,channel
2026-04-01T09:12:00,1,1,0.92,34,DE,web
2026-04-01T10:05:00,0,0,0.71,29,DE,mobile
2026-04-01T11:18:00,1,0,0.55,55,EU,web
2026-04-02T08:30:00,0,0,0.88,67,DE,mobile
2026-04-02T14:22:00,1,1,0.94,41,DE,web
```

The module computes:
- Daily accuracy + degradation against the configured threshold.
- KS test for numeric drift on `age`.
- Chi-square test for categorical drift on `region`, `channel`.
- Z-score outlier rate per numeric column (`age`).

### 7.4 Configuration knobs

Performance + drift thresholds are exposed in the page form; see Audit
Manual §4.5 for the values.

### 7.5 Evidently AI panel

Optional expander below the recommendations. Splits the same dataframe
at the median `timestamp` into reference / current halves, runs
Evidently's `DataDriftPreset`, and offers a downloadable HTML report
(~4–5 MB on demo data because Plotly is inlined).

### 7.6 Common errors

| Error | Cause | Fix |
| --- | --- | --- |
| `❌ <file> is missing required columns: ['timestamp']` | Missing one of the three required columns | Add it; capitalisation matters |
| `Could not parse timestamp` | Non-ISO date format | Re-format to `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS` |
| Empty drift / outlier tables | Only the three required columns present, no feature columns | Add any feature columns to enable drift analysis |
| Evidently report fails on tiny frames | <50 rows total | Get more monitoring data |

---

## 8. Cybersecurity — active ART testing (Art. 15(5))

**Page**: [pages/13_Cybersecurity.py](../pages/13_Cybersecurity.py) — bottom expander
**Library**: `adversarial-robustness-toolbox`
**EU AI Act**: Article 15(5) (cybersecurity / robustness against attacks)

The questionnaire half of this page has no inputs (see §13 below). The
active-testing expander does:

### 8.1 Required inputs

| Input | Type | Notes |
| --- | --- | --- |
| Model | `.pkl` / `.joblib` | Same scikit-learn pickle convention as Explainability. Must expose `.predict()`. |
| Test CSV | CSV | Features + a target column (name configurable). |

### 8.2 Schema

Identical to the Explainability test CSV. The target column is configurable
via a text input (default `target`). All non-target columns are used as
features. ART wraps the model with `SklearnClassifier(clip_values=…)` and
runs HopSkipJump against the first N rows.

`predict_proba` is **not** required (HopSkipJump is decision-based).

### 8.3 Sample-count cap

The page form lets the analyst pick 1–50 samples. HopSkipJump issues
hundreds of model queries per sample, so 10 is a sensible default; 50 may
take several minutes.

### 8.4 What the page reports

- **Original accuracy** — baseline on the unperturbed rows.
- **Adversarial accuracy** — after the attack.
- **Attack success rate** — fraction of rows whose prediction flipped.
- **Mean L2 perturbation** — average magnitude of the adversarial change.

Severity thresholds match the rest of the app: success rate <20 % ok,
<50 % warning, ≥50 % critical.

---

## 9. Captum — Art. 13 / CV attribution

**Page**: [pages/18_Captum.py](../pages/18_Captum.py)
**Library**: `captum` (PyTorch)
**EU AI Act**: Article 13 (transparency, PyTorch-specific path)

### 9.1 Required inputs

| Input | Type | Notes |
| --- | --- | --- |
| PyTorch model | `.pt` / `.pth` | Full pickled `nn.Module`, **not** a state dict. See §2.3. |
| Numeric test CSV | CSV | Feature-only (no target column needed for attribution). All columns must be numeric. |

### 9.2 Schema

- One row per sample.
- Every column is fed as a feature; there is **no target column** in this
  CSV (attribution is computed against a chosen target class index, not
  ground truth).
- All values must be numeric — Captum constructs a `torch.tensor` directly.

### 9.3 Configuration

| Setting | Default | Notes |
| --- | --- | --- |
| Target class index | 1 | Index in the model's output tensor to attribute toward. Binary classifiers: 1 = positive class. |
| Integration steps | 50 | More = smoother attribution, slower. |

### 9.4 v0 scope

Tabular input only. Image / pixel-level attribution (the *Quality
Inspection* and *Medical Imaging* use cases on the website) is the
natural extension — same algorithm, just an image-upload widget and a
heatmap visualisation. Tracked as a follow-up in HANDOVER.

---

## 10. TextAttack — Art. 15 / NLP robustness

**Page**: [pages/19_TextAttack.py](../pages/19_TextAttack.py)
**Library**: `textattack` + `transformers`
**EU AI Act**: Article 15 (robustness, NLP / chatbots / content moderation)

### 10.1 Required inputs

| Input | Type | Notes |
| --- | --- | --- |
| HuggingFace model id | text | A `transformers` text-classification checkpoint. Default: `distilbert-base-uncased-finetuned-sst-2-english` (binary sentiment). |
| Text CSV | CSV (optional) | If supplied, must have `text` + `label` columns. Otherwise the page uses a 5-sample built-in demo set. |

### 10.2 Text CSV schema

| Column | Type | Required | Range / notes |
| --- | --- | --- | --- |
| `text` | string | ✅ | One sentence or short paragraph per row. No length limit at the CSV level; tokenisation may truncate to the model's max sequence length. |
| `label` | int | ✅ | Integer label matching the model's output index space (typically 0 / 1 for binary). |

### 10.3 Example text CSV

```csv
text,label
"This product is absolutely fantastic and I love it.",1
"Worst experience I have ever had with a service.",0
"The food was decent but the wait was long.",0
"Highly recommend, the team went above and beyond!",1
```

### 10.4 Model download

The first run of a given HuggingFace model id pulls the weights to
`~/.cache/huggingface/`. ~250 MB for the default DistilBERT, more for
larger models. Subsequent runs hit the cache.

NLTK corpora (stopwords, wordnet, etc.) are fetched on first import; the
page handles the macOS SSL workaround automatically.

---

## 11. Sustainability — voluntary

**Page**: [pages/14_Sustainability.py](../pages/14_Sustainability.py)
**Library**: in-house helpers backed by CodeCarbon's intensity table.
**EU AI Act**: voluntary (Art. 95 / AI Pact / codes of conduct).

**No file uploads.** All inputs are numeric / dropdown form fields:

| Field | Type | Notes |
| --- | --- | --- |
| Training energy | float (kWh) | Convert from GPU-hours or pull from CodeCarbon logs |
| Training CO₂ override | float (kg, optional) | Replaces the kWh × intensity calc if set |
| Inference energy per 1k predictions | float (kWh) | Typical: small tabular 0.0001–0.001; LLM 0.1–1.0 |
| Monthly predictions | int | Production volume |
| Deployment region | dropdown | 213 countries from CodeCarbon + 2 aggregates |
| Carbon intensity | float (g/kWh) | Pre-filled per region; editable |
| Assumptions, data source, notes | text | Free-form |

For an authoritative training-time number, ask the customer to wrap their
training script with CodeCarbon's `EmissionsTracker` (snippet in the
generated Markdown deliverable).

---

## 12. Combined Report — orchestrates 1–7

**Page**: [pages/0_Combined_Report.py](../pages/0_Combined_Report.py)

Doesn't add new input types. Per-module radio selectors let the analyst
pick *demo data* vs *upload* for each of: Data Quality, Bias,
Explainability, Performance Monitoring. The inputs are exactly as
specified in §§3–7 above.

Logging is interview-only (Combined includes it via the same form fields
as the standalone Logging page).

---

## 13. Pure-questionnaire modules — no inputs

The following modules consume **no uploaded data**. They're driven
entirely by the form fields documented in the Audit Manual:

| Module | Page |
| --- | --- |
| Logging Framework | [4_Logging_Framework.py](../pages/4_Logging_Framework.py) |
| Risk Register | [11_Risk_Management.py](../pages/11_Risk_Management.py) |
| Human Oversight | [12_Human_Oversight.py](../pages/12_Human_Oversight.py) |
| Cybersecurity (questionnaire half) | [13_Cybersecurity.py](../pages/13_Cybersecurity.py) (top) |
| Sustainability | [14_Sustainability.py](../pages/14_Sustainability.py) |
| Incidents | [15_Incidents.py](../pages/15_Incidents.py) |
| Right to Explanation | [16_Right_To_Explanation.py](../pages/16_Right_To_Explanation.py) |
| Model Card | [17_Model_Card.py](../pages/17_Model_Card.py) |

For these, the "input spec" is the schema of the corresponding DB table
in [src/wavetest_app/db/models.py](../src/wavetest_app/db/models.py).

---

## Z. Feasibility — Central Project-level input store

> **Short answer**: yes, well worth doing. The 5 input artefacts above
> (tabular CSV, sklearn model pickle, PyTorch model pickle, HF model id,
> two small JSON configs) can be uploaded once per project and consumed
> by every page. Below is the proposed shape, the trade-offs, and a
> migration plan.

### Z.1 What gets centralised

Inputs in the matrix (§1) collapse to **seven slots per project**:

| Slot | Type | Used by |
| --- | --- | --- |
| `dataset` | CSV | Data Quality, Bias, Explain (test / train), Monitoring, Cybersecurity (ART), Captum |
| `dataset_train` | CSV (optional) | Explainability (background) |
| `sklearn_model` | `.pkl` | Explainability, Cybersecurity (ART) |
| `pytorch_model` | `.pt` | Captum |
| `hf_model_id` | string | TextAttack |
| `privileged_groups_json` | JSON | Bias |
| `target_population_json` | JSON | Data Quality |

The **column-mapping problem**: different modules expect different
columns in `dataset` (Bias wants `y_true`/`y_pred` + sensitive
features; Monitoring wants `timestamp` + the same; Explain wants
features + a *target column* whose name varies). Two ways to handle it:

- **Convention** — require the canonical project dataset to use named
  columns: `timestamp`, `y_true`, `y_pred`, optional `confidence`, then
  arbitrary features. Explainability's target column defaults to
  `y_true`. Bias gets sensitive features from the privileged-groups
  JSON keys. Monitoring is then a near-trivial subset.
- **Column-mapping config** — the project remembers per-module column
  roles in a small JSON: `{"target": "outcome", "predictions": "y_pred",
  "timestamp": "ts"}`. More flexible, more UI.

Recommendation: ship convention first; promote to column-mapping if
real customer datasets refuse to cooperate.

### Z.2 Proposed schema

New table:

```python
class ProjectInput(Base):
    __tablename__ = "project_inputs"

    input_id:    Mapped[str] = mapped_column(String(16), primary_key=True)
    project_id:  Mapped[str] = mapped_column(
        ForeignKey("projects.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    # One row per (project, slot) — slot is the symbolic name from §Z.1
    slot:        Mapped[str] = mapped_column(String(32), nullable=False)
    # File-based slots: relative path under project.folder_path / "inputs/"
    file_path:   Mapped[Optional[str]] = mapped_column(Text)
    # Inline-value slots (hf_model_id, JSON blobs): stored verbatim
    value:       Mapped[Optional[str]] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(64), default="")
    size_bytes:  Mapped[int] = mapped_column(default=0)

    uploaded_by: Mapped[str] = mapped_column(String(64), default="system")
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False,
    )
    notes:       Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (
        UniqueConstraint("project_id", "slot", name="uq_project_slot"),
    )
```

`UniqueConstraint("project_id", "slot")` enforces "one of each kind per
project". Upload replaces; we keep a hash + size for audit.

Files live in `artifacts/<client>/<project>/inputs/<slot>.<ext>` —
inside the existing per-project artefacts folder, so backups/cleanup
already cover them.

### Z.3 Proposed UI

New admin sub-page **Project Inputs** under Admin (or as a tab on the
existing Projects page):

```
Project: PRJ0001 — ACME / Cardio Audit

📁 Datasets
  [ Upload dataset.csv ]      (last uploaded by vjmayr · 2026-05-04 · 1.2 MB)
  [ Upload dataset_train.csv ]  (none yet)

🤖 Models
  [ Upload sklearn_model.pkl ]  (vjmayr · 2026-05-04 · 320 KB)
  [ Upload pytorch_model.pt  ]  (none yet)
  HuggingFace id: [distilbert-base-uncased-finetuned-sst-2-english] [Save]

🧩 Config
  Privileged groups JSON: [text area]  [Save]
  Target population JSON: [text area]  [Save]

🗑 Reset slot ▾
```

Every change writes an `audit_log` entry under module `project_inputs`.

### Z.4 Integration with assessment pages

Each affected page gets a third radio next to *Demo data* and *Upload CSV*:

```
Data source: ( ) Demo data   ( ) Upload now   (●) Use project inputs
```

When *Use project inputs* is selected, the page reads the relevant slot(s)
via a small helper:

```python
from wavetest_app.inputs import load_project_input

dataset_path = load_project_input(project, "dataset")
if dataset_path is None:
    st.error("No `dataset` uploaded for this project. "
             "Go to **Admin → Project Inputs**.")
    st.stop()
df = pd.read_csv(dataset_path)
```

For JSON / string slots the helper returns the value directly.

The existing *Upload now* path stays — useful for ad-hoc runs and demos.

### Z.5 Trade-offs

| Pro | Con |
| --- | --- |
| One upload per project, not per page-run | Adds a new admin page + table (more surface to maintain) |
| Audit trail of who uploaded what when | We hold sensitive customer data on disk longer than the current "upload-and-discard" pattern. Need a clear retention policy. |
| Column conventions become explicit (analyst documents them once) | Loss of per-run flexibility — analysts who want to vary the dataset across runs (e.g. before / after a re-export) need *Upload now* anyway |
| Combined Report becomes a one-click run after inputs are uploaded | If multiple analysts upload at once, last-write-wins on the unique constraint |

### Z.6 Migration plan

Roughly 1.5 days of work:

1. **(2 h)** New `ProjectInput` model + Alembic migration. CASCADE delete with project.
2. **(2 h)** Helpers in a new `wavetest_app.inputs` module:
   - `save_project_input(project, slot, *, file=None, value=None) -> Path | str`
   - `load_project_input(project, slot) -> Path | str | None`
   - `list_project_inputs(project) -> dict[slot, metadata]`
3. **(3 h)** New page `pages/20_Project_Inputs.py` under Admin. Per-slot upload widgets, last-uploaded captions, reset buttons.
4. **(4 h)** Update the 7 assessment pages (1–5 + 13 + 18) to add the *Use project inputs* radio option.
5. **(1 h)** Pytest fixtures + 4–6 new tests (roundtrip, CASCADE, slot uniqueness, helper functions).
6. **(1 h)** Update `AUDIT_MANUAL.md` §1.2 + this spec doc.

### Z.7 What I'd *not* centralise (yet)

- **TextAttack text CSV** — too domain-specific; analysts often want to
  attack a fresh evaluation set each run.
- **Captum's PyTorch model** — keep behind the standalone page for now;
  centralise once the CV / image upload variant lands.

These can still live on their own pages with ad-hoc uploads; only the
core 7 slots above need centralisation to unblock the typical workflow.

---

**waveImpact GmbH** · Bremen · Internal tool · companion to `AUDIT_MANUAL.md`
