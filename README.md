# wavetest-app

Streamlit GUI for the [waveImpact Responsible AI Toolchain](https://github.com/waveImpactGmbH/RAI-TOOLCHAIN).
An internal multi-analyst tool that replaces the notebook-based workflow with a browser UI.

> **Analyst quickstart:** see [docs/AUDIT_MANUAL.md](docs/AUDIT_MANUAL.md) for
> the step-by-step audit workflow, per-module input requirements, example CSVs,
> and how to read the reports.

---

## Architecture

```
wavetest-app/
├── Home.py                         # Streamlit entry: landing page
├── pages/                          # Streamlit auto-discovers
│   └── 1_Data_Quality.py           # Assessment page (Article 10 + GDPR Art. 9)
├── src/wavetest_app/
│   ├── config.py                   # paths, DB URL
│   ├── db/
│   │   ├── models.py               # SQLAlchemy: Client, System, ProjectType, Project
│   │   └── session.py              # engine + session factory
│   ├── adapters/                   # bridge DB rows → toolchain orchestrators
│   │   └── dataquality.py
│   └── ui/                         # shared Streamlit helpers
├── scripts/
│   ├── install_toolchain.sh        # editable installs of the six wavetest_* packages
│   └── import_console_json.py      # one-shot: waveImpact_ClientManagement/*.json → SQLite
├── alembic/                        # schema migrations
├── data/                           # SQLite DB (gitignored)
├── artifacts/                      # generated reports/dashboards (gitignored)
└── tests/
```

The app **owns the persistence layer** (SQLite). The `wavetest_*` packages are imported as
libraries — the app instantiates each orchestrator with kwargs read from the DB and writes
artefacts to a per-project folder. Running an assessment never touches the toolchain repo.

## Prerequisites

- Python 3.10+
- The `RAI-TOOLCHAIN` repo checked out somewhere on disk (default expectation:
  `~/Documents/GitHub/RAI-TOOLCHAIN`).

## Setup

```bash
cd ~/develop/wavetest-app

# 1. Create a venv
python3 -m venv .venv
source .venv/bin/activate

# 2. Install the app + deps
pip install -e .

# 3. Editable-install the six wavetest_* packages from your toolchain checkout
./scripts/install_toolchain.sh ~/Documents/GitHub/RAI-TOOLCHAIN

# 4. Initialise the SQLite database (creates data/wavetest_app.db with all tables)
alembic upgrade head

# 5. (Optional) Import your existing waveImpact_ClientManagement/*.json data
python scripts/import_console_json.py --toolchain ~/Documents/GitHub/RAI-TOOLCHAIN

# 6. Bootstrap the first user (auth/users.yaml is gitignored)
python scripts/auth_add_user.py

# 7. Run the app
streamlit run Home.py
```

Streamlit serves on `http://localhost:8501` by default. The Home page renders
a login form; every other page is gated by the same auth cookie.

## Running tests

```bash
pytest tests/
```

## Schema migrations

Alembic is the source of truth for the schema. The `f9bff52d…_baseline_schema`
revision creates all four tables (`clients`, `systems`, `projects`,
`project_types`).

After altering `src/wavetest_app/db/models.py`:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

For first-time setup, `alembic upgrade head` creates the schema and stamps the
DB at the latest revision. `python -m wavetest_app.db.session --init` is still
available as a quick `Base.metadata.create_all()` shortcut for throwaway dev
databases — but if you use it, run `alembic stamp head` afterwards so future
migrations apply cleanly.

If you have an existing pre-Alembic database, stamp it once:

```bash
alembic stamp head
```

## Authentication

`streamlit-authenticator` gates every page. Credentials live in `auth/users.yaml`
(gitignored — never commit) with bcrypt-hashed passwords and a JWT cookie key.

**Add a user:**

```bash
python scripts/auth_add_user.py
# or non-interactively:
python scripts/auth_add_user.py --username jdoe --email jdoe@example.com \
    --name "John Doe" --password 's3cr3t'
```

The first run generates a random `cookie.key` and writes the file with mode
`0600`. Re-run to add more users; pass `--force` to overwrite an existing one.

Edits to `auth/users.yaml` are picked up on the next page render — no
Streamlit restart needed.

The authenticated username is automatically captured in the `audit_log.actor`
column for every assessment run.

## Multi-analyst deployment (planned)

When deploying to a shared server:

1. Move SQLite DB to a persistent volume; configure backups via [Litestream](https://litestream.io)
2. Mount the `artifacts/` directory on a shared volume so all analysts see the same outputs
3. Optionally swap the in-app auth for an OIDC reverse proxy (Caddy / nginx + oauth2-proxy) if SSO is required

These are not in scope for the localhost-only scaffold but the architecture is designed for them.

---

**waveImpact GmbH** · Bremen, Germany
