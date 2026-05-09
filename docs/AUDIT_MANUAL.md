# Running an EU AI Act Audit — Analyst Manual

This is the step-by-step guide for waveImpact analysts running an audit through
**wavetest-app**. It covers the full workflow (login → set up the engagement →
run assessments → deliver to the customer) and includes per-module input
requirements, example CSVs, and how to read the results.

> **Audience:** Internal consultants. Assumes you can navigate a web app, know
> what an AI system is, and have a basic feel for compliance work. No coding
> required — every assessment is launched from the browser UI.

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

After login, the sidebar shows **Signed in as <Your Name>** and a logout
button. The same identity is automatically stamped onto every assessment
run in the audit log — so when a customer asks "who ran this report?",
the answer is in the database.

### 1.2 Check the toolchain status

On the Home page, expand the **Toolchain status** panel. All six
`wavetest_*` packages should show ✓. If any show ❌, an admin needs to
run `./scripts/install_toolchain.sh` before you can run that module.

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

---

**waveImpact GmbH** · Bremen · Internal tool
