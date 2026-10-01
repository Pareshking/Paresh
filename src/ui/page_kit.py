"""The parts every page is built from, so they all read alike.

The Screener set the pattern: a header that says what the page is for, one
strip of readings in plain words, cards for each block, at most one amber note
placed above what it qualifies. These helpers draw exactly that, with the
classes the shared stylesheet in src/ui/theme.py already styles.
"""
from __future__ import annotations

import html
import math
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Literal

import pandas as pd
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


def toolbar(key: str):
    """The bar that holds a page's pickers and buttons, centred on one line."""
    return st.container(horizontal=True, vertical_alignment="center",
                        gap="small", key=f"tb_{key}")


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


def df_card(title: str, key: str, df: pd.DataFrame, *, column_config: dict | None = None,
            aside: str = "", height: int | str = "auto") -> None:
    """A card holding a configured st.dataframe, for tables that need no
    per-cell colouring or stock links (those stay on the HTML table renderers)."""
    with card(title, key, aside):
        st.dataframe(df, hide_index=True, width="stretch", height=height,
                     column_config=column_config or None)


def col_pct(label: str, *, fmt: str = "percent", help: str | None = None):
    """A column of fractions shown as percentages (0.123 -> 12.3%)."""
    return st.column_config.NumberColumn(label, format=fmt, help=help)


def col_rupee(label: str, *, help: str | None = None):
    """A column of rupee amounts, whole rupees with thousands separators."""
    return st.column_config.NumberColumn(label, format="\u20b9%,.0f", help=help)


def col_num(label: str, fmt: str = "%.2f", *, help: str | None = None):
    return st.column_config.NumberColumn(label, format=fmt, help=help)


def col_rank(label: str = "Rank", *, top: int = 750):
    """A rank drawn as a bar scaled to the list length (a longer bar is a
    larger rank number, i.e. a worse position)."""
    return st.column_config.ProgressColumn(label, min_value=0, max_value=top,
                                           format="%d")


def caption(text: str) -> None:
    st.html(f'<p class="pg-cap">{html.escape(text)}</p>')


def _slug(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in s).strip("_")


def equity_chart(
    labels: list[str],
    strategy: list[float],
    benchmark: list[float] | None,
    names: tuple[str, str] = ("Strategy", "Nifty 500"),
    key: str = "equity",
) -> None:
    """Render absolute portfolio equity values, not growth factors.

    The Portfolio history builder supplies rupee-denominated ending values.
    Keeping this chart contract explicit prevents a growth-factor formatter
    from accidentally multiplying real portfolio values by 100.
    """
    import altair as alt

    if len(strategy) < 2:
        return

    start_value = float(strategy[0])

    # The legend names each line's latest value only. The since-inception
    # percentage is not repeated here: the Equity view's figures are this
    # month's, and a cumulative % beside them read as the headline.
    def end(s, cls, name):
        v = float(s[-1])
        return (
            f'<span class="{cls}"><i></i>{html.escape(name)} '
            f'<b>₹{v:,.0f}</b></span>'
        )

    st.html(
        '<div class="gc-legend">'
        + end(strategy, "gc-ls", names[0])
        + (end(benchmark, "gc-lb", names[1]) if benchmark else "")
        + "</div>"
    )

    rows = [
        {"x": i, "label": lab, "series": names[0], "value": float(v)}
        for i, (lab, v) in enumerate(zip(labels, strategy))
    ]
    if benchmark:
        rows += [
            {"x": i, "label": lab, "series": names[1], "value": float(v)}
            for i, (lab, v) in enumerate(zip(labels, benchmark))
        ]
    data = pd.DataFrame(rows)
    step = max(1, len(labels) // 8)
    ticks = list(range(0, len(labels), step))
    label_expr = "{" + ",".join(f"{i}:'{labels[i]}'" for i in ticks) + "}[datum.value]"
    x = alt.X(
        "x:Q",
        axis=alt.Axis(
            values=ticks,
            labelExpr=label_expr,
            title=None,
            grid=False,
            labelColor="#5E6878",
            tickColor="#E3E6EB",
            domainColor="#E3E6EB",
        ),
        scale=alt.Scale(domain=[0, len(labels) - 1], nice=False),
    )
    y = alt.Y(
        "value:Q",
        scale=alt.Scale(zero=False),
        axis=alt.Axis(
            title=None,
            format=",.0f",
            labelColor="#5E6878",
            gridColor="#EDEFF3",
            domain=False,
            ticks=False,
        ),
    )
    colour = alt.Color(
        "series:N",
        legend=None,
        scale=alt.Scale(domain=list(names), range=["#4F46E5", "#98A1AE"]),
    )
    lines = alt.Chart(data).mark_line(
        strokeWidth=2.5, interpolate="monotone"
    ).encode(
        x=x,
        y=y,
        color=colour,
        tooltip=[
            alt.Tooltip("label:N", title="When"),
            alt.Tooltip("series:N", title=""),
            alt.Tooltip("value:Q", title="₹", format=",.0f"),
        ],
    )
    base = alt.Chart(pd.DataFrame({"y": [start_value]})).mark_rule(
        strokeDash=[4, 4], color="#D0D5DD"
    ).encode(y="y:Q")
    chart = (
        (base + lines)
        .properties(height=260)
        .configure_view(strokeWidth=0)
        .configure(background="#FFFFFF", font="Geist, system-ui, sans-serif")
    )
    st.altair_chart(chart, width="stretch", key=f"ec_{key}")


def growth_chart(
    labels: list[str],
    strategy: list[float],
    benchmark: list[float] | None,
    names: tuple[str, str] = ("Strategy", "Nifty 500"),
    key: str = "growth",
) -> None:
    """Growth of ₹100: `strategy` and `benchmark` are growth factors (1.0 =
    the start) at each label. They are re-based to a ₹100 start here and drawn
    by equity_chart, so the two charts cannot drift apart. The Backtest and
    Track Record pages draw this; equity_chart takes absolute rupee values."""
    base = 100.0
    equity_chart(
        labels,
        [float(v) * base for v in strategy],
        None if not benchmark else [float(v) * base for v in benchmark],
        names=names,
        key=f"growth_{key}",
    )


def drawdown_chart(labels: list[str], drawdown: list[float], key: str = "drawdown") -> None:
    """Render portfolio drawdown as a percentage, not as an equity-value chart."""
    import altair as alt

    if len(drawdown) < 2:
        return

    rows = [{"x": i, "label": lab, "drawdown": value * 100.0}
            for i, (lab, value) in enumerate(zip(labels, drawdown))]
    data = pd.DataFrame(rows)
    step = max(1, len(labels) // 8)
    ticks = list(range(0, len(labels), step))
    label_expr = "{" + ",".join(f"{i}:'{labels[i]}'" for i in ticks) + "}[datum.value]"
    x = alt.X(
        "x:Q",
        axis=alt.Axis(values=ticks, labelExpr=label_expr, title=None, grid=False,
                      labelColor="#5E6878", tickColor="#E3E6EB", domainColor="#E3E6EB"),
        scale=alt.Scale(domain=[0, len(labels) - 1], nice=False),
    )
    y = alt.Y(
        "drawdown:Q",
        scale=alt.Scale(domain=[min(0.0, float(data["drawdown"].min())), 0.0], nice=False),
        axis=alt.Axis(title="%", format=".1f", labelColor="#5E6878", gridColor="#EDEFF3",
                      domain=False, ticks=False),
    )
    area = alt.Chart(data).mark_area(opacity=0.16).encode(x=x, y=y)
    line = alt.Chart(data).mark_line(strokeWidth=2.5, interpolate="monotone").encode(
        x=x, y=y,
        tooltip=[
            alt.Tooltip("label:N", title="When"),
            alt.Tooltip("drawdown:Q", title="Drawdown (%)", format=".1f"),
        ],
    )
    zero = alt.Chart(pd.DataFrame({"y": [0.0]})).mark_rule(
        strokeDash=[4, 4], color="#D0D5DD"
    ).encode(y="y:Q")
    chart = (zero + area + line).properties(height=260).configure_view(
        strokeWidth=0
    ).configure(background="#FFFFFF", font="Geist, system-ui, sans-serif")
    st.altair_chart(chart, width="stretch", key=f"dd_{key}")
