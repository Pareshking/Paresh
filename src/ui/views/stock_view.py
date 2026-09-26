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

from src.engine.corporate_actions import load_events
from src.engine.momentum import ATR_DERIVED_COLUMNS, CARRIED_MARK
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
        changes += f'<span class="sp-chg {cls}">{arrow} {abs(v) * 100:.1f}% · {m}M</span>'

    cls_parts = [p for p in (industry, sector) if p and p.lower() != "nan"]
    if len(cls_parts) == 2 and cls_parts[0] == cls_parts[1]:
        cls_parts = cls_parts[:1]
    cls_line = " · ".join(_html.escape(p) for p in cls_parts)

    rank = _num(row.get("Rank"))
    path = []
    for col, label in (("Rank (-3M)", "3M ago"), ("Rank (-1M)", "1M ago"), ("Rank", "now")):
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
    ema_cell = (
        f'<span class="v {"up" if above else "down"}">{ema_txt}</span>'
        f'<span class="s">{"EMA ≈ " + _money(ema_val) if ema_val is not None else ""}</span>'
    )
    hi_date = _date_label(row.get("52W High Date"))
    hi_sub = f"{_money(hi, 2)} set on {hi_date}" if hi_date else _money(hi, 2)
    if not near and hi is not None:
        hi_sub = f"High {_money(hi, 2)} · filter line {_money(hi * 0.8, 2)}"
    hi_cell = (f'<span class="v {"up" if near else "down"}">{dist(pct_hi)}</span>'
               f'<span class="s">{_html.escape(hi_sub)}</span>')
    ath_src = str(row.get("ATH Source") or "").strip()
    ath_date = _date_label(row.get("ATH Date"))
    if ath_src == "in_memory_window":
        ath_sub = "2-year high: no all-time record for this stock"
    else:
        ath_sub = f"{_money(ath, 2)} set on {ath_date}" if ath_date else _money(ath, 2)
    ath_cell = (f'<span class="v">{dist(pct_ath)}</span>'
                f'<span class="s">{_html.escape(ath_sub)}</span>')
    mark = {"pass": "✓", "part": "!", "fail": "✕"}[state]
    _html_block(
        f'<section class="sp-verdict {state}" aria-label="Screener filters">'
        f'<div class="vh"><span class="vm">{mark}</span><span><b>{title}</b><i>{sub}</i></span></div>'
        f'<div class="vc"><span class="k">Above 50-day EMA</span>{ema_cell}</div>'
        f'<div class="vc"><span class="k">Within 20% of 52-week high</span>{hi_cell}</div>'
        f'<div class="vc"><span class="k">All-time high <em>(bonus)</em></span>{ath_cell}</div>'
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
    cmp_v = _num(row.get("CMP"))
    hi = _num(row.get("52W High"))
    pct_hi = _num(row.get("% High"))
    ath = _num(row.get("ATH"))
    ath_date = _date_label(row.get("ATH Date"))
    ema_pct = _num(row.get("% 50 EMA"))
    ema_val = cmp_v / (1 + ema_pct / 100) if cmp_v is not None and ema_pct is not None else None
    line = hi * 0.8 if hi is not None else None

    # The range bar: 52-week low to high, with the filter line and the EMA.
    bar = ""
    if hi is not None and year_low is not None and hi > year_low and cmp_v is not None:
        span = hi - year_low

        def x(v: float) -> float:
            return max(0.0, min(100.0, (v - year_low) / span * 100))

        marks = (f'<i class="m-line" style="left:{x(line):.1f}%" title="Filter line"></i>'
                 if line is not None else "")
        if ema_val is not None:
            marks += f'<i class="m-ema" style="left:{x(ema_val):.1f}%" title="50-day EMA"></i>'
        bar = (
            '<div class="sp-range"><div class="track">'
            f'<div class="fill" style="width:{x(cmp_v):.1f}%"></div>{marks}'
            f'<span class="dot" style="left:{x(cmp_v):.1f}%"></span></div>'
            f'<div class="ends"><span>52-week low {_money(year_low)}</span>'
            '<span class="key"><i class="m-line"></i>filter line <i class="m-ema"></i>50-day EMA</span>'
            f'<span>52-week high {_money(hi)}</span></div></div>'
        )

    rows = []

    def item(label: str, value: str, sub: str = "", cls: str = "") -> None:
        rows.append(
            f'<div class="li"><span class="lk">{_html.escape(label)}</span>'
            f'<span class="lv {cls}">{value}</span>'
            f'<span class="ls">{_html.escape(sub)}</span></div>'
        )

    item("52W High", _money(hi, 2),
         (f"price {_pct(pct_hi)}" if pct_hi and abs(pct_hi) >= 0.05 else "price is at the high"),
         "down" if pct_hi and pct_hi <= -0.05 else "")
    if ath is not None:
        item("All-time high", _money(ath, 2),
             (f"set on {ath_date}" if ath_date else "")
             + (f" · price {_pct(row.get('% ATH'))}" if _num(row.get("% ATH")) is not None else ""))
    if line is not None:
        item("Filter line · 20% below high", _money(line),
             "price is above it" if cmp_v is not None and cmp_v >= line else "price is below it",
             "" if cmp_v is not None and cmp_v >= line else "down")
    if ema_val is not None:
        item("50-day EMA", _money(ema_val), f"price {_pct(ema_pct)}",
             "up" if ema_pct >= 0 else "down")
    if year_low is not None and cmp_v:
        item("52-week low", _money(year_low), f"price {_pct((cmp_v / year_low - 1) * 100, 0)}")
    dd = _num(row.get("Max DD 12M"))
    if dd is not None:
        item("Worst fall, 12 months", f"−{abs(dd):.1f}%", "peak to trough", "down")
    pers = _num(row.get("Persistence"))
    if pers is not None:
        item("Up-days, last 6 months", f"{pers:.1f}%", "share of sessions that closed higher")
    vol = str(row.get("Volume") or "").strip()
    if vol:
        item("Volume vs normal", _html.escape(vol), "")

    # Stop levels are DROPPED, not blanked, when the ranking carries no ATR. A
    # history of closing prices has no intraday range, so the pipeline removes
    # ATR_DERIVED_COLUMNS rather than derive a number that would read as a
    # true ATR and size a stop about half as wide as intended.
    if any(_num(row.get(col)) is not None for col in ATR_DERIVED_COLUMNS):
        item("Stop Loss", _money(row.get("Stop Loss")), "price − 2 × ATR", "down")
        item("Chandelier Exit", _money(row.get("Chand Exit")), "22-day high − 3 × ATR", "warn")
        item("ATR (14-day)", _money(row.get("ATR"), 1), f"{_ratio(row.get('ATR %'))}% of price")

    _html_block(
        '<section class="sp-card sp-ladder" aria-label="Where the price sits">'
        '<h2>Where the price sits</h2>'
        f'{bar}<div class="list">{"".join(rows)}</div></section>'
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
                    cell = (f'<a href="?stock={_quote(sym, safe="")}" target="_self">'
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
        (ffill > 10, f"Gap-filled prices: {ffill:.1f}%" if ffill else "No gap-filled prices"),
        ("🔴" in gap, "A data gap in the price history" if "🔴" in gap else "No data gaps"),
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

    if on_back:
        on_back()

    _render_identity(row, total_stocks)
    _render_verdict(row)
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
