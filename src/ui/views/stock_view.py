"""Single-stock detail page — redesigned light edition.

Layout order (matches agreed design canvas StockLight):
  1. HERO         symbol, rank ring (score arc / rank text), CMP, index chips, gates
  2. KPI BAND     12M Return · 12M Sharpe · Rank Δ 3M · Max DD 12M
  3. CHART        price action first — TradingView chart + RS pane
  4. KEY LEVELS   52W high, ATH, stop loss, Chandelier, ATR (tinted tiles)
  5. PERFORMANCE  return / Sharpe / drawdown matrix across all windows (heatmap cells)
  6. DYNAMICS     rank dynamics (left) + data health (right) — two-column card
  7. PEERS        industry peers table, current stock highlighted
"""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from src.engine.corporate_actions import load_events
from src.ui.charts import render_stock_chart
from src.ui.components import render_data_quality_footer, to_bool_mask
from src.ui.theme import render_saas_table

# ── Palette tokens ───────────────────────────────────────────────────────────
POS   = "#059669"
NEG   = "#e11d48"
WARN  = "#d97706"
ACC   = "#4f46e5"
INK   = "#0f172a"
SUB   = "#475569"
MUTED = "#64748b"
LINE  = "#e2e8f0"

PERIODS = (1, 3, 6, 9, 12)


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


# ── SVG rank ring ────────────────────────────────────────────────────────────

def _rank_ring(rank: int | None, total: int, score: float | None, size: int = 76) -> str:
    """Partial-arc ring: score fills the arc (indigo→emerald gradient), rank in center."""
    if rank is None:
        return ""
    cx = cy = size / 2
    r = size * 0.395          # ≈ 30px for 76px ring
    circ = 2 * math.pi * r
    s = max(0.0, min(1.0, float(score) if score is not None else 0.8))
    offset = (1.0 - s) * circ
    total_str = f"of {total}" if total else ""
    fs_rank = int(size * 0.224)   # ≈ 17px
    fs_sub  = int(size * 0.105)   # ≈ 8px
    y_rank  = cy - size * 0.053   # slightly above center
    y_sub   = cy + size * 0.118   # slightly below
    uid = f"rg{rank}"
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
        f'xmlns="http://www.w3.org/2000/svg" style="flex-shrink:0;">'
        f'<defs><linearGradient id="{uid}" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="#4f46e5"/>'
        f'<stop offset="100%" stop-color="#059669"/></linearGradient></defs>'
        f'<circle cx="{cx}" cy="{cy}" r="{r:.1f}" fill="none" stroke="#e2e8f0" stroke-width="4.5"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r:.1f}" fill="none" stroke="url(#{uid})"'
        f' stroke-width="5.5" stroke-dasharray="{circ:.1f}" stroke-dashoffset="{offset:.1f}"'
        f' transform="rotate(-90 {cx} {cy})" stroke-linecap="round"/>'
        f'<text x="{cx}" y="{y_rank:.1f}" text-anchor="middle" dominant-baseline="middle"'
        f' font-family="Outfit,sans-serif" font-weight="900" font-size="{fs_rank}"'
        f' fill="#4f46e5">#{rank}</text>'
        f'<text x="{cx}" y="{y_sub:.1f}" text-anchor="middle" dominant-baseline="middle"'
        f' font-family="Plus Jakarta Sans,sans-serif" font-size="{fs_sub}"'
        f' fill="#94a3b8">{total_str}</text>'
        f'</svg>'
    )


# ── UI building blocks ───────────────────────────────────────────────────────

def _chip(text: str, bg: str = "#f1f5f9", fg: str = SUB, border: str = LINE) -> str:
    return (
        f'<span style="display:inline-block;font-size:0.68rem;font-weight:700;'
        f'padding:2px 7px;border-radius:4px;background:{bg};color:{fg};'
        f'border:1px solid {border};letter-spacing:.03em;white-space:nowrap;">'
        f'{text}</span>'
    )


def _gate(label: str, passed: bool) -> str:
    colour = POS if passed else MUTED
    mark = "✓" if passed else "✗"
    return (
        f'<span style="display:inline-flex;align-items:center;gap:5px;padding:3px 10px;'
        f'border-radius:20px;background:{colour}0D;border:1px solid {colour}30;'
        f"font-family:'JetBrains Mono',monospace;font-size:0.68rem;font-weight:700;"
        f'color:{colour};">{mark} {label}</span>'
    )


def _section(title: str, note: str = "") -> None:
    note_html = (
        f'<span style="color:{MUTED};font-weight:500;"> · {note}</span>' if note else ""
    )
    st.markdown(
        f'<div style="font-size:0.76rem;font-weight:800;color:{INK};letter-spacing:0.01em;'
        f'margin:18px 0 8px;padding-bottom:6px;border-bottom:2px solid #eef2ff;">'
        f'{title}{note_html}</div>',
        unsafe_allow_html=True,
    )


def _kpi_tile(label: str, value: str, colour: str = INK, sub: str = "") -> str:
    """Large KPI band tile — Outfit 900 number."""
    sub_html = (
        f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:0.68rem;'
        f'color:{MUTED};margin-top:3px;">{sub}</div>'
        if sub else ""
    )
    return (
        f'<div style="flex:1 1 0;min-width:110px;padding:14px 16px;background:#ffffff;'
        f'border:1px solid {LINE};border-radius:12px;">'
        f'<div style="font-size:0.64rem;text-transform:uppercase;letter-spacing:.06em;'
        f'color:{MUTED};font-weight:700;font-family:\'JetBrains Mono\',monospace;">{label}</div>'
        f'<div style="font-family:\'Outfit\',sans-serif;font-size:1.55rem;font-weight:900;'
        f'color:{colour};margin-top:4px;letter-spacing:-.02em;">{value}</div>'
        f'{sub_html}</div>'
    )


def _tile(label: str, value: str, *, sub: str = "", colour: str = INK,
          title: str = "", bg: str = "#ffffff") -> str:
    """Detail tile for key levels and data rows."""
    tip = f' title="{title}"' if title else ""
    sub_html = (
        f'<div style="font-size:0.65rem;color:{MUTED};margin-top:2px;">{sub}</div>'
        if sub else ""
    )
    return (
        f'<div{tip} style="flex:1 1 130px;min-width:120px;padding:10px 14px;'
        f'background:{bg};border:1px solid {LINE};border-radius:10px;">'
        f'<div style="font-size:0.63rem;text-transform:uppercase;letter-spacing:.04em;'
        f'color:{MUTED};font-weight:700;">{label}</div>'
        f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:0.97rem;'
        f'font-weight:700;color:{colour};margin-top:3px;">{value}</div>'
        f'{sub_html}</div>'
    )


def _row(tiles: list[str]) -> str:
    return (
        '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;">'
        + "".join(tiles)
        + "</div>"
    )


# ── Corporate actions notice ─────────────────────────────────────────────────

def _render_corporate_actions(symbol: str) -> None:
    events = [e for e in load_events() if e.get("symbol", "").upper() == symbol.upper()]
    if not events:
        return
    lines = []
    for e in sorted(events, key=lambda x: x.get("date", "")):
        date = e.get("date", "—")
        move = e.get("move")
        move_str = f"{move * 100:+.1f}%" if move is not None else "—"
        kind = e.get("looks_like") or e.get("kind") or "unknown"
        lines.append(f"**{date}** — {move_str} session · {kind}")
    st.warning(
        "**Corporate action detected in price history.** "
        "The backtest rescales history before this event so the strategy sees the "
        "real trajectory — the drop below is not a real loss.\n\n"
        + "\n\n".join(lines)
    )


# ── 1. HERO ──────────────────────────────────────────────────────────────────

def _render_identity(row: pd.Series, total_stocks: int) -> None:
    sym     = str(row["Symbol"])
    rank    = _num(row.get("Rank"))
    rank_i  = int(rank) if rank is not None else None
    score   = _num(row.get("Score"))
    industry = row.get("Industry") or "—"
    sector   = row.get("TV_Sector") or ""
    indices  = str(row.get("Indices") or "").strip()
    cmp_val  = _money(row.get("CMP"))
    r3       = _num(row.get("3M Return"))

    # Index chips
    idx_chips = ""
    for idx_raw in indices.split(","):
        idx_s = idx_raw.strip()
        if not idx_s or idx_s == "—":
            continue
        if "50" in idx_s and "500" not in idx_s:
            idx_chips += _chip("N50", "#ede9fe", "#5b21b6", "#ddd6fe")
        elif "500" in idx_s:
            idx_chips += _chip("N500", "#ecfdf5", "#065f46", "#bbf7d0")
        elif "MIDCAP" in idx_s.upper():
            idx_chips += _chip("MID", "#fff7ed", "#9a3412", "#fed7aa")
        elif "SMALLCAP" in idx_s.upper():
            idx_chips += _chip("SM", "#fef9c3", "#713f12", "#fde68a")
        else:
            idx_chips += _chip(idx_s[:8], "#f1f5f9", SUB, LINE)

    # Industry chip
    if industry and industry != "—":
        ind_short = industry[:18] + "…" if len(industry) > 19 else industry
        idx_chips += _chip(ind_short, "#f8fafc", MUTED, LINE)

    gates = "".join([
        _gate("Above 50 EMA",
              bool(to_bool_mask(pd.Series([row.get("Above 50 EMA")])).iloc[0])),
        _gate("Near 52W High",
              bool(to_bool_mask(pd.Series([row.get("Near 52W High")])).iloc[0])),
        _gate("At ATH",
              bool(to_bool_mask(pd.Series([row.get("At ATH")])).iloc[0])),
    ])

    ring_svg = _rank_ring(rank_i, total_stocks, score, size=76)

    r3_str  = f"{r3 * 100:+.1f}% · 3M" if r3 is not None else ""
    r3_clr  = _sign_colour(r3)
    av_bg   = "linear-gradient(135deg,#eef2ff,#e0e7ff)"

    ring_html = (
        f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px;">'
        + ring_svg
        + "</div>"
        if ring_svg else ""
    )
    industry_or_sector = sector if sector else industry

    html = (
        f'<div style="background:linear-gradient(150deg,#eef2ff 0%,#f0fdf4 55%,#faf5ff 100%);'
        f'border:1px solid {LINE};border-radius:16px;padding:20px 22px;margin-bottom:10px;">'
        f'<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">'
        # avatar
        f'<div style="width:52px;height:52px;border-radius:14px;background:{av_bg};'
        f'border:1px solid #c7d2fe;display:flex;align-items:center;justify-content:center;'
        f'font-family:\'Outfit\',sans-serif;font-weight:900;font-size:1.2rem;color:{ACC};">'
        f'{sym[:2]}</div>'
        # name + chips
        f'<div style="flex:1;min-width:0;">'
        f'<div style="font-family:\'Outfit\',sans-serif;font-weight:900;font-size:1.6rem;'
        f'color:{INK};letter-spacing:-.025em;line-height:1;">{sym}</div>'
        f'<div style="font-size:0.72rem;color:{MUTED};margin-top:4px;">'
        + industry_or_sector
        + f'</div>'
        f'<div style="display:flex;gap:5px;flex-wrap:wrap;margin-top:6px;">{idx_chips}</div>'
        f'</div>'
        # rank ring
        + ring_html
        # CMP block
        + f'<div style="text-align:right;margin-left:auto;">'
        f'<div style="font-family:\'Outfit\',sans-serif;font-weight:900;font-size:2rem;'
        f'color:{INK};letter-spacing:-.03em;line-height:1;">{cmp_val}</div>'
        f'<div style="font-family:\'JetBrains Mono\',monospace;font-size:0.78rem;'
        f'font-weight:700;color:{r3_clr};margin-top:4px;">{r3_str}</div>'
        f'</div>'
        f'</div>'
        # gate row
        f'<div style="display:flex;gap:7px;flex-wrap:wrap;margin-top:14px;">{gates}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ── 2. KPI BAND ──────────────────────────────────────────────────────────────

def _render_kpi_band(row: pd.Series) -> None:
    r12  = _num(row.get("12M Return"))
    s12  = _num(row.get("12M Sharpe"))
    d3m  = _num(row.get("Rank Δ 3M"))
    dd12 = _num(row.get("Max DD 12M"))

    r12_str  = f"{r12 * 100:+.1f}%" if r12 is not None else "—"
    s12_str  = f"{s12:.2f}" if s12 is not None else "—"
    d3m_val  = int(d3m) if d3m is not None else None
    d3m_str  = (f"▲ {d3m_val}" if d3m_val and d3m_val > 0
                else (f"▼ {abs(d3m_val)}" if d3m_val and d3m_val < 0 else "—"))
    dd12_str = f"{dd12:.1f}%" if dd12 is not None else "—"

    tiles = "".join([
        _kpi_tile("12M Return", r12_str, colour=_sign_colour(r12), sub="vs universe"),
        _kpi_tile("12M Sharpe", s12_str,
                  colour=POS if s12 and s12 > 1 else (WARN if s12 and s12 > 0 else NEG)),
        _kpi_tile("Rank Δ 3M", d3m_str, colour=_sign_colour(d3m),
                  sub="+ = climbed"),
        _kpi_tile("Max DD 12M", dd12_str, colour=NEG if dd12 else INK,
                  sub="worst drawdown"),
    ])
    st.markdown(
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px;">{tiles}</div>',
        unsafe_allow_html=True,
    )


# ── 4. KEY LEVELS ─────────────────────────────────────────────────────────────

def _render_key_levels(row: pd.Series) -> None:
    _section("Key levels", "highs carry the date they were printed")

    hi_52    = row.get("52W High")
    pct_hi   = _num(row.get("% High"))
    ath      = row.get("ATH")
    pct_ath  = _num(row.get("% ATH"))
    ath_date = str(row.get("ATH Date") or "").strip()
    ath_src  = str(row.get("ATH Source") or "").strip()

    ath_sub  = f"peak {ath_date}" if ath_date else ""
    if ath_src == "in_memory_window":
        ath_sub = "2y window, not all-time"

    hi_52_date = str(row.get("52W High Date") or "").strip()
    hi_sub = f"peak {hi_52_date}" if hi_52_date else (
        f"{_pct(pct_hi)} away" if pct_hi is not None else ""
    )

    # Tile background tints: green = good/high, amber = caution, red = risk level
    hi_bg  = "#f0fdf4" if pct_hi and pct_hi > -5 else ("#fffbeb" if pct_hi and pct_hi > -15 else "#fff1f2")
    sl_bg  = "#fff1f2"   # stop loss → always red-tinted (risk)
    cex_bg = "#fffbeb"   # chandelier exit → amber (caution)
    ema_bg = "#f0fdf4" if _sign_colour(row.get("% 50 EMA")) == POS else "#fff1f2"

    tiles = [
        _tile("52W High", _money(hi_52), sub=hi_sub, colour=INK, bg=hi_bg,
              title=f"Peak printed {hi_52_date}" if hi_52_date else ""),
        _tile("All-Time High", _money(ath), sub=ath_sub, colour=INK,
              title=f"Peak printed {ath_date}" if ath_date else ""),
        _tile("% from 52W High", _pct(pct_hi), colour=_sign_colour(pct_hi), bg=hi_bg),
        _tile("% from ATH", _pct(pct_ath), colour=_sign_colour(pct_ath),
              title=f"Peak printed {ath_date}" if ath_date else ""),
        _tile("Stop Loss", _money(row.get("Stop Loss")),
              sub="CMP − 2×ATR", colour=NEG, bg=sl_bg),
        _tile("Chandelier Exit", _money(row.get("Chand Exit")),
              sub="22D high − 3×ATR", colour=WARN, bg=cex_bg),
        _tile("ATR", _money(row.get("ATR"), 1),
              sub=f"{_ratio(row.get('ATR %'))}% of price", colour=INK),
        _tile("vs 50 EMA", _pct(row.get("% 50 EMA")),
              colour=_sign_colour(row.get("% 50 EMA")), bg=ema_bg),
    ]
    st.markdown(_row(tiles), unsafe_allow_html=True)


# ── 5. PERFORMANCE MATRIX ────────────────────────────────────────────────────

def _render_performance_matrix(row: pd.Series) -> None:
    _section("Performance across every window",
             "shape across windows says more than any single one")

    def _cell_bg(value, positive_good: bool = True) -> str:
        v = _num(value)
        if v is None:
            return ""
        if positive_good:
            if v > 0.3:   return "background:#bbf7d0;color:#065f46;"
            if v > 0.1:   return "background:#d1fae5;color:#065f46;"
            if v > 0:     return "background:#f0fdf4;color:#059669;"
            if v > -0.1:  return "background:#fff1f2;color:#e11d48;"
            if v > -0.2:  return "background:#fecdd3;color:#be123c;"
            return              "background:#fca5a5;color:#991b1b;"
        else:
            # drawdown: more negative = darker red
            if v < -20:   return "background:#fca5a5;color:#991b1b;"
            if v < -15:   return "background:#fecdd3;color:#be123c;"
            if v < -10:   return "background:#fff1f2;color:#e11d48;"
            if v < -5:    return "background:#fffbeb;color:#92400e;"
            return              "background:#f0fdf4;color:#065f46;"

    def _sharpe_bg(v_raw) -> str:
        v = _num(v_raw)
        if v is None:
            return ""
        if v > 2:    return "background:#bbf7d0;color:#065f46;"
        if v > 1:    return "background:#d1fae5;color:#065f46;"
        if v > 0.5:  return "background:#f0fdf4;color:#059669;"
        if v > 0:    return "background:#fffbeb;color:#92400e;"
        return              "background:#fff1f2;color:#e11d48;"

    header = "".join(
        f'<th style="padding:8px 12px;text-align:right;font-size:0.65rem;'
        f'text-transform:uppercase;letter-spacing:.05em;color:{MUTED};'
        f'font-weight:700;background:#f8fafc;">{m}M</th>'
        for m in PERIODS
    )

    def band(label: str, fmt, get_bg) -> str:
        cells = ""
        for m in PERIODS:
            key = {"Return": f"{m}M Return",
                   "Sharpe": f"{m}M Sharpe",
                   "Max Drawdown": f"Max DD {m}M"}[label]
            raw = row.get(key)
            v = _num(raw)
            bg = get_bg(v)
            txt = fmt(raw)
            cells += (
                f'<td style="padding:7px 12px;text-align:right;'
                f"font-family:'JetBrains Mono',monospace;font-size:0.82rem;"
                f'font-weight:700;{bg}">{txt}</td>'
            )
        return (
            f'<tr><td style="padding:7px 12px;font-size:0.72rem;font-weight:700;'
            f'color:{INK};white-space:nowrap;background:#fafafa;">{label}</td>{cells}</tr>'
        )

    st.markdown(
        f'<div style="overflow-x:auto;background:#ffffff;border:1px solid {LINE};'
        f'border-radius:12px;margin-bottom:12px;">'
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr>'
        f'<th style="padding:8px 12px;background:#f8fafc;text-align:left;'
        f'font-size:0.65rem;color:{MUTED};font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.05em;"></th>{header}</tr></thead>'
        f'<tbody>'
        + band("Return",
               lambda v: _pct((_num(v) or 0) * 100) if _num(v) is not None else "—",
               lambda v: _cell_bg(v * 100 if v is not None else None))
        + band("Sharpe", _ratio, _sharpe_bg)
        + band("Max Drawdown",
               lambda v: _pct(v, signed=False) if _num(v) is not None else "—",
               lambda v: _cell_bg(v, positive_good=False))
        + "</tbody></table></div>",
        unsafe_allow_html=True,
    )


# ── 6a. RANK DYNAMICS ────────────────────────────────────────────────────────

def _render_rank_dynamics(row: pd.Series, total_stocks: int) -> None:
    _section("Rank dynamics")

    def delta_tile(label: str, key: str) -> str:
        v = _num(row.get(key))
        if v is None:
            return _tile(label, "—")
        arrow = "▲" if v > 0 else ("▼" if v < 0 else "—")
        bg = "#f0fdf4" if v > 0 else ("#fff1f2" if v < 0 else "#f8fafc")
        return _tile(label, f"{arrow} {abs(int(v))}", colour=_sign_colour(v), bg=bg)

    tiles = [
        _tile("Score", _ratio(row.get("Score"), 3)),
        _tile("Rank", f"#{int(_num(row.get('Rank')))}" if _num(row.get("Rank")) is not None else "—",
              bg="#eef2ff", colour=ACC),
        delta_tile("Rank Δ 1M", "Rank Δ 1M"),
        delta_tile("Rank Δ 3M", "Rank Δ 3M"),
        _tile("Persistence", _ratio(row.get("Persistence"))),
        _tile("Volume", str(row.get("Volume") or "—")),
        _tile("Market Cap",
              f"₹{_num(row.get('Market Cap (Cr)')):,.0f} Cr"
              if _num(row.get("Market Cap (Cr)")) is not None else "—"),
    ]
    st.markdown(_row(tiles), unsafe_allow_html=True)


# ── 6b. DATA HEALTH ──────────────────────────────────────────────────────────

def _render_data_health(row: pd.Series) -> None:
    _section("Data health", "caveats before the chart")
    gap       = str(row.get("Data Gap") or "🟢")
    short_hist = str(row.get("Short History") or "No")
    ffill     = _num(row.get("FFill %"))
    ath_src   = str(row.get("ATH Source") or "")

    tiles = [
        _tile("Gap-filled", _pct(ffill, signed=False) if ffill is not None else "—",
              colour=WARN if (ffill or 0) > 10 else INK,
              bg="#fffbeb" if (ffill or 0) > 10 else "#f8fafc"),
        _tile("Data Gap", "Yes" if "🔴" in gap else "No",
              colour=NEG if "🔴" in gap else POS,
              bg="#fff1f2" if "🔴" in gap else "#f0fdf4"),
        _tile("Short history", short_hist, sub="< 126 sessions",
              colour=WARN if short_hist == "Yes" else POS,
              bg="#fffbeb" if short_hist == "Yes" else "#f8fafc"),
        _tile("ATH source",
              "20y snapshot" if ath_src == "snapshot" else "2y window",
              colour=INK if ath_src == "snapshot" else WARN),
    ]
    st.markdown(_row(tiles), unsafe_allow_html=True)


# ── 7. PEERS ─────────────────────────────────────────────────────────────────

def _render_peers(row: pd.Series, rank_df: pd.DataFrame) -> None:
    industry = row.get("Industry")
    if not industry or "Industry" not in rank_df.columns:
        return
    peers = rank_df[rank_df["Industry"] == industry].sort_values("Rank").head(10)
    if len(peers) <= 1:
        return
    _section(f"Peers — {industry}", f"{len(peers)} shown · highlighted = this stock")

    sym = str(row["Symbol"])
    cols = [c for c in ["Rank", "Symbol", "CMP", "3M Return", "6M Return",
                         "12M Return", "3M Sharpe", "% High", "% ATH", "Volume"]
            if c in peers.columns]
    peers_display = peers[cols].copy()

    # Render as custom HTML to highlight the selected row
    _render_peers_table(peers_display, highlight_sym=sym)


def _render_peers_table(df: pd.DataFrame, highlight_sym: str) -> None:
    """Peers table with the current stock row highlighted in indigo."""
    headers = "".join(
        f'<th style="padding:7px 10px;text-align:right;font-family:\'JetBrains Mono\',monospace;'
        f'font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;'
        f'color:{MUTED};background:#f8fafc;white-space:nowrap;">{c}</th>'
        for c in df.columns
    )

    rows_html = []
    for _, r in df.iterrows():
        is_hl = str(r.get("Symbol", "")).upper() == highlight_sym.upper()
        row_bg = "#eef2ff" if is_hl else "#ffffff"
        row_border = f"border-left:3px solid {ACC};" if is_hl else "border-left:3px solid transparent;"
        cells = ""
        for col, val in r.items():
            align = "left" if col in ("Symbol", "Industry") else "right"
            fw = "800" if col == "Symbol" else "600"
            if isinstance(val, float) and pd.notna(val):
                if "Return" in col or "Alpha" in col:
                    txt = f"{val:+.1%}"
                    clr = POS if val > 0 else NEG
                elif "Sharpe" in col or "Score" in col:
                    txt = f"{val:.2f}"
                    clr = INK
                elif "%" in col:
                    txt = f"{val:.1f}%"
                    clr = _sign_colour(val)
                elif col in ("CMP", "Stop Loss"):
                    txt = f"₹{val:,.0f}"
                    clr = INK
                else:
                    txt = f"{val:.1f}"
                    clr = INK
            else:
                txt = str(val) if pd.notna(val) else "—"
                clr = ACC if col == "Symbol" and is_hl else INK
            cells += (
                f'<td style="padding:6px 10px;text-align:{align};font-weight:{fw};'
                f"font-family:'JetBrains Mono',monospace;font-size:12px;"
                f'color:{clr};white-space:nowrap;">{txt}</td>'
            )
        rows_html.append(
            f'<tr style="background:{row_bg};{row_border}'
            f'border-bottom:1px solid #f1f5f9;">{cells}</tr>'
        )

    st.markdown(
        f'<div style="overflow-x:auto;border:1px solid {LINE};border-radius:12px;'
        f'margin-bottom:12px;">'
        f'<table style="width:100%;border-collapse:collapse;white-space:nowrap;">'
        f'<thead><tr>{headers}</tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody>'
        f'</table></div>',
        unsafe_allow_html=True,
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

    if on_back:
        on_back()

    # 1. Hero
    _render_identity(row, total_stocks)

    # 2. KPI band
    _render_kpi_band(row)

    # 3. Chart — moved up so the most visual element follows the headline numbers
    _render_corporate_actions(str(row["Symbol"]))
    _section("Price action",
             "drag to pan · 20/50 EMA toggleable · volume · Relative Strength")
    render_stock_chart(
        str(row["Symbol"]),
        rank_df,
        adj_close,
        high_prices=high_prices,
        low_prices=low_prices,
        volume_data=volume_data,
        open_prices=open_prices,
    )

    # 4. Key levels
    _render_key_levels(row)

    # 5. Performance matrix
    _render_performance_matrix(row)

    # 6. Rank dynamics + data health — two columns
    col_dyn, col_health = st.columns(2, gap="medium")
    with col_dyn:
        _render_rank_dynamics(row, total_stocks)
    with col_health:
        _render_data_health(row)

    # 7. Peers
    _render_peers(row, rank_df)

    render_data_quality_footer(
        total_stocks=total_stocks,
        gap_count=int((rank_df.get("Data Gap", pd.Series(dtype=str)) == "🔴").sum()),
        short_count=int((rank_df.get("Short History", pd.Series(dtype=str)) == "Yes").sum()),
    )
