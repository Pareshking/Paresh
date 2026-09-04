"""Data-grounded Stock Detail for the v2 verification build."""
from __future__ import annotations
import html
import pandas as pd
import streamlit as st

PERIODS=(1,3,6,9,12)

def _num(v):
    try:
        if v is None or pd.isna(v): return None
        return float(v)
    except (TypeError,ValueError): return None

def _pct(v,signed=True):
    x=_num(v)
    if x is None: return "—"
    return f"{x:+.1f}%" if signed else f"{x:.1f}%"

def _ret(v):
    x=_num(v)
    return f"{x*100:+.1f}%" if x is not None else "—"

def _money(v):
    x=_num(v)
    return f"₹{x:,.2f}" if x is not None else "—"

def _bool(v):
    return str(v).strip().lower() in {"true","yes","1","y","✓","🟢"}

def _row(df,symbol):
    hit=df[df["Symbol"].astype(str).str.upper()==str(symbol).upper()]
    return hit.iloc[0] if not hit.empty else None

def _card(label,value,sub=""):
    sub_html=f'<div class="v2-table-note">{html.escape(sub)}</div>' if sub else ""
    st.markdown(f'<div class="v2-card"><div class="v2-strip-label">{html.escape(label)}</div><div class="v2-big-number" style="margin-top:6px">{html.escape(str(value))}</div>{sub_html}</div>',unsafe_allow_html=True)

def _chart(row,data):
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except Exception:
        st.warning("Plotly is unavailable; the quantitative sections below remain available.")
        return
    sym=str(row["Symbol"]); close=data.get("close_prices")
    if close is None or sym not in close.columns:
        st.info("Price history is not available for this stock."); return
    frame=pd.DataFrame({"Close":pd.to_numeric(close[sym],errors="coerce")})
    for name,key in (("Open","open_prices"),("High","high_prices"),("Low","low_prices"),("Volume","volume_data")):
        src=data.get(key)
        if src is not None and sym in src.columns: frame[name]=pd.to_numeric(src[sym],errors="coerce")
    frame=frame.dropna(subset=["Close"]).tail(252)
    fig=make_subplots(rows=2,cols=1,shared_xaxes=True,row_heights=[.78,.22],vertical_spacing=.035)
    if all(x in frame for x in ["Open","High","Low"]):
        fig.add_trace(go.Candlestick(x=frame.index,open=frame["Open"],high=frame["High"],low=frame["Low"],close=frame["Close"],name=sym),row=1,col=1)
    else: fig.add_trace(go.Scatter(x=frame.index,y=frame["Close"],name="Close",mode="lines"),row=1,col=1)
    fig.add_trace(go.Scatter(x=frame.index,y=frame["Close"].ewm(span=50,min_periods=30).mean(),name="50 EMA",mode="lines"),row=1,col=1)
    hi=_num(row.get("52W High")); ath=_num(row.get("ATH"))
    if hi is not None: fig.add_hline(y=hi,line_dash="dot",annotation_text="52W High",row=1,col=1)
    if ath is not None and (hi is None or abs(ath-hi)>1e-9): fig.add_hline(y=ath,line_dash="dash",annotation_text="ATH",row=1,col=1)
    if "Volume" in frame: fig.add_trace(go.Bar(x=frame.index,y=frame["Volume"],name="Volume",opacity=.35),row=2,col=1)
    fig.update_layout(height=500,margin=dict(l=8,r=8,t=18,b=8),template="plotly_white",hovermode="x unified",showlegend=True,legend=dict(orientation="h",y=1.02,x=0))
    fig.update_xaxes(rangeslider_visible=False)
    st.plotly_chart(fig,width="stretch",config={"displaylogo":False,"scrollZoom":False})

def render(data,symbol):
    df=data["rank_df"].copy()
    if "Score" in df: df["Score Percentile"]=df["Score"].rank(pct=True)*100
    if not symbol:
        st.markdown('<div class="v2-page-title">Stock Detail</div><div class="v2-page-sub">Select a stock from the Screener to open its quantitative evidence trail.</div>',unsafe_allow_html=True)
        st.info("No stock selected. Return to Screener and select a row or card."); return
    row=_row(df,symbol)
    if row is None: st.error(f"Stock `{symbol}` is not present in the current ranked universe."); return
    sym=str(row.get("Symbol",symbol)); industry=str(row.get("Industry","") or ""); score=_num(row.get("Score")); pctile=_num(row.get("Score Percentile")); rank=_num(row.get("Rank"))
    states=[]
    if _bool(row.get("Above 50 EMA")): states.append("Above 50 EMA")
    if _bool(row.get("Near 52W High")): states.append("Near 52W High")
    if _bool(row.get("At ATH")): states.append("At ATH")
    if str(row.get("Volume","")).lower() in {"high","surge"}: states.append("High Volume")
    badges=''.join(f'<span class="v2-badge v2-badge-good">{html.escape(s)}</span>' for s in states) or '<span class="v2-badge">No special state</span>'
    st.button("← Back to Screener",key="v2_back",on_click=lambda:st.session_state.update({"v2_page":"Screener"}))
    st.markdown(f'<div class="v2-detail-hero"><div class="v2-stock-top"><div><div class="v2-detail-symbol">{html.escape(sym)}</div><div class="v2-detail-meta">{html.escape(industry)} · quantitative evidence trail</div><div class="v2-badges">{badges}</div></div><div style="text-align:right"><div class="v2-big-number">{_money(row.get("CMP"))}</div><div class="v2-detail-meta">Rank #{int(rank) if rank is not None else "—"} · {pctile:.0f}th percentile</div></div></div></div>',unsafe_allow_html=True)

    st.markdown('<div class="v2-section">Momentum position</div>',unsafe_allow_html=True)
    a,b,c,d=st.columns(4)
    for col,label,value,sub in [(a,"Score",f"{score:.2f}" if score is not None else "—","composite momentum"),(b,"Percentile",f"{pctile:.0f}" if pctile is not None else "—","cross-sectional"),(c,"Rank Δ 1M",f"{_num(row.get('Rank Δ 1M')):+.0f}" if _num(row.get('Rank Δ 1M')) is not None else "—","rank movement"),(d,"Rank Δ 3M",f"{_num(row.get('Rank Δ 3M')):+.0f}" if _num(row.get('Rank Δ 3M')) is not None else "—","rank movement")]:
        with col: _card(label,value,sub)

    st.markdown('<div class="v2-section">Price & technicals</div>',unsafe_allow_html=True); _chart(row,data)
    st.markdown('<div class="v2-section">Momentum windows</div>',unsafe_allow_html=True)
    perf=pd.DataFrame(index=["Return","Sharpe","Max Drawdown"],columns=[f"{m}M" for m in PERIODS])
    for m in PERIODS:
        perf.loc["Return",f"{m}M"]=_ret(row.get(f"{m}M Return")); s=_num(row.get(f"{m}M Sharpe")); perf.loc["Sharpe",f"{m}M"]=f"{s:.2f}" if s is not None else "—"; perf.loc["Max Drawdown",f"{m}M"]=_pct(row.get(f"Max DD {m}M"),False)
    st.dataframe(perf,width="stretch",height=165)

    st.markdown('<div class="v2-section">Trend, highs & risk</div>',unsafe_allow_html=True)
    items=[("50 EMA",_pct(row.get("% 50 EMA")),"distance from EMA"),("52W High",_money(row.get("52W High")),str(row.get("52W High Date","") or "")),("From 52W High",_pct(row.get("% High")),"distance"),("ATH",_money(row.get("ATH")),str(row.get("ATH Date","") or "")),("From ATH",_pct(row.get("% ATH")),"distance"),("6M Persistence",_pct(row.get("Persistence"),False),"positive sessions"),("ATR",_money(row.get("ATR")),f"{_num(row.get('ATR %')):.1f}% of price" if _num(row.get("ATR %")) is not None else ""),("Stop Loss",_money(row.get("Stop Loss")),"2 × ATR"),("Chandelier Exit",_money(row.get("Chand Exit")),"3 × ATR"),("12M Max Drawdown",_pct(row.get("Max DD 12M"),False),"worst observed"),("Volume",str(row.get("Volume","—")),"volume status")]
    for i in range(0,len(items),3):
        cs=st.columns(3)
        for col,(label,value,sub) in zip(cs,items[i:i+3]):
            with col: _card(label,value,sub)

    st.markdown('<div class="v2-section">Metadata & data quality</div>',unsafe_allow_html=True)
    meta={k:row.get(k) for k in ["Market Cap (Cr)","Industry","Indices","Short History","FFill %","Data Gap"] if k in row.index}
    st.dataframe(pd.DataFrame([meta]),hide_index=True,width="stretch",height=90)
    st.caption("This build intentionally excludes unsupported fundamentals, news, analyst ratings, shareholding, peer models, and generic RS scores.")
