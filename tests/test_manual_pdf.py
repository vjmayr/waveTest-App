"""Tests for the Markdown → PDF manual builder."""

from pathlib import Path

import pytest

from wavetest_app.branding.manual import build_manual_pdf, render_body


SAMPLE_MD = """\
# Sample Manual

This is a one-paragraph paragraph followed by a small table.

| Column A | Column B |
| --- | --- |
| 1 | foo |
| 2 | bar |

## Section heading

Some `inline code` and a fenced block:

```python
def hello():
    return "world"
```

> A blockquote, italic and **bold** text.
"""


def test_render_body_produces_a_pdf(tmp_path: Path):
    out = tmp_path / "body.pdf"
    render_body(SAMPLE_MD, out)
    assert out.exists()
    # PDFs always start with the magic %PDF- header
    assert out.read_bytes().startswith(b"%PDF-")
    # Body should be at least a couple of KB even for this tiny input
    assert out.stat().st_size > 1_000


def test_build_manual_pdf_with_cover(tmp_path: Path):
    src = tmp_path / "in.md"
    src.write_text(SAMPLE_MD)
    out = tmp_path / "manual.pdf"
    build_manual_pdf(
        src, out,
        modules_included=["Data Quality", "Bias Detection"],
    )
    assert out.exists()
    assert out.read_bytes().startswith(b"%PDF-")
    # Should be at least 2 pages (cover + body); pypdf can verify.
    from pypdf import PdfReader
    reader = PdfReader(str(out))
    assert len(reader.pages) >= 2

    # Temp cover/body files should be cleaned up
    assert not (tmp_path / "manual__cover.pdf").exists()
    assert not (tmp_path / "manual__body.pdf").exists()


def test_build_manual_pdf_without_cover(tmp_path: Path):
    src = tmp_path / "in.md"
    src.write_text(SAMPLE_MD)
    out = tmp_path / "manual.pdf"
    build_manual_pdf(src, out, include_cover=False)
    assert out.exists()
    from pypdf import PdfReader
    reader = PdfReader(str(out))
    # Body-only — fewer pages than the cover-included variant
    assert len(reader.pages) >= 1


def test_missing_input_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        build_manual_pdf(
            tmp_path / "does_not_exist.md", tmp_path / "out.pdf",
        )
