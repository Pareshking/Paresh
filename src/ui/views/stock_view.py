"""Single-stock detail page.

Layout reasoning, since the old drilldown was a chart with a few numbers beside
it and everything else was left in the screener row the reader had just come
from:

  1. IDENTITY      who this is, what it costs, where it ranks, and the three
                   qualification gates -- the things you check before anything
                   else earns attention.
  2. KEY LEVELS    52W high and all-time high WITH THE DATES they were printed,
                   plus the exit levels. A price is a fact; a price without its
                   date is an assertion. Over a twenty-year window one bad tick
                   sets a phantom high, and the date is what lets a reader spot
                   it rather than trust it.
  3. PERFORMANCE   every calendar window as a matrix -- return, Sharpe and
                   drawdown down the same columns -- because the interesting
                   question is almost never one window, it is the shape across
                   them. A stock strong at 12M and weak at 1M is a different
                   animal from the reverse, and a row of scattered tiles hides
                   that while a grid shows it.
  4. RANK DYNAMICS where it sits and which way it is moving.
  5. DATA HEALTH   how much of this is real, gathered in one place so a caveat
                   is never discovered halfway down a chart.
  6. CHART         last, because it answers "what happened" once the numbers
                   have answered "is this worth looking at".
  7. PEERS         the same industry, for context.

Numbers come first and the chart comes last on purpose: a chart invites you to
find a story in the shape, and the numbers are what discipline that.
"""

from __future__ import annotations

import pandas as pd

import streamlit as st

from src.ui.charts import render_stock_chart
from src.ui.components import render_data_quality_footer, to_bool_mask
from src.ui.theme import render_saas_table

# ── Formatting helpers ───────────────────────────────────────────────────────
POS = "#059669"
NEG = "#e11d48"
WARN = "#d97706"
INK = "#0f172a"
MUTED = "#64748b"
LINE = "#e2e8f0"


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


def _sign_colour(value, neutral: str = MUTED) -> str:
    v = _num(value)
    if v is None:
        return neutral
    return POS if v > 0 else (NEG if v < 0 else neutral)


def _tile(label: str, value: str, *, sub: str = "", colour: str = INK,
          title: str = "") -> str:
    """One statistic. Label above, value below, optional caption under that."""
    tip = f' title="{title}"' if title else ""
    sub_html = (
        f'<div style="font-size:0.66rem;color:{MUTED};margin-top:2px;">{sub}</div>'
        if sub else ""
    )
    return (
        f'<div{tip} style="flex:1 1 130px;min-width:120px;padding:9px 12px;'
        f'background:#ffffff;border:1px solid {LINE};border-radius:9px;">'
        f'<div style="font-size:0.64rem;text-transform:uppercase;letter-spacing:0.04em;'
        f'color:{MUTED};font-weight:700;">{label}</div>'
        f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:0.98rem;'
        f'font-weight:700;color:{colour};margin-top:3px;">{value}</div>'
        f"{sub_html}</div>"
    )


def _row(tiles: list[str]) -> str:
    return (
        '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;">'
        + "".join(tiles)
        + "</div>"
    )


def _section(title: str, note: str = "") -> None:
    note_html = f'<span style="color:{MUTED};font-weight:500;"> · {note}</span>' if note else ""
    st.markdown(
        f'<div style="font-size:0.78rem;font-weight:800;color:{INK};'
        f'letter-spacing:0.01em;margin:14px 0 7px;">{title}{note_html}</div>',
        unsafe_allow_html=True,
    )


def _gate(label: str, passed: bool) -> str:
    colour = POS if passed else MUTED
    mark = "✓" if passed else "✗"
    return (
        f'<span style="display:inline-flex;align-items:center;gap:5px;padding:3px 10px;'
        f'border-radius:20px;background:{colour}0D;border:1px solid {colour}30;'
        f"font-family:'IBM Plex Mono',monospace;font-size:0.7rem;font-weight:700;"
        f'color:{colour};">{mark} {label}</span>'
    )


# ── The page ─────────────────────────────────────────────────────────────────
PERIODS = (1, 3, 6, 9, 12)


def render_stock_view(
    symbol: str,
    rank_df: pd.DataFrame,
    adj_close: pd.DataFrame,
    high_prices: pd.DataFrame | None = None,
    low_prices: pd.DataFrame | None = None,
    volume_data: pd.DataFrame | None = None,
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

    if on_back:
        on_back()

    _render_identity(row)
    _render_key_levels(row)
    _render_performance_matrix(row)
    _render_rank_dynamics(row)
    _render_data_health(row)

    _section("Price action", "20/50 EMA toggleable · volume · RSI(14)")
    render_stock_chart(
        str(row["Symbol"]),
        rank_df,
        adj_close,
        high_prices=high_prices,
        low_prices=low_prices,
        volume_data=volume_data,
    )

    _render_peers(row, rank_df)

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=int((rank_df.get("Data Gap", pd.Series(dtype=str)) == "🔴").sum()),
        short_count=int((rank_df.get("Short History", pd.Series(dtype=str)) == "Yes").sum()),
    )


def _render_identity(row: pd.Series) -> None:
    sym = str(row["Symbol"])
    rank = _num(row.get("Rank"))
    rank_txt = f"#{int(rank)}" if rank is not None else "—"
    industry = row.get("Industry") or "—"
    sector = row.get("TV_Sector") or ""
    indices = str(row.get("Indices") or "").strip()
    cmp_val = _money(row.get("CMP"))
    r3 = _num(row.get("3M Return"))

    gates = "".join([
        _gate("Above 50 EMA", bool(to_bool_mask(pd.Series([row.get("Above 50 EMA")])).iloc[0])),
        _gate("Near 52W High", bool(to_bool_mask(pd.Series([row.get("Near 52W High")])).iloc[0])),
        _gate("At ATH", bool(to_bool_mask(pd.Series([row.get("At ATH")])).iloc[0])),
    ])

    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:space-between;'
        f'flex-wrap:wrap;gap:14px;padding:16px 18px;background:#ffffff;'
        f'border:1px solid {LINE};border-radius:14px;margin-bottom:12px;">'
        f'<div style="display:flex;align-items:center;gap:14px;">'
        f'<div style="width:46px;height:46px;border-radius:12px;background:#f1f5f9;'
        f'border:1px solid {LINE};display:flex;align-items:center;justify-content:center;'
        f'font-weight:800;font-size:1.05rem;color:{INK};">{sym[:2]}</div>'
        f"<div>"
        f'<div style="display:flex;align-items:center;gap:9px;flex-wrap:wrap;">'
        f'<span style="font-weight:800;font-size:1.35rem;color:{INK};'
        f'letter-spacing:-0.02em;">{sym}</span>'
        f'<span style="font-family:\'IBM Plex Mono\',monospace;font-size:0.72rem;'
        f'font-weight:700;background:#eef2ff;color:#4f46e5;border:1px solid #c7d2fe;'
        f'padding:2px 9px;border-radius:20px;">Rank {rank_txt}</span></div>'
        f'<div style="font-size:0.76rem;color:{MUTED};margin-top:3px;">{industry}'
        + (f" · {sector}" if sector else "")
        + (f'<br><span style="font-size:0.68rem;">{indices}</span>' if indices else "")
        + "</div></div></div>"
        f'<div style="text-align:right;">'
        f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:1.6rem;'
        f'font-weight:800;color:{INK};">{cmp_val}</div>'
        f'<div style="font-family:\'IBM Plex Mono\',monospace;font-size:0.78rem;'
        f'font-weight:700;color:{_sign_colour(r3)};">'
        f"{_pct((r3 or 0) * 100) if r3 is not None else '—'} · 3M</div></div>"
        f'<div style="display:flex;gap:7px;flex-wrap:wrap;width:100%;">{gates}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_key_levels(row: pd.Series) -> None:
    _section("Key levels", "highs carry the date they were printed")

    hi_52 = row.get("52W High")
    pct_hi = _num(row.get("% High"))
    ath = row.get("ATH")
    pct_ath = _num(row.get("% ATH"))
    ath_date = str(row.get("ATH Date") or "").strip()
    ath_source = str(row.get("ATH Source") or "").strip()

    ath_sub = f"peak {ath_date}" if ath_date else ""
    if ath_source == "in_memory_window":
        ath_sub = "2y window, not all-time"

    tiles = [
        _tile("52W High", _money(hi_52),
              sub=f"{_pct(pct_hi)} away" if pct_hi is not None else "",
              colour=INK),
        _tile("All-Time High", _money(ath),
              sub=ath_sub,
              colour=INK,
              title=f"Peak printed {ath_date}" if ath_date else ""),
        _tile("% from 52W High", _pct(pct_hi), colour=_sign_colour(pct_hi)),
        _tile("% from ATH", _pct(pct_ath), colour=_sign_colour(pct_ath),
              title=f"Peak printed {ath_date}" if ath_date else ""),
        _tile("Stop Loss", _money(row.get("Stop Loss")), sub="CMP − 2×ATR", colour=NEG),
        _tile("Chandelier Exit", _money(row.get("Chand Exit")), sub="22D high − 3×ATR",
              colour=WARN),
        _tile("ATR", _money(row.get("ATR"), 1),
              sub=f"{_ratio(row.get('ATR %'))}% of price", colour=INK),
        _tile("vs 50 EMA", _pct(row.get("% 50 EMA")),
              colour=_sign_colour(row.get("% 50 EMA"))),
    ]
    st.markdown(_row(tiles), unsafe_allow_html=True)


def _render_performance_matrix(row: pd.Series) -> None:
    _section("Performance across every window",
             "the shape across windows says more than any one of them")

    header = "".join(
        f'<th style="padding:7px 10px;text-align:right;font-size:0.66rem;'
        f'text-transform:uppercase;letter-spacing:0.04em;color:{MUTED};">{m}M</th>'
        for m in PERIODS
    )

    def band(label: str, fmt, colourise: bool) -> str:
        cells = ""
        for m in PERIODS:
            key = {"Return": f"{m}M Return", "Sharpe": f"{m}M Sharpe",
                   "Max Drawdown": f"Max DD {m}M"}[label]
            raw = row.get(key)
            colour = _sign_colour(raw) if colourise else INK
            cells += (
                f'<td style="padding:7px 10px;text-align:right;'
                f"font-family:'IBM Plex Mono',monospace;font-size:0.82rem;"
                f'font-weight:700;color:{colour};">{fmt(raw)}</td>'
            )
        return (
            f'<tr><td style="padding:7px 10px;font-size:0.72rem;font-weight:700;'
            f'color:{INK};white-space:nowrap;">{label}</td>{cells}</tr>'
        )

    st.markdown(
        f'<div style="overflow-x:auto;background:#ffffff;border:1px solid {LINE};'
        f'border-radius:10px;padding:4px 6px;margin-bottom:10px;">'
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr><th style="padding:7px 10px;"></th>{header}</tr></thead>'
        f"<tbody>"
        + band("Return", lambda v: _pct((_num(v) or 0) * 100) if _num(v) is not None else "—", True)
        + band("Sharpe", _ratio, True)
        + band("Max Drawdown", lambda v: _pct(v, signed=False), False)
        + "</tbody></table></div>",
        unsafe_allow_html=True,
    )


def _render_rank_dynamics(row: pd.Series) -> None:
    _section("Rank dynamics")

    def delta_tile(label: str, key: str) -> str:
        v = _num(row.get(key))
        if v is None:
            return _tile(label, "—")
        arrow = "▲" if v > 0 else ("▼" if v < 0 else "—")
        return _tile(label, f"{arrow} {abs(int(v))}", colour=_sign_colour(v))

    tiles = [
        _tile("Composite Score", _ratio(row.get("Score"), 3)),
        _tile("Rank", f"#{int(_num(row.get('Rank')))}" if _num(row.get("Rank")) is not None else "—"),
        delta_tile("Rank Δ 1M", "Rank Δ 1M"),
        delta_tile("Rank Δ 3M", "Rank Δ 3M"),
        _tile("Persistence", _ratio(row.get("Persistence"))),
        _tile("Exp Regression Rank",
              f"#{int(_num(row.get('Exp Rank')))}" if _num(row.get("Exp Rank")) is not None else "—"),
        _tile("Market Cap", f"₹{_num(row.get('Market Cap (Cr)')):,.0f} Cr"
              if _num(row.get("Market Cap (Cr)")) is not None else "—"),
        _tile("Volume", str(row.get("Volume") or "—")),
    ]
    st.markdown(_row(tiles), unsafe_allow_html=True)


def _render_data_health(row: pd.Series) -> None:
    _section("Data health", "caveats belong before the chart, not after it")
    gap = str(row.get("Data Gap") or "🟢")
    short_hist = str(row.get("Short History") or "No")
    ffill = _num(row.get("FFill %"))

    tiles = [
        _tile("Gap-filled", _pct(ffill, signed=False) if ffill is not None else "—",
              colour=WARN if (ffill or 0) > 10 else INK),
        _tile("Data Gap", "Yes" if "🔴" in gap else "No",
              colour=NEG if "🔴" in gap else POS),
        _tile("Short history", short_hist,
              sub="< 126 sessions", colour=WARN if short_hist == "Yes" else POS),
        _tile("ATH source",
              "20y snapshot" if str(row.get("ATH Source")) == "snapshot" else "2y window",
              colour=INK if str(row.get("ATH Source")) == "snapshot" else WARN),
    ]
    st.markdown(_row(tiles), unsafe_allow_html=True)


def _render_peers(row: pd.Series, rank_df: pd.DataFrame) -> None:
    industry = row.get("Industry")
    if not industry or "Industry" not in rank_df.columns:
        return
    peers = rank_df[rank_df["Industry"] == industry].sort_values("Rank").head(10)
    if len(peers) <= 1:
        return
    _section(f"Peers in {industry}", f"{len(peers)} shown by rank")
    cols = [c for c in ["Rank", "Symbol", "CMP", "3M Return", "6M Return",
                        "12M Return", "3M Sharpe", "% High", "% ATH", "Volume"]
            if c in peers.columns]
    render_saas_table(peers[cols], key=f"peers_{row['Symbol']}")
