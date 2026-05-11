"""
wavetest_app.branding.manual — Markdown → branded PDF helper
================================================================

Pure-Python pipeline (markdown-pdf + PyMuPDF + pypdf + reportlab):

  1. ``markdown_pdf.MarkdownPdf`` renders the Markdown body to PDF.
  2. ``wavetest_app.branding.cover.render_cover`` renders the title page.
  3. ``pypdf.PdfWriter`` concatenates them.

Used by ``scripts/build_manual_pdf.py``. Extracted into a function so
pytest can exercise it.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from wavetest_app.branding.cover import render_cover

# `[label](#anchor)` — in-document fragment links that PyMuPDF's
# markdown-pdf backend can't resolve because its heading slugifier
# disagrees with the labels used in AUDIT_MANUAL.md's hand-written TOC
# (e.g. `## 1. Before you start` produces a different id than
# `#1-before-you-start`). The PDF gets its own outline-pane TOC via
# `toc_level`, so we strip the in-document links and keep the label
# text. External `[label](https://...)` links are untouched.
_FRAGMENT_LINK_RE = re.compile(r"\[([^\]]+)\]\(#[^)]*\)")


def _strip_fragment_links(md_text: str) -> str:
    """Replace ``[label](#anchor)`` with plain ``label`` (see _FRAGMENT_LINK_RE)."""
    return _FRAGMENT_LINK_RE.sub(r"\1", md_text)

# Brand CSS injected into the body — keeps tables readable, code blocks
# distinct, and headings on-brand.
BRAND_CSS = """
body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt;
       line-height: 1.45; color: #1f2434; }
h1 { color: #764ba2; font-size: 22pt; margin-top: 18pt;
     padding-bottom: 4pt; border-bottom: 2pt solid #667eea; }
h2 { color: #667eea; font-size: 16pt; margin-top: 16pt;
     padding-bottom: 2pt; border-bottom: 0.5pt solid #e1e4ee; }
h3 { color: #1f2434; font-size: 13pt; margin-top: 14pt; }
h4 { color: #1f2434; font-size: 11pt; margin-top: 10pt; }
p  { margin: 6pt 0; }
code { background: #f5f5f7; padding: 1pt 4pt; border-radius: 2pt;
       font-family: Menlo, Courier, monospace; font-size: 9pt; }
pre { background: #f5f5f7; padding: 8pt; border-radius: 3pt;
      font-family: Menlo, Courier, monospace; font-size: 8.5pt;
      line-height: 1.3; }
table { border-collapse: collapse; margin: 8pt 0; width: 100%; }
th { background: #eef1f9; text-align: left; padding: 4pt 6pt;
     border: 0.5pt solid #c8ccda; font-size: 9.5pt; }
td { padding: 4pt 6pt; border: 0.5pt solid #d8dbe5; vertical-align: top;
     font-size: 9.5pt; }
blockquote { border-left: 3pt solid #764ba2; margin-left: 0;
             padding-left: 12pt; color: #555a6b; font-style: italic; }
hr { border: 0; border-top: 0.5pt solid #c8ccda; margin: 14pt 0; }
a { color: #667eea; text-decoration: none; }
"""


def render_body(md_text: str, output_path: Path, *, toc_level: int = 3) -> Path:
    """Render Markdown text to PDF using markdown-pdf + PyMuPDF.

    A separate function so callers can test it without involving the cover
    or the merge step.
    """
    from markdown_pdf import MarkdownPdf, Section

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pdf = MarkdownPdf(toc_level=toc_level, optimize=True)
    pdf.meta["title"] = "waveTest Analyst Manual"
    pdf.meta["author"] = "waveImpact GmbH"
    pdf.meta["creator"] = "wavetest-app · scripts/build_manual_pdf.py"
    pdf.add_section(
        Section(_strip_fragment_links(md_text), paper_size="A4"),
        user_css=BRAND_CSS,
    )
    pdf.save(str(output_path))
    return output_path


def build_manual_pdf(
    input_md: Path,
    output_pdf: Path,
    *,
    include_cover: bool = True,
    project_id: str = "MANUAL",
    project_name: str = "Analyst Manual",
    client_name: str = "waveImpact GmbH (internal)",
    modules_included: Optional[Iterable[str]] = None,
    articles: Iterable[str] = (
        "9", "10", "11", "12", "13", "14", "15", "61", "72", "73", "86",
    ),
    subtitle: Optional[str] = None,
) -> Path:
    """Render ``input_md`` as a branded PDF at ``output_pdf``.

    Returns the output path. Both arguments are coerced to ``Path``.
    """
    from pypdf import PdfWriter

    input_md = Path(input_md)
    output_pdf = Path(output_pdf)
    if not input_md.exists():
        raise FileNotFoundError(f"input not found: {input_md}")
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    md_text = input_md.read_text(encoding="utf-8")

    body_pdf = output_pdf.with_name(output_pdf.stem + "__body.pdf")
    render_body(md_text, body_pdf)

    if not include_cover:
        body_pdf.replace(output_pdf)
        return output_pdf

    cover_pdf = output_pdf.with_name(output_pdf.stem + "__cover.pdf")
    render_cover(
        cover_pdf,
        project_id=project_id,
        project_name=project_name,
        client_name=client_name,
        modules_included=list(modules_included or []),
        articles=articles,
        generated_at=datetime.now(),
        subtitle=subtitle or (
            f"Step-by-step audit workflow · v"
            + datetime.now().strftime("%Y.%m.%d")
        ),
    )

    writer = PdfWriter()
    writer.append(str(cover_pdf))
    writer.append(str(body_pdf))
    with output_pdf.open("wb") as f:
        writer.write(f)
    writer.close()

    cover_pdf.unlink(missing_ok=True)
    body_pdf.unlink(missing_ok=True)
    return output_pdf
