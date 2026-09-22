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
import json

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO
import requests
try:
    from curl_cffi import requests as curl_requests
except ImportError:
    curl_requests = None
try:
    from curl_cffi import requests as curl_requests
except ImportError:
    curl_requests = None

INDEX_NAMES = {
    "nifty50": "NIFTY 50",
    "nifty_next50": "NIFTY NEXT 50",
    "nifty_midcap150": "NIFTY MIDCAP 150",
    "nifty_smallcap250": "NIFTY SMALLCAP 250",
    "nifty_microcap250": "NIFTY MICROCAP 250",
}

URL = "https://www.niftyindices.com/Backpage.aspx/getHistoricaldatatabletoString"
NSE_FALLBACK_URL = "https://www.niftyindices.com/Backpage.aspx/getHistoricaldatatabletoString"
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


def _fetch_archive_day(day: date) -> list[dict]:
    url = f"https://nsearchives.nseindia.com/content/indices/ind_close_all_{day:%d%m%Y}.csv"
    headers = {
        "User-Agent": HEADERS["User-Agent"],
        "Accept": "text/csv,*/*",
        "Referer": "https://www.nseindia.com/",
    }
    response = requests.get(url, headers=headers, timeout=30)
    if response.status_code != 200 or not response.content.strip():
        return []
    frame = pd.read_csv(StringIO(response.text))
    frame.columns = [str(x).strip() for x in frame.columns]
    name_col = next((x for x in ("Index Name", "Index Name ") if x in frame.columns), None)
    if name_col is None:
        return []
    wanted = set(INDEX_NAMES.values())
    rows = []
    for _, row in frame.iterrows():
        name = str(row[name_col]).strip()
        if name not in wanted:
            continue
        rows.append(
            {
                "date": pd.Timestamp(day),
                "index_name": name,
                "open": _number(row.get("Open")),
                "high": _number(row.get("High")),
                "low": _number(row.get("Low")),
                "close": _number(row.get("Close")),
            }
        )
    return rows


def _fetch_archive_range(start: date, end: date) -> list[dict]:
    days = pd.date_range(start, end, freq="B").date
    rows = []
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = {pool.submit(_fetch_archive_day, day): day for day in days}
        for future in as_completed(futures):
            try:
                rows.extend(future.result())
            except requests.RequestException:
                continue
    return rows

def _fetch_range(session, index_name: str, start: date, end: date):
    inner = (
        "{'name':'" + index_name +
        "','startDate':'" + start.strftime("%d-%b-%Y") +
        "','endDate':'" + end.strftime("%d-%b-%Y") +
        "','indexName':'" + index_name + "'}"
    )
    payload = {"cinfo": inner}
    headers = {
        **HEADERS,
        "Content-Type": "application/json; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.niftyindices.com",
        "Referer": "https://www.niftyindices.com/reports/historical-data",
    }
    for attempt in range(4):
        try:
            response = session.post(URL, data=json.dumps(payload), headers=headers, timeout=60)
            if response.status_code == 200:
                body = response.json()
                raw = body.get("d", "[]")
                if not raw:
                    time.sleep(2 ** attempt)
                    continue
                rows_raw = json.loads(raw) if isinstance(raw, str) else raw
                rows = []
                for row in rows_raw:
                    raw_date = row.get("HistoricalDate")
                    parsed = pd.to_datetime(raw_date, dayfirst=True, errors="coerce")
                    if pd.isna(parsed):
                        continue
                    rows.append(
                        {
                            "date": parsed.normalize(),
                            "open": _number(row.get("OPEN")),
                            "high": _number(row.get("HIGH")),
                            "low": _number(row.get("LOW")),
                            "close": _number(row.get("CLOSE")),
                        }
                    )
                if rows:
                    return rows
        except (ValueError, json.JSONDecodeError, requests.RequestException):
            pass
        time.sleep(2 ** attempt)
    raise RuntimeError(f"Nifty Indices historical request failed: {index_name} {start}..{end}")


def build(output: Path, start: date, end: date) -> dict:
    rows = _fetch_archive_range(start, end)
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise RuntimeError("NSE daily index archive returned no rows")

    frame["index"] = frame["index_name"].map(
        {name: key for key, name in INDEX_NAMES.items()}
    )
    frame = frame.dropna(subset=["index"])
    frame["source"] = "NSE daily index archive"
    frame["evidence_date"] = pd.Timestamp(end)
    frame = frame.drop_duplicates(["index", "date"], keep="last")
    frame = frame[
        ["date", "index", "open", "high", "low", "close", "source", "evidence_date"]
    ].sort_values(["index", "date"])
    expected = set(INDEX_NAMES)
    actual = set(frame["index"])
    missing = expected - actual
    if missing:
        raise RuntimeError(f"NSE index archive missing indices: {sorted(missing)}")
    if frame["close"].isna().any():
        raise RuntimeError("NSE index archive contains null close values")
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(output, index=False)
    summary = {
        "rows": len(frame),
        "indices": int(frame["index"].nunique()),
        "first_date": str(frame["date"].min().date()),
        "last_date": str(frame["date"].max().date()),
    }
    print(summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--start",
        type=date.fromisoformat,
        default=date.today() - timedelta(days=3650),
    )
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    build(args.output, args.start, args.end)


if __name__ == "__main__":
    main()
