"""Refresh data/nse_fo_symbols.json: the stocks NSE currently trades in F&O.

Why it matters: the corporate-actions detector reads a one-day move beyond
+/-35% as a split, bonus or demerger because NSE circuit limits (20% at most)
make it impossible as a price move -- but F&O stocks have no circuit limit.
For them a move that matches no split/bonus ratio is treated as real until
Screener restates the history (src/engine/corporate_actions.needs_confirmation).

Source: NSE's market-lot file, one row per F&O underlying (index rows dropped).
A short or unreadable download leaves the committed list untouched.

    python scripts/sync_fo_symbols.py
"""

from __future__ import annotations

import csv
import io
import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

URL = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"
OUT = Path(__file__).resolve().parents[1] / "data" / "nse_fo_symbols.json"
MIN_SYMBOLS = 100  # NSE lists ~200 stock underlyings; fewer means a bad download
INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50"}


def parse(text: str) -> list[str]:
    """Stock symbols from the market-lot CSV, header and index rows dropped."""
    out = set()
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2:
            continue
        symbol = row[1].strip().upper()
        if not symbol or symbol == "SYMBOL" or symbol in INDEX_SYMBOLS:
            continue
        out.add(symbol)
    return sorted(out)


def main() -> int:
    symbols: list[str] = []
    for attempt in range(1, 4):  # nsearchives answers intermittently
        try:
            resp = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            resp.raise_for_status()
            symbols = parse(resp.text)
            break
        except requests.RequestException as exc:
            print(f"attempt {attempt}: {type(exc).__name__}")
            time.sleep(5 * attempt)
    else:
        print(f"::warning::F&O list not refreshed; keeping {OUT.name}.")
        return 0
    if len(symbols) < MIN_SYMBOLS:
        print(f"::warning::F&O list has only {len(symbols)} symbols; keeping {OUT.name}.")
        return 0
    OUT.write_text(json.dumps({"as_of": date.today().isoformat(), "source": URL,
                               "symbols": symbols}, indent=1) + "\n", encoding="utf-8")
    print(f"F&O symbols: {len(symbols)} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
