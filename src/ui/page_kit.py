"""The parts every page is built from, so they all read alike.

The Screener set the pattern: a header that says what the page is for, one
strip of readings in plain words, cards for each block, at most one amber note
placed above what it qualifies. These helpers draw exactly that, with the
classes the shared stylesheet in src/ui/theme.py already styles.
"""
from __future__ import annotations

import html
import math
from urllib.parse import quote
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Literal

import streamlit as st


@dataclass(frozen=True)
class Reading:
    """One tile of a readings strip: label, figure, and what it means."""

    label: str
    value: str
    note: str = ""
    tone: str = ""  # "", "up", "down" or "warn"
    spark: str = ""  # a spark_img() beside the figure (S99), or ""


def sentence(text: str) -> str:
    """First letter capitalised, the rest as written (owner, 7 Nov: labels and
    asides began in lower case). Not str.capitalize(), which would lower
    "200D EMA" and "Nifty"."""
    text = str(text or "")
    # Only when the text starts with a letter: "2 holdings would be sold" keeps
    # its lower case after the figure.
    return text[:1].upper() + text[1:] if text[:1].isalpha() else text


def page_head(title: str, sub: str, *, actions: bool = False):
    """Title and one plain sentence. With actions=True, returns a container on
    the right for the page's main buttons (a download, a picker)."""
    head = (f'<div class="scr-head"><h1>{html.escape(title)}</h1>'
            f'<p>{html.escape(sentence(sub))}</p></div>')
    if not actions:
        st.html(head)
        return None
    left, right = st.columns([2.2, 1.8], vertical_alignment="bottom")
    with left:
        st.html(head)
    return right.container(horizontal=True, horizontal_alignment="right",
                           key=f"pg_actions_{_slug(title)}")


def _name_class(value: str) -> str:
    """A tile value that is a name (an industry), not a figure, reads smaller."""
    return " ms-name" if sum(c.isalpha() for c in value) > 8 else ""


def spark_img(s, w: int = 120, h: int = 28, last: int | None = 63) -> str:
    """A small trend line drawn beside a headline figure (S99, owner, 8 Nov
    2026: tipsheet puts one next to its numbers). Blue when the series ends
    above where it starts, rust when below; "" for fewer than five points.

    st.html strips inline <svg>, so the line travels as an image; an image
    cannot read CSS variables, so the colour is the token's value.
    """
    import base64

    import pandas as pd

    from src.ui.tokens import C

    v = pd.to_numeric(pd.Series(s), errors="coerce").dropna()
    if last:
        v = v.iloc[-last:]
    if len(v) < 5:
        return ""
    lo, hi = float(v.min()), float(v.max())
    span = (hi - lo) or 1.0
    pts = " ".join(f"{i * (w - 2) / (len(v) - 1) + 1:.1f},{h - 2 - (x - lo) / span * (h - 4):.1f}"
                   for i, x in enumerate(v))
    tone = C.up if v.iloc[-1] >= v.iloc[0] else C.down
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
           f'<polyline fill="none" stroke="{tone}" stroke-width="1.3" points="{pts}"/></svg>')
    data = base64.b64encode(svg.encode()).decode()
    # A short description, not alt="": the page's sanitiser drops an empty alt,
    # leaving the image unlabelled for screen readers (audit, 8 Nov 2026).
    trend = "rising" if v.iloc[-1] >= v.iloc[0] else "falling"
    return (f'<img src="data:image/svg+xml;base64,{data}" width="{w}" height="{h}" '
            f'alt="Trend line, {trend} over the period shown">')


def readings(tiles: list[Reading], label: str) -> None:
    """The strip of big figures under the header."""
    cells = "".join(
        f'<div class="ms-tile"><span class="ms-k">{html.escape(t.label)}</span>'
        f'<span class="ms-v {t.tone}{_name_class(t.value)}" title="{html.escape(t.value)}">'
        f'{html.escape(t.value)}</span>'
        + (f'<span class="ms-spark">{t.spark}</span>' if t.spark else "")
        + (f'<span class="ms-s">{html.escape(sentence(t.note))}</span>' if t.note else "")
        + "</div>"
        for t in tiles
    )
    st.html(f'<section class="mkt-strip pg-strip" aria-label="{html.escape(label)}">{cells}</section>')


def empty(lead: str, text: str = "") -> None:
    """An empty state in the page's own voice (audit F59): a plain line under a
    rule, not a coloured alert box."""
    st.html(f'<div class="pg-empty" role="status"><b>{html.escape(lead)}</b>'
            + (f" {html.escape(text)}" if text else "") + "</div>")


def note(lead: str, text: str = "") -> None:
    """The page's one amber note: a bold first line, then the detail."""
    st.html(f'<div class="pg-note" role="note"><b>{html.escape(lead)}</b>'
            + (f" {html.escape(text)}" if text else "") + "</div>")


@contextmanager
def card(title: str, key: str, aside: str = "") -> Iterator[None]:
    """A white card with a heading; anything drawn inside lands in it."""
    with st.container(key=f"pgcard_{key}"):
        st.html(f'<div class="pg-card-h"><h2 id="s-{_slug(key)}">{html.escape(title)}</h2>'
                + (f'<span>{html.escape(sentence(aside))}</span>' if aside else "") + "</div>")
        yield


def bar_list(rows: list[tuple[str, float, str, bool]], scale: float) -> str:
    """Label, bar and figure per row. `scale` is the value of a full bar; a
    flagged row (at a cap, say) is drawn in amber."""
    out = []
    for label, value, shown, flagged in rows:
        w = 0.0 if scale <= 0 else max(0.0, min(100.0, value / scale * 100))
        out.append(
            f'<div class="pg-bar"><span class="pg-bar-l">{html.escape(label)}</span>'
            f'<span class="pg-bar-t"><i class="{"warn" if flagged else ""}" style="width:{w:.1f}%"></i></span>'
            f'<span class="pg-bar-v">{html.escape(shown)}</span></div>'
        )
    return f'<div class="pg-bars">{"".join(out)}</div>'


@dataclass(frozen=True)
class Metric:
    """One figure inside a card: a label, the figure, and optionally how it moved.

    `tone` is st.metric's delta_color: "normal" (up is good), "inverse" (up is
    bad) or "off" (no colour). Delta colour is the only judgement drawn here.
    """

    label: str
    value: str
    delta: str | None = None
    tone: Literal["normal", "inverse", "off"] = "off"
    help: str | None = None


def _finite(x) -> float | None:
    try:
        v = float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def signed_number(v: float, digits: int = 1, plus: bool = True) -> str:
    """Rounded first, then signed with a true minus (U+2212): never "-0.0"."""
    r = round(v, digits)
    sign = ("+" if plus else "") if r > 0 else "\u2212" if r < 0 else ""
    return f"{sign}{abs(r):.{digits}f}"


def pts(x: float | None) -> str:
    """A difference between two returns (a fraction) in percentage points:
    0.083 -> "+8.3 pts" (owner, 8 Nov 2026, S97 d). Formatting only."""
    v = _finite(x)
    if v is None:
        return "\u2014"
    return f"{signed_number(100 * v)} pts"


def pct(x: float | None, signed: bool = True) -> str:
    """A fraction as a percentage for display; an em dash when it is not a
    finite number. Formatting only: no figure is computed here."""
    v = _finite(x)
    if v is None:
        return "\u2014"
    return f"{signed_number(100 * v, plus=signed)}%"



def metric_tile(m: Metric) -> None:
    """One bordered figure. Every tile in the app is drawn by this call, so a
    figure has the same border, radius and delta colouring on every page."""
    st.metric(m.label, m.value, delta=m.delta, delta_color=m.tone, help=m.help,
              border=True)


def metric_row(tiles: list[Metric], key: str) -> None:
    """A row of bordered figures, aligned to one baseline. The row wraps on a
    phone instead of squeezing four columns into 360px."""
    with st.container(horizontal=True, gap="small", vertical_alignment="top",
                      key=f"mrow_{key}"):
        for m in tiles:
            metric_tile(m)


def callout(title: str, body: str = "", tone: str = "muted") -> None:
    """A bordered, tinted block for a result that needs a word of explanation.
    Tones: "up", "down", "warn" or "muted". Text is escaped."""
    tone = tone if tone in ("up", "down", "warn", "muted") else "muted"
    st.html(f'<div class="pg-callout {tone}" role="note"><b>{html.escape(title)}</b>'
            + (f"<span>{html.escape(body)}</span>" if body else "") + "</div>")


_BADGE_COLOURS = {"up": "green", "down": "red", "warn": "orange", "info": "blue"}


def badge(label: str, tone: str = "") -> None:
    """A small status pill, drawn by Streamlit so it follows the theme."""
    st.badge(label, color=_BADGE_COLOURS.get(tone, "gray"))


def tradingview_url(symbol: str) -> str:
    """The symbol's chart on TradingView: an external site, so a new tab is right."""
    return "https://www.tradingview.com/chart/?symbol=" + quote(f"NSE:{symbol}", safe="")


def caption(text: str) -> None:
    st.html(f'<p class="pg-cap">{html.escape(sentence(text))}</p>')


def caption_link(text: str, href: str, label: str) -> None:
    """A caption that ends in a link onward (audit F33): "… on Actions →"."""
    st.html(f'<p class="pg-cap">{html.escape(text)} '
            f'<a class="pg-onward" href="{html.escape(href)}" target="_self">{html.escape(label)} →</a></p>')


def kv_line(pairs: list[tuple[str, str]], lead: str = "") -> None:
    """Settings in effect as one line of "name value" pairs; wraps on a phone."""
    cells = "".join(f"<span>{html.escape(k)} <b>{html.escape(v)}</b></span>" for k, v in pairs)
    st.html('<div class="pg-kv">' + (f"<b>{html.escape(lead)}</b>" if lead else "")
            + cells + "</div>")


def _slug(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in s).strip("_")


def equity_chart(
    dates,
    strategy: list[float],
    benchmark: list[float] | None,
    names: tuple[str, str] = ("Strategy", "Nifty 500"),
    key: str = "equity",
    fmt: str = "rupee",
    drawdown: list[float] | None = None,
) -> None:
    """Strategy against benchmark on real dates, with the drawdown under it when
    given. Values are drawn as passed (rupees, not growth factors), so a
    growth-factor formatter cannot multiply a portfolio value by 100. Hover for
    the date and every value."""
    from src.ui import lw_chart as lw

    if len(strategy) < 2:
        return
    series = [{"name": names[0], "type": "line", "color": lw.INDIGO, "fmt": fmt,
               "data": lw.series_points(dates, strategy)}]
    if benchmark:
        series.append({"name": names[1], "type": "line", "color": lw.GREY, "fmt": fmt,
                       "data": lw.series_points(dates, benchmark)})
    panes = [{"height": 300, "series": series}]
    if drawdown:
        panes.append({"height": 150, "series": [
            {"name": "Drawdown", "type": "baseline", "color": lw.RED, "negColor": lw.RED,
             "fmt": "pct", "data": lw.series_points(dates, drawdown, scale=100.0)}]})
    lw.render(panes, key=key)


def growth_chart(
    dates,
    strategy: list[float],
    benchmark: list[float] | None,
    names: tuple[str, str] = ("Strategy", "Nifty 500"),
    key: str = "growth",
) -> None:
    """Growth of 100: `strategy` and `benchmark` are growth factors (1.0 = the
    start), re-based to a start of 100 and drawn by equity_chart so the two
    charts cannot drift apart."""
    equity_chart(
        dates,
        [float(v) * 100.0 for v in strategy],
        None if not benchmark else [float(v) * 100.0 for v in benchmark],
        names=names, key=f"growth_{key}", fmt="num",
    )


# ── Editorial type (owner, 7 Nov) ──────────────────────────────────────────
# A serif for page titles, question headings, verdicts and headline figures;
# Plex Sans stays for body text and Plex Mono for dense tables. Loaded once by
# app.py for every page (prototyped on the Dashboard and Breadth, then rolled
# out on the owner's word). Source Serif 4 (SIL Open Font
# Licence), not tipsheet's own face, so the site keeps its own identity.
EDITORIAL_FONT = "app/static/fonts.css"   # self-hosted with the other faces (audit F61)
_EDITORIAL_CSS = """<style>
@import url('""" + EDITORIAL_FONT + """');
:root{--font-serif:'Source Serif 4','Source Serif Pro',Georgia,'Times New Roman',serif}
.scr-head h1{font-family:var(--font-serif)!important;font-weight:400!important;font-size:52px!important;
  line-height:1.06!important;letter-spacing:-0.6px!important;max-width:16em}
.scr-head p{font-size:17px!important;line-height:1.55!important;max-width:42em;color:var(--c-text_2)!important}
.scr-kicker{font-size:13px;color:var(--c-muted);margin:0 0 8px}
body .qp h2{font-family:var(--font-serif)!important;font-weight:400!important;font-size:40px!important;
  line-height:1.1!important;letter-spacing:-0.4px!important;margin-bottom:6px!important}
body .qp-v{font-family:var(--font-serif);font-weight:400;font-size:36px;letter-spacing:-0.3px}
body .qp-s{font-size:17px;max-width:38em}
body .qp h3{font-size:15px!important}
body .qp li{font-size:15px}
body .qp td.big{font-family:var(--font-serif);font-size:22px;font-weight:400;line-height:1.1}
body .qp td.big span.sub{font-family:var(--font-ui);font-size:12px;color:var(--c-muted);line-height:1.45;display:inline-block;margin-top:2px}
body .mq h2{font-family:var(--font-serif)!important;font-weight:400!important;font-size:24px!important;line-height:1.15!important}
body .mq-v{font-family:var(--font-serif);font-weight:400;font-size:32px;letter-spacing:-0.3px}
body .mq-s{font-size:15px}
.pg-card-h h2{font-family:var(--font-serif)!important;font-weight:400!important;font-size:24px!important}
.br-charts-h{font-family:var(--font-serif)!important;font-weight:400!important;font-size:32px!important}
.rng{position:relative;width:170px;height:14px;display:inline-block;vertical-align:middle}
.rng i.t{position:absolute;left:0;right:0;top:6px;height:2px;background:var(--c-rule)}
.rng i.m{position:absolute;top:4px;height:6px;border-radius:3px;background:var(--c-down_tint)}
.rng i.d{position:absolute;top:1px;width:12px;height:12px;margin-left:-6px;border-radius:50%;background:var(--c-ink)}
.rng i.d.up{background:var(--c-up)}.rng i.d.down{background:var(--c-down)}
/* Headline figures and the other titles, site-wide */
body .mkt-strip.pg-strip .ms-v, body [class*="st-key-mrow_"] [data-testid="stMetricValue"]{
  font-family:var(--font-serif)!important;font-weight:400!important;font-size:30px!important;letter-spacing:-0.3px!important}
body .mkt-strip.pg-strip .ms-v.ms-name{font-size:22px!important}
body h1.sp-name{font-family:var(--font-serif)!important;font-weight:400!important;font-size:44px!important;letter-spacing:-0.5px!important}
body .sp-price{font-family:var(--font-serif);font-weight:400;font-size:38px}
body .sp-rank-big span{font-family:var(--font-serif);font-weight:400;font-size:56px}
body .gd h2{font-family:var(--font-serif)!important;font-weight:400!important;font-size:28px!important;border-top-color:var(--c-ink)}
body .cfg-intro h2{font-family:var(--font-serif)!important;font-weight:400!important;font-size:24px!important}
body .cr-year-head h3{font-family:var(--font-serif);font-weight:400;font-size:22px}
body .gd p,body .gd li,body .gd dd{font-size:16px!important}
@media (max-width:900px){.scr-head h1{font-size:36px!important}.qp h2{font-size:30px!important}.rng{width:110px}}
</style>"""


def editorial_style() -> None:
    # @import inside the style: st.html drops <link> elements.
    st.html(_EDITORIAL_CSS)


def headline(kicker: str, title: str, sub: str = "") -> None:
    """A page that opens with a sentence of news, not a page name: a small
    kicker ("Dashboard · closes of 6 Nov"), the sentence as the title, then
    the detail."""
    st.html(f'<div class="scr-head"><p class="scr-kicker">{html.escape(kicker)}</p>'
            f'<h1>{html.escape(title)}</h1>'
            + (f'<p>{html.escape(sentence(sub))}</p>' if sub else "") + "</div>")
