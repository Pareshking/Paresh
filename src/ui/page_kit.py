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


def page_head(title: str, sub: str, *, actions: bool = False):
    """Title and one plain sentence. With actions=True, returns a container on
    the right for the page's main buttons (a download, a picker)."""
    head = (f'<div class="scr-head"><h1>{html.escape(title)}</h1>'
            f'<p>{html.escape(sub)}</p></div>')
    if not actions:
        st.html(head)
        return None
    left, right = st.columns([2.2, 1.8], vertical_alignment="bottom")
    with left:
        st.html(head)
    return right.container(horizontal=True, horizontal_alignment="right",
                           key=f"pg_actions_{_slug(title)}")


def readings(tiles: list[Reading], label: str) -> None:
    """The strip of big figures under the header."""
    cells = "".join(
        f'<div class="ms-tile"><span class="ms-k">{html.escape(t.label)}</span>'
        f'<span class="ms-v {t.tone}">{html.escape(t.value)}</span>'
        + (f'<span class="ms-s">{html.escape(t.note)}</span>' if t.note else "")
        + "</div>"
        for t in tiles
    )
    st.html(f'<section class="mkt-strip pg-strip" aria-label="{html.escape(label)}">{cells}</section>')


def note(lead: str, text: str = "") -> None:
    """The page's one amber note: a bold first line, then the detail."""
    st.html(f'<div class="pg-note" role="note"><b>{html.escape(lead)}</b>'
            + (f" {html.escape(text)}" if text else "") + "</div>")


@contextmanager
def card(title: str, key: str, aside: str = "") -> Iterator[None]:
    """A white card with a heading; anything drawn inside lands in it."""
    with st.container(key=f"pgcard_{key}"):
        st.html(f'<div class="pg-card-h"><h2>{html.escape(title)}</h2>'
                + (f'<span>{html.escape(aside)}</span>' if aside else "") + "</div>")
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


def pct(x: float | None, signed: bool = True) -> str:
    """A fraction as a percentage for display; an em dash when it is not a
    finite number. Formatting only: no figure is computed here."""
    try:
        v = float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "\u2014"
    if not math.isfinite(v):
        return "\u2014"
    return f"{v:+.1%}" if signed else f"{v:.1%}"


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
    st.html(f'<p class="pg-cap">{html.escape(text)}</p>')


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
