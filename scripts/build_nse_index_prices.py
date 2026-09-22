"""Acquire historical OHLC-style index series for the five research indices.

NSE's public daily archive and interactive historical endpoint are not reachable
from the GitHub Actions runner reliably. Screener exposes the same NSE index
series through its chart API; this archive therefore records the source as
Screener and never pretends it is a direct NSE feed.
"""

from __future__ import annotations

import argparse
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

INDEX_SLUGS = {
    "nifty50": "NIFTY",
    "nifty_next50": "id/1272613",
    "nifty_midcap150": "NMIDCAP150",
    "nifty_smallcap250": "SMALLCA250",
    "nifty_microcap250": "NFMICRO250",
}

DEEP_DAYS = 3650


def build(output: Path, start: date, end: date) -> dict:
    import requests

    session = requests.Session()
    parts = []
    for key, name in INDEX_NAMES.items():
        cid = resolve_id(INDEX_SLUGS[key], session)
        if not cid:
            raise RuntimeError(f"Screener could not resolve index {name}")
        got = fetch_series(cid, session, days=DEEP_DAYS)
        if got is None:
            raise RuntimeError(f"Screener returned no history for {name}")
        close, volume = got
        frame = pd.DataFrame({"close": close, "volume": volume})
        frame.index = pd.DatetimeIndex(frame.index).normalize()
        frame = frame[(frame.index.date >= start) & (frame.index.date <= end)]
        frame = frame.reset_index(names="date")
        frame["index"] = key
        frame["open"] = frame["close"]
        frame["high"] = frame["close"]
        frame["low"] = frame["close"]
        frame["source"] = "Screener index chart (NSE index)"
        frame["evidence_date"] = pd.Timestamp(end)
        parts.append(frame[["date","index","open","high","low","close","source","evidence_date"]])

    result = pd.concat(parts, ignore_index=True).drop_duplicates(["index","date"])
    result = result.sort_values(["index","date"])
    if set(result["index"]) != set(INDEX_NAMES):
        raise RuntimeError("Screener index archive is missing one or more research indices")
    if result["close"].isna().any():
        raise RuntimeError("Screener index archive contains null closes")
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output, index=False)
    summary = {
        "rows": len(result),
        "indices": int(result["index"].nunique()),
        "first_date": str(result["date"].min().date()),
        "last_date": str(result["date"].max().date()),
        "source": "Screener index chart (NSE index)",
    }
    print(summary)
    return summary


def _number(value):
    if value is None or str(value).strip() in {"", "-", "NA", "null"}:
        return None
    return float(str(value).replace(",", "").strip())


def _records(payload):
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    return data if isinstance(data, list) else []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", type=date.fromisoformat, default=date.today() - timedelta(days=3650))
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    build(args.output, args.start, args.end)


if __name__ == "__main__":
    main()
