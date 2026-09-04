"""PARESH QUANT — focused two-page quantitative terminal.

Presentation only: the existing System-1 MomentumEngine remains the source of quantitative calculations.
"""
from __future__ import annotations

import hashlib
import html
from typing import Any

import pandas as pd
import streamlit as st

from src.engine.calendar_momentum import _apply_weight_composite, _compute_period_z_scores
from src.engine.momentum import MomentumEngine
from src.loaders.indices_loader import fetch_indices_data
from src.loaders.mcap_loader import fetch_market_caps
from src.loaders.price_loader import extract_ohlcv, fetch_price_history

PERIODS = (1, 3, 6, 9, 12)
WEIGHTS = (0.10, 0.30, 0.30, 0.20, 0.10)

CSS = """
<style>
:root{--bg:#f6f7f9;--surface:#fff;--ink:#17202f;--muted:#667085;--soft:#98a2b3;--line:#dfe3e8;--accent:#3157d5;--green:#087443;--red:#c43232}
[data-testid="stAppViewContainer"]{background:var(--bg)}
[data-testid="stHeader"]{background:var(--bg)}
[data-testid="stMainBlockContainer"]{max-width:1480px;padding:20px 28px 64px}
section[data-testid="stSidebar"]{display:none}
.v3-brand{display:flex;align-items:center;gap:10px;margin-bottom:28px}.v3-mark{width:30px;height:30px;border:1px solid #cfd5dd;border-radius:7px;background:#172554;color:#fff;display:grid;place-items:center;font:900 10px Arial}.v3-brand-name{font:800 12px Arial;letter-spacing:.04em;color:var(--ink)}.v3-brand-sub{font:500 9px Arial;color:var(--muted);margin-top:2px}
.v3-head{margin-bottom:18px}.v3-title{font:800 30px Arial;letter-spacing:-.035em;color:var(--ink)}.v3-sub{font:500 12px Arial;color:var(--muted);margin-top:5px;max-width:700px}.v3-rule{border-top:1px solid var(--line);margin-bottom:12px}
.v3-section{display:flex;align-items:baseline;justify-content:space-between;border-bottom:1px solid var(--line);padding-bottom:7px;margin:25px 0 10px}.v3-section-title{font:800 11px Arial;letter-spacing:.09em;text-transform:uppercase;color:var(--ink)}.v3-section-note{font:500 10px Arial;color:var(--muted)}
.v3-mobile-list{display:none}.v3-card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:13px 14px;margin-bottom:8px}.v3-card-top{display:flex;justify-content:space-between;gap:12px}.v3-rank{font:800 10px 'JetBrains Mono',monospace;color:var(--accent)}.v3-symbol{font:900 17px Arial;color:var(--ink);margin-top:2px}.v3-industry{font:500 10px Arial;color:var(--muted);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:220px}.v3-price{font:800 15px 'JetBrains Mono',monospace;text-align:right;color:var(--ink)}.v3-day{font:800 10px 'JetBrains Mono',monospace;text-align:right;margin-top:4px}.v3-green{color:var(--green)}.v3-red{color:var(--red)}
.v3-state{display:flex;gap:5px;flex-wrap:wrap;margin:10px 0}.v3-badge{font:700 8px 'JetBrains Mono',monospace;padding:3px 6px;border:1px solid #e4e7ec;border-radius:5px;color:#475467;background:#f8fafc}.v3-badge.good{color:#067647;background:#ecfdf3;border-color:#abefc6}.v3-metrics{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid #eef0f3;padding-top:9px;gap:8px}.v3-label{font:700 8px Arial;color:var(--soft);text-transform:uppercase;letter-spacing:.05em}.v3-value{font:800 10px 'JetBrains Mono',monospace;color:var(--ink);margin-top:3px}
.v3-detail-head{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;border-bottom:1px solid var(--line);padding:5px 0 18px}.v3-detail-rank{font:800 10px 'JetBrains Mono',monospace;color:var(--accent);margin-bottom:4px}.v3-detail-symbol{font:900 29px Arial;color:var(--ink);letter-spacing:-.03em}.v3-detail-meta{font:500 11px Arial;color:var(--muted);margin-top:4px}.v3-detail-price{font:900 23px 'JetBrains Mono',monospace;text-align:right;color:var(--ink)}
.v3-summary{display:grid;grid-template-columns:1.2fr 1fr 1fr 1fr;border-bottom:1px solid var(--line)}.v3-summary-cell{padding:13px 15px 13px 0;margin-right:15px;border-right:1px solid #eef0f3}.v3-summary-cell:last-child{border-right:0}.v3-summary-value{font:900 18px 'JetBrains Mono',monospace;color:var(--ink);margin-top:3px}.v3-summary-label{font:700 8px Arial;color:var(--soft);letter-spacing:.07em;text-transform:uppercase}
.v3-table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);font-family:Arial}.v3-table th{font:700 8px Arial;color:var(--soft);text-transform:uppercase;letter-spacing:.07em;text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);background:#fafbfc}.v3-table td{font:700 11px 'JetBrains Mono',monospace;color:var(--ink);padding:9px 10px;border-bottom:1px solid #eef0f3}.v3-table td:first-child{font-family:Arial;font-weight:700}.v3-table tr:last-child td{border-bottom:0}.v3-table .pos{color:var(--green)}.v3-table .neg{color:var(--red)}.v3-quality{font:500 10px Arial;color:var(--muted);padding:9px 0}
@media(max-width:767px){[data-testid="stMainBlockContainer"]{padding:12px 12px 44px}.v3-brand{margin-bottom:20px}.v3-title{font-size:24px}.v3-sub{font-size:11px}.v3-desktop{display:none}.v3-mobile-list{display:block}.v3-detail-head{display:block}.v3-detail-symbol{font-size:25px}.v3-detail-price{text-align:left;margin-top:10px}.v3-summary{grid-template-columns:repeat(2,1fr)}.v3-summary-cell{border-right:0;border-bottom:1px solid #eef0f3;padding:11px 8px 11px 0}.v3-metrics{grid-template-columns:repeat(2,1fr)}}
</style>
"""


def _num(v: Any) -> float | None:
    try:
        if v is None or pd.isna(v): return None
        return float(v)
    except (TypeError, ValueError): return None


def _bool(v: Any) -> bool:
    return str(v).strip().lower() in {"true", "yes", "1", "y", "✓", "🟢"}


def _ret(v: Any) -> str:
    x = _num(v); return "—" if x is None else f"{x * 100:+.1f}%"


def _pct(v: Any) -> str:
    x = _num(v); return "—" if x is None else f"{x:+.1f}%"


def _money(v: Any) -> str:
    x = _num(v); return "—" if x is None else f"₹{x:,.2f}"


def _fmt(v: Any, digits: int = 2) -> str:
    x = _num(v); return "—" if x is None else f"{x:.{digits}f}"


def _hash_symbols(symbols: list[str]) -> str:
    return hashlib.md5(",".join(sorted(s.upper() for s in symbols)).encode()).hexdigest()[:12]


def _hash_frame(df: pd.DataFrame | None) -> str:
    if df is None or df.empty: return "empty"
    try:
        last = pd.to_numeric(df.iloc[-1], errors="coerce").to_numpy(dtype="float64")
        return f"{df.index[-1]}_{df.shape}_{hashlib.md5(last.tobytes()).hexdigest()[:10]}"
    except Exception: return "unknown"


@st.cache_data(show_spinner=False, ttl=3600)
def _prices(symbol_key: str, symbols: tuple[str, ...]):
    return fetch_price_history(list(symbols), period="2y", force_refresh=False)


@st.cache_data(show_spinner=False, ttl=3600)
def _mcaps(symbol_key: str, symbols: tuple[str, ...]):
    return fetch_market_caps(list(symbols), force_refresh=False)


@st.cache_data(show_spinner=False, ttl=3600)
def _ohlcv(raw_key: str, symbol_key: str, raw: Any, symbols: tuple[str, ...]):
    return extract_ohlcv(raw, list(symbols))


@st.cache_resource(show_spinner=False)
def _engine(price_key: str, universe_key: str, adj: pd.DataFrame, high: pd.DataFrame, low: pd.DataFrame, close: pd.DataFrame, volume: pd.DataFrame, idx: pd.DataFrame, mcaps: Any, weights: tuple[float, ...]):
    calc = MomentumEngine(adj, high_df=high, low_df=low, close_df=close, volume_df=volume, weights=list(weights))
    _compute_period_z_scores(calc); calc._precompute_signals(idx, mcaps, close, high); _apply_weight_composite(calc, list(weights)); return calc


@st.cache_data(show_spinner=False, ttl=1800)
def _rankings(_calc: MomentumEngine, idx: pd.DataFrame, mcaps: Any, close: pd.DataFrame, high: pd.DataFrame, weights: tuple[float, ...]):
    _calc.weights = list(weights); _apply_weight_composite(_calc, list(weights)); return _calc.get_rankings(idx, mcaps, close_prices_df=close, high_prices_df=high)


def _daily_change(close: pd.DataFrame, symbols: pd.Series) -> pd.Series:
    result = {}
    for symbol in symbols.astype(str):
        try:
            values = pd.to_numeric(close[symbol], errors="coerce").dropna()
            result[symbol] = ((values.iloc[-1] / values.iloc[-2]) - 1) * 100 if len(values) > 1 else None
        except Exception: result[symbol] = None
    return symbols.astype(str).map(result)


def load_data() -> dict[str, Any] | None:
    if st.session_state.pop("v3_force_refresh", False): st.cache_data.clear(); st.cache_resource.clear()
    indices = st.session_state.get("v3_indices", ["NIFTY TOTAL MARKET"]); idx = fetch_indices_data(indices)
    if idx is None or idx.empty or "Symbol" not in idx: return None
    symbols = tuple(idx["Symbol"].dropna().astype(str).unique().tolist()); symbol_key = _hash_symbols(list(symbols)); raw = _prices(symbol_key, symbols)
    if raw is None or raw.empty: return None
    adj, close, high, low, volume, open_ = _ohlcv(_hash_frame(raw), symbol_key, raw, symbols)
    if adj is None or adj.empty: return None
    mcaps = _mcaps(symbol_key, symbols); calc = _engine(_hash_frame(adj), f"{len(idx)}_{symbol_key}", adj, high, low, close, volume, idx, mcaps, WEIGHTS); rank = _rankings(calc, idx, mcaps, close, high, WEIGHTS)
    if rank is None or rank.empty: return None
    return {"calc": calc, "rank": rank, "close": close, "open": open_, "high": high, "low": low, "volume": volume}


def _enrich(rank: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    df = rank.copy(); df["Score Percentile"] = df["Score"].rank(pct=True) * 100 if "Score" in df else 0.0; df["1D Change"] = _daily_change(close, df["Symbol"]); return df


def _badges(row: pd.Series) -> str:
    items = []
    for col, label in (("Above 50 EMA", "ABOVE 50 EMA"), ("Near 52W High", "NEAR 52W HIGH"), ("At ATH", "AT ATH")):
        if _bool(row.get(col)): items.append(label)
    if str(row.get("Volume", "")).lower() in {"high", "surge"}: items.append("HIGH VOLUME")
    return "".join(f'<span class="v3-badge good">{html.escape(x)}</span>' for x in items)


def _filters(df: pd.DataFrame) -> pd.DataFrame:
    with st.container(border=True):
        a, b, c = st.columns([2.2, 1.2, 1.2], gap="small")
        with a: query = st.text_input("Search", placeholder="Symbol or industry", label_visibility="collapsed", key="v3_search")
        with b:
            options = ["All Stocks", "Top 50", "Above 50 EMA", "Near 52W High", "High Volume"]
            if "Qualified" in df.columns: options.insert(2, "Qualified")
            preset = st.selectbox("Universe", options, label_visibility="collapsed", key="v3_preset")
        with c: sort = st.selectbox("Sort", ["Rank", "Score", "3M Return", "12M Return", "3M Sharpe", "% High"], label_visibility="collapsed", key="v3_sort")
    out = df.copy()
    if query:
        mask = out["Symbol"].astype(str).str.contains(query, case=False, na=False)
        if "Industry" in out: mask |= out["Industry"].astype(str).str.contains(query, case=False, na=False)
        out = out[mask]
    if preset == "Top 50": out = out[pd.to_numeric(out["Rank"], errors="coerce") <= 50]
    elif preset == "Qualified" and "Qualified" in out: out = out[out["Qualified"].map(_bool)]
    elif preset == "Above 50 EMA": out = out[out["Above 50 EMA"].map(_bool)]
    elif preset == "Near 52W High": out = out[out["Near 52W High"].map(_bool)]
    elif preset == "High Volume": out = out[out["Volume"].astype(str).str.lower().isin(["high", "surge"])]
    return out.sort_values(sort, ascending=(sort == "Rank"), na_position="last")


def _mobile_card(row: pd.Series) -> str:
    rank = _num(row.get("Rank")); day = _num(row.get("1D Change")); day_cls = "v3-green" if day is not None and day >= 0 else "v3-red"
    metrics = [("1M", _ret(row.get("1M Return"))), ("3M", _ret(row.get("3M Return"))), ("6M", _ret(row.get("6M Return"))), ("12M", _ret(row.get("12M Return"))), ("3M Sharpe", _fmt(row.get("3M Sharpe"))), ("52W", _pct(row.get("% High"))), ("50 EMA", _pct(row.get("% 50 EMA"))), ("12M DD", _pct(row.get("Max DD 12M")))]
    cells = "".join(f'<div><div class="v3-label">{a}</div><div class="v3-value">{b}</div></div>' for a, b in metrics)
    return f'<div class="v3-card"><div class="v3-card-top"><div><div class="v3-rank">RANK #{int(rank) if rank is not None else "—"}</div><div class="v3-symbol">{html.escape(str(row.get("Symbol", "—")))}</div><div class="v3-industry">{html.escape(str(row.get("Industry", "—")))}</div></div><div><div class="v3-price">{_money(row.get("CMP"))}</div><div class="v3-day {day_cls}">{"—" if day is None else f"{day:+.1f}%"} 1D</div></div></div><div class="v3-state">{_badges(row)}</div><div class="v3-metrics">{cells}</div></div>'


def _section(title: str, note: str = "") -> None:
    st.markdown(f'<div class="v3-section"><div class="v3-section-title">{html.escape(title)}</div><div class="v3-section-note">{html.escape(note)}</div></div>', unsafe_allow_html=True)


def render_screener(data: dict[str, Any]) -> None:
    df = _enrich(data["rank"], data["close"])
    st.markdown('<div class="v3-brand"><div class="v3-mark">PQ</div><div><div class="v3-brand-name">PARESH QUANT</div><div class="v3-brand-sub">SYSTEM-1 · SHARPE MOMENTUM</div></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="v3-head"><div class="v3-title">Screener</div><div class="v3-sub">Ranked comparison of the universe. Use the stock page for the full quantitative read.</div></div><div class="v3-rule"></div>', unsafe_allow_html=True)
    filtered = _filters(df); _section("Ranked universe", f'{len(filtered):,} stocks · sorted by {st.session_state.get("v3_sort", "Rank")}')
    if filtered.empty: st.info("No stocks match the current filters."); return
    shown = filtered.head(100); desktop_cols = [c for c in ["Rank", "Symbol", "Industry", "CMP", "1D Change", "1M Return", "3M Return", "6M Return", "12M Return", "3M Sharpe", "% High", "% 50 EMA", "Volume"] if c in shown.columns]
    with st.container(key="v3-desktop", border=False):
        cfg = {"Rank": st.column_config.NumberColumn("Rank", format="%d", width="small", pinned=True), "Symbol": st.column_config.TextColumn("Symbol", width="small", pinned=True), "Industry": st.column_config.TextColumn("Industry", width="medium"), "CMP": st.column_config.NumberColumn("CMP", format="₹%.2f", width="small"), "1D Change": st.column_config.NumberColumn("1D", format="%+.1f%%", width="small"), "1M Return": st.column_config.NumberColumn("1M", format="%+.1f%%", width="small"), "3M Return": st.column_config.NumberColumn("3M", format="%+.1f%%", width="small"), "6M Return": st.column_config.NumberColumn("6M", format="%+.1f%%", width="small"), "12M Return": st.column_config.NumberColumn("12M", format="%+.1f%%", width="small"), "3M Sharpe": st.column_config.NumberColumn("3M S", format="%.2f", width="small"), "% High": st.column_config.NumberColumn("52W", format="%+.1f%%", width="small"), "% 50 EMA": st.column_config.NumberColumn("EMA", format="%+.1f%%", width="small")}
        event = st.dataframe(shown[desktop_cols].reset_index(drop=True), column_config=cfg, hide_index=True, width="stretch", height=min(620, 48 + len(shown) * 35), on_select="rerun", selection_mode="single-row", key="v3_table")
        if event.selection.rows:
            st.session_state.v3_symbol = str(shown.iloc[event.selection.rows[0]]["Symbol"]); st.session_state.v3_page = "Stock Detail"; st.rerun()
    with st.container(key="v3-mobile-list", border=False):
        st.caption("Open a stock for the full quantitative read")
        for i, (_, row) in enumerate(shown.iterrows()):
            symbol = str(row["Symbol"])
            if st.button(f"Open {symbol}", key=f"v3_mobile_{symbol}_{i}", width="stretch", type="secondary"):
                st.session_state.v3_symbol = symbol; st.session_state.v3_page = "Stock Detail"; st.rerun()
            st.markdown(_mobile_card(row), unsafe_allow_html=True)


def _momentum_table(row: pd.Series) -> str:
    rows = []
    for p in PERIODS:
        r = _num(row.get(f"{p}M Return")); cls = "pos" if r is not None and r >= 0 else "neg"
        rows.append(f'<tr><td>{p}M</td><td class="{cls}">{_ret(r)}</td><td>{_fmt(row.get(f"{p}M Sharpe"))}</td><td>{_pct(row.get(f"Max DD {p}M"))}</td></tr>')
    return '<table class="v3-table"><thead><tr><th>Window</th><th>Return</th><th>Sharpe</th><th>Max Drawdown</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>'


def _risk_table(row: pd.Series) -> str:
    fields = [("50 EMA distance", "% 50 EMA", "pct"), ("52W high distance", "% High", "pct"), ("ATH distance", "% ATH", "pct"), ("6M persistence", "6M Persistence", "num"), ("ATR", "ATR", "num"), ("ATR %", "ATR%", "num"), ("Stop Loss", "Stop Loss", "num"), ("Chandelier Exit", "Chand Exit", "num")]
    cells = ''.join(f'<tr><td>{html.escape(label)}</td><td>{_pct(row.get(col)) if kind=="pct" else _fmt(row.get(col))}</td></tr>' for label, col, kind in fields if col in row.index)
    return '<table class="v3-table"><thead><tr><th>Measure</th><th>Value</th></tr></thead><tbody>' + cells + '</tbody></table>'


def render_stock(data: dict[str, Any], symbol: str) -> None:
    df = _enrich(data["rank"], data["close"]); found = df[df["Symbol"].astype(str).str.upper() == symbol.upper()]
    if found.empty: st.error("Stock not found in the current universe."); return
    row = found.iloc[0]
    if st.button("← Screener", key="v3_back", type="tertiary"): st.session_state.v3_page = "Screener"; st.rerun()
    day = _num(row.get("1D Change")); day_cls = "v3-green" if day is not None and day >= 0 else "v3-red"; day_text = "—" if day is None else f"{day:+.1f}%"
    st.markdown(f'<div class="v3-detail-head"><div><div class="v3-detail-rank">RANK #{_num(row.get("Rank")):.0f}</div><div class="v3-detail-symbol">{html.escape(str(row.get("Symbol")))}</div><div class="v3-detail-meta">{html.escape(str(row.get("Industry", "—")))} · {html.escape(str(row.get("Indices", "—")))}</div></div><div><div class="v3-detail-price">{_money(row.get("CMP"))}</div><div class="v3-day {day_cls}">{day_text} 1D</div></div></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="v3-state">{_badges(row)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="v3-summary"><div class="v3-summary-cell"><div class="v3-summary-label">System-1 score</div><div class="v3-summary-value">{_fmt(row.get("Score"),3)}</div></div><div class="v3-summary-cell"><div class="v3-summary-label">Score percentile</div><div class="v3-summary-value">{_fmt(row.get("Score Percentile"),0)}</div></div><div class="v3-summary-cell"><div class="v3-summary-label">3M return</div><div class="v3-summary-value">{_ret(row.get("3M Return"))}</div></div><div class="v3-summary-cell"><div class="v3-summary-label">3M Sharpe</div><div class="v3-summary-value">{_fmt(row.get("3M Sharpe"))}</div></div></div>', unsafe_allow_html=True)

    _section("Price structure", "2-year history · 50 EMA · 52W high · ATH")
    try:
        import plotly.graph_objects as go
        prices = pd.to_numeric(data["close"][symbol], errors="coerce").dropna(); op = pd.to_numeric(data["open"][symbol], errors="coerce").reindex(prices.index); hi = pd.to_numeric(data["high"][symbol], errors="coerce").reindex(prices.index); lo = pd.to_numeric(data["low"][symbol], errors="coerce").reindex(prices.index)
        fig = go.Figure(go.Candlestick(x=prices.index, open=op, high=hi, low=lo, close=prices, name="Price")); fig.add_trace(go.Scatter(x=prices.index, y=prices.ewm(span=50, adjust=False).mean(), mode="lines", name="50 EMA"))
        for col, label in (("52W High", "52W High"), ("ATH", "ATH")):
            value = _num(row.get(col))
            if value is not None: fig.add_hline(y=value, annotation_text=label)
        fig.update_layout(height=420, margin=dict(l=4, r=4, t=8, b=4), xaxis_rangeslider_visible=False, template="plotly_white", legend=dict(orientation="h")); st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    except Exception as exc: st.warning(f"Price chart unavailable: {exc}")

    _section("Momentum", "System-1 calendar windows")
    st.markdown(_momentum_table(row), unsafe_allow_html=True)
    _section("Trend & risk", "Technical state derived by the engine")
    st.markdown(_risk_table(row), unsafe_allow_html=True)
    _section("Data quality")
    quality = [f"{col}: <strong>{html.escape(str(row.get(col, '—')))}</strong>" for col in ("Short History", "FFill %", "Data Gap", "Market Cap (Cr)") if col in row.index]
    st.markdown('<div class="v3-quality">' + ' &nbsp; · &nbsp; '.join(quality or ["No additional quality flags supplied by the engine."]) + '</div>', unsafe_allow_html=True)


def run() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.session_state.setdefault("v3_page", "Screener")
    with st.spinner("Loading quantitative universe…"): data = load_data()
    if data is None: st.error("Quantitative data could not be loaded."); st.stop()
    if st.session_state.v3_page == "Stock Detail" and st.session_state.get("v3_symbol"): render_stock(data, st.session_state.v3_symbol)
    else: render_screener(data)
