"""PARESH QUANT v2 verification UI: Screener + Stock Detail only.

The quantitative/data layer is reused from the existing production modules.
No unsupported fundamentals, news, RS scores, or new momentum models are used.
"""
from __future__ import annotations
import hashlib, html
import pandas as pd
import streamlit as st

from src.engine.calendar_momentum import _apply_weight_composite, _compute_period_z_scores
from src.engine.momentum import MomentumEngine
from src.loaders.indices_loader import fetch_indices_data
from src.loaders.mcap_loader import fetch_market_caps
from src.loaders.price_loader import extract_ohlcv, fetch_price_history, get_market_regime

PERIODS=(1,3,6,9,12)

CSS='''<style>
[data-testid="stAppViewContainer"]{background:#f5f7fa}[data-testid="stHeader"]{background:rgba(245,247,250,.92)}
[data-testid="stMainBlockContainer"]{max-width:1540px;padding:1rem 1.4rem 3rem}
section[data-testid="stSidebar"]{display:none}.v2-brand{display:flex;align-items:center;gap:12px;margin-bottom:8px}.v2-mark{width:34px;height:34px;border-radius:9px;background:#3157d5;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:900}.v2-brand-name{font:800 1.08rem Arial;color:#101828}.v2-brand-sub,.v2-page-sub{color:#667085;font:.68rem Arial}.v2-page-title{font:800 1.55rem Arial;color:#101828;letter-spacing:-.025em}.v2-page-sub{font-size:.78rem;margin-top:4px}.v2-strip{display:flex;overflow-x:auto;white-space:nowrap;background:#fff;border:1px solid #e4e7ec;border-radius:12px;margin:10px 0 14px}.v2-strip-item{padding:9px 15px;border-right:1px solid #eaecf0}.v2-strip-label{color:#667085;font:700 .58rem Arial;text-transform:uppercase;letter-spacing:.07em}.v2-strip-value{color:#101828;font:800 .78rem 'JetBrains Mono',monospace;margin-top:4px}.v2-card,.v2-detail-hero,.v2-stock-card{background:#fff;border:1px solid #e4e7ec;border-radius:14px;padding:14px;box-shadow:0 1px 2px rgba(16,24,40,.03)}.v2-detail-hero{border-radius:16px;padding:18px}.v2-section{color:#101828;font:800 .78rem Arial;text-transform:uppercase;letter-spacing:.06em;margin:16px 0 8px}.v2-stock-top{display:flex;justify-content:space-between;gap:10px}.v2-rank{color:#3157d5;font:800 .72rem 'JetBrains Mono',monospace}.v2-symbol,.v2-detail-symbol{color:#101828;font:900 1rem Arial}.v2-detail-symbol{font-size:1.75rem}.v2-industry,.v2-detail-meta{color:#667085;font:.66rem Arial;margin-top:3px}.v2-detail-meta{font-size:.72rem}.v2-price,.v2-big-number{color:#101828;font:800 .95rem 'JetBrains Mono',monospace;text-align:right}.v2-big-number{font-size:1.6rem}.v2-delta-pos{color:#087443;font:700 .65rem 'JetBrains Mono';text-align:right;margin-top:4px}.v2-delta-neg{color:#c43232;font:700 .65rem 'JetBrains Mono';text-align:right;margin-top:4px}.v2-badges{display:flex;flex-wrap:wrap;gap:5px;margin:10px 0}.v2-badge{padding:3px 7px;border-radius:6px;background:#f2f4f7;border:1px solid #eaecf0;color:#475467;font:700 .59rem 'JetBrains Mono'}.v2-badge-good{background:#ecfdf3;border-color:#abefc6;color:#067647}.v2-score{display:flex;align-items:center;gap:8px}.v2-score-track{flex:1;height:5px;background:#eaecf0;border-radius:10px;overflow:hidden}.v2-score-fill{height:100%;background:#3157d5;border-radius:10px}.v2-score-text{color:#475467;font:700 .62rem 'JetBrains Mono'}.v2-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-top:10px}.v2-metric{border-top:1px solid #f0f2f5;padding-top:7px}.v2-metric-label{color:#98a2b3;font:700 .55rem Arial;text-transform:uppercase}.v2-metric-value{color:#101828;font:800 .68rem 'JetBrains Mono';margin-top:3px}.v2-table-note{color:#667085;font:500 .66rem Arial;margin-top:4px}
@media(max-width:760px){[data-testid="stMainBlockContainer"]{padding-left:.75rem;padding-right:.75rem}.v2-page-title{font-size:1.3rem}.v2-metrics{grid-template-columns:repeat(2,1fr)}.v2-strip-item{padding:8px 11px}}
</style>'''

def _num(v):
    try:
        if v is None or pd.isna(v): return None
        return float(v)
    except (TypeError,ValueError): return None

def _pct(v,signed=True):
    x=_num(v)
    return "—" if x is None else (f"{x:+.1f}%" if signed else f"{x:.1f}%")

def _ret(v):
    x=_num(v); return "—" if x is None else f"{x*100:+.1f}%"

def _money(v):
    x=_num(v); return "—" if x is None else f"₹{x:,.2f}"

def _bool(v): return str(v).strip().lower() in {"true","yes","1","y","✓","🟢"}

def _hash_symbols(symbols): return hashlib.md5(",".join(sorted(str(s).upper() for s in symbols)).encode()).hexdigest()[:12]

def _hash_prices(df):
    if df is None or df.empty:return "empty"
    try:
        last=pd.to_numeric(df.iloc[-1],errors="coerce").to_numpy(dtype="float64")
        return f"{df.index[-1]}_{df.shape[0]}x{df.shape[1]}_{hashlib.md5(last.tobytes()).hexdigest()[:12]}"
    except Exception:return "unknown"

@st.cache_data(show_spinner=False,ttl=3600)
def _prices(key,symbols): return fetch_price_history(list(symbols),period="2y",force_refresh=False)
@st.cache_data(show_spinner=False,ttl=3600)
def _mcaps(key,symbols): return fetch_market_caps(list(symbols),force_refresh=False)
@st.cache_data(show_spinner=False,ttl=3600)
def _ohlcv(key,skey,raw,symbols): return extract_ohlcv(raw,symbols)
@st.cache_data(show_spinner=False,ttl=3600)
def _engine(ph,uh,adj,high,low,close,vol,idx,mcaps):
    c=MomentumEngine(adj,high_df=high,low_df=low,close_df=close,volume_df=vol,weights=[.2]*5)
    _compute_period_z_scores(c); c._precompute_signals(idx,mcaps,close,high); return c
@st.cache_data(show_spinner=False,ttl=3600)
def _ranked(base,weights,calc,idx,mcaps,close,high):
    calc.weights=list(weights); _apply_weight_composite(calc,list(weights)); return calc,calc.get_rankings(idx,mcaps,close_prices_df=close,high_prices_df=high)

def load_data():
    if st.session_state.pop("v2_force_refresh",False): st.cache_data.clear()
    indices=st.session_state.get("v2_indices",["NIFTY TOTAL MARKET"])
    rw=[float(st.session_state.get(f"v2_w{i}",x)) for i,x in enumerate((.10,.30,.30,.20,.10),1)]; tw=sum(rw); weights=tuple(w/tw for w in rw) if tw else (.2,)*5
    idx=fetch_indices_data(indices)
    if idx is None or idx.empty or "Symbol" not in idx:return None
    symbols=idx["Symbol"].dropna().astype(str).unique().tolist(); skey=_hash_symbols(symbols); raw=_prices(skey,symbols)
    if raw is None or raw.empty:return None
    adj,close,high,low,vol,open_=_ohlcv(_hash_prices(raw),skey,raw,symbols)
    if adj is None or adj.empty:return None
    mcaps=_mcaps(skey,symbols); ph=_hash_prices(adj); uh=f"{len(idx)}_{skey}"; base=f"{ph}_{uh}_v2"
    calc_base=_engine(ph,uh,adj,high,low,close,vol,idx,mcaps); calc,rank=_ranked(base,weights,calc_base,idx,mcaps,close,high)
    if rank is None or rank.empty:return None
    try: regime=get_market_regime()
    except Exception: regime=None
    return dict(calc=calc,rank_df=rank,close_prices=close,open_prices=open_,high_prices=high,low_prices=low,volume_data=vol,regime=regime)

def _daily(close,symbols):
    out={}
    for s in symbols:
        try:
            x=pd.to_numeric(close[s],errors="coerce").dropna(); out[s]=((x.iloc[-1]/x.iloc[-2])-1)*100 if len(x)>1 else None
        except Exception:out[s]=None
    return symbols.map(out)

def _enrich(df,close):
    x=df.copy(); x["Score Percentile"]=x["Score"].rank(pct=True)*100; x["1D Change"]=_daily(close,x["Symbol"])
    def state(r):
        s=[]
        if _bool(r.get("Above 50 EMA")):s.append("Above EMA")
        if _bool(r.get("Near 52W High")):s.append("Near 52W")
        if _bool(r.get("At ATH")):s.append("ATH")
        if str(r.get("Volume","")).lower() in {"high","surge"}:s.append("High Volume")
        return " · ".join(s) or "—"
    x["State"]=x.apply(state,axis=1); return x

def render_screener(data):
    df=_enrich(data["rank_df"],data["close_prices"]); total=len(df); ema=int(df["Above 50 EMA"].map(_bool).sum()); near=int(df["Near 52W High"].map(_bool).sum()); top=int((pd.to_numeric(df["Rank"],errors="coerce")<=50).sum()); hv=int(df["Volume"].astype(str).str.lower().isin(["high","surge"]).sum())
    st.markdown('<div class="v2-brand"><div class="v2-mark">PQ</div><div><div class="v2-brand-name">PARESH QUANT</div><div class="v2-brand-sub">NSE Momentum Terminal · v2 verification build</div></div></div>',unsafe_allow_html=True)
    st.markdown('<div class="v2-page-title">Screener</div><div class="v2-page-sub">Comparison-first ranking using the existing momentum engine. Nothing in this build requires a new research data source.</div>',unsafe_allow_html=True)
    regime=getattr(data.get("regime"),"status",None) or "—"; breadth=ema/total*100 if total else 0
    st.markdown(f'<div class="v2-strip"><div class="v2-strip-item"><div class="v2-strip-label">Regime</div><div class="v2-strip-value">{html.escape(str(regime))}</div></div><div class="v2-strip-item"><div class="v2-strip-label">Universe</div><div class="v2-strip-value">{total:,}</div></div><div class="v2-strip-item"><div class="v2-strip-label">Above 50 EMA</div><div class="v2-strip-value">{ema:,} · {breadth:.0f}%</div></div><div class="v2-strip-item"><div class="v2-strip-label">Near 52W High</div><div class="v2-strip-value">{near:,}</div></div><div class="v2-strip-item"><div class="v2-strip-label">Top 50</div><div class="v2-strip-value">{top:,}</div></div><div class="v2-strip-item"><div class="v2-strip-label">High Volume</div><div class="v2-strip-value">{hv:,}</div></div></div>',unsafe_allow_html=True)
    q=st.text_input("Search",placeholder="Search symbol or industry…",label_visibility="collapsed",key="v2_search")
    preset=st.pills("Universe",["All Stocks","Top 50","Qualified","Above 50 EMA","Near 52W High","High Volume"],default="All Stocks",key="v2_preset")
    f=df.copy()
    if q:
        m=f["Symbol"].astype(str).str.contains(q,case=False,na=False)
        if "Industry" in f:m=m|f["Industry"].astype(str).str.contains(q,case=False,na=False)
        f=f[m]
    if preset=="Top 50":f=f[pd.to_numeric(f["Rank"],errors="coerce")<=50]
    elif preset=="Qualified" and "Qualified" in f:f=f[f["Qualified"].map(_bool)]
    elif preset=="Above 50 EMA":f=f[f["Above 50 EMA"].map(_bool)]
    elif preset=="Near 52W High":f=f[f["Near 52W High"].map(_bool)]
    elif preset=="High Volume":f=f[f["Volume"].astype(str).str.lower().isin(["high","surge"])]
    a,b,c=st.columns([1.5,1,1])
    with a:sort=st.selectbox("Sort",["Rank","Score","3M Return","12M Return","3M Sharpe","% High"],label_visibility="collapsed",key="v2_sort")
    with b:view=st.segmented_control("View",["Table","Cards"],default="Table",key="v2_view",label_visibility="collapsed")
    with c:n=st.selectbox("Rows",[25,50,100],label_visibility="collapsed",key="v2_rows")
    f=f.sort_values(sort,ascending=sort=="Rank",na_position="last"); shown=f.head(n)
    st.markdown(f'<div class="v2-section">{len(f):,} matching stocks <span class="v2-muted">· select a row/card to open Stock Detail</span></div>',unsafe_allow_html=True)
    if shown.empty:st.info("No stocks match the current filters.");return
    if view=="Cards":
        left,right=st.columns(2)
        for i,(_,r) in enumerate(shown.iterrows()):
            sym=str(r["Symbol"]); pctile=_num(r.get("Score Percentile")) or 0; d=_num(r.get("1D Change")); badges=[]
            if _bool(r.get("Above 50 EMA")):badges.append("ABOVE 50 EMA")
            if _bool(r.get("Near 52W High")):badges.append("NEAR 52W HIGH")
            if _bool(r.get("At ATH")):badges.append("ATH")
            if str(r.get("Volume","")).lower() in {"high","surge"}:badges.append("HIGH VOLUME")
            bh=''.join(f'<span class="v2-badge v2-badge-good">{x}</span>' for x in badges) or '<span class="v2-badge">No special state</span>'
            vals=[("1M",_ret(r.get("1M Return"))),("3M",_ret(r.get("3M Return"))),("6M",_ret(r.get("6M Return"))),("12M",_ret(r.get("12M Return"))),("52W High",_pct(r.get("% High"))),("50 EMA",_pct(r.get("% 50 EMA"))),("3M Sharpe",f"{_num(r.get('3M Sharpe')):.2f}" if _num(r.get("3M Sharpe")) is not None else "—"),("12M DD",_pct(r.get("Max DD 12M"),False))]
            mh=''.join(f'<div class="v2-metric"><div class="v2-metric-label">{x}</div><div class="v2-metric-value">{y}</div></div>' for x,y in vals); dc="v2-delta-pos" if (d or 0)>=0 else "v2-delta-neg"
            card=f'<div class="v2-stock-card"><div class="v2-stock-top"><div><div class="v2-rank">RANK #{int(_num(r.get("Rank"))) if _num(r.get("Rank")) is not None else "—"}</div><div class="v2-symbol">{html.escape(sym)}</div><div class="v2-industry">{html.escape(str(r.get("Industry","") or ""))}</div></div><div><div class="v2-price">{_money(r.get("CMP"))}</div><div class="{dc}">{_pct(d)}</div></div></div><div class="v2-badges">{bh}</div><div class="v2-score"><div class="v2-score-track"><div class="v2-score-fill" style="width:{pctile:.1f}%"></div></div><div class="v2-score-text">{pctile:.0f}th percentile</div></div><div class="v2-metrics">{mh}</div></div>'
            with (left if i%2==0 else right):st.html(card); st.button(f"Open {sym}",key=f"v2_card_{i}_{sym}",on_click=lambda s=sym:st.session_state.update(v2_selected_symbol=s,v2_page="Stock Detail"))
        return
    cols=["Rank","Symbol","Industry","CMP","1D Change","Score","Score Percentile","Rank Δ 1M","Rank Δ 3M","1M Return","3M Return","6M Return","12M Return","3M Sharpe","12M Sharpe","% High","% 50 EMA","Volume","State"];cols=[x for x in cols if x in shown]
    t=shown[cols].copy()
    for c_ in ["1M Return","3M Return","6M Return","12M Return"]:t[c_]=pd.to_numeric(t[c_],errors="coerce")*100
    cfg={"Rank":st.column_config.NumberColumn("Rank",format="%d",pinned=True),"Symbol":st.column_config.TextColumn("Stock",pinned=True),"CMP":st.column_config.NumberColumn("Price",format="₹ %.2f"),"1D Change":st.column_config.NumberColumn("1D",format="%+.2f%%"),"Score":st.column_config.NumberColumn("Score",format="%.2f"),"Score Percentile":st.column_config.ProgressColumn("Percentile",format="%.0f",min_value=0,max_value=100),"Rank Δ 1M":st.column_config.NumberColumn("Δ 1M",format="%+d"),"Rank Δ 3M":st.column_config.NumberColumn("Δ 3M",format="%+d"),"1M Return":st.column_config.NumberColumn("1M",format="%+.1f%%"),"3M Return":st.column_config.NumberColumn("3M",format="%+.1f%%"),"6M Return":st.column_config.NumberColumn("6M",format="%+.1f%%"),"12M Return":st.column_config.NumberColumn("12M",format="%+.1f%%"),"3M Sharpe":st.column_config.NumberColumn("3M Sharpe",format="%.2f"),"12M Sharpe":st.column_config.NumberColumn("12M Sharpe",format="%.2f"),"% High":st.column_config.NumberColumn("vs 52W High",format="%+.1f%%"),"% 50 EMA":st.column_config.NumberColumn("vs 50 EMA",format="%+.1f%%")}
    ev=st.dataframe(t,column_config=cfg,hide_index=True,width="stretch",height=560,row_height=34,on_select="rerun",selection_mode="single-row",key="v2_screener_table")
    if ev.selection.rows:st.session_state.update(v2_selected_symbol=str(shown.iloc[ev.selection.rows[0]]["Symbol"]),v2_page="Stock Detail");st.rerun()

def render_stock(data,symbol):
    df=data["rank_df"].copy();df["Score Percentile"]=df["Score"].rank(pct=True)*100
    if not symbol:st.markdown('<div class="v2-page-title">Stock Detail</div><div class="v2-page-sub">Select a stock from Screener to open its quantitative evidence trail.</div>',unsafe_allow_html=True);st.info("No stock selected.");return
    hit=df[df["Symbol"].astype(str).str.upper()==str(symbol).upper()]
    if hit.empty:st.error(f"Stock `{symbol}` is not in the current ranked universe.");return
    r=hit.iloc[0];sym=str(r["Symbol"]);score=_num(r.get("Score"));pctile=_num(r.get("Score Percentile"));rank=_num(r.get("Rank"));states=[]
    for key,label in [("Above 50 EMA","Above 50 EMA"),("Near 52W High","Near 52W High"),("At ATH","At ATH")]:
        if _bool(r.get(key)):states.append(label)
    if str(r.get("Volume","")).lower() in {"high","surge"}:states.append("High Volume")
    badges=''.join(f'<span class="v2-badge v2-badge-good">{x}</span>' for x in states) or '<span class="v2-badge">No special state</span>'
    st.button("← Back to Screener",key="v2_back",on_click=lambda:st.session_state.update(v2_page="Screener"))
    st.markdown(f'<div class="v2-detail-hero"><div class="v2-stock-top"><div><div class="v2-detail-symbol">{html.escape(sym)}</div><div class="v2-detail-meta">{html.escape(str(r.get("Industry","") or ""))} · quantitative evidence trail</div><div class="v2-badges">{badges}</div></div><div><div class="v2-big-number">{_money(r.get("CMP"))}</div><div class="v2-detail-meta">Rank #{int(rank) if rank is not None else "—"} · {pctile:.0f}th percentile</div></div></div></div>',unsafe_allow_html=True)
    st.markdown('<div class="v2-section">Momentum position</div>',unsafe_allow_html=True);a,b,c,d=st.columns(4)
    for col,label,val,sub in [(a,"Score",f"{score:.2f}" if score is not None else "—","composite momentum"),(b,"Percentile",f"{pctile:.0f}" if pctile is not None else "—","cross-sectional"),(c,"Rank Δ 1M",f"{_num(r.get('Rank Δ 1M')):+.0f}" if _num(r.get('Rank Δ 1M')) is not None else "—","rank movement"),(d,"Rank Δ 3M",f"{_num(r.get('Rank Δ 3M')):+.0f}" if _num(r.get('Rank Δ 3M')) is not None else "—","rank movement")]:
        with col:_card(label,val,sub)
    st.markdown('<div class="v2-section">Price & technicals</div>',unsafe_allow_html=True);_chart(r,data)
    st.markdown('<div class="v2-section">Momentum windows</div>',unsafe_allow_html=True);perf=pd.DataFrame(index=["Return","Sharpe","Max Drawdown"],columns=[f"{m}M" for m in PERIODS])
    for m in PERIODS:
        perf.loc["Return",f"{m}M"]=_ret(r.get(f"{m}M Return"));s=_num(r.get(f"{m}M Sharpe"));perf.loc["Sharpe",f"{m}M"]=f"{s:.2f}" if s is not None else "—";perf.loc["Max Drawdown",f"{m}M"]=_pct(r.get(f"Max DD {m}M"),False)
    st.dataframe(perf,width="stretch",height=165)
    st.markdown('<div class="v2-section">Trend, highs & risk</div>',unsafe_allow_html=True)
    items=[("50 EMA",_pct(r.get("% 50 EMA")),"distance from EMA"),("52W High",_money(r.get("52W High")),str(r.get("52W High Date","") or "")),("From 52W High",_pct(r.get("% High")),"distance"),("ATH",_money(r.get("ATH")),str(r.get("ATH Date","") or "")),("From ATH",_pct(r.get("% ATH")),"distance"),("6M Persistence",_pct(r.get("Persistence"),False),"positive sessions"),("ATR",_money(r.get("ATR")),f"{_num(r.get('ATR %')):.1f}% of price" if _num(r.get("ATR %")) is not None else ""),("Stop Loss",_money(r.get("Stop Loss")),"2 × ATR"),("Chandelier Exit",_money(r.get("Chand Exit")),"3 × ATR"),("12M Max Drawdown",_pct(r.get("Max DD 12M"),False),"worst observed"),("Volume",str(r.get("Volume","—")),"volume status")]
    for i in range(0,len(items),3):
        cs=st.columns(3)
        for col,(label,val,sub) in zip(cs,items[i:i+3]):
            with col:_card(label,val,sub)
    st.markdown('<div class="v2-section">Metadata & data quality</div>',unsafe_allow_html=True);meta={k:r.get(k) for k in ["Market Cap (Cr)","Industry","Indices","Short History","FFill %","Data Gap"] if k in r.index};st.dataframe(pd.DataFrame([meta]),hide_index=True,width="stretch",height=90)

def _card(label,value,sub=""):
    st.markdown(f'<div class="v2-card"><div class="v2-strip-label">{html.escape(label)}</div><div class="v2-big-number" style="text-align:left;margin-top:6px">{html.escape(str(value))}</div><div class="v2-table-note">{html.escape(sub)}</div></div>',unsafe_allow_html=True)

def _chart(r,data):
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except Exception:st.warning("Plotly is unavailable.");return
    sym=str(r["Symbol"]);close=data["close_prices"]
    if sym not in close:st.info("Price history is unavailable.");return
    frame=pd.DataFrame({"Close":pd.to_numeric(close[sym],errors="coerce")});
    for name,key in (("Open","open_prices"),("High","high_prices"),("Low","low_prices"),("Volume","volume_data")):
        src=data.get(key)
        if src is not None and sym in src:frame[name]=pd.to_numeric(src[sym],errors="coerce")
    frame=frame.dropna(subset=["Close"]).tail(252);fig=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.78,.22],vertical_spacing=.035)
    if all(x in frame for x in ["Open","High","Low"]):fig.add_trace(go.Candlestick(x=frame.index,open=frame.Open,high=frame.High,low=frame.Low,close=frame.Close,name=sym),row=1,col=1)
    else:fig.add_trace(go.Scatter(x=frame.index,y=frame.Close,name="Close"),row=1,col=1)
    fig.add_trace(go.Scatter(x=frame.index,y=frame.Close.ewm(span=50,min_periods=30).mean(),name="50 EMA"),row=1,col=1);hi=_num(r.get("52W High"));ath=_num(r.get("ATH"))
    if hi is not None:fig.add_hline(y=hi,line_dash="dot",annotation_text="52W High",row=1,col=1)
    if ath is not None and (hi is None or abs(ath-hi)>1e-9):fig.add_hline(y=ath,line_dash="dash",annotation_text="ATH",row=1,col=1)
    if "Volume" in frame:fig.add_trace(go.Bar(x=frame.index,y=frame.Volume,name="Volume",opacity=.35),row=2,col=1)
    fig.update_layout(height=500,margin=dict(l=8,r=8,t=18,b=8),template="plotly_white",hovermode="x unified",showlegend=True);fig.update_xaxes(rangeslider_visible=False);st.plotly_chart(fig,width="stretch",config={"displaylogo":False})

def run():
    st.html(CSS)
    if "v2_page" not in st.session_state:st.session_state["v2_page"]="Screener"
    if "v2_selected_symbol" not in st.session_state:st.session_state["v2_selected_symbol"]=None
    a,b,c=st.columns([1,3,1])
    with a:st.markdown("**PARESH QUANT**")
    with b:
        p=st.pills("Navigation",["Screener","Stock Detail"],default=st.session_state["v2_page"],key="v2_nav",label_visibility="collapsed")
        if p:st.session_state["v2_page"]=p
    with c:
        if st.button("↻ Refresh data",key="v2_refresh"):st.session_state["v2_force_refresh"]=True;st.rerun()
    with st.spinner("Loading quantitative universe…"):data=load_data()
    if not data:st.error("Unable to initialize the existing quantitative universe/data pipeline.");st.stop()
    if st.session_state["v2_page"]=="Stock Detail":render_stock(data,st.session_state.get("v2_selected_symbol"))
    else:render_screener(data)
