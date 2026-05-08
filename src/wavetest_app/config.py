"""
wavetest_app — Configuration
==============================

All paths and the database URL flow through here. Override any value via
environment variables (prefix ``WAVETEST_``) for production deployment.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Repository / data roots
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(os.environ.get("WAVETEST_DATA_ROOT", REPO_ROOT / "data"))
ARTIFACTS_ROOT = Path(
    os.environ.get("WAVETEST_ARTIFACTS_ROOT", REPO_ROOT / "artifacts")
)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATA_ROOT.mkdir(parents=True, exist_ok=True)
DEFAULT_DB_PATH = DATA_ROOT / "wavetest_app.db"

DB_URL = os.environ.get(
    "WAVETEST_DB_URL", f"sqlite:///{DEFAULT_DB_PATH.absolute()}"
)

# ---------------------------------------------------------------------------
# Toolchain checkout — used by scripts/install_toolchain.sh and the JSON import
# ---------------------------------------------------------------------------
DEFAULT_TOOLCHAIN_ROOT = Path(
    os.environ.get(
        "WAVETEST_TOOLCHAIN_ROOT",
        Path.home() / "Documents/GitHub/RAI-TOOLCHAIN",
    )
)


def project_artifacts_dir(client_id: str, company_name: str,
                          project_id: str, project_name: str) -> Path:
    """Standard layout for one project's generated artefacts."""
    safe_company = company_name.replace(" ", "_")
    safe_project = project_name.replace(" ", "_")
    folder = ARTIFACTS_ROOT / f"{client_id}_{safe_company}" / f"{project_id}_{safe_project}"
    for sub in ("data", "reports", "analysis", "documentation"):
        (folder / sub).mkdir(parents=True, exist_ok=True)
    return folder
