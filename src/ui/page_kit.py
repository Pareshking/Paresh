"""The parts every page is built from, so they all read alike.

The Screener set the pattern: a header that says what the page is for, one
strip of readings in plain words, cards for each block, at most one amber note
placed above what it qualifies. These helpers draw exactly that, with the
classes the shared stylesheet in src/ui/theme.py already styles.
"""
from __future__ import annotations

import html
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

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


def caption(text: str) -> None:
    st.html(f'<p class="pg-cap">{html.escape(text)}</p>')


def _slug(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "_" for c in s).strip("_")


def growth_chart(labels: list[str], strategy: list[float], benchmark: list[float] | None,
                 names: tuple[str, str] = ("Strategy", "Nifty 500"), key: str = "growth") -> None:
    """Growth of ₹100: two lines from a common start, with the end values in
    a legend above. `strategy` and `benchmark` are growth factors (1.0 = start)
    at each label. Drawn with Altair, which ships with Streamlit, so it needs
    no CDN and survives the HTML sanitiser that strips inline SVG."""
    import altair as alt

    if len(strategy) < 2:
        return

    def end(s, cls, name):
        v = s[-1]
        return (f'<span class="{cls}"><i></i>{html.escape(name)} '
                f'<b>₹{v * 100:,.0f}</b> ({"+" if v >= 1 else "−"}{abs(v - 1) * 100:.1f}%)</span>')

    st.html('<div class="gc-legend">' + end(strategy, "gc-ls", names[0])
            + (end(benchmark, "gc-lb", names[1]) if benchmark else "") + "</div>")

    rows = [{"x": i, "label": lab, "series": names[0], "value": v * 100}
            for i, (lab, v) in enumerate(zip(labels, strategy))]
    if benchmark:
        rows += [{"x": i, "label": lab, "series": names[1], "value": v * 100}
                 for i, (lab, v) in enumerate(zip(labels, benchmark))]
    data = pd.DataFrame(rows)
    step = max(1, len(labels) // 8)
    ticks = list(range(0, len(labels), step))
    label_expr = "{" + ",".join(f"{i}:'{labels[i]}'" for i in ticks) + "}[datum.value]"
    x = alt.X("x:Q", axis=alt.Axis(values=ticks, labelExpr=label_expr, title=None, grid=False,
                                   labelColor="#5E6878", tickColor="#E3E6EB", domainColor="#E3E6EB"),
              scale=alt.Scale(domain=[0, len(labels) - 1], nice=False))
    y = alt.Y("value:Q", scale=alt.Scale(zero=False),
              axis=alt.Axis(title=None, format=",.0f", labelColor="#5E6878", gridColor="#EDEFF3",
                            domain=False, ticks=False))
    colour = alt.Color("series:N", legend=None,
                       scale=alt.Scale(domain=list(names), range=["#4F46E5", "#98A1AE"]))
    lines = alt.Chart(data).mark_line(strokeWidth=2.5, interpolate="monotone").encode(
        x=x, y=y, color=colour,
        tooltip=[alt.Tooltip("label:N", title="When"), alt.Tooltip("series:N", title=""),
                 alt.Tooltip("value:Q", title="₹", format=",.1f")],
    )
    base = alt.Chart(pd.DataFrame({"y": [100]})).mark_rule(strokeDash=[4, 4], color="#D0D5DD").encode(y="y:Q")
    chart = (base + lines).properties(height=260).configure_view(strokeWidth=0).configure(background="#FFFFFF",
        font="Geist, system-ui, sans-serif")
    st.altair_chart(chart, width="stretch", key=f"gc_{key}")
