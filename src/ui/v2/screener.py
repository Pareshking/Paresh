"""PARESH QUANT v2 screener."""
from __future__ import annotations
import html
import pandas as pd
import streamlit as st


def _num(v):
    try:
        if v is None or pd.isna(v): return None
        return float(v)
    except (TypeError, ValueError): return None


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
    return str(v).strip().lower() in {"true","yes","1","y","✓","🟢"}


def _daily_changes(close, symbols):
    if close is None or close.empty: return pd.Series(index=symbols.index, dtype=float)
    out = {}
    for sym in symbols:
        try:
            s = pd.to_numeric(close[sym], errors="coerce").dropna()
            out[sym] = ((s.iloc[-1] / s.iloc[-2]) - 1) * 100 if len(s) >= 2 else None
        except Exception: out[sym] = None
    return symbols.map(out)


def _enrich(df, close):
    out = df.copy()
    out["Score Percentile"] = out["Score"].rank(pct=True, method="average") * 100 if "Score" in out else float("nan")
    out["1D Change"] = _daily_changes(close, out["Symbol"])
    def state(row):
        s=[]
        if _bool(row.get("Above 50 EMA")): s.append("Above EMA")
        if _bool(row.get("Near 52W High")): s.append("Near 52W")
        if _bool(row.get("At ATH")): s.append("ATH")
        if str(row.get("Volume","")).lower() in {"high","surge"}: s.append("High Volume")
        return " · ".join(s) if s else "—"
    out["State"] = out.apply(state, axis=1)
    return out


def _card(row, i):
    sym = str(row.get("Symbol","—")); industry = str(row.get("Industry","") or "")
    rank = _num(row.get("Rank")); pctile = _num(row.get("Score Percentile")) or 0
    badges=[]
    if _bool(row.get("Above 50 EMA")): badges.append("ABOVE 50 EMA")
    if _bool(row.get("Near 52W High")): badges.append("NEAR 52W HIGH")
    if _bool(row.get("At ATH")): badges.append("ATH")
    if str(row.get("Volume","")).lower() in {"high","surge"}: badges.append("HIGH VOLUME")
    bh=''.join(f'<span class="v2-badge v2-badge-good">{html.escape(x)}</span>' for x in badges) or '<span class="v2-badge">No special state</span>'
    vals=[("1M",_ret(row.get("1M Return"))), ("3M",_ret(row.get("3M Return"))), ("6M",_ret(row.get("6M Return"))), ("12M",_ret(row.get("12M Return"))), ("52W High",_pct(row.get("% High"))), ("50 EMA",_pct(row.get("% 50 EMA"))), ("3M Sharpe",f"{_num(row.get('3M Sharpe')):.2f}" if _num(row.get("3M Sharpe")) is not None else "—"), ("12M DD",_pct(row.get("Max DD 12M"),False))]
    mh=''.join(f'<div class="v2-metric"><div class="v2-metric-label">{a}</div><div class="v2-metric-value">{b}</div></div>' for a,b in vals)
    d=_num(row.get("1D Change")); dc="v2-delta-pos" if (d or 0)>=0 else "v2-delta-neg"
    st.html(f'<div class="v2-stock-card"><div class="v2-stock-top"><div><div class="v2-rank">RANK #{int(rank) if rank is not None else "—"}</div><div class="v2-symbol">{html.escape(sym)}</div><div class="v2-industry">{html.escape(industry)}</div></div><div><div class="v2-price">{_money(row.get("CMP"))}</div><div class="{dc}">{_pct(d)}</div></div></div><div class="v2-badges">{bh}</div><div class="v2-score"><div class="v2-score-track"><div class="v2-score-fill" style="width:{max(0,min(100,pctile)):.1f}%"></div></div><div class="v2-score-text">{pctile:.0f}th percentile</div></div><div class="v2-metrics">{mh}</div></div>')
    if st.button(f"Open {sym}", key=f"v2_card_{i}_{sym}"):
        st.session_state["v2_selected_symbol"]=sym; st.session_state["v2_page"]="Stock Detail"; st.rerun()


def render(data: dict):
    df=_enrich(data["rank_df"],data["close_prices"]); total=len(df)
    st.markdown('<div class="v2-brand"><div class="v2-mark">PQ</div><div><div class="v2-brand-name">PARESH QUANT</div><div class="v2-brand-sub">NSE Momentum Terminal · v2 verification build</div></div></div>',unsafe_allow_html=True)
    st.markdown('<div class="v2-page-title">Screener</div><div class="v2-page-sub">Find the strongest momentum stocks, compare the evidence, and drill into risk without leaving the ranking surface.</div>',unsafe_allow_html=True)
    regime=getattr(data.get("regime"),"status",None) or "—"
    ema=int(df["Above 50 EMA"].map(_bool).sum()); near=int(df["Near 52W High"].map(_bool).sum()); top50=int((pd.to_numeric(df["Rank"],errors="coerce")<=50).sum()); hv=int(df["Volume"].astype(str).str.lower().isin(["high","surge"]).sum()); breadth=ema/total*100 if total else 0
    st.markdown(f'<div class="v2-strip"><div class="v2-strip-item"><div class="v2-strip-label">Regime</div><div class="v2-strip-value">{html.escape(str(regime))}</div></div><div class="v2-strip-item"><div class="v2-strip-label">Universe</div><div class="v2-strip-value">{total:,}</div></div><div class="v2-strip-item"><div class="v2-strip-label">Above 50 EMA</div><div class="v2-strip-value">{ema:,} · {breadth:.0f}%</div></div><div class="v2-strip-item"><div class="v2-strip-label">Near 52W High</div><div class="v2-strip-value">{near:,}</div></div><div class="v2-strip-item"><div class="v2-strip-label">Top 50</div><div class="v2-strip-value">{top50:,}</div></div><div class="v2-strip-item"><div class="v2-strip-label">High Volume</div><div class="v2-strip-value">{hv:,}</div></div></div>',unsafe_allow_html=True)
    q=st.text_input("Search",placeholder="Search symbol or industry…",label_visibility="collapsed",key="v2_search")
    preset=st.pills("Universe",["All Stocks","Top 50","Qualified","Above 50 EMA","Near 52W High","High Volume"],default="All Stocks",key="v2_preset")
    f=df.copy()
    if q:
        m=f["Symbol"].astype(str).str.contains(q,case=False,na=False)
        if "Industry" in f: m=m|f["Industry"].astype(str).str.contains(q,case=False,na=False)
        f=f[m]
    if preset=="Top 50": f=f[pd.to_numeric(f["Rank"],errors="coerce")<=50]
    elif preset=="Qualified" and "Qualified" in f: f=f[f["Qualified"].map(_bool)]
    elif preset=="Above 50 EMA": f=f[f["Above 50 EMA"].map(_bool)]
    elif preset=="Near 52W High": f=f[f["Near 52W High"].map(_bool)]
    elif preset=="High Volume": f=f[f["Volume"].astype(str).str.lower().isin(["high","surge"])]
    c1,c2,c3=st.columns([1.5,1,1])
    with c1: sort=st.selectbox("Sort",["Rank","Score","3M Return","12M Return","3M Sharpe","% High"],label_visibility="collapsed",key="v2_sort")
    with c2: view=st.segmented_control("View",["Table","Cards"],default="Table",key="v2_view",label_visibility="collapsed")
    with c3: n=st.selectbox("Rows",[25,50,100],label_visibility="collapsed",key="v2_rows")
    f=f.sort_values(sort,ascending=(sort=="Rank"),na_position="last"); shown=f.head(n)
    st.markdown(f'<div class="v2-section">{len(f):,} matching stocks <span class="v2-muted">· select a row to open Stock Detail</span></div>',unsafe_allow_html=True)
    if shown.empty: st.info("No stocks match the current filters."); return
    if view=="Cards":
        a,b=st.columns(2)
        for i,(_,r) in enumerate(shown.iterrows()):
            with (a if i%2==0 else b): _card(r,i)
        return
    cols=["Rank","Symbol","Industry","CMP","1D Change","Score","Score Percentile","Rank Δ 1M","Rank Δ 3M","1M Return","3M Return","6M Return","12M Return","3M Sharpe","12M Sharpe","% High","% 50 EMA","Volume","State"]
    cols=[c for c in cols if c in shown.columns]; table=shown[cols].copy()
    for c in ["1M Return","3M Return","6M Return","12M Return"]: table[c]=pd.to_numeric(table[c],errors="coerce")*100
    cfg={"Rank":st.column_config.NumberColumn("Rank",format="%d",width="small",pinned=True),"Symbol":st.column_config.TextColumn("Stock",width="medium",pinned=True),"Industry":st.column_config.TextColumn("Industry",width="medium"),"CMP":st.column_config.NumberColumn("Price",format="₹ %.2f"),"1D Change":st.column_config.NumberColumn("1D",format="%+.2f%%"),"Score":st.column_config.NumberColumn("Score",format="%.2f"),"Score Percentile":st.column_config.ProgressColumn("Percentile",format="%.0f",min_value=0,max_value=100),"Rank Δ 1M":st.column_config.NumberColumn("Δ 1M",format="%+d"),"Rank Δ 3M":st.column_config.NumberColumn("Δ 3M",format="%+d"),"1M Return":st.column_config.NumberColumn("1M",format="%+.1f%%"),"3M Return":st.column_config.NumberColumn("3M",format="%+.1f%%"),"6M Return":st.column_config.NumberColumn("6M",format="%+.1f%%"),"12M Return":st.column_config.NumberColumn("12M",format="%+.1f%%"),"3M Sharpe":st.column_config.NumberColumn("3M Sharpe",format="%.2f"),"12M Sharpe":st.column_config.NumberColumn("12M Sharpe",format="%.2f"),"% High":st.column_config.NumberColumn("vs 52W High",format="%+.1f%%"),"% 50 EMA":st.column_config.NumberColumn("vs 50 EMA",format="%+.1f%%"),"Volume":st.column_config.TextColumn("Volume"),"State":st.column_config.TextColumn("State",width="large")}
    ev=st.dataframe(table,column_config=cfg,hide_index=True,width="stretch",height=560,row_height=34,on_select="rerun",selection_mode="single-row",key="v2_screener_table")
    if ev.selection.rows:
        st.session_state["v2_selected_symbol"]=str(shown.iloc[ev.selection.rows[0]]["Symbol"]); st.session_state["v2_page"]="Stock Detail"; st.rerun()
    st.caption("Quantitative fields come from the existing engine. Percentile and 1D change are transparent presentation-level derivations.")
