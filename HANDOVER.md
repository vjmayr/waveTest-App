# Handover — wavetest-app

## ⚠ Working-directory rule

**All future development happens in this repo only.**
The toolchain at `/Users/vjmayr/Documents/GitHub/RAI-TOOLCHAIN` is treated
as a frozen dependency: do not modify, do not commit. If a toolchain change
is genuinely required (real bug, missing API), surface it explicitly and
ask before editing.

```
✅  edit  /Users/vjmayr/develop/wavetest-app/...
❌  edit  /Users/vjmayr/Documents/GitHub/RAI-TOOLCHAIN/...
```

The toolchain is installed editable into this repo's `.venv`, so its source
is on `sys.path` for inspection — that's fine. Only writes are off-limits.

---

## Repos at a glance

| Repo | Path | Role |
|---|---|---|
| `wavetest-app` | `/Users/vjmayr/develop/wavetest-app` | Streamlit GUI + persistence + orchestration. **All work here.** |
| `RAI-TOOLCHAIN` | `/Users/vjmayr/Documents/GitHub/RAI-TOOLCHAIN` | Six `wavetest_*` packages. **Frozen — do not modify.** |

The app imports the toolchain as a library; it never re-implements
fairness/explain/dataquality/logging/monitoring/report logic.

## What the app does

Internal multi-analyst tool that replaces the toolchain's notebook workflow
with a browser UI. Consultants log in, pick a project, run any of the five
EU AI Act assessments individually or all at once, and download a branded
combined PDF for the customer presentation.

## Architecture

```
wavetest-app/
├── Home.py                              # Streamlit entry — toolchain status + project tree
├── pages/                               # auto-discovered, sorted by leading number
│   ├── 0_Combined_Report.py             # all 5 → one PDF
│   ├── 1_Data_Quality.py                # Article 10 + GDPR Art. 9
│   ├── 2_Bias_Detection.py              # Articles 10/13/61
│   ├── 3_Explainability.py              # Article 13 (SHAP)
│   ├── 4_Logging_Framework.py           # Articles 12/72
│   ├── 5_Performance_Monitoring.py      # Articles 15/72
│   ├── 6_Clients.py                     # admin
│   ├── 7_Systems.py                     # admin (EU AI Act questionnaire)
│   ├── 8_Projects.py                    # admin
│   └── 9_Project_Types.py               # admin
├── src/wavetest_app/
│   ├── config.py                        # paths, DB URL, env-var overrides
│   ├── classification.py                # EU AI Act risk classifier
│   ├── db/
│   │   ├── session.py                   # engine + Base + get_session()
│   │   ├── models.py                    # Client, System, Project, ProjectType
│   │   └── ids.py                       # collision-safe next_id()
│   ├── adapters/                        # DB row → toolchain orchestrator
│   │   ├── _common.py                   # ProjectSnapshot + load_project_snapshot
│   │   ├── dataquality.py
│   │   ├── fairness.py
│   │   ├── explain.py
│   │   ├── logging.py
│   │   └── monitoring.py
│   └── ui/
│       ├── helpers.py                   # page_header, project_picker, risk_pill,
│       │                                  show_recommendations
│       └── uploads.py                   # csv_uploader, model_uploader,
│                                          array_csv_uploader
├── alembic/                             # configured; no migrations yet (init_db
│                                          uses Base.metadata.create_all)
├── scripts/
│   ├── install_toolchain.sh             # editable installs from sibling checkout
│   └── import_console_json.py           # one-shot waveImpact_ClientManagement → SQLite
├── tests/                               # 15 pytest tests, in-memory SQLite
├── data/                                # SQLite DB lives here (gitignored)
└── artifacts/                           # generated reports/dashboards (gitignored)
```

### Key technical decisions

- **Persistence**: SQLite + SQLAlchemy 2.x. Suitable for the team's scale
  (≤10 analysts). Migrate to Postgres if you ever need multiple services
  sharing the DB. Use Litestream for continuous S3 replication (~1 h to
  set up). Alembic is wired up but no production migrations exist —
  current `init_db()` does `Base.metadata.create_all()`.
- **Adapters never carry SQLAlchemy state across the boundary** — they
  load the project + first system, snapshot the strings/lists into a
  `ProjectSnapshot` dataclass, then close the session before the
  orchestrator instance is constructed. No `DetachedInstanceError`
  possible by construction.
- **PDF backend is reportlab**, not weasyprint. Zero system deps; works
  on any laptop. Weasyprint pulls Pango/Cairo system libraries which
  break on macOS without homebrew + careful path setup.
- **Combined report** orchestrates the five assessments and merges via
  `wavetest_report.ReportEnvelope.combined(*envelopes)` — the worst
  module's status drives the overall colour.
- **No auth yet**. App listens on localhost only. Multi-user deployment
  with auth is open work (see below).

## Setup (clean machine)

```bash
cd ~/develop/wavetest-app
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
./scripts/install_toolchain.sh ~/Documents/GitHub/RAI-TOOLCHAIN  # editable installs
python -m wavetest_app.db.session --init                        # creates SQLite tables
python scripts/import_console_json.py --toolchain ~/Documents/GitHub/RAI-TOOLCHAIN  # optional seed
streamlit run Home.py
```

## Test status

```bash
.venv/bin/python -m pytest tests/ -q
# 15 passed
```

Coverage:

- `tests/test_models.py` — 4 SQLAlchemy roundtrip tests against in-memory SQLite.
- `tests/test_admin.py` — 5 `next_id` tests (incl. the post-delete collision case)
  + 6 EU AI Act classifier tests.

## Recent commits (most recent first)

```
b979910  add real-CSV ingestion to four assessment pages + model upload to Explainability
6f507e1  add Combined Report page (all 5 assessments → one branded PDF)
9af793b  add 4 admin pages: Clients, Systems, Projects, Project Types
adfc884  add 4 remaining assessment pages + shared snapshot helper
c8c5ae9  initial commit: skeleton + JSON import + Data Quality page
```

## Known caveats

1. The `client_id` on a deleted client cascades to its systems and projects
   (intentional, but no soft-delete / audit trail yet).
2. `datetime.utcnow()` is used in a few places; deprecated in Python 3.12+.
   Switch to `datetime.now(UTC)` when convenient.
3. Streamlit's session state is per-browser-session: a refresh wipes
   in-progress assessment results unless they were already exported. The
   Combined Report writes its outputs to disk so its downloads survive a
   refresh; individual pages don't.
4. The IDE may show "Cannot find module 'streamlit'" / "Cannot find module
   'wavetest_*'" diagnostics — those are false positives from a linter
   pointing at the system Python. The `.venv` interpreter resolves
   everything correctly.

## Open follow-ups (priority order)

> **`next_id` second-order race.** A Python lock now serialises the
> read+compute inside `next_id()` (good defense-in-depth) but each
> caller's SQLAlchemy session establishes its read snapshot **before**
> the lock fires, so two concurrent submissions can still both see the
> same max and collide on commit. Proper fix: an ``id_sequences`` table
> with atomic ``INSERT … ON CONFLICT … RETURNING``. ~1 hour. Until then
> the user sees an `IntegrityError` if they're unlucky and just retries.
>
> **Combined Report audit-failure gap.** The 5 individual assessment pages
> wrap their run block in `audit_assessment(...)` so a mid-run exception
> writes a `status="FAILED"` audit entry. The Combined Report does not —
> wrapping its ~220-line orchestration via re-indent was rejected as too
> invasive for the value. If Combined throws mid-pipeline you'll see the
> Streamlit error but no audit row. Acceptable today; a small refactor
> (extract `_run_combined()` helper, call inside `audit_assessment`)
> would close the gap when convenient.


1. **Production deployment + Litestream** — the localhost-only auth is in
   place; what's outstanding is choosing a deploy target (internal Linux
   box / Docker), wiring the reverse proxy, and adding Litestream for
   continuous SQLite backups. Was bundled with the auth task in the
   original list; deferred to a separate task once a target is chosen.
2. **OIDC SSO option** — current auth is in-app username/password from
   `auth/users.yaml`. If SSO is later required, swap `wavetest_app.auth`
   for header-based identity from an oauth2-proxy and have it write
   `st.session_state["username"]` from `X-Forwarded-User`. The rest of
   the app already reads from session state.

### Recently closed

- **Risk Register (Art. 9)** — new `risk_register` table (Alembic
  migration `aea6f9f57c46`), `wavetest_app.risk` helper for the
  severity × likelihood matrix, page `pages/11_Risk_Management.py`
  with create / list / edit / delete, residual scoring, mitigation-
  status tracker, CSV export. Every change is captured in the audit
  log under module `risk_management`. CASCADE delete with the project.
  8 new pytest tests for the matrix and the persistence layer.
- **Auth gate** — `streamlit-authenticator` 0.4 + `auth/users.yaml`
  (gitignored, bcrypt-hashed passwords, random JWT cookie key generated by
  the bootstrap script). `Home.py` renders the login form; every other
  page calls `wavetest_app.auth.require_login()` which reads the cookie,
  drops a "Signed in as …" caption + logout button into the sidebar, and
  stops the page if not authenticated. The authenticated username flows
  into `audit_log.actor` automatically. Bootstrap with
  `python scripts/auth_add_user.py`.
- **Audit log table** — `audit_log` table + Alembic migration
  (`1403231b5deb_add_audit_log_table`). Each assessment page calls
  `wavetest_app.audit.record_run(...)` after a successful run, capturing
  module, status, severity colour, free-form detail, actor (OS login until
  auth lands), and duration. Project deletion sets the FK to NULL but
  preserves history via name snapshots. Page `10_Audit_Log.py` is a
  filterable read-only viewer with CSV export.
- **Branded title page** — `src/wavetest_app/branding/cover.py` renders a
  one-page reportlab cover (gradient band + project metadata + Article
  chips + brand footer) that gets prepended to the toolchain's PDF via
  pypdf. App-side only; toolchain stays frozen.
- **First Alembic migration** — `alembic/versions/f9bff52d1773_baseline_schema.py`
  creates all four tables. The live dev DB has been stamped at this revision;
  fresh setups use `alembic upgrade head` (see README). `init_db()` still works
  as a `create_all` shortcut but you should `alembic stamp head` after using it.
- **datetime.utcnow() migration** — replaced 13 call sites with
  `wavetest_app._time.utc_now()` (naive UTC, preserves on-disk format). Test
  suite is now warning-free.
- **Combined-report uploads** — `pages/0_Combined_Report.py` now offers a
  per-module Demo-vs-Upload radio (CSV for DataQuality / Bias / Monitoring,
  model + test/train CSVs for Explainability) so the customer presentation
  can run against real client data. Logging stays interview-only.

## Toolchain reference (frozen)

If you need to look up an API:

| Module | Public class / fn | What it does |
|---|---|---|
| `wavetest_dataquality` | `DataQualityAssessment`, `generate_demo_data`, `DataLoader` | Article 10 metrics + GDPR keyword scan + chi-square representativeness |
| `wavetest_fairness` | `FairnessAssessment`, `generate_demo_data` | AIF360-powered bias metrics |
| `wavetest_explain` | `ExplainabilityAssessment`, `AssessmentConfig`, `generate_demo_model` | SHAP global + local + consistency + Article 13 mapping |
| `wavetest_logging` | `LoggingAssessment`, `CurrentLoggingState`, `SystemProfile`, `AISystemLogger` | Article 12 gap analysis + framework code generator |
| `wavetest_monitoring` | `MonitoringAssessment`, `MonitoringConfig`, `MonitoringSystemProfile`, `generate_demo_monitoring_data` | Performance + KS drift + Z-score outliers |
| `wavetest_report` | `ReportEnvelope`, `JSONRenderer`, `HTMLRenderer`, `PDFRenderer` | Unified envelope; render JSON / HTML / PDF |

Every orchestrator exposes `from_project(project_id, console_path=…)` —
the app **does not** use that path; it instantiates orchestrators directly
via the adapters with kwargs from SQLite.

---

**waveImpact GmbH** · Bremen · Internal tool
