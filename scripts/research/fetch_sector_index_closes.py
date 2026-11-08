"""Fetch ~3 years of closes for NSE's sector indices and the Nifty 500 from
Screener's index charts (scratch, for the RRG comparison with StockCharts)."""
import sys
import time

import pandas as pd
import requests

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from src.loaders.screener_loader import ScreenerBlocked, fetch_series, resolve_id  # noqa: E402

OUT = sys.argv[1]
IDS = {"NIFTY500": "1272615", "NIFTY50": None, "BANK": "1272670", "IT": "1272649", "PHARMA": "1272672",
       "AUTO": "1272796", "FMCG": "1272711", "METAL": "1272797", "REALTY": "1272692", "MEDIA": "1272799",
       "PSUBANK": "1272693", "FINSERV": "1272803", "PSE": "1272714", "SERVICES": "1272770",
       "ENERGY": "1272671", "INFRA": "1272689", "MIDCAP100": "1272674"}

time.sleep(90)  # Screener answered 429 to the id scan; let it rest first
s = requests.Session()
IDS["NIFTY50"] = resolve_id("NIFTY", s)
time.sleep(3)
for days in (400, 1100):
    frames = {}
    for name, cid in IDS.items():
        r = None
        for _ in range(3):
            try:
                r = fetch_series(cid, s, days=days)
                break
            except ScreenerBlocked:
                time.sleep(45)
        if not r:
            print(days, name, "no data", flush=True)
            continue
        c = r[0].sort_index()
        frames[name] = c
        gap = c.index.to_series().diff().dt.days.median()
        print(f"{days} {name:10} {cid} {c.index[0].date()}..{c.index[-1].date()} n={len(c)} gap={gap:.0f}d", flush=True)
        time.sleep(3)
    pd.DataFrame(frames).to_parquet(f"{OUT}/sector_closes_{days}d.parquet")
print("done", flush=True)
