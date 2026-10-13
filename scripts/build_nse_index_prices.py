"""Build durable daily OHLC history for the five NSE research indices.

NSE Indices' own historical data first; Screener's index chart (fixed index
ids, close only) when that fails. There is no Yahoo fallback any more (TODO
S10, 13 Oct 2026).
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.loaders.screener_loader import fetch_series, resolve_id

INDEX_NAMES = {
    "nifty50": "NIFTY 50",
    "nifty_next50": "NIFTY NEXT 50",
    "nifty_midcap150": "NIFTY MIDCAP 150",
    "nifty_smallcap250": "NIFTY SMALLCAP 250",
    "nifty_microcap250": "NIFTY MICROCAP 250",
}

URL = "https://www.niftyindices.com/Backpage.aspx/getHistoricaldatatabletoString"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://www.niftyindices.com/reports/historical-data",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/json; charset=UTF-8",
}


def _number(value):
    if value is None or str(value).strip() in {"", "-", "NA", "null"}:
        return None
    return float(str(value).replace(",", "").strip())


def _fetch_official(name: str, start: date, end: date) -> pd.DataFrame:
    import requests

    inner = "{'name':'%s','startDate':'%s','endDate':'%s','indexName':'%s'}" % (
        name, start.strftime("%d-%b-%Y"), end.strftime("%d-%b-%Y"), name
    )
    response = requests.post(URL, json={"cinfo": inner}, headers=HEADERS, timeout=45)
    response.raise_for_status()
    raw = response.json().get("d", "[]")
    rows = json.loads(raw) if isinstance(raw, str) else raw
    out = []
    for row in rows:
        dt = pd.to_datetime(row.get("HistoricalDate"), dayfirst=True, errors="coerce")
        if pd.isna(dt):
            continue
        out.append({
            "date": dt.normalize(),
            "open": _number(row.get("OPEN")),
            "high": _number(row.get("HIGH")),
            "low": _number(row.get("LOW")),
            "close": _number(row.get("CLOSE")),
        })
    if not out:
        raise RuntimeError(f"empty official Nifty response for {name}")
    return pd.DataFrame(out)


def _fetch_screener(name_key: str, name: str, start: date, end: date) -> pd.DataFrame:
    slugs = {
        "nifty50": "NIFTY",
        "nifty_next50": "id/1272613",
        "nifty_midcap150": "NMIDCAP150",
        "nifty_smallcap250": "SMALLCA250",
        "nifty_microcap250": "NFMICRO250",
    }
    import requests
    session = requests.Session()
    cid = resolve_id(slugs[name_key], session)
    if not cid:
        raise RuntimeError(f"Screener could not resolve index {name}")
    got = fetch_series(cid, session, days=3650)
    if got is None:
        raise RuntimeError(f"Screener returned no history for {name}")
    close, _ = got
    frame = pd.DataFrame({"date": close.index, "close": close.values})
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame = frame[(frame["date"].dt.date >= start) & (frame["date"].dt.date <= end)]
    if frame.empty:
        raise RuntimeError(f"Screener history outside requested range for {name}")
    frame["open"] = pd.NA
    frame["high"] = pd.NA
    frame["low"] = pd.NA
    frame["index"] = name_key
    frame["source"] = "Screener index chart (NSE index)"
    return frame[["date", "open", "high", "low", "close", "index", "source"]]

def build(output: Path, start: date, end: date) -> dict:
    parts = []
    for key, name in INDEX_NAMES.items():
        try:
            frame = _fetch_official(name, start, end)
            source = "NSE Indices historical data"
        except Exception as official_error:
            frame = _fetch_screener(key, name, start, end)
            source = "Screener index chart (NSE index)"
            print(f"INDEX_SOURCE_FALLBACK index={name} official={type(official_error).__name__}")
        frame["index"] = key
        frame["source"] = source
        frame["evidence_date"] = pd.Timestamp(end)
        frame = frame.drop_duplicates(["index", "date"], keep="last")
        if frame["close"].isna().any():
            raise RuntimeError(f"{name}: null close values")
        parts.append(frame[["date", "index", "open", "high", "low", "close", "source", "evidence_date"]])
    result = pd.concat(parts, ignore_index=True).sort_values(["index", "date"])
    assert set(result["index"]) == set(INDEX_NAMES)
    assert result[["index", "date"]].duplicated().sum() == 0
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output, index=False)
    print({
        "rows": len(result),
        "indices": int(result["index"].nunique()),
        "first_date": str(result["date"].min().date()),
        "last_date": str(result["date"].max().date()),
        "sources": result["source"].value_counts().to_dict(),
    })
    return {"rows": len(result), "indices": int(result["index"].nunique())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", type=date.fromisoformat, default=date.today() - timedelta(days=3650))
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    build(args.output, args.start, args.end)
