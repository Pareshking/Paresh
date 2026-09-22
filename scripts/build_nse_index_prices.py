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

import requests
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
NSE_FALLBACK_URL = "https://www.nseindia.com/api/historical/indicesHistory"
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


def _fetch_range(session, index_name: str, start: date, end: date):
    payload = {
        "cinfo": json.dumps(
            {
                "name": index_name,
                "startDate": start.strftime("%d-%b-%Y"),
                "endDate": end.strftime("%d-%b-%Y"),
                "indexName": index_name,
            }
        )
    }
    headers = {
        **HEADERS,
        "Content-Type": "application/json; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.niftyindices.com",
        "Referer": "https://www.niftyindices.com/reports/historical-data",
    }
    for attempt in range(4):
        try:
            response = session.post(URL, json=payload, headers=headers, timeout=60)
            if response.status_code == 200:
                body = response.json()
                raw = body.get("d", "[]")
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

