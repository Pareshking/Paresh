"""Two Dashboard panels from S91 (owner, 7 Nov 2026: "build it").

Momentum health reads data/momentum_health.csv (scripts/build_momentum_health.py,
monthly; method and the IIMA check in docs/MOMENTUM_HEALTH.md). Flows reads
data/fii_dii_flows.csv (scripts/collect_fii_dii.py, each trading evening). Both
files are written and checked by scheduled jobs on the failure alert; a panel
whose file is missing or too thin says so instead of drawing.
"""
from __future__ import annotations

import base64
import html
from pathlib import Path

import pandas as pd
import streamlit as st

from src.engine.momentum_health import health
from src.ui import formats as fmt
from src.ui.tokens import C

ROOT = Path(__file__).resolve().parents[3]
MOMENTUM_FILE = ROOT / "data" / "momentum_health.csv"
FLOWS_FILE = ROOT / "data" / "fii_dii_flows.csv"
IIMA_CHECK = "correlation 0.83 with IIM Ahmedabad's momentum factor, Feb 2010 to Dec 2025"


@st.cache_data(show_spinner=False, ttl=3600)
def _read(path: str, stamp: float) -> pd.DataFrame | None:
    try:
        return pd.read_csv(path)
    except Exception:  # noqa: BLE001
        return None


def _load(path: Path) -> pd.DataFrame | None:
    return _read(str(path), path.stat().st_mtime) if path.exists() else None


def ordinal(n: int) -> str:
    """1st, 2nd, 3rd, 4th, 11th, 12th, 13th, 21st, 42nd."""
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def percentile_word(p: float) -> str:
    return ("weak" if p < 20 else "below usual" if p < 40 else "about usual" if p < 60
            else "above usual" if p < 80 else "strong")


def _bars_svg(values: list[float], width: int = 300, height: int = 64) -> str:
    """Monthly spreads as diverging bars, as a data-URI image (st.html strips inline SVG)."""
    if not values:
        return ""
    top = max(max(abs(v) for v in values), 1e-9)
    mid = height / 2
    w = width / len(values)
    bars = []
    for i, v in enumerate(values):
        h = abs(v) / top * (mid - 2)
        y = mid - h if v >= 0 else mid
        bars.append(f'<rect x="{i * w + 1:.1f}" y="{y:.1f}" width="{max(w - 2, 1):.1f}" height="{max(h, 0.5):.1f}" '
                    f'fill="{C.up if v >= 0 else C.down}"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
           f'<line x1="0" x2="{width}" y1="{mid}" y2="{mid}" stroke="{C.rule}" stroke-width="1"/>{"".join(bars)}</svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def momentum_health_html(spreads: pd.DataFrame | None) -> str | None:
    h = health(spreads) if spreads is not None else None
    if h is None:
        return None
    month = pd.Period(h["month"], freq="M")
    t12, last = h["trailing_12m"], h["month_spread"]
    word = percentile_word(h["percentile"])
    lede = (f"Over the last 12 months the top fifth of our ranking beat the bottom fifth by "
            f"{fmt.signed(t12)} points: {word} ({ordinal(round(h['percentile']))} percentile since 2010). "
            f"{month:%B}: {fmt.signed(last)} points.")
    if t12 < 0:
        lede = (f"Over the last 12 months the top fifth of our ranking trailed the bottom fifth by "
                f"{fmt.signed(abs(t12), plus=False)} points: {word} ({ordinal(round(h['percentile']))} percentile "
                f"since 2010). {month:%B}: {fmt.signed(last)} points.")
    crash = (f'<p class="db-flag">{month:%B} was in the worst 10% of months since 2010: momentum '
             "stocks fell well behind the laggards.</p>") if h["crash"] else ""
    recent = spreads.tail(24)["spread"].astype(float).tolist()
    img = _bars_svg(recent)
    alt = (f"Monthly spread, top fifth minus bottom fifth, last {len(recent)} months: from "
           f"{fmt.signed(min(recent))} to {fmt.signed(max(recent))} points.")
    tone = "up" if t12 > 0 else "down" if t12 < 0 else ""
    return (f'<div class="db-mh"><div class="db-big {tone}">{fmt.signed(t12)}<span> pts, 12 months</span></div>'
            f'<p class="db-lede">{html.escape(lede)}</p>{crash}'
            f'<img src="{img}" alt="{html.escape(alt)}" width="300" height="64" style="max-width:100%"></div>')


def flows_html(flows: pd.DataFrame | None) -> str | None:
    if flows is None or flows.empty:
        return None
    f = flows.copy()
    f["date"] = pd.to_datetime(f["date"])
    last_day = f["date"].max()
    day = f[f["date"] == last_day].set_index("category")["net"]

    def side(cat: str, label: str) -> str:
        v = day.get(cat)
        if v is None or pd.isna(v):
            return f"<dt>{label}</dt><dd>—</dd>"
        word = "bought" if v > 0 else "sold"
        tone = "up" if v > 0 else "down"
        return (f'<dt>{label}</dt><dd><b class="{tone}">{fmt.inr(abs(v))} Cr</b> net {word}</dd>')

    rows = side("FII/FPI", "FII/FPI") + side("DII", "DII")
    days = f["date"].nunique()
    since = ""
    if days > 1:
        tot = f.groupby("category")["net"].sum()
        since = (f'<p class="db-note">Since {f["date"].min():%-d %b} ({days} sessions): foreign '
                 f'{fmt.inr(tot.get("FII/FPI", 0), plus=True)} Cr, domestic {fmt.inr(tot.get("DII", 0), plus=True)} Cr.</p>')
    return (f'<p class="db-lede">Cash market, {last_day:%-d %b %Y} (provisional).</p>'
            f'<dl class="db-kv">{rows}</dl>{since}')


def render(kit, left, right) -> None:
    """The two cards, momentum health on the left, flows on the right."""
    with left, kit.card("Momentum health", "db_mh", "top fifth minus bottom fifth"):
        out = momentum_health_html(_load(MOMENTUM_FILE))
        if out is None:
            kit.caption("Momentum health is not available right now: its monthly file is missing or "
                        "shorter than two years.")
        else:
            st.html(out)
            kit.caption("Each month-end the Nifty 500's members are ranked by this site's score; the "
                        "spread is the next month's return of the top fifth minus the bottom fifth. "
                        f"Bars: the last 24 months. Checked: {IIMA_CHECK}. How momentum has been "
                        "paying, not a forecast.")
    with right, kit.card("Flows", "db_flows", "FII and DII, NSE"):
        out = flows_html(_load(FLOWS_FILE))
        if out is None:
            kit.caption("Flows are not available right now.")
        else:
            st.html(out)
            kit.caption("NSE's provisional figures for the day, collected each trading evening. NSE "
                        "keeps no history of these, so the record starts on 6 Nov 2026.")
