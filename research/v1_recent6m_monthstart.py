from pathlib import Path
from math import sqrt
import numpy as np, pandas as pd, requests, yfinance as yf
NSE_URL='https://niftyindices.com/IndexConstituent/ind_niftytotalmarket_list.csv'; OUT=Path('research/outputs'); LOOK={"1M":21,"3M":63,"6M":126,"9M":189,"12M":252}; W={"1M":.10,"3M":.30,"6M":.30,"9M":.20,"12M":.10}; E={k:.2 for k in LOOK}
def universe():
 r=requests.get(NSE_URL,headers={'User-Agent':'Mozilla/5.0'},timeout=30); r.raise_for_status(); d=pd.read_csv(pd.io.common.BytesIO(r.content)); c=next(c for c in d if str(c).strip().lower() in {'symbol','ticker'}); return sorted(x for x in d[c].astype(str).str.strip().str.upper() if x!='NAN')
def download(syms):
 out=[]; ts=[s+'.NS' for s in syms]
 for i in range(0,len(ts),100):
  x=yf.download(ts[i:i+100],period='10y',auto_adjust=False,progress=False,group_by='ticker',threads=True)
  if x is None or x.empty: continue
  if isinstance(x.columns,pd.MultiIndex):
   lev=x.columns.get_level_values(-1); p=x.xs('Adj Close' if 'Adj Close' in lev else 'Close',level=-1,axis=1); p.columns=[str(c).replace('.NS','').upper() for c in p]
  else: p=x[[('Adj Close' if 'Adj Close' in x.columns else 'Close')]].copy(); p.columns=[ts[i].replace('.NS','').upper()]
  out.append(p)
 p=pd.concat(out,axis=1); p=p.loc[:,~p.columns.duplicated()].sort_index(); p.index=pd.to_datetime(p.index).tz_localize(None); return p.dropna(axis=1,how='all')
def z(s):
 m=s.replace([np.inf,-np.inf],np.nan).dropna()
 if len(m)<20 or m.std(ddof=1)==0:return pd.Series(np.nan,index=s.index)
 w=m.clip(m.mean()-3*m.std(ddof=1),m.mean()+3*m.std(ddof=1)); return ((s-w.mean())/(w.std(ddof=1)+1e-12)).clip(-3,3)
def factor(pr,e,n):
 p=pr.iloc[e-n:e+1]; r=p.pct_change(fill_method=None).iloc[1:]; lr=np.log(p/p.shift(1)).iloc[1:]; sd=lr.std(ddof=1); logr=np.log(p.iloc[-1]/p.iloc[0]); simple=p.iloc[-1]/p.iloc[0]-1; sharpe=r.mean()/r.std(ddof=1)*sqrt(252); t=np.arange(len(p),dtype=float); r2=np.log(p.clip(lower=.01)).corrwith(pd.Series(t,index=p.index))**2; pos=(r>0).sum()/r.notna().sum().replace(0,np.nan); neg=(r<0).sum()/r.notna().sum().replace(0,np.nan); ram=logr/(sd*np.sqrt(len(lr))); return {'simple':simple,'log':logr,'ram':ram,'sharpe':sharpe,'r2':ram*r2,'fip':ram*np.sign(logr)*(pos-neg)}
def comp(fs,k,w): return sum(z(fs[h][k]).fillna(0)*v for h,v in w.items())
def future(pr,e,m):
 n={1:21,3:63,6:126}[m]
 return pr.iloc[e+n]/pr.iloc[e]-1 if e+n<len(pr) else pd.Series(np.nan,index=pr.columns)
def main():
 OUT.mkdir(parents=True,exist_ok=True); pr=download(universe()); last=pr.index.max(); start=last-pd.DateOffset(months=6)
 # Month-start snapshots: first available trading day of each calendar month within the last 6 calendar months.
 ends=[]
 for _,g in pr.loc[pr.index>=start].groupby(pr.loc[pr.index>=start].index.to_period('M')): ends.append(pr.index.get_loc(g.index[0]))
 ends=[e for e in ends if e>=260 and e+126<len(pr)]; rows=[]
 for e in ends:
  fs={h:factor(pr,e,n) for h,n in LOOK.items()}; models={k:comp(fs,k,E) for k in ['simple','log','ram','sharpe','r2','fip']}; models['RAM_log_default']=comp(fs,'ram',W)
  for name,score in models.items():
   r={'model':name,'date':pr.index[e]}
   for m in (1,3,6):
    f=future(pr,e,m).reindex(score.index); v=score.notna()&f.notna(); r[f'ic_{m}']=score[v].corr(f[v],method='spearman') if v.sum()>=30 else np.nan; q=score[v].rank(pct=True); r[f'top_{m}']=f[v][q>=.9].mean() if v.sum()>=30 else np.nan; r[f'bot_{m}']=f[v][q<=.1].mean() if v.sum()>=30 else np.nan
   rows.append(r)
 d=pd.DataFrame(rows); s=[]
 for model,g in d.groupby('model'):
  o={'model':model,'snapshots':len(g)}
  for m in (1,3,6): o[f'rank_ic_{m}m']=g[f'ic_{m}'].mean(); o[f'positive_ic_{m}m']=(g[f'ic_{m}']>0).mean(); o[f'top_{m}m_avg']=g[f'top_{m}'].mean(); o[f'spread_{m}m_avg']=(g[f'top_{m}']-g[f'bot_{m}']).mean()
  s.append(o)
 s=pd.DataFrame(s).sort_values('rank_ic_6m',ascending=False); s.to_csv(OUT/'v1_recent6m_monthstart_summary.csv',index=False); d.to_csv(OUT/'v1_recent6m_monthstart_detail.csv',index=False); print('SNAPSHOTS',sorted(str(pr.index[e].date()) for e in ends)); print(s.to_string(index=False))
if __name__=='__main__': main()
