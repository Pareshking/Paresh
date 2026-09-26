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

from src.ui import screener_table

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
    sizes = [float(n) for n in re.findall(r"font-size:\s*([\d.]+)px", REDESIGN_CSS[name])]
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
TEXT_COLOURS = {
    "ink": "#0E1726", "secondary": "#3C4657", "muted": "#5E6878",
    "quiet": "#667080", "gain": "#067647", "loss": "#B42318",
    "caution": "#B54708", "link": "#4338CA",
}
SURFACES = {"card": "#FFFFFF", "page": "#F6F7F9", "subtle": "#F4F5F8"}


@pytest.mark.parametrize("fg", TEXT_COLOURS)
@pytest.mark.parametrize("bg", SURFACES)
def test_every_text_colour_meets_4_5_to_1(fg, bg):
    ratio = _contrast(TEXT_COLOURS[fg], SURFACES[bg])
    assert ratio >= 4.5, f"{fg} on {bg}: {ratio:.2f}:1"


def test_the_chips_keep_their_contrast_on_their_tints():
    pairs = [("#067647", "#E8F5EE"), ("#B42318", "#FDEDEB"), ("#3730A3", "#EEF0FF"),
             ("#054F31", "#E8F5EE"), ("#7A2E0E", "#FEF6EA")]
    for fg, bg in pairs:
        assert _contrast(fg, bg) >= 4.5, f"{fg} on {bg}: {_contrast(fg, bg):.2f}:1"
