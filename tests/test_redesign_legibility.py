"""The light redesign's two legibility promises, checked where they live.

The audit that started the redesign measured 8.3px card labels in #94A3B8 on
white (2.6:1). The design promised no text under 11px and 4.5:1 contrast for
every text colour on the backgrounds it sits on. These tests hold the CSS the
redesign added to that, so a later tweak cannot quietly undo it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.ui import screener_table, tokens

ROOT = Path(__file__).resolve().parents[1]
THEME = (ROOT / "src" / "ui" / "theme.py").read_text(encoding="utf-8")


def _block(start: str, end: str) -> str:
    a = THEME.index(start)
    return THEME[a:THEME.index(end, a)]


REDESIGN_CSS = {
    "top bar": _block(".st-key-app_header_shell {", "/* Keep the Streamlit popover"),
    "screener": _block("/* ── Screener page (redesign phase 2)", "/* ── Stock page (redesign phase 3)"),
    "stock page": _block("/* ── Stock page (redesign phase 3)", "/* ── Command Bar"),
    "screener table": screener_table._CSS,
}


@pytest.mark.parametrize("name", REDESIGN_CSS)
def test_no_redesigned_text_is_smaller_than_11px(name):
    # Sizes are theme tokens now (src/ui/tokens.py is the one theme file), so
    # the guard resolves them to px before measuring.
    css = tokens.resolve(REDESIGN_CSS[name])
    sizes = [float(n) for n in re.findall(r"font-size:\s*([\d.]+)px", css)]
    assert sizes, f"no font sizes found in the {name} CSS; the guard lost its target"
    small = [s for s in sizes if s < 11]
    assert not small, f"{name}: font sizes under 11px: {small}"


def _luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    chans = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in chans]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(fg: str, bg: str) -> float:
    a, b = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


# Every colour the redesign sets text in, and the surfaces it sets it on.
# Paper B · Ledger, white ground (owner, 7 Nov 2026).
TEXT_COLOURS = {
    "ink": "#1C1B19", "secondary": "#3A3A37", "muted": "#5F5F5B",
    "gain": "#1D5FA6", "loss": "#A4441A", "caution": "#B54708",
}
SURFACES = {"page": "#FFFFFF", "subtle": "#F7F7F5", "fill": "#F2F2EF"}


@pytest.mark.parametrize("fg", TEXT_COLOURS)
@pytest.mark.parametrize("bg", SURFACES)
def test_every_text_colour_meets_4_5_to_1(fg, bg):
    ratio = _contrast(TEXT_COLOURS[fg], SURFACES[bg])
    assert ratio >= 4.5, f"{fg} on {bg}: {ratio:.2f}:1"


def test_the_chips_keep_their_contrast_on_their_tints():
    pairs = [("#1D5FA6", "#EAF1F8"), ("#A4441A", "#F8ECE5"), ("#1C1B19", "#F2F2EF"),
             ("#154A82", "#EAF1F8"), ("#7A2E0E", "#FEF6EA")]
    for fg, bg in pairs:
        assert _contrast(fg, bg) >= 4.5, f"{fg} on {bg}: {_contrast(fg, bg):.2f}:1"


def test_the_range_bar_legend_keeps_its_swatches():
    """Unscoped, the bar's absolute marks rule also lifted the legend's two
    swatches out of the legend; one floated under the chart as a stray "|"
    (owner's phone screenshot, 26 Sep)."""
    css = REDESIGN_CSS["stock page"]
    absolute = [ln for ln in css.splitlines() if "position: absolute" in ln and "m-ema" in ln]
    assert absolute and all(".track i.m-" in ln for ln in absolute), absolute
    assert "position: static" in css[css.index(".sp-range .key i"):][:200]
