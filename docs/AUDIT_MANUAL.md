# Running an EU AI Act Audit — Analyst Manual

This is the step-by-step guide for waveImpact analysts running an audit through
**wavetest-app**. It covers the full workflow (login → set up the engagement →
run assessments → deliver to the customer) and includes per-module input
requirements, example CSVs, and how to read the results.

> **Audience:** Internal consultants. Assumes you can navigate a web app, know
> what an AI system is, and have a basic feel for compliance work. No coding
> required — every assessment is launched from the browser UI.
>
> **Companion document:** [INPUT_SPEC.md](INPUT_SPEC.md) is the rigorous
> contract for the input data each module expects — exact column names,
> value ranges, file formats, validation rules. Share that with the
> customer before the engagement so they ship the right files; the manual
> below assumes they already have.

---

## Table of contents

1. [Before you start](#1-before-you-start)
2. [Set up the engagement](#2-set-up-the-engagement)
3. [General assessment workflow](#3-general-assessment-workflow)
4. [Per-module reference](#4-per-module-reference)
   - [4.1 Data Quality](#41-data-quality--art-10--gdpr-art-9)
   - [4.2 Bias Detection](#42-bias-detection--art-10--13--61)
   - [4.3 Explainability](#43-explainability--art-13)
   - [4.4 Logging Framework](#44-logging-framework--art-12--72)
   - [4.5 Performance Monitoring](#45-performance-monitoring--art-15--72)
   - [4.6 Risk Register](#46-risk-register--art-9)
   - [4.7 Human Oversight](#47-human-oversight--art-14)
   - [4.8 Cybersecurity](#48-cybersecurity--art-155)
   - [4.9 Sustainability](#49-sustainability--voluntary)
   - [4.10 Incidents](#410-incidents--art-73)
   - [4.11 Right to Explanation](#411-right-to-explanation--art-86)
   - [4.12 Model Card](#412-model-card--art-11--13)
   - [4.13 Captum](#413-captum--art-13--cv-attribution)
   - [4.14 TextAttack](#414-textattack--art-15--nlp-robustness)
5. [Combined Report](#5-combined-report)
6. [Audit Log](#6-audit-log)
7. [Where files live](#7-where-files-live)
8. [Status legend](#8-status-legend)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Before you start

### 1.1 Open the app

The dev / internal server runs at **http://localhost:8501** (or wherever an
admin has deployed it). Open it in your browser.

You'll see a **login form** on the Home page. Enter your username and
password. If you don't have an account, ask the admin to run
`python scripts/auth_add_user.py` for you.

After login the sidebar shows **Signed in as &lt;Your Name&gt;** plus a
logout button, and splits into two grouped sections:

- **Modules** — the assessments and governance pages. Anyone with the
  `analyst` role can use them.
- **Admin** — Clients / Systems / Projects / Project Types / Audit Log.
  Requires the `admin` role; non-admins see a polite "this page needs
  the admin role" notice.

The authenticated identity is automatically stamped onto every assessment
run in the audit log — so when a customer asks "who ran this report?",
the answer is in the database.

### 1.2 Check the toolchain status

On the Home page, expand the **Toolchain status** panel. All six
`wavetest_*` packages should show ✓. If any show ❌, an admin needs to
run `./scripts/install_toolchain.sh` before you can run that module.

The newer modules (Captum, TextAttack, Evidently, ART, Fairlearn,
Great Expectations, ydata-profiling, CodeCarbon, LIME) are pulled in
via `pip install -e .` and don't appear in the toolchain-status panel —
if one fails to import, the page shows a polite error inline.

---

## 2. Set up the engagement

Every audit lives inside a **Project**, which belongs to a **Client** and
references a classified **System**. Set them up in this order from the
sidebar:

### Step 1 — Create the client

Open **🏢 Clients**. Fill in:

- **Company name** (e.g. *Cardio Diagnostics GmbH*)
- **Country** (default: Germany)
- **Languages** — controls the language of the generated reports
  (`en`, `de`, etc.). `en` is always added automatically.

Click **Create client**. The client gets an ID like `CLI0007`.

### Step 2 — Classify the AI system

Open **🤖 Systems** and run the EU AI Act questionnaire for the client's
system:

- Entity type, system name, description
- Is it an AI System under the EU AI Act definition?
- Does it pose significant risk to health, safety, or fundamental rights?
- Annex III high-risk areas
- Prohibited practices
- Transparency obligations

The questionnaire produces an overall risk classification:
`PROHIBITED`, `HIGH-RISK`, `LIMITED-RISK`, or `MINIMAL-RISK`. The full
answer set is stored on the system record (`SYS0001`) and surfaces on
the project later.

### Step 3 — Pick or create a project type

Open **🗂 Project Types**. A project type bundles a name + a list of
**standard services** the engagement covers (e.g. *Bias Detection &
Mitigation* with services *screen / diagnose / mitigate*). If a suitable
type already exists, skip to step 4. Otherwise create one.

### Step 4 — Create the project

Open **📋 Projects** and create a project bound to the client + project
type. The artefacts directory under `artifacts/<client>/<project>/` is
created the first time an assessment runs against this project.

### Step 5 — (Recommended) Upload the customer's inputs once

Open **📥 Project Inputs** (top of the Modules section). For each
artefact the engagement needs, fill the matching slot:

| Slot | What goes in it | Used by |
| --- | --- | --- |
| `dataset` | Canonical CSV: `y_true` + (optional) `y_pred`, `timestamp`, `confidence`, features | Data Quality, Bias, Explainability, Monitoring, Cybersecurity (ART), Captum |
| `dataset_train` | Optional training CSV | Explainability (SHAP background) |
| `sklearn_model` | Pickled scikit-learn classifier | Explainability, Cybersecurity (ART) |
| `pytorch_model` | Full pickled `nn.Module` | Captum |
| `hf_model_id` | HuggingFace model id (string) | TextAttack |
| `privileged_groups_json` | JSON `{column: privileged_value, …}` | Bias |
| `target_population_json` | JSON `{column: {category: proportion, …}, …}` | Data Quality |

Every assessment page now offers **"Use project inputs"** as the
first data-source option — the page reads the matching slot(s),
validates the column convention, and runs without per-page re-uploads.
The Combined Report has a single top-level checkbox that applies the
override across every enabled module.

You're ready to audit.

---

## 3. General assessment workflow

Every assessment page (Data Quality, Bias, Explainability, Logging,
Monitoring, Combined Report) follows the same shape:

1. **Pick the project** from the sidebar dropdown.
2. **Choose data source**: *Demo data* (synthetic, controllable severity)
   or *Upload CSV / Upload model*. Demo is for internal smoke tests
   and demos; uploads are what you'll use against real client data.
3. **Tune thresholds** in the *Configure* expander. Defaults match
   EU AI Act guidance — only change them if the customer has specific
   numbers.
4. Click **▶ Run assessment**. The result appears below: status pills,
   dashboard plot, detail tables, recommendations.
5. **Download exports** — every page exposes JSON and CSV downloads at
   minimum; some also export a Markdown guide or generated code.
6. The run is automatically appended to the **Audit Log**
   (📜 *Audit Log* in the sidebar) with your username, the project, and
   the resulting status.

For the customer presentation, use the **🧾 Combined Report** page to
run all five modules and ship one branded PDF.

---

## 4. Per-module reference

Each module section below covers:

- **What you need from the client** (in plain English)
- **CSV column requirements** + a worked example
- **Configuration options** that matter
- **How to read the result**

> All assessments support a **Demo data** option that generates synthetic
> data of controllable severity. Use it to walk a customer through the
> deliverable before they hand over their real data.

---

### 4.1 Data Quality — Art. 10 + GDPR Art. 9

**What it does:** Scores the dataset against EU AI Act Article 10
(*data governance and quality management*) and flags GDPR Article 9
*special category* columns. Tests the dataset for representativeness
against a target population.

**What you need from the client:**

- The training (or production-input) dataset as a CSV.
- The expected demographic breakdown of the target population (e.g.
  Germany 2024 demographic profile) — used for the chi-square
  representativeness test.

**CSV requirements:**

Any tabular CSV. There are *no required columns* — every column is
analysed for missingness, duplicates, and outliers. Columns whose
**names** match GDPR Art. 9 keywords (race, religion, health, …) are
flagged automatically.

**Example dataset:**

```csv
record_id,age,gender,nationality,credit_score,income,outcome
R0001,32,M,DE,712,48000,1
R0002,28,F,DE,685,52000,1
R0003,45,M,EU,640,73000,0
R0004,51,F,Non-EU,710,29000,0
R0005,29,M,DE,668,41000,1
```

**Target-population JSON** (in the *Configure* expander):

```json
{
  "gender":      {"M": 0.49, "F": 0.51},
  "age_group":   {"18-30": 0.25, "31-45": 0.35, "46-60": 0.28, "60+": 0.12},
  "nationality": {"DE": 0.85, "EU": 0.12, "Non-EU": 0.03}
}
```

The keys must match column names in the CSV. Categories that don't appear
in the CSV are treated as 0% observed (which usually fails the chi-square
test — flag this to the customer).

**Configuration knobs:**

| Setting | Default | Meaning |
|---|---|---|
| Max missing values per column | 5% | Article 10 threshold |
| Max outliers per numeric column | 5% | Statistical outliers (Z>3) |
| Minimum sample size | 1 000 | Smaller datasets get a warning |

**How to read the report:**

| Pill | Meaning |
|---|---|
| **Quality Score 0–100** | Combined completeness + consistency. ≥90 EXCELLENT, 75–89 GOOD, 60–74 ACCEPTABLE (borderline), <60 POOR (non-compliant). |
| **Classification** | The bucket name above. Drives the colour. |
| **Missing %** | Per-column missing rate. <5% = Article 10 compliant. |
| **Duplicates %** | Exact-row duplicates. >3% suggests a broken ETL pipeline; inflates model accuracy artificially. |
| **Article 10** | *Compliant* if all thresholds pass; *Gaps* otherwise. |

The **representativeness** table shows χ², p-value, and result for each
target-population key. p > 0.05 = REPRESENTATIVE; p < 0.01 = NOT
REPRESENTATIVE (recommend resampling or weighting).

The **GDPR Art. 9** panel lists columns whose names suggest sensitive
data. Even one match is a conversation with the client about lawful
basis for processing.

**Optional deep dives** (two extra expanders below the report):

- **📋 Extended profile (ydata-profiling)** — pick a sample size,
  click *Run* and the page produces a full automatic dataset profile
  (column types, distributions, correlations, alerts) as a downloadable
  HTML. Sample because the full report is slow on >5 000 rows; the
  full dataset is still used for the metrics above.
- **✅ Great Expectations validation** — runs a canned suite (≥95 %
  non-null on every column, every numeric column within its observed
  min / max) and shows pass / fail per expectation. For a
  project-specific suite, define expectations on the toolchain side
  and re-import.

---

### 4.2 Bias Detection — Art. 10 / 13 / 61

**What it does:** Computes group-fairness metrics (disparate impact,
statistical parity, equal opportunity) across protected attributes and
maps the worst metric to a risk level.

**What you need from the client:**

- Predictions + ground truth, **for cases where the outcome is observed**
  (e.g. hired employees who passed/failed probation, not rejected
  applicants).
- The protected attributes you want to assess (gender, age group,
  nationality, disability, …).

**CSV requirements:**

Required columns: `y_true`, `y_pred` (both 0/1).
Plus one column per key in the privileged-groups JSON (default keys are
German: `geschlecht`, `alter_gruppe`, `nationalitaet`, `behinderung`).

**Example dataset:**

```csv
application_id,y_true,y_pred,geschlecht,alter_gruppe,nationalitaet,behinderung
APP0001,1,1,M,<30,DE,false
APP0002,0,1,W,<30,DE,false
APP0003,1,1,M,30-45,EU,false
APP0004,1,0,W,45-60,DE,true
APP0005,0,0,M,>60,Non-EU,false
```

**Privileged-groups JSON** (defines who the *advantaged* group is per
attribute):

```json
{
  "geschlecht":    "M",
  "alter_gruppe":  "<30",
  "nationalitaet": "DE",
  "behinderung":   false
}
```

The value is the **privileged** category. Everything else is treated as
*unprivileged* for that attribute.

**How to read the report:**

| Pill | Meaning |
|---|---|
| **Overall Risk** | `NIEDRIG` / `LOW` (ok), `MITTEL` / `MEDIUM` (warning), `HOCH` / `HIGH` (critical). The worst attribute wins. |
| **Critical findings** | How many attributes hit the *high-risk* threshold. |
| **Features analysed** | Total attributes assessed. |

Per-feature dataframe shows the underlying metrics. The two to flag in
client conversations:

- **Disparate Impact (DI)**: ratio of positive-prediction rates between
  unprivileged and privileged groups. **1.0 = equal**, **<0.8** trips the
  US "four-fifths rule" used as a global benchmark.
- **Equal Opportunity Difference**: difference in true-positive rates.
  **0 = perfectly fair**; ±0.1 is concerning.

The **dashboard** plots distributions and metric-vs-threshold bars; the
**protected-attribute distributions** plot is useful evidence that the
sample wasn't trivially imbalanced.

**📊 Per-group metrics (Fairlearn)** — expander below the dashboard.
AIF360 gives you the risk level; Fairlearn shows what's actually
happening per group. One tab per protected attribute, each with a
`MetricFrame` table of accuracy / selection rate / true-positive rate /
false-positive rate per subgroup, plus the **demographic parity
difference** and **equalized odds difference** numbers underneath.
This is what you'll point at in the client conversation when you say
"the model picks group X 40 % of the time and group Y 16 % of the time"
— much more concrete than a single risk pill.

---

### 4.3 Explainability — Art. 13

**What it does:** Computes SHAP values to explain individual predictions
and the model's global behaviour. Maps results to the seven Article 13
transparency sub-clauses.

**What you need from the client:**

- The trained model as a **pickled scikit-learn-compatible object** (.pkl
  / .joblib). Must implement `predict()` AND `predict_proba()`.
- A **test CSV** containing the feature columns + the target column.
- Optionally: the training CSV with the same columns — improves SHAP's
  background sampling.

If the client can't share the model file (IP / contract), we can't run
SHAP. Falling back to API-only or container-only access is on the
roadmap but not supported today.

**Example test CSV:**

```csv
age,income,credit_score,employed_years,defaults_5y,target
32,48000,712,6,0,1
28,52000,685,3,0,1
45,73000,640,15,1,0
51,29000,710,2,0,0
29,41000,668,4,0,1
```

The **target column name** is configurable (default `target`).

**Configuration knobs that matter:**

| Setting | Default | Meaning |
|---|---|---|
| Risk level | high-risk | Drives strictness of compliance mapping. Match the system's classification. |
| Confidence threshold | 0.85 | Predictions below this are flagged as *borderline*. |
| Consistency threshold | 0.70 | Cosine similarity between explanations of similar cases. |
| Explanation samples | 30 | Number of test rows SHAP explains in detail. More = slower. |

**How to read the report:**

| Pill | Meaning |
|---|---|
| **Accuracy** | Top-line model accuracy on the test set. ≥85% ok, 70–84% warning, <70% critical. |
| **Consistency** | Average explanation similarity across pairs of similar cases. ≥70% ok, otherwise the model isn't reasoning consistently. |
| **Compliance** | Mapped against the 7 Article 13 sub-clauses. `ERFÜLLT` / fulfilled = ok. |

The **Global feature importance** table ranks features by mean
|SHAP value|. **Top-3 concentration** is a useful soundbite ("85% of the
model's behaviour is explained by just 3 features"). **Local case
explanations** lists each scored test sample with its prediction,
confidence, and a borderline flag — borderline cases are the natural
audit targets for a domain expert.

**🔍 LIME local explanations** — expander below the SHAP local-cases
table. Builds a `LimeTabularExplainer` from the training data
(or test data as fallback), picks up to 3 borderline cases, and shows
each one as a small (feature-range, weight) table. LIME is often more
client-readable than raw SHAP — the discretised feature ranges
(e.g. `100 <= income <= 250`) translate directly into plain language
in the customer letter. Requires `predict_proba()` on the uploaded
model; if missing, the expander shows a polite "not available" note.

For deeper PyTorch attribution (Integrated Gradients), see the
separate **🖼 Captum** module on its own page.

---

### 4.4 Logging Framework — Art. 12 / 72

**What it does:** *Interview-only — no CSV needed.* Asks the client a
short questionnaire about their current logging, identifies gaps against
Article 12, and **generates a standalone `AISystemLogger` Python module**
they can drop into their codebase.

**What you need from the client:**

A short interview covering current state:

- Is the system logging anything today?
- What is logged: inputs / outputs / timestamps / user info / model
  version / confidence?
- Storage method (none / file / database / cloud) and retention period.
- System profile: classification, deployment shape, latency requirements,
  whether personal data is processed.

Fill the answers into the page's checkboxes / dropdowns and run.

**How to read the report:**

| Pill | Meaning |
|---|---|
| **Compliance %** | What share of Article 12 requirements are met today. 100% ok, 50–99% warning, <50% critical. |
| **Open gaps** | Total requirements not yet met. |
| **Critical gaps** | Subset of gaps blocking high-risk deployment. |
| **Smoke tests** | The generated logger is unit-tested before download. `5/5` = fully working. |
| **Article 12** | *Compliant* once gaps == 0. |

The **gap chart** visualises severity by category. The **designed schema**
table shows the fields the generated logger writes per event. Download
the **`.py` standalone file** and hand it to the client's engineering
team — they import `AISystemLogger`, instantiate it, and call it on each
prediction.

---

### 4.5 Performance Monitoring — Art. 15 / 72

**What it does:** Combines accuracy / drift / outlier checks against a
production-monitoring dataset. The output is what you hand the customer
for their Article 15 ongoing-monitoring file.

**What you need from the client:**

A monitoring dataset spanning the period under review (typically
30–90 days of daily inference records).

**CSV requirements:**

Required: `timestamp`, `y_true`, `y_pred`.
Optional: `confidence`, plus any number of feature columns — extra
numeric columns get drift-tested via Kolmogorov-Smirnov; categorical
columns via chi-square.

**Example dataset:**

```csv
timestamp,y_true,y_pred,confidence,age,income,credit_score
2026-01-02,1,1,0.87,32,48000,712
2026-01-02,0,0,0.92,55,29000,640
2026-01-03,1,1,0.78,29,41000,668
2026-01-03,1,0,0.61,45,73000,640
2026-01-04,0,0,0.95,38,55000,701
```

**Configuration knobs that matter:**

| Setting | Default | Meaning |
|---|---|---|
| Min accuracy | 85% | Below this triggers WARNING / CRITICAL |
| Degradation tolerance | 5% | Allowed accuracy drop vs. training baseline |
| Drift p-value cutoff | 0.05 | Below this = drift detected for that feature |
| Critical drift KS statistic | 0.10 | KS magnitude that escalates a drift to critical |
| Outlier Z-score cutoff | 3.0 | Threshold for flagging an input as an outlier |
| Max outlier rate per feature | 5% | Above this = warning |

**How to read the report:**

| Pill | Meaning |
|---|---|
| **Accuracy** | Period accuracy of the production model. |
| **Status** | `GOOD` / `WARNING` / `CRITICAL` from accuracy + degradation. |
| **Drift** | `N / total` features where the input distribution shifted. >2 features warrants retraining. |
| **Critical outliers** | Features whose outlier rate exceeded the configured max. |
| **Article 15** | *Compliant* when accuracy is in spec, no critical drift, no critical outliers. |

The **dashboard** plot shows accuracy over time. The **drift detection**
and **outlier rates** tables list per-feature stats — copy the worst
rows directly into the customer's monitoring report. The **daily
metrics** table + **trend** caption give a 14-day view: a downward trend
is the early-warning signal you want to surface.

**📊 Evidently AI — drift HTML report** — expander below the
recommendations. Splits the timeline at the median timestamp into a
reference half + a current half, runs Evidently's `DataDriftPreset`,
and offers a self-contained HTML download. The report has per-feature
distribution plots, KS / chi-square test results, and a numerical
summary — the kind of thing you forward to a customer's data-science
team rather than carry into a compliance meeting. Heavy file
(~5 MB on demo data because Plotly is inlined for offline viewing).

---

### 4.6 Risk Register — Art. 9

**What it does:** A per-project register of identified risks. Each entry has
a pre-mitigation severity × likelihood scoring, a mitigation plan + status,
and a post-mitigation residual scoring. Article 9 of the EU AI Act requires
this register to be maintained throughout the system's lifecycle.

**What you need from the client:** Conversation, not data. Risks come out of:

- The other assessment outputs (Data Quality, Bias, Explainability, Logging,
  Monitoring) — convert findings into register entries.
- A risk workshop with the client's domain experts.
- Existing internal incident or near-miss reports.

**Workflow on the page:**

1. Pick the project.
2. Open **➕ Add a risk**, fill in:
   - **Title** + **Description** (what is the risk?)
   - **Category**: `data_quality`, `bias`, `security`, `oversight`,
     `performance`, `governance`, `other`
   - **Severity** (LOW / MEDIUM / HIGH / CRITICAL) and
     **Likelihood** (RARE / UNLIKELY / POSSIBLE / LIKELY / ALMOST_CERTAIN)
   - **Mitigation plan** + status (`proposed` / `in_progress` /
     `implemented` / `verified`)
   - **Owner** (person accountable) + **Next review date**
3. The page computes the **risk level** automatically from the
   severity × likelihood matrix. Levels: LOW → MEDIUM → HIGH → CRITICAL.
4. Once mitigation is implemented, expand the risk and fill in the
   **Residual severity** + **Residual likelihood** to record what's left.
5. Filter by category / level / status to focus the conversation, and
   export to **CSV** for the client's compliance file.

**Severity × likelihood matrix:**

| Severity \\ Likelihood | RARE | UNLIKELY | POSSIBLE | LIKELY | ALMOST_CERTAIN |
| --- | --- | --- | --- | --- | --- |
| **LOW** | LOW | LOW | LOW | MEDIUM | MEDIUM |
| **MEDIUM** | LOW | MEDIUM | MEDIUM | HIGH | HIGH |
| **HIGH** | MEDIUM | HIGH | HIGH | CRITICAL | CRITICAL |
| **CRITICAL** | HIGH | HIGH | CRITICAL | CRITICAL | CRITICAL |

**How to read the dashboard:**

- **Risks tracked** — total count for the project
- **Critical / High** — counts at the top two levels (the "must mitigate" ones)
- **Open mitigations** — entries still in `proposed` or `in_progress`
- **Risk matrix** — pivot table showing how many risks land in each cell

Every create / update / delete is captured in the **Audit Log** under
module `risk_management` so the admin can review changes over time.

**Tip:** treat the register as a living document. After every Data Quality
or Monitoring run, ask "is there a new risk to record, or has an existing
one changed?" — that's exactly the lifecycle Art. 9 asks for.

---

### 4.7 Human Oversight — Art. 14

**What it does:** Captures the project's *Human Oversight Plan* against
the six Article 14.4 (a)–(e) checkpoints. One plan per project,
edit-in-place. Generates a Markdown deliverable for the customer file.

**What you need from the client:** Conversation, not data:

- Operator profile — who runs the system day-to-day, training, decision
  authority, throughput
- For each Art. 14.4 checkpoint: yes / partial / no
- The current gaps and a mitigation plan
- A next-review date

**The six checkpoints:**

| # | Requirement | Sub-clause |
| --- | --- | --- |
| 1 | Operators have documentation covering capabilities + limitations | Art. 14.4(a) |
| 2 | Operators are trained to recognise automation bias | Art. 14.4(b) |
| 3 | Outputs include confidence / uncertainty information | Art. 14.4(c) |
| 4 | Operators can disregard or reverse system outputs | Art. 14.4(d) |
| 5 | Overrides are logged and traceable to a specific operator | Art. 14.4(d) |
| 6 | Stop / interrupt mechanism exists and is documented | Art. 14.4(e) |

**Scoring:** each *yes* = 3 points, *partial* = 1, *no* = 0. Total ÷ 18 → percent.

**How to read the result:**

| Pill | Meaning |
| --- | --- |
| **Compliance %** | 100 = ok (green), 50–99 = warning (yellow), <50 = critical (red). |
| **Last updated** / **Next review** | Drive the lifecycle; pick a review date that makes sense for the deployment cadence. |

The page lists per-checkpoint **recommendations** automatically — one
per `no` (treat as blocker for high-risk deployment) and one per `partial`
(define gap + mitigation). Use the **Markdown export** to send the plan
to the customer.

**Interplay with the Risk Register:** every *no* on a Human Oversight
checkpoint is a candidate **risk** to record on page 11 with category
`oversight`. The two pages are designed to feed each other.

---

### 4.8 Cybersecurity — Art. 15(5)

**What it does:** Records the project's cybersecurity posture against
the eight Art. 15(5) checkpoints — both classical infosec hygiene and
AI-specific attacks. Generates a Markdown deliverable.

**Why it's a v0:** Real adversarial-robustness testing (FGSM, PGD,
membership-inference, model-inversion against an actual uploaded model)
needs the Adversarial Robustness Toolbox (ART) and a few days of
wrapping. This page is the questionnaire-driven precursor — it captures
what the team *has done* and *plans to do* against each Art. 15(5)
threat class. The active-testing module is a tracked follow-up.

**The eight checkpoints:**

1. Threat model is documented and current
2. SBOM maintained + scanned for CVEs
3. Penetration testing performed in the last 12 months
4. Training-data integrity controls (against data poisoning)
5. Inference-time adversarial-input defences (against evasion)
6. Defences against membership-inference / model-inversion
7. Access controls documented (deploy / retrain / serve)
8. Incident-response playbook for compromise

**Scoring:** same yes/partial/no → 3/1/0 → `÷ 24 → percent` as the
oversight page. 100% = ok, 50–99% = warning, <50% = critical.

**Tip:** the questions about training-data integrity, adversarial inputs,
and privacy attacks are AI-specific and often surface unfamiliar to a
generic infosec team. Bring those up in the threat-model conversation
explicitly — they're what the EU AI Act adds beyond standard ISO 27001
hygiene.

**🎯 Active adversarial testing (IBM ART)** — expander below the plan
download. Where the questionnaire asks "do you have controls against
inference-time evasion?", this expander **runs an actual attack** to
show what happens when there aren't any. Workflow:

1. Upload the customer's pickled scikit-learn model + a small test CSV.
2. Pick the number of samples (1–50; HopSkipJump needs many model
   queries per sample, so stay small while exploring).
3. Click *Run HopSkipJump attack*.
4. The page wraps the model with `art.estimators.SklearnClassifier`,
   runs HopSkipJump (decision-based, blackbox — needs only `.predict()`,
   no gradients, no PyTorch), and reports four pills:

   | Pill | Meaning |
   | --- | --- |
   | **Original accuracy** | Baseline accuracy on the unperturbed test rows |
   | **Adversarial accuracy** | Accuracy after the attack — if this drops to ~0, the model has no defence |
   | **Attack success rate** | Fraction of samples where the predicted class flipped. <20 % ok, <50 % warning, ≥50 % critical |
   | **Mean L2 perturbation** | Average size of the adversarial change in feature space — small numbers = the model can be fooled with subtle inputs |

The audit log captures every run under module `cybersecurity` with
the success rate in `status_detail`, so the trend across versions is
visible from the Audit Log page.

**When to run it:** any time the client claims they have adversarial-
input defences. If HopSkipJump still flips ≥50 % of predictions in a
few seconds, the defences aren't working.

---

### 4.9 Sustainability — voluntary

**What it does:** Captures a project's carbon footprint estimate. **Not**
required by the EU AI Act (those are voluntary under Art. 95 + the AI
Pact / codes of conduct), but customers reporting under CSRD or
ISO/IEC 42001 ask for these numbers anyway.

**Inputs (every field is optional — partial data still produces a partial estimate):**

- **Training energy** (kWh) — convert from GPU-hours via
  `kWh ≈ GPU-hours × board-TDP-W / 1000`, or pull straight from CodeCarbon
  / eco2AI logs.
- **Direct CO₂eq override** (kg, optional) — if the client measured
  training carbon directly, use this instead of the kWh × intensity calc.
- **Inference energy** (kWh per 1000 predictions) — typical ranges:
  small tabular models 0.0001–0.001 kWh/1k; LLM serving 0.1–1.0 kWh/1k.
- **Monthly predictions** (count) — production volume.
- **Deployment region** — picks a default carbon intensity (gCO₂eq/kWh).
  **213 countries** sourced from CodeCarbon's `global_energy_mix.json`
  plus two curated aggregates (EU-Average, Global-Average) and a
  *Custom* slot for region-spanning deployments.
- **Carbon intensity** — overridable if the customer has a better figure.

**Computed automatically:**

- **Training carbon (kg)** = override OR (training kWh × intensity / 1000)
- **Monthly inference energy (kWh)** = (predictions / 1000) × kWh/1k
- **Annual operational footprint (kg CO₂eq)** = training + 12 × monthly inference × intensity / 1000

**How to read it:**

| Pill | Meaning |
| --- | --- |
| **Training** | One-shot training-time CO₂eq |
| **Annual** | Training + 12 months of inference at the configured volume |
| **Region** + **Intensity** | The grid the system runs on |

**Tip:** even sketchy numbers are better than none for CSRD reporting.
Get the order of magnitude right first; refine over time.

**For an authoritative training-time number**, ask the customer to wrap
their training script with [CodeCarbon's](https://codecarbon.io)
`EmissionsTracker`:

```python
from codecarbon import EmissionsTracker
with EmissionsTracker(project_name="cardio-v2",
                      country_iso_code="DEU") as tracker:
    train_model(...)
# tracker writes emissions.csv with kWh + kg CO₂eq
```

The page's Markdown export already includes this snippet for the
customer.

---

### 4.10 Incidents — Art. 73

**What it does:** Tracks serious incidents per project. Each entry
captures dates (occurred / detected / reported), severity, affected
persons, root cause, corrective action, and authority-notification
metadata. Generates a Markdown packet ready for the notified body.

**Reporting deadlines per Art. 73:**

| Severity | Deadline |
| --- | --- |
| Death or serious health harm | **2 days** from awareness |
| Fundamental rights infringement | 15 days |
| Property / environmental damage | 15 days |
| Near-miss (no harm) | 15 days |

The page computes a **deadline pill** per incident from
`detected → reported`:

- **green** — already reported
- **green** if days remaining > 3
- **yellow** if 0–3 days remaining
- **red** if overdue (negative days)

**Workflow:**

1. Open **➕ Log a new incident** — title, summary, severity, affected
   persons, occurred / detected dates, initial status.
2. Once an incident exists, expand it to record:
   - **Root cause** + **corrective action** (text)
   - **Status** transitions: `open` → `investigating` →
     `corrective_actions` → `closed`
   - **Date reported** to the authority
   - **Authority name** + **case reference**
3. Click **⬇ Notified-body packet** to download a Markdown report bundle
   for filing.

**Tip:** the authority you report to is the *market-surveillance
authority of the Member State where the incident occurred* — not
necessarily the client's home regulator. Confirm with the client's
compliance team. Common ones: **BNetzA** (Germany), **AGCM** (Italy),
**ACPR/CNIL** (France), **AP** (Netherlands).

**Interplay with the Audit Log:** every create / update writes an entry
under module `incidents`, so admins can audit what changed and when.

**Persistence note:** if a project is later deleted, its incidents are
*not* lost — the FK is set to NULL but the project + client name
snapshots survive. The same pattern as the Audit Log.

---

### 4.11 Right to Explanation — Art. 86

**What it does:** Tracks individual right-to-explanation requests under
Art. 86. Different from the Explainability page, which explains the
*model* in general — Art. 86 is about a specific decision affecting a
specific person. The deliverable is a **plain-language letter to the
affected individual**.

**Inputs per request:**

- **Customer / case reference** — the deployer's case ID. **Never enter
  the natural person's name** here (GDPR data minimisation).
- **Decision date** + **decision outcome** (one sentence in plain language).
- **Date request received** — drives the response deadline (default
  30 days, mirroring GDPR Art. 12 cadence).
- **Human review offered?** — most high-risk deployments do; uncheck only
  if not available for this specific decision.

**Drafting the letter:**

Each request opens to an edit form with two free-text fields that go
*directly* into the customer letter:

1. **Top factors** — translate model features into language the affected
   person will understand. Aim for **3 bullet points**, no jargon.
   Example: ❌ "Income feature value 28000 contributed -0.32 SHAP" →
   ✅ "Reported income below the standard threshold for the product."
2. **What could change the outcome** — conditions under which the
   decision would change. If nothing reasonable would, say so.

**The letter template** automatically includes:

- A "How an AI system was involved" paragraph (boilerplate).
- The two free-text sections you wrote.
- A "Your right to human review" paragraph that varies based on the
  *Human review offered?* checkbox.
- A close referencing the deployer + the internal request ID.

**Status pills:**

| Pill | Meaning |
| --- | --- |
| **Status** | `open` (red), `in_progress` (yellow), `sent` / `closed` (green) |
| **Deadline** | Days remaining until response due — green > 5, yellow ≤ 5, red overdue, green if already sent |
| **Human review** | "offered" (green) or "not offered" (yellow) |

**Tip:** the response deadline isn't fixed by the AI Act itself —
national implementations vary. The 30-day default mirrors GDPR. If your
client's national regulator publishes a stricter timeline, override the
**Response due date** field.

---

### 4.12 Model Card — Art. 11 + 13

**What it does:** A per-project Model Card following Google's
published schema. Fulfils EU AI Act Article 11 (technical
documentation) and a chunk of Article 13 (deployer transparency) at
the same time — both regulators ask for what's already on a Model
Card. The deliverable is two files: a **Markdown** version (for the
customer file) and a **JSON** version (for downstream toolchains —
interchangeable with output from Google's `model-card-toolkit`).

**What you need from the client:** Conversation, not data. Inputs
mirror the schema:

- **Model details**: name, version, owners, license, citation,
  references, free-text overview.
- **Intended use**: primary uses, primary users, **out-of-scope uses**
  (the most important section for Art. 13 — where the model
  *shouldn't* be used).
- **Factors**: subgroups / environments / instrumentation conditions
  the behaviour might depend on, and which of those were evaluated.
- **Metrics**: pull headline numbers from the Performance Monitoring,
  Bias Detection, and Explainability runs.
- **Data**: training-data + evaluation-data summaries.
- **Ethical considerations** + **caveats** + **recommendations**.

**Workflow:** open the page, fill what you have, save. The form is
upsert-style — one card per project, edit-in-place. Export Markdown
or JSON when ready for the customer.

**Why this isn't model-card-toolkit:** Google's official Python
package isn't installable on Python 3.13 (its build pin is too old).
The schema is the value — we mirror it field-for-field on a DB row
and emit the same JSON shape.

---

### 4.13 Captum — Art. 13 / CV attribution

**What it does:** Per-row attribution for **PyTorch** classifiers via
Captum's Integrated Gradients. Complements SHAP / LIME on the
Explainability page — same goal (which features drove this
prediction?), but works on differentiable PyTorch models that the
SHAP page can't always handle (deep networks, CV models).

**What you need from the client:**

- A **full pickled PyTorch model** (saved with
  `torch.save(model, path)`, **not** a state dict). Must be a
  differentiable `nn.Module`.
- A **numeric test CSV** (no target column needed for attribution).

**Configuration:**

| Setting | Default | Meaning |
| --- | --- | --- |
| Target class index | 1 | Class to attribute toward (1 = positive in binary) |
| Integration steps | 50 | More steps = smoother attribution, slower |

**How to read the result:**

- **Global feature importance**: per-feature mean absolute
  attribution across the test rows. The top of this table tells you
  which inputs matter most overall.
- **Per-row drill-down**: pick a row index, see each feature's value
  alongside its signed attribution (positive = pushed toward the
  target class, negative = pushed away). Useful for explaining a
  specific borderline decision to a domain expert.

**v0 scope:** tabular input only. Image / CV input (the *Quality
Inspection* and *Medical Imaging* use cases the website lists) is the
natural extension — same algorithm, just a different upload widget
and a heatmap visualisation. Tracked as a follow-up.

---

### 4.14 TextAttack — Art. 15 / NLP robustness

**What it does:** Adversarial evasion against a HuggingFace text
classifier. The website lists this as the secondary tool for
**Chatbots** + **Content Moderation** + **Sentiment Analysis** — any
NLP system with a binary or multi-class label.

**What you need from the client:**

- A **HuggingFace model id** — either a public checkpoint
  (default: `distilbert-base-uncased-finetuned-sst-2-english` for
  binary sentiment) or one the customer published privately and gave
  you read access to.
- Optionally, a CSV with `text` + `label` columns to attack. If you
  don't supply one, the page uses a built-in 5-sample demo set.

**Configuration:**

| Setting | Default | Meaning |
| --- | --- | --- |
| Attack recipe | TextFoolerJin2019 | Most-cited tabular benchmark. Alternatives: `DeepWordBugGao2018`, `BAEGarg2019`. |
| Samples to attack | 3 | Each sample takes seconds; stay small while exploring (1–10). |

**How to read the result:**

| Pill | Meaning |
| --- | --- |
| **Samples** | Total attacked rows |
| **Successful attacks** | Rows whose predicted class flipped |
| **Success rate** | Successful / (Total − Skipped). <20 % ok, <50 % warning, ≥50 % critical |
| **Skipped (already wrong)** | Rows the model misclassified before any attack — TextAttack ignores these |

The **Per-sample results** table shows the original text alongside the
adversarial perturbation for every successful attack. Most flips come
from one or two synonym substitutions, which makes for a striking
client demo: "your sentiment classifier flips from POSITIVE to
NEGATIVE when 'fantastic' becomes 'amazing'."

**First-run note:** the chosen HuggingFace model downloads on the
first run (~250 MB for the default DistilBERT). Subsequent runs hit
the local cache. NLTK corpora (stopwords, wordnet, etc.) are also
fetched on first import — the page handles SSL cert workarounds for
macOS.

---

## 5. Combined Report

The **🧾 Combined Report** page runs every selected module against the
same project in one go and produces a single branded PDF for the customer
presentation.

Per-module configuration (demo vs. upload, thresholds) is inside the
*Per-module configuration* expander. The defaults match what the
individual pages use. Toggle modules on/off via the checkboxes above the
expander; disabled modules are skipped (and their config is greyed out).

After clicking **▶ Run all and generate combined PDF** you get:

- **⬇ Combined PDF** — branded cover page (gradient header, project +
  client metadata, Art. chips, brand footer) followed by the full
  report. This is the customer deliverable.
- **⬇ HTML preview** — same content as the PDF but as HTML, for sharing
  via email / Confluence.
- **⬇ Combined JSON** — the structured envelope. Useful for archival or
  feeding into a downstream system.

The Combined run is recorded in the audit log as a single
`combined`-module entry; the worst per-module severity wins for the
combined entry's colour.

---

## 6. Audit Log

Open **📜 Audit Log** to see every assessment run:

- One row per run with **when / module / project / status / actor /
  duration**
- Filter by project, module, severity, and limit to N most recent
- Export the filtered slice as **CSV** for client reporting or your own
  records

The log is the source of truth for "what happened on this engagement?"
— it survives even if the project is later deleted (project ID is set
to NULL but the project + client name snapshots remain).

---

## 7. Where files live

Generated artefacts land under
`artifacts/<CLI_id>_<Company>/<PRJ_id>_<Project>/`:

```
artifacts/
└── CLI0007_Cardio_Diagnostics_GmbH/
    └── PRJ0001_Article_10_Audit/
        ├── data/         # cached intermediate datasets
        ├── reports/      # JSON / CSV / PDF / HTML deliverables
        ├── analysis/     # plots saved by the toolchain
        └── documentation/
```

Per-module pages also expose download buttons that write the same files
to your browser's downloads folder. Use the artefacts directory when
you need to bundle several runs together; use the download buttons for
one-off deliveries to the customer.

---

## 8. Status legend

A unified colour scheme runs across every status pill:

| Colour | Meaning | When you see it |
|---|---|---|
| 🟢 **ok** | Within thresholds, EU AI Act compliant for this dimension | Everything in spec |
| 🟡 **warning** | Borderline; recommend remediation but not blocking | Quality 75–89, accuracy 70–84%, partial logging coverage |
| 🔴 **critical** | Out of compliance — high-risk deployment is blocked | High bias, accuracy <70%, missing logging, Article 12 gaps |
| ⚪ **info** | Neutral / not yet evaluated | Combined report before any module ran |

Numeric / enum status labels you'll see, by module:

| Module | Status labels |
|---|---|
| Data Quality | `EXCELLENT`, `GOOD`, `ACCEPTABLE`, `POOR` (drives the colour) |
| Bias | `NIEDRIG` / `LOW`, `MITTEL` / `MEDIUM`, `HOCH` / `HIGH` |
| Explainability | Numeric accuracy `92.3%`; compliance `ERFÜLLT` / gap-by-gap |
| Logging | Compliance percent `0–100%` |
| Monitoring | `GOOD`, `WARNING`, `CRITICAL` |
| Risk Register | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` (severity × likelihood) |
| Human Oversight | Compliance percent `0–100%` (Art. 14.4 checkpoint score) |
| Cybersecurity | Compliance percent `0–100%` (Art. 15(5) checkpoint) and `ART attack: NN% success` for active runs |
| Sustainability | Annual `kg CO₂eq` (informational, no threshold) |
| Incidents | `LOGGED INCxxxx` / `UPDATED INCxxxx` (severity-coloured) |
| Right to Explanation | `LOGGED RTExxxx` / `UPDATED RTExxxx` (status-coloured) |
| Model Card | `SAVED <model> v<version>` (info) |
| Captum | `IG <N> rows` (info) |
| TextAttack | `<recipe> NN%` success rate (severity-coloured) |
| Combined | The toolchain's combined `overall_status` string |

---

## 9. Troubleshooting

### "🔒 Please log in via the **Home** page"
The auth cookie expired or you opened a page in a fresh browser. Click
**Home** in the sidebar, sign in again, return to the page.

### "No projects in the database"
Either the database is empty (set up a Client → System → Project as in
section 2) or your Streamlit session is pointing at a different DB. Ask
the admin to confirm.

### "Privileged-groups columns missing from CSV"
The Bias page expected one column per key in the *Privileged groups*
JSON. Either rename the CSV columns to match the JSON keys, or change the
JSON keys to match what's in the CSV.

### "Could not unpickle <model>.pkl"
The pickle was created with a different Python or scikit-learn version,
or the file isn't actually a pickled object. Ask the client which Python
+ scikit-learn version they used; we may need to load it in a matching
environment and re-export.

### CSV upload fails with "missing required columns"
The page tells you exactly which columns it expected. Compare against
your CSV's header row — capitalisation matters (`y_true` ≠ `Y_True`).

### The combined PDF cover page looks off
Cover layout lives in `src/wavetest_app/branding/cover.py`. It's reportlab,
fast to tweak. Send a screenshot to the dev team; visual issues are easy
to fix.

### "DetachedInstanceError" or other crash
Take a screenshot of the full traceback (the URL helps too) and send it
to the dev team. The fix usually lands within an hour.

### "⛔ This page requires the admin role"

Your account is `analyst`-only. Ask an admin to upgrade you with
`python scripts/auth_set_role.py --username YOU --role admin`. The
change takes effect on the next page render — no Streamlit restart.

### Captum: "model loaded but attribution failed"

The most common cause is that the uploaded `.pt` file is a **state dict**
rather than a full pickled module. `torch.load(...)` returns the dict
and the page can't call it as a model. Re-save with
`torch.save(model, "path.pt")` (no `.state_dict()`) and re-upload.

### TextAttack: "Resource 'stopwords' not found" / SSL error

The first import of TextAttack tries to fetch NLTK corpora. On macOS
the system Python's SSL chain sometimes rejects nltk.org. The page
retries the download under an unverified context at runtime; if that
still fails (corporate proxy, offline laptop), open a Python shell
and run:

```python
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
import nltk
for pkg in ("stopwords", "wordnet", "punkt", "averaged_perceptron_tagger"):
    nltk.download(pkg)
```

Then refresh the page.

### TextAttack: HuggingFace model takes forever to download

First-run downloads can be 200–500 MB and depend on the customer's
network. The model goes into the local `~/.cache/huggingface/`
directory; subsequent runs are instant. If you're on a slow link,
keep the *Samples to attack* number low and run once to warm the cache.

### Evidently report fails on tiny frames

Evidently's `DataDriftPreset` needs enough rows on each side of the
split to compute a sensible test statistic. If the dataset has fewer
than ~50 rows total, the page falls back to "comparing the dataset
against itself" — a degenerate case but it doesn't crash. Ask the
customer for more monitoring data and re-run.

### Great Expectations validation throws "must be added to the DataContext"

The GE 1.x API changed; if you see this error your wavetest-app is
running an outdated `pages/1_Data_Quality.py`. Pull the latest from
`main`. If you're already on latest, send the traceback to the dev team.

### CodeCarbon: "country not found"
The dropdown shows ISO-3 country codes from CodeCarbon's data file. If
the customer's deployment region isn't covered (small islands, some
overseas territories), pick **Custom** and enter the carbon intensity
the customer's grid operator publishes.

---

**waveImpact GmbH** · Bremen · Internal tool
