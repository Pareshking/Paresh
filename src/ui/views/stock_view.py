"""Single-stock page, as drawn in the approved light design.

Order, top to bottom:
  1. HERO       company, price with its close date, change chips; rank card
                with the path from three months ago and the score
  2. VERDICT    passes both screener filters, one, or neither -- by how much
  3. NOTICES    corporate action in the price history, when there is one
  4. CHART      price with EMAs and volume, relative strength beneath
  5. LADDER     where the price sits: 52-week range, filter line, EMA, ATH,
                stop levels when the source has intraday highs and lows
  6. RETURNS    gain vs pain: each window's return beside the fall it took,
                with the Nifty 500 and the typical stock on the same bars
  7. PEERS      the industry's best-ranked stocks, linked
  8. CHECKS     data caveats; opens itself when one needs reading
"""

from __future__ import annotations

import html as _html
from urllib.parse import quote as _quote

import numpy as np

import pandas as pd
import streamlit as st

from src.ui.system_param import stock_href
from src.engine.corporate_actions import load_events
from src.engine.momentum import CARRIED_MARK
from src.ui.charts import render_stock_chart
from src.ui.components import gap_count, render_data_quality_footer, to_bool_mask

# ── Palette tokens ───────────────────────────────────────────────────────────
POS   = "#067647"
NEG   = "#B42318"
WARN  = "#B54708"
ACC   = "#4F46E5"
INK   = "#0E1726"
SUB   = "#3C4657"
MUTED = "#5E6878"
LINE  = "#E3E6EB"

PERIODS = (1, 3, 6, 9, 12)
_LONG = {1: "1 month", 3: "3 months", 6: "6 months", 9: "9 months", 12: "12 months"}

INDEX_NAMES = {
    "N50": "Nifty 50", "NN50": "Nifty Next 50", "MID150": "Nifty Midcap 150",
    "SMALL250": "Nifty Smallcap 250", "MICRO250": "Nifty Microcap 250",
}


# ── Formatting primitives ────────────────────────────────────────────────────

def _num(value) -> float | None:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _money(value, decimals: int = 0) -> str:
    v = _num(value)
    return f"₹{v:,.{decimals}f}" if v is not None else "—"


def _pct(value, decimals: int = 1, signed: bool = True) -> str:
    v = _num(value)
    if v is None:
        return "—"
    return f"{v:+.{decimals}f}%" if signed else f"{v:.{decimals}f}%"


def _ratio(value, decimals: int = 2) -> str:
    v = _num(value)
    return f"{v:.{decimals}f}" if v is not None else "—"


def _sign_colour(value, neutral: str = INK) -> str:
    v = _num(value)
    if v is None:
        return neutral
    return POS if v > 0 else (NEG if v < 0 else neutral)


def _signed_pct(frac: float | None, decimals: int = 1) -> str:
    """A fraction as a signed percentage with a real minus sign."""
    if frac is None:
        return "—"
    sign = "+" if frac > 0 else "−" if frac < 0 else ""
    return f"{sign}{abs(frac) * 100:.{decimals}f}%"


def _flag(row: pd.Series, col: str) -> bool:
    return bool(to_bool_mask(pd.Series([row.get(col)])).iloc[0])


def _date_label(raw) -> str:
    if raw is None or str(raw).strip() in ("", "nan", "NaT", "None"):
        return ""
    try:
        return pd.Timestamp(str(raw)[:10]).strftime("%d %b %Y")
    except (ValueError, TypeError):
        return ""


def _html_block(markup: str) -> None:
    # st.markdown, not st.html: the page's tests read at.markdown, and the
    # shared stylesheet styles both the same.
    st.markdown(markup, unsafe_allow_html=True)


def _price_day() -> pd.Timestamp | None:
    from src.core import startup_metrics as _metrics

    try:
        day = pd.Timestamp(
            str(_metrics.snapshot().get("facts", {}).get("price_as_of") or "")[:10])
    except (ValueError, TypeError):
        return None
    return None if pd.isna(day) else day


# ── 1. HERO ──────────────────────────────────────────────────────────────────

def _render_identity(row: pd.Series, total_stocks: int) -> None:
    sym = str(row["Symbol"])
    name = str(row.get("Company Name") or "").strip() or sym
    industry = str(row.get("Industry") or "").strip()
    sector = str(row.get("TV_Sector") or "").strip()
    tags = [t.strip().upper() for t in str(row.get("Indices") or "").split(",") if t.strip()]

    # Exact tags, as indices_loader writes them (config.SHORT_FORMS). A
    # substring test ("50" in tag) once gave every MID150/SMALL250/MICRO250
    # stock a Nifty 50 badge.
    chips = f'<span class="sp-sym">{_html.escape(sym)}</span>'
    for t in tags:
        if t in ("—", "NAN"):
            continue
        chips += f'<span class="sp-tag">{_html.escape(INDEX_NAMES.get(t, t))}</span>'

    day = _price_day()
    mcap = _num(row.get("Market Cap (Cr)"))
    close_bits = [f"Close · {day:%a %d %b %Y}" if day is not None else "Close"]
    if mcap is not None:
        close_bits.append(f"Market cap ₹{mcap:,.0f} Cr")

    changes = ""
    for m in (1, 3, 12):
        v = _num(row.get(f"{m}M Return"))
        if v is None:
            continue
        cls = "up" if v > 0 else "down" if v < 0 else "flat"
        arrow = "▲" if v > 0 else "▼" if v < 0 else "•"
        changes += (
            f'<span class="sp-chg {cls}">'
            f'<i>{m}M</i><b>{arrow} {abs(v) * 100:.1f}%</b>'
            '</span>'
        )

    cls_parts = [p for p in (industry, sector) if p and p.lower() != "nan"]
    if len(cls_parts) == 2 and cls_parts[0] == cls_parts[1]:
        cls_parts = cls_parts[:1]
    cls_line = " · ".join(_html.escape(p) for p in cls_parts)

    rank = _num(row.get("Rank"))
    path = []
    for col, label in (
        ("Rank (-6M)", "6M"),
        ("Rank (-3M)", "3M"),
        ("Rank (-2M)", "2M"),
        ("Rank (-1M)", "1M"),
        ("Rank", "Now"),
    ):
        v = _num(row.get(col))
        if v is not None:
            path.append((int(v), label))
    path_html = ""
    if len(path) >= 2:
        steps = []
        for i, (r, label) in enumerate(path):
            cls = "now" if label == "now" else ""
            steps.append(f'<span class="sp-step {cls}"><b>#{r}</b><i>{label}</i></span>')
            if i < len(path) - 1:
                steps.append('<span class="sp-arrow">→</span>')
        path_html = f'<div class="sp-path">{"".join(steps)}</div>'
    score = _num(row.get("Score"))
    hz = _num(row.get("Horizons Scored"))
    facts = []
    if score is not None:
        facts.append(f"<span>Score <b>{score:.3f}</b></span>")
    if hz is not None:
        facts.append(f"<span>Horizons scored <b>{int(hz)} of 5</b></span>")

    _html_block(
        '<section class="sp-hero">'
        '<div class="sp-card sp-id">'
        f'<div class="sp-chips">{chips}</div>'
        f'<div class="sp-cls">{cls_line}</div>'
        f'<h1 class="sp-name">{_html.escape(name)}</h1>'
        '<div class="sp-price-row"><div class="sp-price-col">'
        f'<span class="sp-price">{_money(row.get("CMP"), 2)}</span>'
        f'<span class="sp-close">{_html.escape(" · ".join(close_bits))}</span></div>'
        f'<div class="sp-changes">{changes}</div></div>'
        '</div>'
        '<div class="sp-card sp-rank">'
        '<span class="sp-k">Momentum rank</span>'
        f'<div class="sp-rank-big"><span>#{int(rank) if rank is not None else "—"}</span>'
        f'<i>of {total_stocks} stocks</i></div>'
        f'{path_html}'
        f'<div class="sp-facts">{"".join(facts)}</div>'
        '</div></section>'
    )


# ── 2. VERDICT ───────────────────────────────────────────────────────────────

def _render_verdict(row: pd.Series) -> None:
    above = _flag(row, "Above 50 EMA")
    near = _flag(row, "Near 52W High")
    cmp_v = _num(row.get("CMP"))
    ema_pct = _num(row.get("% 50 EMA"))
    hi = _num(row.get("52W High"))
    pct_hi = _num(row.get("% High"))
    ath = _num(row.get("ATH"))
    pct_ath = _num(row.get("% ATH"))

    if above and near:
        state, title, sub = "pass", "Passes both filters", "Eligible for the portfolio"
    elif above or near:
        state, title, sub = "part", "Passes one filter of two", "Not eligible until both pass"
    else:
        state, title, sub = "fail", "Fails both filters", "Not eligible for the portfolio"

    def dist(p: float | None) -> str:
        if p is None:
            return "—"
        if abs(p) < 0.05:
            return "At the high"
        return f"{abs(p):.1f}% {'above' if p > 0 else 'below'}"

    ema_val = cmp_v / (1 + ema_pct / 100) if cmp_v is not None and ema_pct is not None else None
    ema_txt = "—" if ema_pct is None else f"{abs(ema_pct):.1f}% {'above' if ema_pct >= 0 else 'below'}"
    hi_date = _date_label(row.get("52W High Date"))
    ath_date = _date_label(row.get("ATH Date"))

    mark = {"pass": "✓", "part": "!", "fail": "✕"}[state]

    ema_status = "PASS" if above else "FAIL"
    hi_status = "PASS" if near else "FAIL"
    ema_value = ema_txt
    hi_value = dist(pct_hi)
    ath_value = dist(pct_ath)

    _html_block(
        f'<section class="sp-verdict {state}" aria-label="Screener filters">'
        f'<div class="sv-head"><span class="sv-head-mark">{mark}</span>'
        f'<div><b>{title}</b><i>{sub}</i></div>'
        f'<span class="sv-state">{ "ELIGIBLE" if state == "pass" else "REVIEW" }</span></div>'
        f'<div class="sv-card ema">'
        f'<div class="sv-main"><span class="sv-k">50D EMA</span>'
        f'<strong>{_html.escape(ema_value)}</strong>'
        f'<b class="sv-price">{_money(ema_val)}</b></div>'
        f'<div class="sv-side"><em class="{"pass" if above else "fail"}">{ema_status}</em>'
        f'<span>CMP</span><b>{_money(cmp_v)}</b></div></div>'
        f'<div class="sv-card high">'
        f'<div class="sv-main"><span class="sv-k">52W High</span>'
        f'<strong>{_html.escape(hi_value)}</strong>'
        f'<b class="sv-price">{_money(hi)}</b></div>'
        f'<div class="sv-side"><em class="{"pass" if near else "fail"}">{hi_status}</em>'
        f'<span>Date</span><b>{_html.escape(hi_date or "—")}</b></div></div>'
        f'<div class="sv-card ath">'
        f'<div class="sv-main"><span class="sv-k">ATH</span>'
        f'<strong>{_html.escape(ath_value)}</strong>'
        f'<b class="sv-price">{_money(ath)}</b></div>'
        f'<div class="sv-side"><em class="bonus">BONUS</em>'
        f'<span>Date</span><b>{_html.escape(ath_date or "—")}</b></div></div>'
        '</section>'
    )

# ── 3. NOTICES ───────────────────────────────────────────────────────────────

def _render_corporate_actions(symbol: str) -> None:
    events = [e for e in load_events() if e.get("symbol", "").upper() == symbol.upper()]
    if not events:
        return
    lines = []
    for e in sorted(events, key=lambda x: x.get("date", "")):
        move = e.get("move")
        move_str = f"{move * 100:+.1f}%" if move is not None else "a large amount"
        kind = e.get("looks_like") or e.get("kind") or "corporate action"
        day = _date_label(e.get("date")) or str(e.get("date", "—"))
        lines.append(
            f"On <b>{_html.escape(day)}</b> the price moved <b>{_html.escape(move_str)}</b> in "
            f"one session, which looks like a {_html.escape(str(kind))}."
        )
    _html_block(
        '<section class="sp-notice" aria-label="Corporate action">'
        '<b>Corporate action in the price history</b>'
        f'<p>{" ".join(lines)} History before the event is rescaled, so the jump is '
        'not counted as a real gain or loss in the ranking or the backtest.</p></section>'
    )


# ── 5. LADDER ────────────────────────────────────────────────────────────────

def _year_low(symbol: str, adj_close: pd.DataFrame | None,
              low_prices: pd.DataFrame | None) -> float | None:
    for frame in (low_prices, adj_close):
        if frame is not None and symbol in getattr(frame, "columns", []):
            s = pd.to_numeric(frame[symbol], errors="coerce").dropna().tail(252)
            if not s.empty:
                return float(s.min())
    return None


def _render_price_ladder(row: pd.Series, year_low: float | None = None) -> None:
    """Render the compact price-position scale used on the stock page."""
    cmp_v = _num(row.get("CMP"))
    hi = _num(row.get("52W High"))
    ema_pct = _num(row.get("% 50 EMA"))
    ema_val = cmp_v / (1 + ema_pct / 100) if cmp_v is not None and ema_pct is not None else None
    line = hi * 0.8 if hi is not None else None

    if hi is None or year_low is None or hi <= year_low:
        # Some unit tests exercise the renderer with only ranking columns.
        # Keep the section visible without inventing a range position.
        fallback_items = []
        if hi is not None:
            fallback_items.append(f'<span><b>52W High</b><strong>{_money(hi)}</strong></span>')
        if ema_val is not None:
            fallback_items.append(f'<span><b>50D EMA</b><strong>{_money(ema_val)}</strong></span>')
        if line is not None:
            fallback_items.append(f'<span><b>-20% 52W High</b><strong>{_money(line)}</strong></span>')
        if not fallback_items:
            return
        _html_block(
            '<section class="sp-card sp-ladder sp-price-position" aria-label="Where the price sits">'
            '<h2>Where the price sits</h2>'
            '<div class="sp-range-fallback">'
            + "".join(fallback_items)
            + '</div></section>'
            '<style>'
            '.sp-range-fallback{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px;}'
            '.sp-range-fallback span{display:flex;flex-direction:column;gap:3px;min-width:120px;padding:10px 12px;border-radius:10px;background:#F6F7F9;}'
            '.sp-range-fallback b{font-size:12px;color:#5E6878;}'
            '.sp-range-fallback strong{font-family:var(--font-mono);font-size:16px;color:#0E1726;}'
            '</style>'
            '</section>'
        )
        return

    span = hi - year_low

    def x(value: float | None) -> float:
        if value is None:
            return 0.0
        return max(0.0, min(100.0, (value - year_low) / span * 100))

    ema_x = x(ema_val)
    line_x = x(line)

    # Keep the label row collision-free on narrow screens. The 52W High
    # marker is right-aligned, so when the EMA marker gets close to it the
    # EMA label also anchors to its right edge instead of overlapping it.
    ema_near_high = (100.0 - ema_x) < 20.0

    _html_block(
        '<section class="sp-card sp-ladder sp-price-position" aria-label="Where the price sits">'
        '<h2>Where the price sits</h2>'
        '<div class="sp-range-clean">'
        '<div class="sp-range-labels">'
        f'<div class="sp-range-marker" style="left:0%">'
        f'<span class="sp-range-k">52W Low</span><b>{_money(year_low)}</b></div>'
        f'<div class="sp-range-marker {"near-high" if ema_near_high else ""}" style="left:{ema_x:.1f}%">'
        f'<span class="sp-range-k">50D EMA</span><b>{_money(ema_val)}</b></div>'
        f'<div class="sp-range-marker" style="left:{line_x:.1f}%">'
        f'<span class="sp-range-k">-20% 52W High</span><b>{_money(line)}</b></div>'
        f'<div class="sp-range-marker" style="left:100%">'
        f'<span class="sp-range-k">52W High</span><b>{_money(hi)}</b></div>'
        '</div>'
        '<div class="sp-range-track" aria-hidden="true">'
        f'<span class="sp-range-segment muted" style="left:0%;width:{ema_x:.1f}%"></span>'
        f'<span class="sp-range-segment positive" style="left:{ema_x:.1f}%;width:{100 - ema_x:.1f}%"></span>'
        f'<i class="sp-range-dot low" style="left:0%"></i>'
        f'<i class="sp-range-dot ema" style="left:{ema_x:.1f}%"></i>'
        f'<i class="sp-range-dot threshold" style="left:{line_x:.1f}%"></i>'
        f'<i class="sp-range-dot high" style="left:100%"></i>'
        '</div>'
        '</div>'
        '</section>'
        '<style>'
        '.sp-price-position{margin:14px 0;}'
        '.sp-range-clean{margin-top:22px;padding:0 2px 2px;}'
        '.sp-range-labels{position:relative;height:58px;}'
        '.sp-range-marker{position:absolute;top:0;width:118px;text-align:center;transform:translateX(-50%);}'
        '.sp-range-marker:first-child{transform:translateX(0);text-align:left;}'
        '.sp-range-marker:last-child{transform:translateX(-100%);text-align:right;}'
        '.sp-range-k{display:block;font-family:var(--font-ui);font-size:12.5px;line-height:1.2;color:#5E6878;white-space:nowrap;}'
        '.sp-range-marker b{display:block;margin-top:4px;font-family:var(--font-mono);font-size:17px;line-height:1;color:#0E1726;font-weight:700;white-space:nowrap;}'
        '.sp-range-track{position:relative;height:18px;margin:0 10px;}'
        '.sp-range-segment{position:absolute;top:4px;height:10px;border-radius:5px;}'
        '.sp-range-segment.muted{background:#EDEFF3;}'
        '.sp-range-segment.positive{background:#58D6A1;}'
        '.sp-range-dot{position:absolute;top:0;width:18px;height:18px;margin-left:-9px;border:3px solid #fff;border-radius:50%;box-sizing:border-box;}'
        '.sp-range-dot.low{background:#FF6267;box-shadow:0 0 0 1px #FF6267;}'
        '.sp-range-dot.ema{background:#4F46E5;box-shadow:0 0 0 1px #4F46E5;}'
        '.sp-range-dot.threshold{background:#F4B400;box-shadow:0 0 0 1px #F4B400;}'
        '.sp-range-dot.high{background:#067647;box-shadow:0 0 0 1px #067647;}'
        '@media (max-width:640px){'
        '.sp-price-position{padding:14px 12px;border-radius:16px;}'
        '.sp-range-clean{margin-top:20px;padding:0;}'
        '.sp-range-labels{height:64px;}'
        '.sp-range-marker{width:78px;}'
        '.sp-range-k{font-size:10.5px;line-height:1.15;white-space:normal;}'
        '.sp-range-marker b{font-size:15px;margin-top:3px;}'
        '.sp-range-marker:nth-child(3){transform:translateX(-100%);text-align:right;}'
        '.sp-range-marker:nth-child(2){transform:translateX(-50%);text-align:center;}'
        '.sp-range-marker.near-high{transform:translateX(-100%);text-align:right;}'
        '.sp-range-marker:nth-child(4){transform:translateX(-100%);text-align:right;}'
        '.sp-range-track{margin:0 8px;height:18px;}'
        '}'
        '</style>'
    )


# ── 6. RETURNS: GAIN VS PAIN ─────────────────────────────────────────────────

def _benchmark_returns(day: pd.Timestamp | None) -> dict[int, float]:
    """Nifty 500 price return over each calendar window ending on the price day."""
    try:
        from src.loaders.price_loader import fetch_benchmark_history

        s = fetch_benchmark_history(period="2y")
    except Exception:
        return {}
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return {}
    if day is not None:
        s = s[s.index <= day + pd.Timedelta(days=1)]
    if s.empty:
        return {}
    end_t = s.index[-1]
    out = {}
    for m in PERIODS:
        start = s[s.index <= end_t - pd.DateOffset(months=m)]
        if not start.empty:
            out[m] = float(s.iloc[-1] / start.iloc[-1] - 1)
    return out


def _render_gain_vs_pain(row: pd.Series, rank_df: pd.DataFrame) -> None:
    """Each window's return grows right, the fall it took grows left."""
    bench = _benchmark_returns(_price_day())
    dd_max, r_max = 30.0, 0.0
    data = []
    for m in PERIODS:
        ret = _num(row.get(f"{m}M Return"))
        dd = _num(row.get(f"Max DD {m}M"))
        sh = _num(row.get(f"{m}M Sharpe"))
        pct = None
        col = rank_df.get(f"{m}M Return")
        if ret is not None and col is not None:
            vals = pd.to_numeric(col, errors="coerce").dropna()
            if len(vals):
                pct = float((vals < ret).mean() * 100)
        med = None
        med_col = rank_df.get(f"Max DD {m}M")
        if med_col is not None:
            med = _num(pd.to_numeric(med_col, errors="coerce").median())
        data.append((m, ret, dd, sh, pct, med, bench.get(m)))
        if ret is not None:
            r_max = max(r_max, ret)
        for v in (dd, med):
            if v is not None:
                dd_max = max(dd_max, abs(v))
    r_scale = max(r_max * 1.15, 0.25)

    rows_html = []
    for m, ret, dd, sh, pct, med, nb in data:
        dd_w = abs(dd) / dd_max * 100 if dd is not None else 0
        r_w = max(0.0, ret) / r_scale * 100 if ret is not None else 0
        n_w = max(0.0, nb) / r_scale * 100 if nb is not None else 0
        neg = "neg" if ret is not None and ret < 0 else ""
        med_mark = (f'<i class="gp-med" style="right:{abs(med) / dd_max * 100:.1f}%" '
                    f'title="Typical stock: −{abs(med):.1f}%"></i>' if med is not None else "")
        dots = "".join(
            f'<i class="{"on" if sh is not None and sh >= k + 1 else "half" if sh is not None and sh > k else ""}"></i>'
            for k in range(4)
        )
        if pct is None:
            top, good = "—", ""
        elif pct >= 50:
            top, good = f"Top {max(1, int(np.ceil(100 - pct)))}%", "good"
        else:
            top, good = f"Bottom {max(1, int(np.ceil(pct)))}%", "poor"
        dd_txt = f"−{abs(dd):.1f}%" if dd is not None else "—"
        nb_txt = f"Nifty 500 {_signed_pct(nb)}" if nb is not None else ""
        rows_html.append(
            '<div class="gp-row">'
            f'<span class="gp-w"><b>{m}M</b><i>{_LONG[m]}</i></span>'
            f'<div class="gp-dd">{med_mark}<div class="bar" style="width:{dd_w:.1f}%"></div>'
            f'<span class="lbl" style="right:calc({dd_w:.1f}% + 6px)">{dd_txt}</span></div>'
            '<div class="gp-axis"></div>'
            f'<div class="gp-ret"><div class="bar {neg}" style="width:{r_w:.1f}%"></div>'
            f'<span class="lbl {neg}" style="left:calc({r_w:.1f}% + 8px)">{_signed_pct(ret)}</span>'
            f'<div class="nb" style="width:{n_w:.2f}%"></div>'
            f'<span class="nl" style="left:calc({n_w:.2f}% + 6px)">{nb_txt}</span></div>'
            f'<span class="gp-sh"><span class="dots">{dots}</span><b>{_ratio(sh)}</b></span>'
            f'<span class="gp-top"><em class="{good}">{top}</em></span>'
            '</div>'
        )

    # Say so when one fall is the worst drop in several windows: the old grid
    # repeated the same number four times with no explanation.
    dds = [(d[0], d[2]) for d in data if d[2] is not None]
    note = ""
    if len(dds) >= 2:
        same = [m for m, v in dds if abs(v - dds[0][1]) < 0.01]
        if len(same) >= 2:
            note = (f"The same {abs(dds[0][1]):.1f}% fall is the worst drop in every window "
                    f"from {same[0]}M to {same[-1]}M. ")
    _html_block(
        '<section class="sp-card sp-gp" aria-label="Returns and risk">'
        '<div class="gp-head"><h2>Returns and risk by window</h2>'
        '<span class="gp-legend"><span><i class="k-dd"></i>Max drawdown</span>'
        '<span><i class="k-ret"></i>Return</span><span><i class="k-nb"></i>Nifty 500</span>'
        '<span><i class="k-med"></i>Typical stock</span></span></div>'
        '<div class="gp-row gp-hdr"><span>Window</span><span class="r">Max drawdown</span><span></span>'
        '<span>Return</span><span class="r">Sharpe</span><span class="r">Among all</span></div>'
        f'{"".join(rows_html)}'
        f'<div class="gp-foot">{_html.escape(note)}Price return, excludes dividends. Sharpe is '
        'annualised, one dot per full point. "Among all" ranks the return against every '
        'ranked stock.</div></section>'
    )


# ── 7. PEERS ─────────────────────────────────────────────────────────────────

def _render_peers(row: pd.Series, rank_df: pd.DataFrame) -> None:
    industry = row.get("Industry")
    if not industry or "Industry" not in rank_df.columns:
        return
    in_ind = rank_df[rank_df["Industry"] == industry]
    peers = in_ind.sort_values("Rank").head(8)
    sym = str(row["Symbol"])
    if sym not in set(peers["Symbol"].astype(str)):
        peers = pd.concat([peers.head(7), in_ind[in_ind["Symbol"].astype(str) == sym]])
    if len(peers) <= 1:
        return
    cols = [c for c in ["Rank", "Symbol", "CMP", "3M Return", "6M Return",
                        "12M Return", "3M Sharpe", "% High"] if c in peers.columns]
    _render_peers_table(peers[cols].copy(), highlight_sym=sym,
                        title=f"Best-ranked {industry} stocks", total=len(in_ind))


def _render_peers_table(df: pd.DataFrame, highlight_sym: str, title: str = "Peers",
                        total: int | None = None) -> None:
    """Peers with this stock highlighted; every other row links to its page."""
    labels = {"Symbol": "Stock", "CMP": "Price", "3M Return": "3M", "6M Return": "6M",
              "12M Return": "12M", "3M Sharpe": "Sharpe 3M", "% High": "From 52W high"}
    head = "".join(
        f'<th class="{"l" if c in ("Rank", "Symbol") else ""}">{_html.escape(labels.get(c, c))}</th>'
        for c in df.columns
    )
    body = []
    for _, r in df.iterrows():
        sym = str(r.get("Symbol", ""))
        is_hl = sym.upper() == highlight_sym.upper()
        cells = []
        for col, val in r.items():
            if col == "Symbol":
                if is_hl:
                    cell = f'{_html.escape(sym)}<em>This stock</em>'
                else:
                    cell = (f'<a href="{stock_href(sym)}" target="_self">'
                            f'{_html.escape(sym)}</a>')
                cells.append(f'<td class="l s">{cell}</td>')
                continue
            # np.floating too: CMP and % High come out of the engine as
            # float32, which is not a Python float, so they printed raw
            # ("1234.5677") instead of "₹1,235".
            if isinstance(val, (int, float, np.integer, np.floating)) and pd.notna(val):
                val = float(val)
                if col == "Rank":
                    cells.append(f'<td class="l">{int(val)}</td>')
                elif "Return" in col:
                    cls = "up" if val > 0 else "down" if val < 0 else ""
                    cells.append(f'<td class="{cls}">{_signed_pct(val)}</td>')
                elif "Sharpe" in col:
                    cells.append(f"<td>{val:.2f}</td>")
                elif col == "% High":
                    cells.append(f'<td>{"At high" if val >= -0.05 else f"−{abs(val):.1f}%"}</td>')
                elif col == "CMP":
                    cells.append(f"<td>₹{val:,.0f}</td>")
                else:
                    cells.append(f"<td>{val:.1f}</td>")
            else:
                cells.append(f"<td>{_html.escape(str(val)) if pd.notna(val) else '—'}</td>")
        body.append(f'<tr class="{"hl" if is_hl else ""}">{"".join(cells)}</tr>')
    more = f"<span>{total} stocks in the industry</span>" if total else ""
    _html_block(
        '<section class="sp-card sp-peers" aria-label="Peers">'
        f'<div class="ph"><h2>{_html.escape(title)}</h2>{more}</div>'
        f'<div class="tw"><table><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table></div></section>'
    )


# ── 8. DATA CHECKS ───────────────────────────────────────────────────────────

def _render_data_health(row: pd.Series) -> None:
    gap = str(row.get("Data Gap") or "")
    short_hist = str(row.get("Short History") or "No") == "Yes"
    ffill = _num(row.get("FFill %")) or 0.0
    ath_src = str(row.get("ATH Source") or "")
    hz = _num(row.get("Horizons Scored"))

    checks = [
        (ffill > 10, f"Gap-filled prices, last 12 months: {ffill:.1f}%" if ffill
         else "No gap-filled prices in the last 12 months"),
        ("🔴" in gap, "A data gap in the last 12 months" if "🔴" in gap else "No data gaps"),
        (CARRIED_MARK in gap, "Price is the last print, not the ranking day's"
         if CARRIED_MARK in gap else "Price is current"),
        (short_hist, "Less than 6 months of history" if short_hist else "Full 12-month history"),
        (ath_src != "snapshot", "All-time high from the 20-year record" if ath_src == "snapshot"
         else "High from a 2-year window, not all-time"),
    ]
    if hz is not None and hz < 5:
        checks.append((True, f"Ranked on {int(hz)} of 5 horizons"))
    issues = sum(1 for bad, _ in checks if bad)
    label = "Data checks · all clear" if not issues else f"Data checks · {issues} to review"
    with st.expander(label, expanded=bool(issues),
                     icon=":material/verified_user:" if not issues else ":material/warning:"):
        _html_block(
            '<div class="sp-checks">'
            + "".join(f'<span class="{"bad" if bad else ""}">{_html.escape(text)}</span>'
                      for bad, text in checks)
            + "</div>"
        )


# ── Actions: back, watchlist, share ──────────────────────────────────────────

def _share_url(sym: str) -> str:
    """The short, public link to this stock's page.

    Built from the address the reader is on, minus Streamlit Cloud's /~/+/
    mount and any page path: the short form is the one production QA has
    confirmed reaches the stock page (audit_deep_links, "short_query").
    """
    from urllib.parse import urlsplit

    try:
        parts = urlsplit(str(st.context.url or ""))
        base = f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else ""
    except Exception:
        base = ""
    return f"{base}/?stock={_quote(sym, safe='')}"


def _render_exit_status(sym: str, rank_df: pd.DataFrame) -> None:
    """If you hold it: where it stands against the three rules that sell it."""
    from src.engine.exit_watch import CLEAR, SELL, STATUS_LABEL, assess

    a = assess(rank_df, [sym])
    if a.empty or a.iloc[0]["status"] not in STATUS_LABEL:
        return
    r = a.iloc[0]
    status = r["status"]
    if status == CLEAR:
        why = "clear of all three sell rules"
    else:
        why = r["why"] or ""
    cls = {SELL: "sell", CLEAR: "clear"}.get(status, "watch")
    _html_block(
        f'<div class="sp-exit {cls}"><span class="lbl">If you hold it</span>'
        f'<b>{_html.escape(STATUS_LABEL[status])}</b><span>{_html.escape(why)}</span>'
        '<a href="/actions" target="_self">Actions →</a></div>'
    )


def _render_actions(sym: str, on_back=None) -> None:
    from src.ui import watchlist_store

    on_list = sym.upper() in watchlist_store.symbols()
    with st.container(key="sp_actions", horizontal=True, vertical_alignment="center",
                      gap="small"):
        if on_back:
            on_back()
        st.space("stretch")
        st.button(
            "In watchlist" if on_list else "Add to watchlist",
            icon=":material/star:" if on_list else ":material/star_border:",
            key="sp_watch",
            type="secondary",
            on_click=watchlist_store.toggle,
            args=(sym,),
            help=("Remove from your watchlist" if on_list else
                  "Save to your watchlist, kept in this browser"),
        )
        with st.popover("Share", icon=":material/link:", key="sp_share"):
            st.caption("Link to this stock's page. Use the copy button on the right.")
            st.code(_share_url(sym), language=None, wrap_lines=True)


# ── Main entry ────────────────────────────────────────────────────────────────

def render_stock_view(
    symbol: str,
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
    high_prices: pd.DataFrame | None = None,
    low_prices: pd.DataFrame | None = None,
    volume_data: pd.DataFrame | None = None,
    open_prices: pd.DataFrame | None = None,
    *,
    on_back=None,
) -> None:
    """Render the detail page for one symbol."""
    match = rank_df[rank_df["Symbol"].astype(str).str.upper() == str(symbol).upper()]
    if match.empty:
        st.warning(f"{symbol} is not in the current ranking.")
        if on_back:
            on_back()
        return
    row = match.iloc[0]
    total_stocks = len(rank_df)
    sym = str(row["Symbol"])

    _render_actions(sym, on_back)
    _render_identity(row, total_stocks)
    _render_verdict(row)
    _render_exit_status(sym, rank_df)
    _render_corporate_actions(sym)

    _html_block('<div class="sp-sec"><h2>Price and relative strength</h2>'
                '<span>Drag to pan · 20 and 50-day EMA · volume · strength against the '
                'Nifty 500 underneath</span></div>')
    render_stock_chart(
        sym,
        rank_df,
        adj_close,
        high_prices=high_prices,
        low_prices=low_prices,
        volume_data=volume_data,
        open_prices=open_prices,
    )

    _render_price_ladder(row, _year_low(sym, adj_close, low_prices))
    _render_gain_vs_pain(row, rank_df)
    _render_peers(row, rank_df)
    _render_data_health(row)

    render_data_quality_footer(
        total_stocks=total_stocks,
        gap_count=gap_count(rank_df),
        short_count=int((rank_df.get("Short History", pd.Series(dtype=str)) == "Yes").sum()),
    )
