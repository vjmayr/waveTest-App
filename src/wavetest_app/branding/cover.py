"""
wavetest_app.branding.cover — Branded title page for the combined PDF
========================================================================

Renders a single-page cover that gets merged in front of the toolchain's
report PDF. Matches the in-app page-header gradient (#667eea → #764ba2)
so the printed deliverable feels like part of the same product.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Sequence

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

BRAND_FROM = HexColor("#667eea")
BRAND_TO = HexColor("#764ba2")
TEXT_DARK = HexColor("#1f2434")
TEXT_MUTED = HexColor("#6b7388")
CHIP_BG = HexColor("#eef1f9")
CHIP_FG = HexColor("#445066")


def _draw_gradient_band(c: canvas.Canvas, x: float, y: float,
                        w: float, h: float, steps: int = 80) -> None:
    """Fake a linear gradient via thin horizontal slices.

    reportlab does have ``Canvas.linearGradient``, but its behaviour
    varies across backends (PDF viewers render the shading differently
    when combined with ``setFillAlpha``). Slicing is verbose but
    bullet-proof and previews identically everywhere.
    """
    for i in range(steps):
        t = i / max(steps - 1, 1)
        r = BRAND_FROM.red + (BRAND_TO.red - BRAND_FROM.red) * t
        g = BRAND_FROM.green + (BRAND_TO.green - BRAND_FROM.green) * t
        b = BRAND_FROM.blue + (BRAND_TO.blue - BRAND_FROM.blue) * t
        c.setFillColorRGB(r, g, b)
        slice_h = h / steps
        c.rect(x, y + i * slice_h, w, slice_h + 0.5, fill=1, stroke=0)


def render_cover(
    output_path: Path,
    *,
    project_id: str,
    project_name: str,
    client_name: str,
    modules_included: Sequence[str] = (),
    articles: Iterable[str] = ("10", "12", "13", "15", "61", "72"),
    generated_at: Optional[datetime] = None,
    subtitle: str = "EU AI Act Conformity Assessment",
) -> Path:
    """Render the cover to ``output_path``. Returns the path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = generated_at or datetime.now()

    c = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4

    # --- Top brand band (gradient, 7 cm tall)
    band_h = 7 * cm
    _draw_gradient_band(c, 0, height - band_h, width, band_h)

    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 34)
    c.drawString(2 * cm, height - 3.2 * cm, "Compliance Report")
    c.setFont("Helvetica", 14)
    c.drawString(2 * cm, height - 4.3 * cm, subtitle)

    # Article chips inside the band
    chips_y = height - band_h + 1.2 * cm
    chip_x = 2 * cm
    c.setFont("Helvetica-Bold", 9)
    for art in articles:
        text = f"EU AI Act Art. {art}"
        text_w = c.stringWidth(text, "Helvetica-Bold", 9)
        chip_w = text_w + 0.6 * cm
        c.setFillColor(white)
        c.setFillAlpha(0.18)
        c.roundRect(chip_x, chips_y, chip_w, 0.65 * cm,
                    0.18 * cm, fill=1, stroke=0)
        c.setFillAlpha(1.0)
        c.setFillColor(white)
        c.drawString(chip_x + 0.3 * cm, chips_y + 0.18 * cm, text)
        chip_x += chip_w + 0.2 * cm

    # --- Body — project metadata
    body_top = height - band_h - 1.5 * cm
    label_x = 2 * cm
    value_x = 2 * cm

    def _row(y: float, label: str, value: str, value_size: int = 16) -> float:
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 10)
        c.drawString(label_x, y, label.upper())
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica-Bold", value_size)
        c.drawString(value_x, y - 0.6 * cm, value)
        return y - 1.8 * cm

    y = body_top
    y = _row(y, "Project", project_name, value_size=20)
    c.setFillColor(TEXT_MUTED)
    c.setFont("Helvetica", 10)
    c.drawString(value_x, y + 1.0 * cm, f"ID: {project_id}")

    y = _row(y, "Client", client_name)

    if modules_included:
        c.setFillColor(TEXT_MUTED)
        c.setFont("Helvetica", 10)
        c.drawString(label_x, y, "MODULES INCLUDED")
        c.setFillColor(TEXT_DARK)
        c.setFont("Helvetica", 12)
        for i, module in enumerate(modules_included):
            c.drawString(value_x, y - 0.6 * cm - i * 0.55 * cm, f"• {module}")

    # --- Footer brand strip
    footer_h = 1.2 * cm
    c.setFillColor(BRAND_TO)
    c.rect(0, 0, width, footer_h, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica", 9)
    c.drawString(2 * cm, 0.45 * cm, "waveImpact GmbH · Bremen")
    c.drawRightString(
        width - 2 * cm, 0.45 * cm,
        f"Generated {generated_at.strftime('%Y-%m-%d %H:%M')}",
    )

    c.showPage()
    c.save()
    return output_path
