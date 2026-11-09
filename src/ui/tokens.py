"""The site's theme in one place: every colour, size and space the UI uses.

Change the look here, nowhere else (owner, 7 Nov 2026: "theme separate, so in
future we can change it easily"). The current values are "Paper B · Ledger"
on a white ground.

How the rest of the UI reads it:

* CSS on the page writes `var(--c-<name>)` for a colour, `var(--fs-<n>)`
  for a type size, `var(--sp-<n>)` for a space, `var(--r-<n>)` for a corner
  and `var(--sh-<n>)` for a shadow. `css_root()` defines them all, and
  `theme.inject_custom_css()` puts them on every page. Change a value here
  and it changes everywhere it is used.
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
    "quiet": "#A9A9A4", "teal": "#3E8A83", "violet": "#6E5A9E", "grid": "#F0F0ED",
}

# ── Type: eight steps, each with one job (design audit, 8 Nov 2026) ──────
# The stylesheet had 39 distinct sizes, four of them inside a 1.5 px range
# doing the same work. A reader learns a page faster when a size means
# something. Chart labels never go below 12 px.
TYPE: dict[str, str] = {
    "12": "12px",      # column headers, labels, footnotes, chart axes
    "13": "13.5px",    # table rows, notes
    "15": "15px",      # body, a card's lede
    "17": "17px",      # a page's lede, one sentence
    "24": "24px",      # card title, section heading (serif)
    "30": "30px",      # the one figure a card is about (serif)
    "36": "36px",      # page headline on a phone (serif)
    "52": "52px",      # page headline (serif)
}

# ── Space: one ladder. Every margin, padding and gap lands on a rung. ─────
SPACE: dict[str, str] = {
    "1": "4px", "2": "8px", "3": "12px", "4": "16px",
    "5": "24px", "6": "32px", "7": "56px",
}

# ── Corners, rules and depth ─────────────────────────────────────────────
RADIUS: dict[str, str] = {"sm": "4px", "round": "50%"}
SHADOW: dict[str, str] = {
    # Only something that floats above the page casts one.
    "1": "0 1px 2px rgba(28, 27, 25, 0.04)",
    "2": "0 4px 12px -2px rgba(28, 27, 25, 0.08)",
    "pop": "0 12px 32px -8px rgba(28, 27, 25, 0.18)",
}

FONTS: dict[str, str] = {
    "ui": "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    "mono": "'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace",
    "serif": "'Source Serif 4', 'Source Serif Pro', Georgia, 'Times New Roman', serif",
    # Self-hosted (audit F61): static/fonts.css, served by Streamlit's static
    # folder. Relative, so it resolves against the app page, from srcdoc frames
    # too (locally /app/static/, on Streamlit Cloud /~/+/app/static/).
    "font_css": "app/static/fonts.css",
}

C = SimpleNamespace(**PALETTE)

_VAR = re.compile(r"var\(--(c|fs|sp|r|sh)-([a-z0-9_]+)\)")
_GROUPS = {"c": PALETTE, "fs": TYPE, "sp": SPACE, "r": RADIUS, "sh": SHADOW}


def css_root() -> str:
    """`:root { --c-ink: #1C1B19; ... }` for the page and for framed documents."""
    parts = [f"--c-{k}: {v};" for k, v in PALETTE.items()]
    parts += [f"--fs-{k}: {v};" for k, v in TYPE.items()]
    parts += [f"--sp-{k}: {v};" for k, v in SPACE.items()]
    parts += [f"--r-{k}: {v};" for k, v in RADIUS.items()]
    parts += [f"--sh-{k}: {v};" for k, v in SHADOW.items()]
    parts += [f"--font-{k}: {v};" for k, v in FONTS.items() if k != "font_css"]
    return ":root { " + " ".join(parts) + " }"


def resolve(text: str) -> str:
    """Write the theme into text bound for a frame or a canvas chart.

    A frame is its own document and cannot see the page's variables, so every
    `var(--c-…)`, `var(--fs-…)`, `var(--sp-…)`, `var(--r-…)` and `var(--sh-…)`
    is replaced by its value. An unknown name raises, so a typo cannot ship as
    an invisible colour or a missing size.
    """
    def sub(m: re.Match) -> str:
        group, name = m.group(1), m.group(2)
        table = _GROUPS[group]
        if name not in table:
            raise KeyError(f"unknown theme value --{group}-{name}")
        return table[name]
    return _VAR.sub(sub, text)
