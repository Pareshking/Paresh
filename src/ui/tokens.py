"""The site's theme in one place: every colour and font the UI uses.

Change the look here, nowhere else (owner, 7 Nov 2026: "theme separate, so in
future we can change it easily"). The current values are "Paper B · Ledger"
on a white ground.

How the rest of the UI reads it:

* CSS on the page writes `var(--c-<name>)`. `css_root()` defines those
  variables, and `theme.inject_custom_css()` puts them on every page.
* Documents drawn in their own frame (the Screener table, the sector table,
  the charts) and canvas charts cannot see the page's variables, so the code
  that sends them passes the text through `resolve()`, which writes the
  colours in.
* Python that needs a colour as a value (a chart series, a chip with an alpha
  suffix) uses `C.<name>`.

`.streamlit/config.toml` cannot read Python, so it repeats a few of these;
`tests/test_theme_tokens.py` fails if the two disagree.
"""
from __future__ import annotations

import re
from types import SimpleNamespace

PALETTE: dict[str, str] = {
    # ink and text
    "ink": "#1C1B19", "ink_2": "#2B2A27", "text_2": "#3A3A37",
    "muted": "#5F5F5B", "muted_2": "#6E6E69", "faint": "#70706B",
    # ground and surfaces
    "ground": "#FFFFFF", "white": "#FFFFFF",
    "subtle": "#F7F7F5", "fill": "#F2F2EF", "fill_soft": "#FAFAF8",
    # rules
    "rule": "#E6E6E3", "rule_soft": "#EEEEEB", "rule_strong": "#D6D6D2",
    # up (blue)
    "up": "#1D5FA6", "up_dark": "#154A82", "up_tint": "#EAF1F8",
    "up_tint_2": "#F3F7FB", "up_tint_3": "#F7FAFD", "up_line": "#D5E3F1", "up_line_2": "#C9DBEE",
    # down (rust)
    "down": "#A4441A", "down_dark": "#7F3414", "down_tint": "#F8ECE5", "down_tint_2": "#FBF3EF",
    "down_line": "#F5E2D8", "down_line_2": "#EED6C9", "down_line_3": "#EAC9B8", "down_line_4": "#E4BBA6",
    # caution (stale data, warnings)
    "caution": "#B54708", "caution_ink": "#7A2E0E", "caution_tint": "#FEF6EA", "caution_line": "#F5D7A8",
    # charts: two series hues that are neither up, down nor caution (the
    # 20-day EMA, the Nifty 500 overlay, a third breadth line); the faint grid
    "teal": "#3E8A83", "violet": "#6E5A9E", "grid": "#F0F0ED",
}

FONTS: dict[str, str] = {
    "ui": "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "mono": "'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
    # Self-hosted (audit F61): static/fonts.css, served by Streamlit's static
    # folder. Relative, so it resolves against the app page, from srcdoc frames
    # too (locally /app/static/, on Streamlit Cloud /~/+/app/static/).
    "font_css": "app/static/fonts.css",
}

C = SimpleNamespace(**PALETTE)

_VAR = re.compile(r"var\(--c-([a-z0-9_]+)\)")


def css_root() -> str:
    """`:root { --c-ink: #1C1B19; ... }` for the page and for framed documents."""
    body = " ".join(f"--c-{k}: {v};" for k, v in PALETTE.items())
    return f":root {{ {body} }}"


def resolve(text: str) -> str:
    """Write the colours into text bound for a frame or a canvas chart.

    Only `var(--c-<name>)` for names in PALETTE is replaced; any other
    variable is left alone. An unknown name raises, so a typo cannot ship as
    an invisible colour.
    """
    def sub(m: re.Match) -> str:
        name = m.group(1)
        if name not in PALETTE:
            raise KeyError(f"unknown theme colour --c-{name}")
        return PALETTE[name]
    return _VAR.sub(sub, text)
