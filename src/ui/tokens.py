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
    "muted": "#5F5F5B", "muted_2": "#6E6E69", "faint": "#6C6C67",
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
    # caution: stale data, warnings and "watch" states ONLY (owner, 23 Nov 2026,
    # S193 G). Never a series, a fill for a category or a marker; a chart that
    # needs another colour takes one from SERIES below or a grey.
    "caution": "#B54708", "caution_ink": "#7A2E0E", "caution_tint": "#FEF6EA", "caution_line": "#F5D7A8",
    # charts: the faint grid, and a quiet grey for a tooltip's date
    "quiet": "#A9A9A4", "grid": "#F0F0ED",
    # teal and violet each mean one series now (SERIES); the names stay for old callers
    "teal": "#3E8A83", "violet": "#6E5A9E",
    # One colour per series, the same on every chart (S193 G). None is the up
    # blue, the down rust or caution, each is at least 3:1 on white, and the
    # series drawn together stay apart under protanopia and deuteranopia
    # (CIEDE2000, Machado 2009 matrices; the numbers are in the S193 G PR).
    "s_book": "#1C1B19",      # the book (model book, portfolio, a backtest's rule): ink, solid
    "s_market": "#5F5F5B",    # Nifty Total Market: grey, dashed
    "s_n500": "#6E5A9E",      # Nifty 500: violet
    "s_mom50": "#6A7F14",     # Nifty500 Momentum 50: olive
    "s_ema20": "#8F3A84",     # 20 EMA on the stock chart: plum
    "s_ema50": "#3E8A83",     # 50 EMA / 50D EMA on the stock chart: teal
    "s_sma200": "#833F51",    # 200 SMA on the stock chart: wine
    "s_dii": "#968670",       # domestic institutions' flows (Dashboard flows bars): warm grey
    # Turning (Strong / Turning / Weak): the neutral middle of a diverging scale
    "mid": "#A9A9A4",
    # size groups, Large to Ultra Nano: one grey ramp, dark to light
    "size_1": "#1C1B19", "size_2": "#4A4A46", "size_3": "#77776F",
    "size_4": "#A3A39D", "size_5": "#C8C8C3", "size_6": "#E3E3DF",
}

# Series name -> PALETTE key. Every chart reads a named series' colour from
# here (series_colour / series_var), so one series is one colour on every page.
SERIES: dict[str, str] = {
    "The book": "s_book", "Model book": "s_book", "This rule": "s_book",
    "Nifty Total Market": "s_market",
    "Nifty 500": "s_n500",
    "Nifty500 Momentum 50": "s_mom50", "Momentum 50": "s_mom50",
    "20 EMA": "s_ema20",
    "50 EMA": "s_ema50", "50D EMA": "s_ema50",
    "200 SMA": "s_sma200",
    "Domestic flows": "s_dii",
}

# Lines for an unnamed set (each size index, each average's share): ink, blue
# and grey with dashes, never caution and never a SERIES hue. [(token, dashed)]
LINE_CYCLE: tuple[tuple[str, bool], ...] = (
    ("ink", False), ("up", False), ("muted", False), ("ink", True), ("up", True), ("muted", True))


def series_colour(name: str) -> str:
    """The hex of a named series (KeyError for a name SERIES does not hold)."""
    return PALETTE[SERIES[name]]


def series_var(name: str) -> str:
    """`var(--c-…)` for a named series, for CSS and frames that `resolve()`."""
    return f"var(--c-{SERIES[name]})"


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
    "36": "36px",      # section heading, page headline on a phone (serif)
    "44": "44px",      # the page's single biggest figure: a price, a rank (serif)
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
    # The "SS4 fallback" faces are the reader's own Noto Serif or Times resized to Source Serif 4's width, so the headline does not re-wrap
    # when the real face arrives (serif_face_css below).
    "serif": "'Source Serif 4', 'SS4 fallback Noto', 'SS4 fallback Times', "
             "Georgia, 'Times New Roman', serif",
    # Self-hosted (audit F61): static/fonts.css, served by Streamlit's static
    # folder. Relative, so it resolves against the app page, from srcdoc frames
    # too (locally /app/static/, on Streamlit Cloud /~/+/app/static/).
    "font_css": "app/static/fonts.css",
}

# Source Serif 4's vertical metrics (hhea and OS/2 typo, read from the woff2,
# units per em 1000), and for each stand-in the width of Source Serif 4 over
# the stand-in's for the same text. Widths were measured in Chromium on 19 Nov
# 2026 for a 150-character Dashboard sentence at 36px, the phone headline
# size: Source Serif 4 is a variable font whose display optical size narrows it
# as it grows (Noto ratio 0.928 at 24px, 0.902 at 36px, 0.869 at 52px), so one
# size-adjust is exact at one size and within about 4% at the others. Not the
# letter-frequency averages in @capsizecss/metrics: those are taken at text
# size and predicted 0.996 for Noto, which left the headline re-wrapping.
_SS4 = {"ascent": 1036, "descent": 335, "lineGap": 0, "upm": 1000}
_SERIF_FALLBACKS = {
    # name: (local() names tried in order, measured width ratio). Android's
    # serif is Noto Serif (measured: Google Fonts' Noto Serif v33). Linux has
    # Liberation Serif, metric-compatible with Times New Roman, which Apple
    # and Windows carry. Georgia is not listed: it could not be measured here,
    # and an unmeasured size-adjust can make the swap worse, not better.
    "Noto": (("Noto Serif", "NotoSerif-Regular", "NotoSerif"), 0.902),
    "Times": (("Times New Roman", "TimesNewRomanPSMT", "Liberation Serif", "LiberationSerif"), 1.056),
}


def fallback_overrides(target: dict, scale: float) -> dict[str, str]:
    """size-adjust and metric overrides that make a stand-in set text at `target`'s size.

    `scale` is target width over stand-in width for the same text. The
    vertical overrides are the target's metrics divided by the scale, because
    the browser applies size-adjust to them as well, so line boxes keep the
    target's height and baseline.
    """
    pct = lambda v: f"{v / target['upm'] / scale * 100:.2f}%"  # noqa: E731
    return {"size-adjust": f"{scale * 100:.2f}%", "ascent-override": pct(target["ascent"]),
            "descent-override": pct(target["descent"]), "line-gap-override": pct(target["lineGap"])}


def serif_face_css(fonts_css: str) -> str:
    """The page's @font-face rules for the serif: the real face and its stand-ins.

    Streamlit writes the rules for the theme's own families (config.toml
    [[theme.fontFaces]]) when the page opens; it writes none for a family the
    theme does not name, so the serif's rules travel in the page's first style
    block. `fonts_css` is static/fonts.css, whose Source Serif 4 rules are
    copied with their URLs made relative to the page, as the theme's are.
    """
    blocks = re.findall(r"@font-face \{[^}]*'Source Serif 4'[^}]*\}", fonts_css)
    out = [b.replace("url(fonts/", "url(app/static/fonts/") for b in blocks]
    for name, (locals_, scale) in _SERIF_FALLBACKS.items():
        src = ", ".join(f'local("{n}")' for n in locals_)
        props = "".join(f" {k}: {v};" for k, v in fallback_overrides(_SS4, scale).items())
        out.append(f"@font-face {{ font-family: 'SS4 fallback {name}'; src: {src};{props} }}")
    return "\n".join(out)


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
