"""Brand assets for waveTest reports (cover page, body, colours)."""

from wavetest_app.branding.body import render_body
from wavetest_app.branding.cover import BRAND_FROM, BRAND_TO, render_cover

__all__ = ["BRAND_FROM", "BRAND_TO", "render_cover", "render_body"]
