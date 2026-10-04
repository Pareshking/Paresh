#!/usr/bin/env python3
"""Isolated 2010 PIT monthly rankings; refuses absent/insufficient membership or prices."""
import argparse, json
from pathlib import Path
from urllib.request import Request, urlopen
import numpy as np
import pandas as pd

def load_url(url, path):
    if not url.startswith("https://"): raise ValueError("Input URL must use HTTPS")
    with urlopen(Request(url, headers={"User-Agent":"Paresh-PIT-audit/1.0"}), timeout=90) as r:
        b=r.read(100_000_001)
    if len(b)>100_000_000: raise ValueError("Input over 100 MB")
    path.write_bytes(b)

def load_membership(path):
    x=json.loads(path.read_text())
    if "indices" in x:
        matches=[v for k,v in x["indices"].items() if k.lower().replace("-","_") in ("nifty_500","nifty500")]
        if not matches: raise ValueError("Membership JSON has no Nifty 500 history; refusing to substitute another index")
        x=matches[0]
    if not x.get("baseline",{}).get("symbols"): raise ValueError("Expected baseline.date, baseline.symbols and dated changes")
    return x

def members_on(h, day):
    base=pd.Timestamp(h["baseline"]["date"])
    if day.normalize()<base.normalize(): raise ValueError(f"No PIT membership for {day.date()}; baseline begins {base.date()}")
    s=set(str(z).strip().upper() for z in h["baseline"]["symbols"])
    for e in sorted(h.get("changes",[]), key=lambda z:z["date"]):
        if pd.Timestamp(e["date"])>day: break
        s.difference_update(str(z).strip().upper() for z in e.get("removed",[]))
        s.update(str(z).strip().upper() for z in e.get("added",[]))
    return s

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--prices",required=True); ap.add_argument("--membership",required=True)
    ap.add_argument("--out",default="output"); ap.add_argument("--tradebook",default="")
    a=ap.parse_args(); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    h=load_membership(Path(a.membership)); px=pd.read_parquet(a.prices)
    if not isinstance(px.index,pd.DatetimeIndex):
        d=next((c for c in ("date","Date","session") if c in px.columns),None)
        if not d: raise ValueError("Prices must be wide Parquet with date index or date column")
        px[d]=pd.to_datetime(px[d]); px=px.set_index(d)
    px.index=pd.to_datetime(px.index).tz_localize(None).normalize(); px=px.sort_index()
    px=px.loc[~px.index.duplicated(keep="last")]; px.columns=[str(c).strip().upper() for c in px.columns]
    px=px.apply(pd.to_numeric,errors="coerce")
    trades=pd.read_csv(a.tradebook) if a.tradebook else pd.DataFrame()
    if len(trades):
        if not {"Stock Name","Entry Date"}.issubset(trades.columns): raise ValueError("Tradebook CSV needs Stock Name and Entry Date")
        trades["Entry Date"]=pd.to_datetime(trades["Entry Date"],errors="coerce")
        trades=trades[trades["Entry Date"].dt.year.eq(2010)].copy()
    rankings=[]; summaries=[]; reconc=[]
    for m in pd.period_range("2010-01","2010-12",freq="M"):
        month_dates=px.index[px.index.to_period("M")==m]
        if not len(month_dates): summaries.append({"month":str(m),"status":"no_price_sessions"}); continue
        first=month_dates[0]; prior=px.index[px.index<first]
        if not len(prior): raise ValueError(f"No prior session for {m}")
        dt=prior[-1]; hist=px.loc[:dt]
        if len(hist)<253: raise ValueError(f"Need 253 close rows for 12M ROC; only {len(hist)} through {dt.date()}")
        mem=members_on(h,dt); now=hist.iloc[-1]; old=hist.iloc[-253]
        vol=hist.pct_change(fill_method=None).iloc[-252:].std(ddof=1)*np.sqrt(252)
        rows=[]
        for sym in sorted(mem):
            if sym not in px.columns: rows.append((sym,np.nan,np.nan,np.nan,"symbol_missing_from_price_file")); continue
            p0,p1,v=old.get(sym,np.nan),now.get(sym,np.nan),vol.get(sym,np.nan)
            if not (pd.notna(p0) and pd.notna(p1) and p0>0 and p1>0 and pd.notna(v) and v>0):
                rows.append((sym,np.nan,np.nan,np.nan,"insufficient_or_invalid_history")); continue
            roc=float(p1/p0-1); rows.append((sym,roc,float(v),float(roc/v),"eligible"))
        sc=pd.DataFrame(rows,columns=["symbol","roc_12m","annualized_volatility","score","price_status"])
        elig=sc[sc.score.notna()].sort_values(["score","symbol"],ascending=[False,True]).copy()
        elig["rank"]=np.arange(1,len(elig)+1)
        sc=sc.merge(elig[["symbol","rank"]],on="symbol",how="left")
        sc.insert(0,"month",str(m)); sc.insert(1,"decision_date",dt.date().isoformat())
        for n in (20,25,30): sc[f"in_top{n}"]=sc["rank"].le(n)
        rankings.append(sc)
        tm=trades[trades["Entry Date"].dt.to_period("M").eq(m)] if len(trades) else trades
        idx=sc.set_index("symbol")
        ranklist=[]
        for _,tr in tm.iterrows():
            sym=str(tr["Stock Name"]).strip().upper()
            rr=idx.loc[sym] if sym in idx.index else None
            if isinstance(rr,pd.DataFrame): rr=rr.iloc[0]
            rank=int(rr["rank"]) if rr is not None and pd.notna(rr["rank"]) else np.nan
            ranklist.append(rank)
            reconc.append({"month":str(m),"decision_date":dt.date().isoformat(),"entry_date":tr["Entry Date"].date().isoformat(),"tradebook_symbol":sym,
                "rank":rank,"score":rr["score"] if rr is not None else np.nan,"roc_12m":rr["roc_12m"] if rr is not None else np.nan,
                "annualized_volatility":rr["annualized_volatility"] if rr is not None else np.nan,
                "top20":bool(pd.notna(rank) and rank<=20),"top25":bool(pd.notna(rank) and rank<=25),"top30":bool(pd.notna(rank) and rank<=30),
                "membership_price_status":rr["price_status"] if rr is not None else "not_in_pit_membership"})
        valid=[r for r in ranklist if pd.notna(r)]
        summaries.append({"month":str(m),"decision_date":dt.date().isoformat(),"pit_members":len(mem),"eligible_ranked":int(sc["rank"].notna().sum()),
            "tradebook_entries":len(tm),"tradebook_in_top20":sum(r<=20 for r in valid),"tradebook_in_top25":sum(r<=25 for r in valid),
            "tradebook_in_top30":sum(r<=30 for r in valid),"tradebook_missing_rank":len(tm)-len(valid),"status":"ranked_and_reconciled" if a.tradebook else "ranked_only"})
    if not rankings: raise ValueError("No rankings generated")
    allr=pd.concat(rankings,ignore_index=True).sort_values(["month","rank","symbol"],na_position="last")
    allr.to_csv(out/"2010_monthly_top30_and_coverage.csv",index=False)
    pd.DataFrame(summaries).to_csv(out/"2010_monthly_audit_summary.csv",index=False)
    if a.tradebook: pd.DataFrame(reconc).to_csv(out/"2010_tradebook_rank_reconciliation.csv",index=False)
    report={"year":2010,"score":"(close[t]/close[t-252]-1)/(sample_std(last_252_daily_simple_returns)*sqrt(252))",
      "decision_convention":"prior available session before each month's first price session; no same-day close look-ahead",
      "membership_baseline_date":h["baseline"]["date"],"price_first_session":px.index.min().date().isoformat(),
      "price_last_session":px.index.max().date().isoformat(),"months_ranked":len(rankings),
      "tradebook_provided":bool(a.tradebook),"tradebook_rows_2010":len(trades),
      "limitations":["Membership evidence is supplied by the user and not independently authenticated here.","Price adjustments and ticker lineage require separate audit.","Tradebook symbols are matched literally; alias reconciliation is not automatic."]}
    (out/"validation_report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=="__main__": main()
