from __future__ import annotations

from pathlib import Path
from math import sqrt
import numpy as np
import pandas as pd
import requests
import yfinance as yf

NSE_URL = "https://niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv"
OUT = Path("research/outputs")
LOOKBACKS = {"1M":21,"3M":63,"6M":126,"9M":189,"12M":252}
WEIGHTS = {"1M":.10,"3M":.30,"6M":.30,"9M":.20,"12M":.10}
EQUAL = {k:.20 for k in LOOKBACKS}

def universe():
    r=requests.get(NSE_URL,headers={"User-Agent":"Mozilla/5.0"},timeout=30); r.raise_for_status()
    d=pd.read_csv(pd.io.common.BytesIO(r.content)); c=next(c for c in d.columns if str(c).strip().lower() in {"symbol","ticker"})
    return sorted(x for x in d[c].astype(str).str.strip().str.upper() if x and x!="NAN")

def download(symbols):
    out=[]; ts=[s+".NS" for s in symbols]
    for i in range(0,len(ts),100):
        x=yf.download(ts[i:i+100],period="10y",auto_adjust=False,progress=False,group_by="ticker",threads=True)
        if x is None or x.empty: continue
        if isinstance(x.columns,pd.MultiIndex):
            lev=x.columns.get_level_values(-1); p=x.xs("Adj Close" if "Adj Close" in lev else "Close",level=-1,axis=1); p.columns=[str(c).replace('.NS','').upper() for c in p.columns]
        else: p=x[["Adj Close" if "Adj Close" in x.columns else "Close"]].copy(); p.columns=[ts[i].replace('.NS','').upper()]
        out.append(p)
    p=pd.concat(out,axis=1); p=p.loc[:,~p.columns.duplicated()].sort_index(); p.index=pd.to_datetime(p.index).tz_localize(None); return p.dropna(axis=1,how="all")

def z(s):
    s=s.replace([np.inf,-np.inf],np.nan); m=s.dropna()
    if len(m)<20 or m.std(ddof=1)==0:return pd.Series(np.nan,index=s.index)
    lo,hi=m.mean()-3*m.std(ddof=1),m.mean()+3*m.std(ddof=1); w=m.clip(lo,hi)
    return ((s-w.mean())/(w.std(ddof=1)+1e-12)).clip(-3,3)

def factor(prices,end,n):
    p=prices.iloc[end-n:end+1]; r=p.pct_change(fill_method=None).iloc[1:]; lr=np.log(p/p.shift(1)).iloc[1:]
    simple=p.iloc[-1]/p.iloc[0]-1; logr=np.log(p.iloc[-1]/p.iloc[0]); sd=lr.std(ddof=1)
    ram_log=logr/(sd*np.sqrt(len(lr))); ram_simple=simple/(sd*np.sqrt(len(lr))); sharpe=r.mean()/r.std(ddof=1)*sqrt(252)
    t=np.arange(len(p),dtype=float); lp=np.log(p.clip(lower=.01)); r2=lp.corrwith(pd.Series(t,index=lp.index))**2
    pos=(r>0).sum()/r.notna().sum().replace(0,np.nan); neg=(r<0).sum()/r.notna().sum().replace(0,np.nan); fip=np.sign(logr)*(pos-neg)
    return dict(simple=simple,log=logr,ram_simple=ram_simple,ram_log=ram_log,sharpe_ann=sharpe,ram_r2=ram_log*r2,ram_fip=ram_log*fip)

def composite(fs,key,weights): return sum(z(fs[h][key]).fillna(0)*w for h,w in weights.items())

def ram_skip_month(prices,end):
    # True 12M-1M: 12-month formation return ending ~1 month before signal date,
    # then risk-adjust using the same 12M-minus-last-month daily return window.
    p=prices.iloc[end-252:end-21+1]
    lr=np.log(p/p.shift(1)).iloc[1:]; logr=np.log(p.iloc[-1]/p.iloc[0]); sd=lr.std(ddof=1)
    return logr/(sd*np.sqrt(len(lr)))

def raw_skip_month(prices,end): return prices.iloc[end-21]/prices.iloc[end-252]-1

def future_return(prices,end,months):
    step={1:21,3:63,6:126,12:252}[months]
    if end+step>=len(prices): return pd.Series(np.nan,index=prices.columns)
    return prices.iloc[end+step]/prices.iloc[end]-1

def main():
    OUT.mkdir(parents=True,exist_ok=True); prices=download(universe())
    ends=[prices.index.get_loc(d) for _,x in prices.groupby(prices.index.to_period('M')) for d in [x.index[-1]]]
    ends=[e for e in ends if e>=260 and e+252<len(prices)]; records=[]
    for end in ends:
        fs={h:factor(prices,end,n) for h,n in LOOKBACKS.items()}
        models={
          'simple_return':composite(fs,'simple',EQUAL),'log_return':composite(fs,'log',EQUAL),
          'RAM_simple':composite(fs,'ram_simple',EQUAL),'RAM_log':composite(fs,'ram_log',EQUAL),
          'Sharpe_annual':composite(fs,'sharpe_ann',EQUAL),'RAM_x_R2':composite(fs,'ram_r2',EQUAL),
          'RAM_x_FIP':composite(fs,'ram_fip',EQUAL),
          'RAM_log_default_10_30_30_20_10':composite(fs,'ram_log',WEIGHTS),
          'RAM_x_R2_default_10_30_30_20_10':composite(fs,'ram_r2',WEIGHTS),
          'Raw_12M_minus_1M':z(raw_skip_month(prices,end)),
          'RAM_12M_minus_1M':z(ram_skip_month(prices,end)),
        }
        for model,score in models.items():
            rec={'model':model,'date':prices.index[end]}
            for h in (1,3,6,12):
                f=future_return(prices,end,h).reindex(score.index); v=score.notna()&f.notna()
                if v.sum()<30: rec.update({f'ic_{h}':np.nan,f'top_{h}':np.nan,f'bot_{h}':np.nan}); continue
                rec[f'ic_{h}']=score[v].corr(f[v],method='spearman'); q=score[v].rank(pct=True)
                rec[f'top_{h}']=f[v][q>=.9].mean(); rec[f'bot_{h}']=f[v][q<=.1].mean()
            records.append(rec)
    d=pd.DataFrame(records); rows=[]
    for model,g in d.groupby('model'):
        o={'model':model,'snapshots':len(g)}
        for h in (1,3,6,12):
            o[f'rank_ic_{h}m']=g[f'ic_{h}'].mean(); o[f'positive_ic_{h}m']=(g[f'ic_{h}']>0).mean(); o[f'top_{h}m_avg']=g[f'top_{h}'].mean(); o[f'spread_{h}m_avg']=(g[f'top_{h}']-g[f'bot_{h}']).mean()
        rows.append(o)
    s=pd.DataFrame(rows).sort_values('rank_ic_6m',ascending=False); s.to_csv(OUT/'v1_hypothesis_summary.csv',index=False); d.to_csv(OUT/'v1_hypothesis_detail.csv',index=False); print(s.to_string(index=False))

if __name__=='__main__': main()
