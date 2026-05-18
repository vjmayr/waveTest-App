# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project at a glance

`wavetest-app` is waveImpact GmbH's **Technical Compliance Toolkit** for
high-risk AI systems under the EU AI Act. It's a Streamlit GUI on top of
the frozen `RAI-TOOLCHAIN` (six `wavetest_*` Python packages installed
editable from a sibling checkout). The app owns persistence (SQLite +
SQLAlchemy 2.x + Alembic); the toolchain packages are pure libraries
imported by adapters.

Two indispensable companion docs:

- [HANDOVER.md](HANDOVER.md) — what's done, what's open, what was
  deliberately deferred. Read before proposing new follow-ups.
- [DEPLOYMENT.md](DEPLOYMENT.md) — Hetzner production runbook.
- [docs/AUDIT_MANUAL.md](docs/AUDIT_MANUAL.md) and
  [docs/INPUT_SPEC.md](docs/INPUT_SPEC.md) — analyst-facing workflow and
  the per-module input-data contract. Customer-facing.

## Common commands

```bash
# Run the full test suite (always uses in-memory SQLite, fast)
.venv/bin/python -m pytest tests/ -q

# Single file / single test
.venv/bin/python -m pytest tests/test_admin.py -q
.venv/bin/python -m pytest tests/test_admin.py::TestNextId::test_concurrent_callers_get_unique_ids -q

# Run the app locally (localhost:8501)
streamlit run Home.py

# Schema changes
alembic revision --autogenerate -m "describe the change"
alembic upgrade head

# Install heavy adversarial-testing extras only when needed
pip install -e '.[cv]'    # Captum (PyTorch CV attribution)
pip install -e '.[nlp]'   # TextAttack (transformers + nltk + datasets)
pip install -e '.[full]'  # both

# Add an analyst (interactive)
python scripts/auth_add_user.py
# Promote to admin
python scripts/auth_set_role.py --username YOU --role admin
```

No lint / format step is wired up — match existing style when editing.

## Architecture

```
Home.py                  # login gate + sidebar nav (Modules / Admin)
pages/0_..20_*.py        # Streamlit auto-discovers; numeric prefix = order
src/wavetest_app/
├── adapters/            # one per assessment module — bridges DB rows to
│                        # the toolchain orchestrators (5-10 lines each,
│                        # all using _common.ProjectSnapshot)
├── db/
│   ├── models.py        # SQLAlchemy 2.x Mapped[]; ~15 tables
│   ├── session.py       # engine + get_session() context manager; SQLite
│   │                    # PRAGMA foreign_keys=ON wired in via event
│   └── ids.py           # atomic next_id() — see below
├── ui/                  # shared Streamlit helpers (uploaders, pills, picker)
├── audit.py             # record_run() + audit_assessment() — see below
├── auth.py              # streamlit-authenticator wrapper; require_login()
│                        # and require_role() are the page-level gates
├── inputs.py            # central "Project Inputs" store (7 canonical
│                        # slots — see INPUT_SPEC §Z)
├── classification.py    # EU AI Act risk classifier (prohibited / high /
│                        # limited / minimal)
├── branding/            # in-app reportlab Platypus PDF body renderer
└── *.py                 # per-module business logic (risk, oversight,
                         # cybersecurity, sustainability, incidents, etc.)
alembic/versions/        # one revision per schema change; data seeds live
                         # inside the migration when needed (see e.g.
                         # 425a86c05930_add_id_sequences_table.py)
deploy/, scripts/setup_server.sh, DEPLOYMENT.md   # Hetzner ops
```

### Patterns to follow

**`next_id` is the only correct way to mint an `{PREFIX}{NNNN}` id.** It
runs an atomic `INSERT … ON CONFLICT(prefix) DO UPDATE SET next_value =
next_value + 1 RETURNING next_value` against the `id_sequences` table.
Semantics: monotonic, independent of the target table, race-safe across
processes. Deleting a row does **not** free its id — that's intentional
(audit traces stay stable). The `id_column` argument is vestigial; only
`prefix` matters.

**Every assessment page wraps its run in `audit_assessment(project,
module)`.** That context manager writes a `status="FAILED"` row to
`audit_log` on exception and re-raises. The success-path `record_run(…)`
goes *inside* the `with` block. Pre-flight validation that uses
`st.stop()` stays *outside* — Streamlit's `StopException` extends
`BaseException` so it's intentionally not caught.

**Adapters are deliberately trivial.** A new assessment module's adapter
is ~5–10 lines: snapshot the project via `_common.ProjectSnapshot`,
instantiate the toolchain orchestrator with kwargs read from the
snapshot, return it. Business logic belongs in the orchestrator (in
`RAI-TOOLCHAIN`) or in a sibling module under `src/wavetest_app/`, never
the adapter.

**Project Inputs are the central upload surface.** Seven canonical slots
(`dataset`, `dataset_train`, `sklearn_model`, `pytorch_model`,
`hf_model_id`, `privileged_groups_json`, `target_population_json`) live
in `project_inputs`. Pages should prefer reading from there via
`load_input()` over hosting their own uploaders. Pattern documented in
`docs/INPUT_SPEC.md §Z`.

**Audit-log writes never raise.** `record_run()` swallows DB exceptions
and logs them — a broken audit write must not break the assessment that
triggered it.

**SQLite foreign keys are ON.** Wired in `db/session.py` via a
`connect` event listener. Don't disable this; FK SET NULL semantics
(name-snapshot columns surviving a client/project delete) are core to
how the audit-log and incident/explanation tables work.

### Test conventions

Tests live in `tests/`. The `in_memory_db` fixture in `conftest.py`
monkeypatches the engine + sessionmaker — almost every test uses it.
File-backed SQLite is only used by the `next_id` concurrency test
(needs real connections across threads). Tests do **not** import
Streamlit; pages aren't unit-tested.

### Schema-change workflow

1. Edit `src/wavetest_app/db/models.py`.
2. `alembic revision --autogenerate -m "..."` — review the generated
   file; autogenerate misses data migrations and complex column type
   changes.
3. If existing rows need seeding (counter values, defaults computed from
   other columns, etc.), add the data step inside the same revision
   file's `upgrade()` — see
   `alembic/versions/425a86c05930_add_id_sequences_table.py` for the
   pattern.
4. `alembic upgrade head`.

## Things to know before editing

- **Don't add new heavy deps to `pyproject.toml` defaults.** The
  `[cv]` / `[nlp]` / `[full]` extras exist so analysts who don't run
  Captum / TextAttack don't pay the torch + transformers install cost.
  Heavy imports must be lazy (inside function bodies) so page modules
  still load without the extras installed.
- **Auth is YAML + bcrypt by design** for 1–3 analysts. The OIDC swap
  point is documented in HANDOVER.md if SSO ever becomes a requirement;
  don't pre-emptively rewrite the auth layer.
- **`auth/users.yaml`, `data/*.db`, `artifacts/*`, `auth/cookie.key` are
  gitignored.** Never commit these. The daily backup pipeline in prod
  uploads `auth/users.yaml` to Hetzner Object Storage; Litestream
  replicates the SQLite DB.
- **The `RAI-TOOLCHAIN` packages are frozen.** If a fix belongs upstream
  but is urgent, prefer a workaround in the app's adapter layer and add
  a tracking note in HANDOVER.md rather than patching the toolchain
  in-tree.
