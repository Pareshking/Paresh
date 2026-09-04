"""PARESH QUANT V3 — ground-up responsive UI.

Presentation is new; quantitative calculations are delegated to the existing
production loaders and System-1 MomentumEngine.
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
from src.loaders.price_loader import extract_ohlcv, fetch_price_history, get_market_regime

PERIODS = (1, 3, 6, 9, 12)
WEIGHTS = (0.10, 0.30, 0.30, 0.20, 0.10)

CSS = """
<style>
:root{--bg:#f5f7fa;--surface:#fff;--ink:#111827;--muted:#667085;--line:#e4e7ec;--accent:#3157d5;--pos:#087443;--neg:#c43232}
[data-testid="stAppViewContainer"]{background:var(--bg)}
[data-testid="stHeader"]{background:rgba(245,247,250,.94)}
[data-testid="stMainBlockContainer"]{max-width:1480px;padding:18px 24px 56px}
section[data-testid="stSidebar"]{display:none}
.st-key-v3-mobile-list{display:none}
.v3-brand{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.v3-mark{width:34px;height:34px;border-radius:9px;background:#172554;color:#fff;display:grid;place-items:center;font:900 11px Arial}
.v3-brand-name{font:800 14px Arial;color:var(--ink);letter-spacing:.01em}.v3-brand-sub{font:500 10px Arial;color:var(--muted);margin-top:2px}
.v3-title{font:800 28px Arial;color:var(--ink);letter-spacing:-.035em}.v3-sub{font:500 12px Arial;color:var(--muted);margin-top:5px;margin-bottom:16px}
.v3-context{display:flex;overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:12px;margin:0 0 14px;white-space:nowrap}
.v3-context-item{padding:10px 15px;border-right:1px solid #eef0f3;min-width:max-content}.v3-context-label{font:700 9px Arial;color:#98a2b3;text-transform:uppercase;letter-spacing:.08em}.v3-context-value{font:800 12px 'JetBrains Mono',monospace;color:var(--ink);margin-top:4px}
.v3-section{font:800 12px Arial;color:var(--ink);letter-spacing:.04em;text-transform:uppercase;margin:18px 0 8px}.v3-count{font:500 11px Arial;color:var(--muted);text-transform:none;letter-spacing:0}
.v3-mobile-card{border:1px solid var(--line);background:#fff;border-radius:14px;padding:14px 14px 12px;margin:0 0 9px}.v3-mobile-card-top{display:flex;justify-content:space-between;gap:12px}.v3-rank{font:800 11px 'JetBrains Mono',monospace;color:var(--accent)}.v3-symbol{font:900 17px Arial;color:var(--ink);margin-top:2px}.v3-industry{font:500 10px Arial;color:var(--muted);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:220px}.v3-cmp{font:800 15px 'JetBrains Mono',monospace;color:var(--ink);text-align:right}.v3-day{font:800 10px 'JetBrains Mono',monospace;text-align:right;margin-top:4px}.v3-pos{color:var(--pos)}.v3-neg{color:var(--neg)}
.v3-badges{display:flex;gap:5px;flex-wrap:wrap;margin:11px 0 9px}.v3-badge{font:700 9px 'JetBrains Mono',monospace;padding:4px 7px;border-radius:6px;background:#f2f4f7;color:#475467;border:1px solid #eaecf0}.v3-badge-good{background:#ecfdf3;color:#067647;border-color:#abefc6}
.v3-score{display:flex;align-items:center;gap:8px;margin:5px 0 10px}.v3-track{height:5px;flex:1;background:#eaecf0;border-radius:5px;overflow:hidden}.v3-fill{height:100%;background:var(--accent);border-radius:5px}.v3-score-label{font:700 10px 'JetBrains Mono',monospace;color:#475467;min-width:62px;text-align:right}
.v3-mini-grid{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid #f0f2f5;padding-top:9px;gap:6px}.v3-mini-label{font:700 8px Arial;color:#98a2b3;text-transform:uppercase}.v3-mini-value{font:800 10px 'JetBrains Mono',monospace;color:var(--ink);margin-top:3px}.v3-card-action{margin-top:9px}
.v3-detail-hero{background:#fff;border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:12px}.v3-detail-row{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.v3-detail-symbol{font:900 27px Arial;color:var(--ink)}.v3-detail-meta{font:500 11px Arial;color:var(--muted);margin-top:4px}.v3-detail-price{font:900 20px 'JetBrains Mono',monospace;color:var(--ink);text-align:right}.v3-detail-rank{font:800 11px 'JetBrains Mono',monospace;color:var(--accent);margin-bottom:3px}
.v3-kpi{background:#fff;border:1px solid var(--line);border-radius:12px;padding:12px 13px}.v3-kpi-label{font:700 9px Arial;color:#98a2b3;text-transform:uppercase;letter-spacing:.06em}.v3-kpi-value{font:900 19px 'JetBrains Mono',monospace;color:var(--ink);margin-top:5px}
.v3-note{font:500 10px Arial;color:var(--muted);margin-top:5px}
@media(max-width:1099px){[data-testid="stMainBlockContainer"]{padding-left:16px;padding-right:16px}.v3-title{font-size:24px}}
@media(max-width:767px){[data-testid="stMainBlockContainer"]{padding:12px 12px 40px}.v3-brand{margin-bottom:8px}.v3-title{font-size:23px}.v3-sub{font-size:11px;margin-bottom:12px}.st-key-v3-desktop-table{display:none}.st-key-v3-mobile-list{display:block}.v3-context-item{padding:8px 12px}.v3-mini-grid{grid-template-columns:repeat(2,1fr);row-gap:8px}.v3-detail-row{flex-direction:column}.v3-detail-price{text-align:left}.v3-detail-symbol{font-size:24px}}
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

def _pct(v: Any, signed: bool = True) -> str:
    x = _num(v)
    if x is None: return "—"
    return f"{x:+.1f}%" if signed else f"{x:.1f}%"

def _money(v: Any) -> str:
    x = _num(v); return "—" if x is None else f"₹{x:,.2f}"

def _hash_symbols(symbols: list[str]) -> str:
    return hashlib.md5(",".join(sorted(s.upper() for s in symbols)).encode()).hexdigest()[:12]

def _hash_frame(df: pd.DataFrame | None) -> str:
    if df is None or df.empty: return "empty"
    try:
        last = pd.to_numeric(df.iloc[-1], errors="coerce").to_numpy(dtype="float64")
        return f"{df.index[-1]}_{df.shape}_{hashlib.md5(last.tobytes()).hexdigest()[:10]}"
    except Exception: return "unknown"

@st.cache_data(show_spinner=False, ttl=3600)
def _prices(symbol_key: str, symbols: tuple[str, ...]): return fetch_price_history(list(symbols), period="2y", force_refresh=False)
@st.cache_data(show_spinner=False, ttl=3600)
def _mcaps(symbol_key: str, symbols: tuple[str, ...]): return fetch_market_caps(list(symbols), force_refresh=False)
@st.cache_data(show_spinner=False, ttl=3600)
def _ohlcv(raw_key: str, symbol_key: str, raw: Any, symbols: tuple[str, ...]): return extract_ohlcv(raw, list(symbols))
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
            values = pd.to_numeric(close[symbol], errors="coerce").dropna(); result[symbol] = ((values.iloc[-1] / values.iloc[-2]) - 1) * 100 if len(values) > 1 else None
        except Exception: result[symbol] = None
    return symbols.astype(str).map(result)

def load_data():
    if st.session_state.pop("v3_force_refresh", False): st.cache_data.clear(); st.cache_resource.clear()
    indices = st.session_state.get("v3_indices", ["NIFTY TOTAL MARKET"]); idx = fetch_indices_data(indices)
    if idx is None or idx.empty or "Symbol" not in idx: return None
    symbols = tuple(idx["Symbol"].dropna().astype(str).unique().tolist()); symbol_key = _hash_symbols(list(symbols)); raw = _prices(symbol_key, symbols)
    if raw is None or raw.empty: return None
    adj, close, high, low, volume, open_ = _ohlcv(_hash_frame(raw), symbol_key, raw, symbols)
    if adj is None or adj.empty: return None
    mcaps = _mcaps(symbol_key, symbols); weights = tuple(float(st.session_state.get(f"v3_w{i}", w)) for i, w in enumerate(WEIGHTS, 1)); total = sum(weights); weights = tuple(w / total for w in weights) if total else WEIGHTS
    calc = _engine(_hash_frame(adj), f"{len(idx)}_{symbol_key}", adj, high, low, close, volume, idx, mcaps, weights); rank = _rankings(calc, idx, mcaps, close, high, weights)
    if rank is None or rank.empty: return None
    try: regime = get_market_regime()
    except Exception: regime = None
    return {"calc": calc, "rank": rank, "close": close, "open": open_, "high": high, "low": low, "volume": volume, "regime": regime}

def _enrich(rank: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    df = rank.copy(); df["Score Percentile"] = df["Score"].rank(pct=True) * 100 if "Score" in df else 0.0; df["1D Change"] = _daily_change(close, df["Symbol"]); return df

def _badges(row: pd.Series) -> str:
    items=[]
    for col,label in (("Above 50 EMA","ABOVE 50 EMA"),("Near 52W High","NEAR 52W HIGH"),("At ATH","AT ATH")):
        if _bool(row.get(col)): items.append(label)
    if str(row.get("Volume","" )).lower() in {"high","surge"}: items.append("HIGH VOLUME")
    return "".join(f'<span class="v3-badge v3-badge-good">{html.escape(x)}</span>' for x in items)

def _context_strip(df: pd.DataFrame, regime: Any) -> None:
    total=len(df); ema=int(df.get("Above 50 EMA",pd.Series(dtype=object)).map(_bool).sum()); near=int(df.get("Near 52W High",pd.Series(dtype=object)).map(_bool).sum()); top=int((pd.to_numeric(df.get("Rank",pd.Series(dtype=float)),errors="coerce")<=50).sum()); hv=int(df.get("Volume",pd.Series(dtype=object)).astype(str).str.lower().isin(["high","surge"]).sum()); breadth=ema/total*100 if total else 0; status=getattr(regime,"status",None) or "—"
    items=[("REGIME",status),("UNIVERSE",f"{total:,}"),("ABOVE 50 EMA",f"{ema:,} · {breadth:.0f}%"),("NEAR 52W HIGH",f"{near:,}"),("TOP 50",f"{top:,}"),("HIGH VOLUME",f"{hv:,}")]
    st.markdown('<div class="v3-context">'+"".join(f'<div class="v3-context-item"><div class="v3-context-label">{a}</div><div class="v3-context-value">{html.escape(str(b))}</div></div>' for a,b in items)+'</div>',unsafe_allow_html=True)

def _filters(df: pd.DataFrame) -> pd.DataFrame:
    search_col,preset_col,sort_col=st.columns([2.2,1.4,1.4],gap="small")
    with search_col: query=st.text_input("Search",placeholder="Search symbol or industry",type="search",label_visibility="collapsed",key="v3_search")
    with preset_col:
        options=["All Stocks","Top 50","Above 50 EMA","Near 52W High","High Volume"]; 
        if "Qualified" in df.columns: options.insert(2,"Qualified")
        preset=st.selectbox("Universe",options,label_visibility="collapsed",key="v3_preset")
    with sort_col: sort=st.selectbox("Sort",["Rank","Score","3M Return","12M Return","3M Sharpe","% High"],label_visibility="collapsed",key="v3_sort")
    out=df.copy()
    if query:
        mask=out["Symbol"].astype(str).str.contains(query,case=False,na=False)
        if "Industry" in out: mask |= out["Industry"].astype(str).str.contains(query,case=False,na=False)
        out=out[mask]
    if preset=="Top 50": out=out[pd.to_numeric(out["Rank"],errors="coerce")<=50]
    elif preset=="Qualified" and "Qualified" in out: out=out[out["Qualified"].map(_bool)]
    elif preset=="Above 50 EMA": out=out[out["Above 50 EMA"].map(_bool)]
    elif preset=="Near 52W High": out=out[out["Near 52W High"].map(_bool)]
    elif preset=="High Volume": out=out[out["Volume"].astype(str).str.lower().isin(["high","surge"])]
    return out.sort_values(sort,ascending=(sort=="Rank"),na_position="last")

def _mobile_card(row: pd.Series) -> str:
    rank=_num(row.get("Rank")); rank_text=f"#{int(rank)}" if rank is not None else "—"; symbol=html.escape(str(row.get("Symbol","—"))); industry=html.escape(str(row.get("Industry","—"))); cmp_text=_money(row.get("CMP")); day=_num(row.get("1D Change")); day_text="—" if day is None else f"{day:+.1f}% 1D"; day_cls="v3-pos" if day is not None and day>=0 else "v3-neg"; pct=max(0,min(100,_num(row.get("Score Percentile")) or 0)); score=_num(row.get("Score")); score_text="—" if score is None else f"{score:.3f}"
    metrics=[("1M",_ret(row.get("1M Return"))),("3M",_ret(row.get("3M Return"))),("6M",_ret(row.get("6M Return"))),("12M",_ret(row.get("12M Return"))),("3M S",f'{_num(row.get("3M Sharpe")):.2f}' if _num(row.get("3M Sharpe")) is not None else "—"),("52W",_pct(row.get("% High"))),("EMA",_pct(row.get("% 50 EMA"),True)),("12M DD",_pct(row.get("Max DD 12M"),False))]; mh="".join(f'<div><div class="v3-mini-label">{a}</div><div class="v3-mini-value">{b}</div></div>' for a,b in metrics)
    return f'<div class="v3-mobile-card"><div class="v3-mobile-card-top"><div><div class="v3-rank">{rank_text}</div><div class="v3-symbol">{symbol}</div><div class="v3-industry">{industry}</div></div><div><div class="v3-cmp">{cmp_text}</div><div class="v3-day {day_cls}">{day_text}</div></div></div><div class="v3-badges">{_badges(row)}</div><div class="v3-score"><div class="v3-track"><div class="v3-fill" style="width:{pct:.1f}%"></div></div><div class="v3-score-label">PCTL {pct:.0f} · {score_text}</div></div><div class="v3-mini-grid">{mh}</div></div>'

def render_screener(data: dict[str,Any]) -> None:
    df=_enrich(data["rank"],data["close"]); st.markdown('<div class="v3-brand"><div class="v3-mark">PQ</div><div><div class="v3-brand-name">PARESH QUANT</div><div class="v3-brand-sub">System-1 · Sharpe Momentum · live ranking</div></div></div>',unsafe_allow_html=True); st.markdown('<div class="v3-title">Screener</div><div class="v3-sub">Find the strongest quantitative setups first. Detail belongs on the stock page; this screen is optimized for comparison.</div>',unsafe_allow_html=True); _context_strip(df,data.get("regime")); filtered=_filters(df); st.markdown(f'<div class="v3-section">{len(filtered):,} matching stocks <span class="v3-count">· ranked by {html.escape(st.session_state.get("v3_sort","Rank"))}</span></div>',unsafe_allow_html=True)
    if filtered.empty: st.info("No stocks match the current filters."); return
    shown=filtered.head(100)
    with st.container(key="v3-desktop-table"):
        display=["Rank","Symbol","Industry","CMP","1D Change","1M Return","3M Return","6M Return","12M Return","3M Sharpe","% High","% 50 EMA","Volume"]; display=[c for c in display if c in shown.columns]; cfg={"Rank":st.column_config.NumberColumn("Rank",format="%d",width="small",pinned=True),"Symbol":st.column_config.TextColumn("Symbol",width="small",pinned=True),"Industry":st.column_config.TextColumn("Industry",width="medium"),"CMP":st.column_config.NumberColumn("CMP",format="₹%.2f",width="small"),"1D Change":st.column_config.NumberColumn("1D",format="%+.1f%%",width="small"),"1M Return":st.column_config.NumberColumn("1M",format="%+.1f%%",width="small"),"3M Return":st.column_config.NumberColumn("3M",format="%+.1f%%",width="small"),"6M Return":st.column_config.NumberColumn("6M",format="%+.1f%%",width="small"),"12M Return":st.column_config.NumberColumn("12M",format="%+.1f%%",width="small"),"3M Sharpe":st.column_config.NumberColumn("3M S",format="%.2f",width="small"),"% High":st.column_config.NumberColumn("52W",format="%+.1f%%",width="small"),"% 50 EMA":st.column_config.NumberColumn("EMA",format="%+.1f%%",width="small")}; event=st.dataframe(shown[display].reset_index(drop=True),column_config=cfg,hide_index=True,use_container_width=True,height=min(620,48+len(shown)*35),on_select="rerun",selection_mode="single-row",key="v3_table")
        if event.selection.rows: st.session_state.v3_symbol=str(shown.iloc[event.selection.rows[0]]["Symbol"]); st.session_state.v3_page="Stock Detail"; st.rerun()
    with st.container(key="v3-mobile-list"):
        st.caption("Tap a stock to open its quantitative detail")
        for i,(_,row) in enumerate(shown.iterrows()):
            symbol=str(row["Symbol"])
            if st.button("View",key=f"v3_mobile_{symbol}_{i}",use_container_width=True): st.session_state.v3_symbol=symbol; st.session_state.v3_page="Stock Detail"; st.rerun()
            st.markdown(_mobile_card(row),unsafe_allow_html=True)

def render_stock(data: dict[str,Any],symbol:str)->None:
    df=_enrich(data["rank"],data["close"]); found=df[df["Symbol"].astype(str).str.upper()==symbol.upper()]
    if found.empty: st.error("Stock not found in the current universe."); return
    row=found.iloc[0]
    if st.button("← Back to Screener",key="v3_back",type="tertiary"): st.session_state.v3_page="Screener"; st.rerun()
    d=_num(row.get("1D Change")); dcls="v3-pos" if (d or 0)>=0 else "v3-neg"; dtext="—" if d is None else f"{d:+.1f}% 1D"; st.markdown(f'<div class="v3-detail-hero"><div class="v3-detail-row"><div><div class="v3-detail-rank">RANK #{_num(row.get("Rank")):.0f}</div><div class="v3-detail-symbol">{html.escape(str(row["Symbol"]))}</div><div class="v3-detail-meta">{html.escape(str(row.get("Industry","—")))} · {html.escape(str(row.get("Indices","—")))}</div></div><div><div class="v3-detail-price">{_money(row.get("CMP"))}</div><div class="v3-day {dcls}">{dtext}</div></div></div><div class="v3-badges">{_badges(row)}</div></div>',unsafe_allow_html=True)
    pctl=_num(row.get("Score Percentile")) or 0; c1,c2,c3,c4=st.columns(4)
    with c1: st.markdown(f'<div class="v3-kpi"><div class="v3-kpi-label">Score</div><div class="v3-kpi-value">{_num(row.get("Score")):.3f}</div></div>',unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="v3-kpi"><div class="v3-kpi-label">Percentile</div><div class="v3-kpi-value">{pctl:.0f}</div></div>',unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="v3-kpi"><div class="v3-kpi-label">Rank Δ 1M</div><div class="v3-kpi-value">{_num(row.get("Rank Δ 1M")):+.0f}</div></div>',unsafe_allow_html=True)
    with c4: st.markdown(f'<div class="v3-kpi"><div class="v3-kpi-label">Rank Δ 3M</div><div class="v3-kpi-value">{_num(row.get("Rank Δ 3M")):+.0f}</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="v3-section">Price structure</div>',unsafe_allow_html=True)
    try:
        import plotly.graph_objects as go
        close=pd.to_numeric(data["close"][symbol],errors="coerce").dropna(); fig=go.Figure(); o=pd.to_numeric(data["open"][symbol],errors="coerce").reindex(close.index); h=pd.to_numeric(data["high"][symbol],errors="coerce").reindex(close.index); l=pd.to_numeric(data["low"][symbol],errors="coerce").reindex(close.index); fig.add_trace(go.Candlestick(x=close.index,open=o,high=h,low=l,close=close,name="Price")); fig.add_trace(go.Scatter(x=close.index,y=close.ewm(span=50,adjust=False).mean(),mode="lines",name="50 EMA"));
        for col,label in (("52W High","52W High"),("ATH","ATH")):
            value=_num(row.get(col));
            if value is not None: fig.add_hline(y=value,annotation_text=label)
        fig.update_layout(height=430,margin=dict(l=4,r=4,t=10,b=4),xaxis_rangeslider_visible=False,template="plotly_white",legend=dict(orientation="h")); st.plotly_chart(fig,use_container_width=True)
    except Exception as exc: st.warning(f"Chart unavailable: {exc}")
    st.markdown('<div class="v3-section">Momentum matrix</div>',unsafe_allow_html=True); matrix=pd.DataFrame([{"Window":f"{p}M","Return":_ret(row.get(f"{p}M Return")),"Sharpe":_num(row.get(f"{p}M Sharpe")),"Max Drawdown":_pct(row.get(f"Max DD {p}M"),False)} for p in PERIODS]); st.dataframe(matrix,use_container_width=True,hide_index=True,column_config={"Sharpe":st.column_config.NumberColumn(format="%.2f")})
    st.markdown('<div class="v3-section">Trend · highs · risk</div>',unsafe_allow_html=True); trend=pd.DataFrame([( "50 EMA distance",_pct(row.get("% 50 EMA"))), ("52W High",_money(row.get("52W High"))), ("52W High Date",row.get("52W High Date","—")), ("From 52W High",_pct(row.get("% High"))), ("ATH",_money(row.get("ATH"))), ("ATH Date",row.get("ATH Date","—")), ("From ATH",_pct(row.get("% ATH"))), ("6M Persistence",_pct(row.get("6M Persistence"),False)), ("ATR",_money(row.get("ATR"))), ("ATR%",_pct(row.get("ATR%"),False)), ("Stop Loss",_money(row.get("Stop Loss"))), ("Chandelier Exit",_money(row.get("Chand Exit"))), ("12M Max Drawdown",_pct(row.get("Max DD 12M"),False)), ("Volume",row.get("Volume","—"))],columns=["Metric","Value"]); st.dataframe(trend,use_container_width=True,hide_index=True)
    st.markdown('<div class="v3-section">Metadata · data quality</div>',unsafe_allow_html=True); meta=pd.DataFrame([(k,row.get(k,"—")) for k in ("Market Cap (Cr)","Industry","Indices","Short History","FFill %","Data Gap")],columns=["Field","Value"]); st.dataframe(meta,use_container_width=True,hide_index=True)

def run()->None:
    st.markdown(CSS,unsafe_allow_html=True)
    if "v3_page" not in st.session_state: st.session_state.v3_page="Screener"
    data=load_data()
    if data is None: st.error("Unable to load the quantitative dataset."); return
    page=st.segmented_control("Page",["Screener","Stock Detail"],default=st.session_state.v3_page,key="v3_page_control",width="content"); st.session_state.v3_page=page
    if page=="Stock Detail" and st.session_state.get("v3_symbol"): render_stock(data,str(st.session_state.v3_symbol))
    else: st.session_state.v3_page="Screener"; render_screener(data)
