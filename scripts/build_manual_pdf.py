"""
scripts/build_manual_pdf.py — render docs/AUDIT_MANUAL.md as a branded PDF
=============================================================================

Local export only — we don't run this in CI. Produces
``docs/AUDIT_MANUAL.pdf`` with our brand cover prepended in front of the
Markdown body. Pure Python (markdown-pdf + PyMuPDF + pypdf + reportlab),
no system dependencies.

Run from the repo root::

    .venv/bin/python scripts/build_manual_pdf.py

Custom output / no cover::

    .venv/bin/python scripts/build_manual_pdf.py --output /tmp/manual.pdf
    .venv/bin/python scripts/build_manual_pdf.py --no-cover
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make src/ importable when running the script directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wavetest_app.branding.manual import build_manual_pdf  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = REPO_ROOT / "docs" / "AUDIT_MANUAL.md"
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "AUDIT_MANUAL.pdf"

DEFAULT_MODULES = [
    "Data Quality", "Bias Detection", "Explainability",
    "Logging Framework", "Performance Monitoring",
    "Risk Register", "Human Oversight", "Cybersecurity",
    "Sustainability", "Incidents", "Right to Explanation",
    "Model Card", "Captum", "TextAttack",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render docs/AUDIT_MANUAL.md as a branded PDF.",
    )
    parser.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT,
        help=f"Markdown source (default: docs/AUDIT_MANUAL.md).",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"PDF destination (default: docs/AUDIT_MANUAL.pdf).",
    )
    parser.add_argument(
        "--no-cover", action="store_true",
        help="Skip the brand cover page.",
    )
    args = parser.parse_args()

    out = build_manual_pdf(
        args.input,
        args.output,
        include_cover=not args.no_cover,
        modules_included=DEFAULT_MODULES,
    )
    size_kb = out.stat().st_size // 1024
    rel = out.relative_to(REPO_ROOT) if out.is_relative_to(REPO_ROOT) else out
    print(f"✅ {rel} ({size_kb:,} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
