"""Acquire official NSE historical OHLC for the five research indices.

This is an independent index-price archive. It does not alter System-1 ranking
prices or the Yahoo/Screener stock-price paths.
"""

from __future__ import annotations

import argparse
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

INDEX_NAMES = {
    "nifty50": "NIFTY 50",
    "nifty_next50": "NIFTY NEXT 50",
    "nifty_midcap150": "NIFTY MIDCAP 150",
    "nifty_smallcap250": "NIFTY SMALLCAP 250",
    "nifty_microcap250": "NIFTY MICROCAP 250",
}

URL = "https://www.nseindia.com/api/historical/indicesHistory"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}


def _number(value):
    if value is None or str(value).strip() in {"", "-", "NA", "null"}:
        return None
    return float(str(value).replace(",", "").strip())


def _records(payload):
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    if isinstance(data, dict):
        for key in (
            "indexCloseOnlineRecords",
            "indexCloseOnlineRecords",
            "records",
            "data",
        ):
            if isinstance(data.get(key), list):
                return data[key]
    return data if isinstance(data, list) else []


def _field(row, *names):
    for name in names:
        if name in row:
            return row[name]
    return None


def _fetch_range(session: requests.Session, index_name: str, start: date, end: date):
    params = {
        "indexType": index_name,
        "from": start.strftime("%d-%m-%Y"),
        "to": end.strftime("%d-%m-%Y"),
    }
    for attempt in range(4):
        response = session.get(URL, params=params, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            payload = response.json()
            rows = []
            for row in _records(payload):
                raw_date = _field(row, "TIMESTAMP", "INDEX_DATE", "DATE", "indexDate")
                if raw_date is None:
                    continue
                parsed = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")
                if pd.isna(parsed):
                    continue
                rows.append(
                    {
                        "date": parsed.normalize(),
                        "open": _number(_field(row, "EOD_OPEN_INDEX_VAL", "OPEN_INDEX_VAL", "OPEN")),
                        "high": _number(_field(row, "EOD_HIGH_INDEX_VAL", "HIGH_INDEX_VAL", "HIGH")),
                        "low": _number(_field(row, "EOD_LOW_INDEX_VAL", "LOW_INDEX_VAL", "LOW")),
                        "close": _number(_field(row, "EOD_CLOSE_INDEX_VAL", "CLOSE_INDEX_VAL", "CLOSE")),
                    }
                )
            return rows
        if response.status_code in {401, 403, 429, 500, 502, 503, 504}:
            time.sleep(2 ** attempt)
            session.get("https://www.nseindia.com/", headers=HEADERS, timeout=30)
            continue
        response.raise_for_status()
    raise RuntimeError(f"NSE index request failed after retries: {index_name} {start}..{end}")


def build(output: Path, start: date, end: date) -> dict:
    session = requests.Session()
    session.headers.update(HEADERS)
    session.get("https://www.nseindia.com/", headers=HEADERS, timeout=30)

    parts = []
    for key, name in INDEX_NAMES.items():
        rows = []
        cursor = start
        while cursor <= end:
            chunk_end = min(end, cursor + timedelta(days=364))
            rows.extend(_fetch_range(session, name, cursor, chunk_end))
            cursor = chunk_end + timedelta(days=1)
            time.sleep(1.0)
        frame = pd.DataFrame(rows)
        if frame.empty:
            raise RuntimeError(f"NSE returned no history for {name}")
        frame["index"] = key
        frame["source"] = "NSE historical indices API"
        frame["evidence_date"] = pd.Timestamp(end)
        frame = frame.drop_duplicates(["index", "date"], keep="last")
        required = ["date", "index", "open", "high", "low", "close", "source", "evidence_date"]
        frame = frame[required].sort_values("date")
        if frame["close"].isna().any():
            raise RuntimeError(f"{name}: null close values in NSE history")
        parts.append(frame)

    result = pd.concat(parts, ignore_index=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output, index=False)
    summary = {
        "rows": len(result),
        "indices": int(result["index"].nunique()),
        "first_date": str(result["date"].min().date()),
        "last_date": str(result["date"].max().date()),
    }
    print(summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", type=date.fromisoformat, default=date.today() - timedelta(days=3650))
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    build(args.output, args.start, args.end)


if __name__ == "__main__":
    main()
