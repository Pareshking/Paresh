"""Data-grounded Stock Detail for the v2 verification build."""

from __future__ import annotations

import html
import pandas as pd
import streamlit as st

from src.ui.v2.theme import *

PERIODS = (1, 3, 6, 9, 12)


def _num(v):
    try:
        if v is None or pd.isna(v): return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _pct(v, signed=True):
    x = _num(v)
    if x is None: return "—"
    return f"{x:+.1f}%" if signed else f"{x:.1f}%"


def _ret(v):
    x = _num(v)
    return f"{x*100:+.1f}%" if x is not None else "—"


def _money(v):
    x = _num(v)
    return f"₹{x:,.2f}" if x is not None else "—"


def _bool(v):
    return str(v).strip().lower() in {"true", "yes", "1", "y", "✓", "🟢"}


def _selected_row(rank_df: pd.DataFrame, symbol: str) -> pd.Series | None:
    if "Symbol" not in rank_df:
        return None
    hit = rank_df[rank_df["Symbol"].astype(str).str.upper() == str(symbol).upper()]
    return hit.iloc[0] if not hit.empty else None


def _chart(row: pd.Series, data: dict) -> None:
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except Exception:
        st.warning("Chart library is unavailable; the quantitative values remain available below.")
        return

    sym = str(row["Symbol"])
    close = data.get("close_prices")
    high = data.get("high_prices")
    low = data.get("low_prices")
    open_ = data.get("open_prices")
    volume = data.get("volume_data")
    if close is None or sym not in close.columns:
        st.info("Price history is not available for this stock.")
        return

    c = pd.to_numeric(close[sym], errors="coerce")
    frame = pd.DataFrame({"Close": c})
    if open_ is not None and sym in open_.columns: frame["Open"] = pd.to_numeric(open_[sym], errors="coerce")
    if high is not None and sym in high.columns: frame["High"] = pd.to_numeric(high[sym], errors="coerce")
    if low is not None and sym in low.columns: frame["Low"] = pd.to_numeric(low[sym], errors="coerce")
    if volume is not None and sym in volume.columns: frame["Volume"] = pd.to_numeric(volume[sym], errors="coerce")
    frame = frame.dropna(subset=["Close"]).tail(252)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.78,.22], vertical_spacing=.035)
    if all(x in frame for x in ["Open","High","Low"]):
        fig.add_trace(go.Candlestick(x=frame.index, open=frame["Open"], high=frame["High"], low=frame["Low"], close=frame["Close"], name=sym), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=frame.index, y=frame["Close"], name="Close", mode="lines"), row=1, col=1)
    ema = frame["Close"].ewm(span=50, min_periods=30).mean()
    fig.add_trace(go.Scatter(x=frame.index, y=ema, name="50 EMA", mode="lines"), row=1, col=1)
    hi52 = _num(row.get("52W High"))
    ath = _num(row.get("ATH"))
    if hi52 is not None: fig.add_hline(y=hi52, line_dash="dot", annotation_text="52W High", row=1, col=1)
    if ath is not None and (hi52 is None or abs(ath-hi52) > 1e-9): fig.add_hline(y=ath, line_dash="dash", annotation_text="ATH", row=1, col=1)
    if "Volume" in frame:
        fig.add_trace(go.Bar(x=frame.index, y=frame["Volume"], name="Volume", opacity=.35), row=2, col=1)
    fig.update_layout(height=500, margin=dict(l=10,r=10,t=20,b=10), template="plotly_white", hovermode="x unified", showlegend=True, legend=dict(orientation="h", y=1.02, x=0))
    fig.update_xaxes(rangeslider_visible=False)
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False, "scrollZoom": False})


def _metric_card(label, value, sub=""):
    st.markdown(f'''<div class="v2-card"><div class="v2-strip-label">{html.escape(label)}</div><div class="v2-big-number" style="margin-top:6px">{html.escape(str(value))}</div>{f'<div class="v2-table-note">{html.escape(sub)}</div>' if sub else ''}</div>''', unsafe_allow_html=True)


def render(data: dict, symbol: str | None) -> None:
    rank_df = data["rank_df"].copy()
    if "Score" in rank_df:
        rank_df["Score Percentile"] = rank_df["Score"].rank(pct=True) * 100
    if not symbol:
        st.markdown('<div class="v2-page-title">Stock Detail</div><div class="v2-page-sub">Select a stock from the Screener to open its quantitative evidence trail.</div>', unsafe_allow_html=True)
        st.info("No stock selected. Return to Screener and select a row or card.")
        return

    row = _selected_row(rank_df, symbol)
    if row is None:
        st.error(f"Stock `{symbol}` is not present in the current ranked universe.")
        return

    sym = str(row.get("Symbol", symbol))
    industry = str(row.get("Industry", "") or "")
    rank = _num(row.get("Rank"))
    percentile = _num(row.get("Score Percentile"))
    score = _num(row.get("Score"))
    cmp_ = _money(row.get("CMP"))
    states = []
    if _bool(row.get("Above 50 EMA")): states.append("Above 50 EMA")
    if _bool(row.get("Near 52W High")): states.append("Near 52W High")
    if _bool(row.get("At ATH")): states.append("At ATH")
    if str(row.get("Volume", "")).lower() in {"high", "surge"}: states.append("High Volume")

    st.button("← Back to Screener", key="v2_back", on_click=lambda: st.session_state.update({"v2_page":"Screener"}))
    st.markdown(f'''<div class="v2-detail-hero"><div class="v2-stock-top"><div><div class="v2-detail-symbol">{html.escape(sym)}</div><div class="v2-detail-meta">{html.escape(industry)} · quantitative evidence trail</div><div class="v2-badges">{''.join(f'<span class="v2-badge v2-badge-good">{html.escape(s)}</span>' for s in states) or '<span class="v2-badge">No special state</span>'}</div></div><div style="text-align:right"><div class="v2-big-number">{cmp_}</div><div class="v2-detail-meta">Rank #{int(rank) if rank is not None else '—'} · {percentile:.0f}th percentile</div></div></div></div>''', unsafe_allow_html=True)

    st.markdown('<div class="v2-section">Momentum position</div>', unsafe_allow_html=True)
    k = st.columns(4)
    for col, (label, value, sub) in zip(k, [("Score", f"{score:.2f}" if score is not None else "—", "composite momentum"), ("Percentile", f"{percentile:.0f}" if percentile is not None else "—", "cross-sectional"), ("Rank Δ 1M", f"{_num(row.get('Rank Δ 1M')):+.0f}" if _num(row.get('Rank Δ 1M')) is not None else "—", "rank movement"), ("Rank Δ 3M", f"{_num(row.get('Rank Δ 3M')):+.0f}" if _num(row.get('Rank Δ 3M')) is not None else "—", "rank movement")]):
        with col: _metric_card(label, value, sub)

    st.markdown('<div class="v2-section">Price & technicals</div>', unsafe_allow_html=True)
    _chart(row, data)

    st.markdown('<div class="v2-section">Momentum windows</div>', unsafe_allow_html=True)
    perf = pd.DataFrame(index=["Return", "Sharpe", "Max Drawdown"], columns=[f"{m}M" for m in PERIODS])
    for m in PERIODS:
        perf.loc["Return", f"{m}M"] = _ret(row.get(f"{m}M Return"))
        s = _num(row.get(f"{m}M Sharpe")); perf.loc["Sharpe", f"{m}M"] = f"{s:.2f}" if s is not None else "—"
        perf.loc["Max Drawdown", f"{m}M"] = _pct(row.get(f"Max DD {m}M"), signed=False)
    st.dataframe(perf, width="stretch", height=165)

    st.markdown('<div class="v2-section">Trend, highs & risk</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="v2-grid2">', unsafe_allow_html=True)
        for label, value, sub in [("50 EMA", _pct(row.get("% 50 EMA")), "distance from EMA"), ("52W High", _money(row.get("52W High")), str(row.get("52W High Date", ""))), ("From 52W High", _pct(row.get("% High")), "distance"), ("ATH", _money(row.get("ATH")), str(row.get("ATH Date", ""))), ("From ATH", _pct(row.get("% ATH")), "distance"), ("6M Persistence", _pct(row.get("Persistence"), signed=False), "positive sessions")]:
            _metric_card(label, value, sub)
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="v2-grid2">', unsafe_allow_html=True)
        for label, value, sub in [("ATR", _money(row.get("ATR"),) if False else _money(row.get("ATR")), f"{_num(row.get('ATR %')):.1f}% of price" if _num(row.get('ATR %')) is not None else ""), ("Stop Loss", _money(row.get("Stop Loss")), "2 × ATR"), ("Chandelier Exit", _money(row.get("Chand Exit")), "3 × ATR"), ("12M Max Drawdown", _pct(row.get("Max DD 12M"), signed=False), "worst observed"), ("Volume", str(row.get("Volume", "—")), "volume status"), ("Volume Ratio", "—", "not separately exposed by current ranking table")]:
            _metric_card(label, value, sub)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="v2-section">Metadata & data quality</div>', unsafe_allow_html=True)
    meta = {k: row.get(k) for k in ["Market Cap (Cr)", "Industry", "Indices", "Short History", "FFill %", "Data Gap"] if k in row.index}
    st.dataframe(pd.DataFrame([meta]), hide_index=True, width="stretch", height=90)
    st.caption("No fundamentals, news, analyst ratings, shareholding, peer model, or invented RS metric are included in this verification build.")
