"""PARESH QUANT v2 screener: comparison-first desktop, ranked cards on mobile-friendly mode."""

from __future__ import annotations

import html
import pandas as pd
import streamlit as st

from src.ui.v2.theme import *


def _num(v):
    try:
        if v is None or pd.isna(v):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _pct(v, signed=True):
    x = _num(v)
    if x is None:
        return "—"
    return f"{x:+.1f}%" if signed else f"{x:.1f}%"


def _money(v):
    x = _num(v)
    return f"₹{x:,.2f}" if x is not None else "—"


def _daily_changes(close: pd.DataFrame, symbols: pd.Series) -> pd.Series:
    out = {}
    if close is None or close.empty:
        return pd.Series(index=symbols.index, dtype=float)
    for sym in symbols:
        try:
            s = pd.to_numeric(close[sym], errors="coerce").dropna()
            out[sym] = ((s.iloc[-1] / s.iloc[-2]) - 1) * 100 if len(s) >= 2 else None
        except Exception:
            out[sym] = None
    return symbols.map(out)


def _enrich(df: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["Score Percentile"] = out["Score"].rank(pct=True, method="average") * 100 if "Score" in out else float("nan")
    out["1D Change"] = _daily_changes(close, out["Symbol"]) if "Symbol" in out else float("nan")

    def state(row):
        states = []
        if str(row.get("Above 50 EMA", "")).lower() in {"true", "yes", "1", "🟢", "✓"}:
            states.append("Above EMA")
        if str(row.get("Near 52W High", "")).lower() in {"true", "yes", "1", "🟢", "✓"}:
            states.append("Near 52W")
        if str(row.get("At ATH", "")).lower() in {"true", "yes", "1", "🟢", "✓"}:
            states.append("ATH")
        if str(row.get("Volume", "")).lower() in {"high", "surge"}:
            states.append("High Volume")
        return " · ".join(states) if states else "—"

    out["State"] = out.apply(state, axis=1)
    return out


def _bool(v) -> bool:
    return str(v).strip().lower() in {"true", "yes", "1", "y", "✓", "🟢"}


def _stock_card(row: pd.Series, position: int) -> None:
    sym = html.escape(str(row.get("Symbol", "—")))
    industry = html.escape(str(row.get("Industry", row.get("TV_Industry", "")) or ""))
    rank = _num(row.get("Rank"))
    score = _num(row.get("Score Percentile"))
    cmp_ = _num(row.get("CMP"))
    d1 = _num(row.get("1D Change"))
    r1 = _num(row.get("1M Return"))
    r3 = _num(row.get("3M Return"))
    r6 = _num(row.get("6M Return"))
    r12 = _num(row.get("12M Return"))
    hi = _num(row.get("% High"))
    ema = _num(row.get("% 50 EMA"))
    badges = []
    if _bool(row.get("Above 50 EMA")): badges.append("ABOVE 50 EMA")
    if _bool(row.get("Near 52W High")): badges.append("NEAR 52W HIGH")
    if _bool(row.get("At ATH")): badges.append("ATH")
    if str(row.get("Volume", "")).lower() in {"high", "surge"}: badges.append("HIGH VOLUME")
    badge_html = "".join(f'<span class="v2-badge v2-badge-good">{html.escape(x)}</span>' for x in badges)
    dclass = "v2-delta-pos" if (d1 or 0) >= 0 else "v2-delta-neg"

    st.html(f"""
    <div class="v2-stock-card">
      <div class="v2-stock-top">
        <div><div class="v2-rank">RANK #{int(rank) if rank is not None else '—'}</div>
        <div class="v2-symbol">{sym}</div><div class="v2-industry">{industry}</div></div>
        <div><div class="v2-price">{_money(cmp_)}</div>
        <div class="{dclass}">{_pct(d1)}</div></div>
      </div>
      <div class="v2-badges">{badge_html or '<span class="v2-badge">No special state</span>'}</div>
      <div class="v2-score"><div class="v2-score-track"><div class="v2-score-fill" style="width:{max(0,min(100,score or 0)):.1f}%"></div></div>
      <div class="v2-score-text">{score:.0f}th percentile</div></div>
      <div class="v2-metrics">
        <div class="v2-metric"><div class="v2-metric-label">1M</div><div class="v2-metric-value">{_pct(r1)}</div></div>
        <div class="v2-metric"><div class="v2-metric-label">3M</div><div class="v2-metric-value">{_pct(r3)}</div></div>
        <div class="v2-metric"><div class="v2-metric-label">6M</div><div class="v2-metric-value">{_pct(r6)}</div></div>
        <div class="v2-metric"><div class="v2-metric-label">12M</div><div class="v2-metric-value">{_pct(r12)}</div></div>
      </div>
      <div class="v2-metrics">
        <div class="v2-metric"><div class="v2-metric-label">52W High</div><div class="v2-metric-value">{_pct(hi)}</div></div>
        <div class="v2-metric"><div class="v2-metric-label">50 EMA</div><div class="v2-metric-value">{_pct(ema)}</div></div>
        <div class="v2-metric"><div class="v2-metric-label">3M Sharpe</div><div class="v2-metric-value">{_num(row.get('3M Sharpe')):.2f}</div></div>
        <div class="v2-metric"><div class="v2-metric-label">12M DD</div><div class="v2-metric-value">{_pct(row.get('Max DD 12M'), signed=False)}</div></div>
      </div>
    </div>
    """)
    if st.button(f"Open {sym}", key=f"v2_card_{position}_{sym}", use_container_width=True):
        st.session_state["v2_selected_symbol"] = str(row["Symbol"])
        st.session_state["v2_page"] = "Stock Detail"
        st.rerun()


def render(data: dict) -> None:
    rank_df = _enrich(data["rank_df"], data["close_prices"])
    total = len(rank_df)

    st.markdown('<div class="v2-brand"><div class="v2-mark">PQ</div><div><div class="v2-brand-name">PARESH QUANT</div><div class="v2-brand-sub">NSE Momentum Terminal · v2 verification build</div></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="v2-page-title">Screener</div><div class="v2-page-sub">Find the strongest momentum stocks, inspect their evidence, and drill into risk without leaving the ranking surface.</div>', unsafe_allow_html=True)

    regime = data.get("regime")
    regime_status = getattr(regime, "status", None) or "—"
    ema_count = int(rank_df["Above 50 EMA"].map(_bool).sum()) if "Above 50 EMA" in rank_df else 0
    near_count = int(rank_df["Near 52W High"].map(_bool).sum()) if "Near 52W High" in rank_df else 0
    top50 = int((pd.to_numeric(rank_df.get("Rank"), errors="coerce") <= 50).sum())
    hi_vol = int(rank_df.get("Volume", pd.Series(index=rank_df.index)).astype(str).str.lower().isin(["high", "surge"]).sum())
    breadth = ema_count / total * 100 if total else 0
    st.markdown(f'''<div class="v2-strip">
      <div class="v2-strip-item"><div class="v2-strip-label">Regime</div><div class="v2-strip-value">{html.escape(str(regime_status))}</div></div>
      <div class="v2-strip-item"><div class="v2-strip-label">Universe</div><div class="v2-strip-value">{total:,}</div></div>
      <div class="v2-strip-item"><div class="v2-strip-label">Above 50 EMA</div><div class="v2-strip-value">{ema_count:,} · {breadth:.0f}%</div></div>
      <div class="v2-strip-item"><div class="v2-strip-label">Near 52W High</div><div class="v2-strip-value">{near_count:,}</div></div>
      <div class="v2-strip-item"><div class="v2-strip-label">Top 50</div><div class="v2-strip-value">{top50:,}</div></div>
      <div class="v2-strip-item"><div class="v2-strip-label">High Volume</div><div class="v2-strip-value">{hi_vol:,}</div></div>
    </div>''', unsafe_allow_html=True)

    q = st.text_input("Search stocks", placeholder="Search symbol or industry…", label_visibility="collapsed", key="v2_search")
    presets = ["All Stocks", "Top 50", "Qualified", "Above 50 EMA", "Near 52W High", "High Volume"]
    preset = st.pills("Universe", presets, default="All Stocks", key="v2_preset")

    filtered = rank_df.copy()
    if q:
        mask = filtered["Symbol"].astype(str).str.contains(q, case=False, na=False)
        if "Industry" in filtered:
            mask = mask | filtered["Industry"].astype(str).str.contains(q, case=False, na=False)
        filtered = filtered[mask]
    if preset == "Top 50": filtered = filtered[pd.to_numeric(filtered["Rank"], errors="coerce") <= 50]
    elif preset == "Qualified" and "Qualified" in filtered: filtered = filtered[filtered["Qualified"].map(_bool)]
    elif preset == "Above 50 EMA": filtered = filtered[filtered["Above 50 EMA"].map(_bool)]
    elif preset == "Near 52W High": filtered = filtered[filtered["Near 52W High"].map(_bool)]
    elif preset == "High Volume": filtered = filtered[filtered["Volume"].astype(str).str.lower().isin(["high", "surge"])]

    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        sort_by = st.selectbox("Sort", ["Rank", "Score", "3M Return", "12M Return", "3M Sharpe", "% High"], label_visibility="collapsed", key="v2_sort")
    with c2:
        view = st.segmented_control("View", ["Table", "Cards"], default="Table", key="v2_view", label_visibility="collapsed")
    with c3:
        rows = st.selectbox("Rows", [25, 50, 100], index=0, label_visibility="collapsed", key="v2_rows")

    ascending = sort_by in {"Rank"}
    filtered = filtered.sort_values(sort_by, ascending=ascending, na_position="last")
    shown = filtered.head(rows).copy()

    st.markdown(f'<div class="v2-section">{len(filtered):,} matching stocks <span class="v2-muted">· select a row to open Stock Detail</span></div>', unsafe_allow_html=True)

    if shown.empty:
        st.info("No stocks match the current search/filter combination.")
        return

    if view == "Cards":
        cols = st.columns(2)
        for i, (_, row) in enumerate(shown.iterrows()):
            with cols[i % 2]:
                _stock_card(row, i)
        return

    cols = ["Rank", "Symbol", "Industry", "CMP", "1D Change", "Score", "Score Percentile", "Rank Δ 1M", "Rank Δ 3M", "1M Return", "3M Return", "6M Return", "12M Return", "3M Sharpe", "12M Sharpe", "% High", "% 50 EMA", "Volume", "State"]
    cols = [c for c in cols if c in shown.columns]
    table = shown[cols].copy()
    cfg = {
        "Rank": st.column_config.NumberColumn("Rank", format="%d", width="small", pinned=True),
        "Symbol": st.column_config.TextColumn("Stock", width="medium", pinned=True),
        "Industry": st.column_config.TextColumn("Industry", width="medium"),
        "CMP": st.column_config.NumberColumn("Price", format="₹ %.2f", width="small"),
        "1D Change": st.column_config.NumberColumn("1D", format="%+.2f%%", width="small"),
        "Score": st.column_config.NumberColumn("Score", format="%.2f", width="small"),
        "Score Percentile": st.column_config.ProgressColumn("Percentile", format="%.0f", min_value=0, max_value=100, width="medium"),
        "Rank Δ 1M": st.column_config.NumberColumn("Δ 1M", format="%+d", width="small"),
        "Rank Δ 3M": st.column_config.NumberColumn("Δ 3M", format="%+d", width="small"),
        "1M Return": st.column_config.NumberColumn("1M", format="%+.1f%%"),
        "3M Return": st.column_config.NumberColumn("3M", format="%+.1f%%"),
        "6M Return": st.column_config.NumberColumn("6M", format="%+.1f%%"),
        "12M Return": st.column_config.NumberColumn("12M", format="%+.1f%%"),
        "3M Sharpe": st.column_config.NumberColumn("3M Sharpe", format="%.2f"),
        "12M Sharpe": st.column_config.NumberColumn("12M Sharpe", format="%.2f"),
        "% High": st.column_config.NumberColumn("vs 52W High", format="%+.1f%%"),
        "% 50 EMA": st.column_config.NumberColumn("vs 50 EMA", format="%+.1f%%"),
        "Volume": st.column_config.TextColumn("Volume"),
        "State": st.column_config.TextColumn("State", width="large"),
    }
    event = st.dataframe(table, column_config=cfg, hide_index=True, width="stretch", height=560, row_height=34, on_select="rerun", selection_mode="single-row", key="v2_screener_table")
    if event.selection.rows:
        st.session_state["v2_selected_symbol"] = str(shown.iloc[event.selection.rows[0]]["Symbol"])
        st.session_state["v2_page"] = "Stock Detail"
        st.rerun()

    st.caption("All displayed values are from the existing quantitative pipeline or transparent presentation-level derivations. Mockup design values are not used by this build.")
