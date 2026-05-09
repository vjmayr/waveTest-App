"""
wavetest_app.branding.body — clean exec-summary PDF body
=============================================================

The toolchain's ``PDFRenderer(engine="reportlab")`` fallback produces a
verbose dump of every metric, table, and chart placeholder; the result
is hard to hand to a customer. This module renders an opinionated
**executive summary** off the same ``ReportEnvelope`` using reportlab's
high-level Platypus API, so layout, pagination, and typography are
handled for us.

Scope: the deliverable now is **cover (one page) + this body (1–3 pages)
+ deeper per-module data attached separately as JSON**. If the customer
wants the metrics dump, they can pull it from the JSON envelope.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

BRAND_FROM = HexColor("#667eea")
BRAND_TO = HexColor("#764ba2")
TEXT_DARK = HexColor("#1f2434")
TEXT_MUTED = HexColor("#6b7388")
RULE = HexColor("#e1e4ee")
BG_OK = HexColor("#e6f4ec")
BG_WARN = HexColor("#fdf3e0")
BG_CRIT = HexColor("#fbe6e6")

_STATUS_BG = {
    "ok":       BG_OK,
    "warning":  BG_WARN,
    "critical": BG_CRIT,
    "info":     RULE,
}


def _styles() -> dict[str, ParagraphStyle]:
    """Custom paragraph styles. We deliberately avoid the default
    `getSampleStyleSheet()` h1/h2 sizes — they're too small for a
    customer-facing report.
    """
    base = getSampleStyleSheet()["BodyText"]
    return {
        "h1": ParagraphStyle(
            "h1", parent=base, fontName="Helvetica-Bold",
            fontSize=20, textColor=TEXT_DARK, spaceAfter=8, leading=24,
        ),
        "h2": ParagraphStyle(
            "h2", parent=base, fontName="Helvetica-Bold",
            fontSize=14, textColor=TEXT_DARK,
            spaceBefore=14, spaceAfter=4, leading=18,
        ),
        "h3": ParagraphStyle(
            "h3", parent=base, fontName="Helvetica-Bold",
            fontSize=11, textColor=TEXT_DARK,
            spaceBefore=8, spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "body", parent=base, fontName="Helvetica",
            fontSize=10.5, textColor=TEXT_DARK, leading=15,
            alignment=TA_LEFT, spaceAfter=4,
        ),
        "muted": ParagraphStyle(
            "muted", parent=base, fontName="Helvetica",
            fontSize=9, textColor=TEXT_MUTED, leading=13,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=base, fontName="Helvetica",
            fontSize=10.5, textColor=TEXT_DARK, leading=15,
            leftIndent=12, bulletIndent=0, spaceAfter=2,
        ),
    }


def _page_decorator(canvas, doc):
    """Footer on every page."""
    canvas.saveState()
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)
    canvas.setFillColor(TEXT_MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(2 * cm, 1.0 * cm, "waveImpact GmbH · waveTest")
    canvas.drawRightString(
        A4[0] - 2 * cm, 1.0 * cm, f"Page {doc.page}",
    )
    canvas.restoreState()


def render_body(
    envelope: Any,
    output_path: Path,
    *,
    project_label: str,
    panel_status: dict[str, tuple[str, str]] | None = None,
) -> Path:
    """Render the executive-summary PDF body.

    Parameters
    ----------
    envelope
        A ``wavetest_report.ReportEnvelope`` (combined or single-module).
    output_path
        Where to write the PDF.
    project_label
        e.g. ``"ACME / Cardio Audit"`` — used in the heading.
    panel_status
        Optional ``{module_label: (status_string, severity_color)}`` so
        the per-module strip shows the latest run's outcome. Pass the
        same dict the page already builds for the on-screen pills.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    styles = _styles()
    flow: list[Any] = []

    # ----------------------------------------------------------------- header
    flow.append(Paragraph(f"Executive Summary", styles["h1"]))
    flow.append(Paragraph(project_label, styles["muted"]))

    proj = getattr(envelope, "project", None)
    meta = getattr(envelope, "meta", None)
    if proj is not None or meta is not None:
        rows = []
        if proj is not None:
            rows.append([
                Paragraph("Project", styles["muted"]),
                Paragraph(
                    f"{getattr(proj, 'project_id', '—')} · "
                    f"{getattr(proj, 'project_name', '')}",
                    styles["body"],
                ),
            ])
            rows.append([
                Paragraph("Client", styles["muted"]),
                Paragraph(getattr(proj, "client_name", "") or "—",
                          styles["body"]),
            ])
            sys_name = getattr(proj, "system_name", "")
            if sys_name:
                rows.append([
                    Paragraph("System", styles["muted"]),
                    Paragraph(sys_name, styles["body"]),
                ])
        if meta is not None:
            rows.append([
                Paragraph("Generated", styles["muted"]),
                Paragraph(getattr(meta, "timestamp", "—"),
                          styles["body"]),
            ])
            rows.append([
                Paragraph("Report ID", styles["muted"]),
                Paragraph(getattr(meta, "report_id", "—"),
                          styles["body"]),
            ])
        meta_table = Table(
            rows, colWidths=[3 * cm, 13 * cm], hAlign="LEFT",
        )
        meta_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        flow.append(Spacer(1, 6))
        flow.append(meta_table)

    # ----------------------------------------------------- overall status box
    summary = getattr(envelope, "summary", None)
    if summary is not None:
        status_str = getattr(summary, "overall_status", "—")
        status_col = (getattr(summary, "status_color", "info") or "info").lower()
        bg = _STATUS_BG.get(status_col, RULE)

        status_table = Table(
            [[Paragraph(
                f'<font size="9" color="#6b7388">OVERALL STATUS</font><br/>'
                f'<font size="18" face="Helvetica-Bold" color="#1f2434">'
                f'{status_str}</font>',
                styles["body"],
            )]],
            colWidths=[16 * cm],
            hAlign="LEFT",
        )
        status_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("BOX", (0, 0), (-1, -1), 0.5, bg),
        ]))
        flow.append(Spacer(1, 14))
        flow.append(status_table)

        # Headline metrics — scoreboard-style table if any. Toolchain
        # emits this as either a dict (single-module) or a list of
        # ``HeadlineMetric`` objects (combined). Normalise both shapes.
        headline = getattr(summary, "headline_metrics", None) or []
        normalised: list[tuple[str, str]] = []
        if isinstance(headline, dict):
            normalised = [(str(k), str(v)) for k, v in headline.items()]
        else:
            for item in headline:
                if isinstance(item, dict):
                    normalised.append((
                        str(item.get("label") or item.get("name") or "—"),
                        str(item.get("value", "—")),
                    ))
                else:
                    label = getattr(item, "label", None) or getattr(item, "name", "—")
                    value = getattr(item, "value", "—")
                    normalised.append((str(label), str(value)))
        if normalised:
            flow.append(Paragraph("Headline metrics", styles["h2"]))
            cells = [
                [Paragraph(k, styles["muted"]),
                 Paragraph(v, styles["body"])]
                for k, v in normalised
            ]
            t = Table(cells, colWidths=[6 * cm, 10 * cm], hAlign="LEFT")
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]))
            flow.append(t)

    # ----------------------------------------------------------- module strip
    if panel_status:
        flow.append(Paragraph("Modules included", styles["h2"]))
        cells = []
        for label, (val, color) in panel_status.items():
            bg = _STATUS_BG.get(color, RULE)
            cells.append([
                Paragraph(label, styles["muted"]),
                Paragraph(
                    f'<font color="#1f2434" size="11">'
                    f'<b>{val}</b></font>',
                    styles["body"],
                ),
            ])
        if cells:
            t = Table(cells, colWidths=[6 * cm, 10 * cm], hAlign="LEFT")
            t.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]))
            flow.append(t)

    # ----------------------------------------------------------- key findings
    if summary is not None:
        findings = getattr(summary, "key_findings", None) or []
        if findings:
            flow.append(Paragraph("Key findings", styles["h2"]))
            for f in findings:
                flow.append(Paragraph(f"• {f}", styles["bullet"]))

        recs = getattr(summary, "recommendations", None) or []
        if recs:
            flow.append(Paragraph("Recommendations", styles["h2"]))
            for i, r in enumerate(recs, start=1):
                flow.append(Paragraph(f"{i}. {r}", styles["bullet"]))

    # ----------------------------------------------------------- back matter
    flow.append(Spacer(1, 14))
    flow.append(Paragraph(
        "_Detailed per-module data (metrics, distributions, charts) is "
        "attached separately as JSON. This document is the executive "
        "summary for the customer presentation._",
        styles["muted"],
    ))

    # -------------------------------------------------------------- assemble
    doc = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title=f"waveTest Executive Summary — {project_label}",
        author="waveImpact GmbH",
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height,
        id="main",
    )
    doc.addPageTemplates([PageTemplate(
        id="default", frames=[frame], onPage=_page_decorator,
    )])
    doc.build(flow)
    return output_path
