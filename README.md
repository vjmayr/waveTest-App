# wavetest-app

Streamlit GUI for the [waveImpact Responsible AI Toolchain](https://github.com/waveImpactGmbH/RAI-TOOLCHAIN).
An internal multi-analyst tool that replaces the notebook-based workflow with a browser UI.

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
python -m wavetest_app.db.session --init

# 5. (Optional) Import your existing waveImpact_ClientManagement/*.json data
python scripts/import_console_json.py --toolchain ~/Documents/GitHub/RAI-TOOLCHAIN

# 6. Run the app
streamlit run Home.py
```

Streamlit serves on `http://localhost:8501` by default.

## Running tests

```bash
pytest tests/
```

## Schema migrations

Alembic is configured but no production migrations exist yet. After altering
`src/wavetest_app/db/models.py`:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

For first-time setup, `python -m wavetest_app.db.session --init` is enough — it issues
`CREATE TABLE` statements for the current model.

## Multi-analyst deployment (planned)

When deploying to a shared server:

1. Move SQLite DB to a persistent volume; configure backups via [Litestream](https://litestream.io)
2. Add auth — recommended: [streamlit-authenticator](https://github.com/mkhorasani/Streamlit-Authenticator) or a reverse proxy (nginx + OIDC)
3. Mount the `artifacts/` directory on a shared volume so all analysts see the same outputs

These are not in scope for the initial scaffold but the architecture is designed for them.

---

**waveImpact GmbH** · Bremen, Germany
