"""Give every ranked stock a TradingView sector.

Owner, 2026-09-27: fill in the Nano Cap stocks with no sector. Sources, in
order:

  1. TradingView's own screener (one batched request) -- the taxonomy the
     app groups Nano Cap and Combined by, so its answer needs no mapping.
  2. Screener.in's company page, whose classification is NSE's (Broad
     Sector / Sector / Industry). Its Sector is mapped to the closest
     TradingView sector (SCREENER_TO_TV) so the app never shows two
     taxonomies side by side; its Industry is kept as the industry name.
  3. Value Research Online was asked for too, but its site answers scripts
     with a Cloudflare challenge (403, cf-mitigated: challenge), so it cannot
     be read automatically; a stock neither source knows stays Unclassified.

Targets: the Nano Cap list's Unclassified rows, and any row of
data/nse_tv_classification.csv whose sector is not a TradingView sector
(the reconcile fallback once wrote NSE's names there). Writes the
classification file and the Nano Cap list's Industry column.

    python scripts/classify_missing.py            # update the files
    python scripts/classify_missing.py --dry-run  # report only
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.core.config import TV_CLASSIFICATION_FILE  # noqa: E402
from src.engine.extra_universe import UNCLASSIFIED  # noqa: E402
from src.loaders.extra_universe_loader import LIST_PATH  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (compatible; umiya-classify/1.0)"}
TV_SCAN = "https://scanner.tradingview.com/india/scan"
SCREENER_PAGE = "https://www.screener.in/company/{}/"

# TradingView's 20 sectors.
TV_SECTORS = frozenset({
    "Commercial Services", "Communications", "Consumer Durables",
    "Consumer Non-Durables", "Consumer Services", "Distribution Services",
    "Electronic Technology", "Energy Minerals", "Finance", "Health Services",
    "Health Technology", "Industrial Services", "Miscellaneous",
    "Non-Energy Minerals", "Process Industries", "Producer Manufacturing",
    "Retail Trade", "Technology Services", "Transportation", "Utilities",
})

# NSE's sector (as Screener.in shows it) -> the closest TradingView sector.
SCREENER_TO_TV = {
    "Automobile and Auto Components": "Consumer Durables",
    "Capital Goods": "Producer Manufacturing",
    "Chemicals": "Process Industries",
    "Construction": "Industrial Services",
    "Construction Materials": "Non-Energy Minerals",
    "Consumer Durables": "Consumer Durables",
    "Consumer Services": "Consumer Services",
    "Diversified": "Miscellaneous",
    "Fast Moving Consumer Goods": "Consumer Non-Durables",
    "Financial Services": "Finance",
    "Forest Materials": "Process Industries",
    "Healthcare": "Health Technology",
    "Information Technology": "Technology Services",
    "Media Entertainment & Publication": "Consumer Services",
    "Metals & Mining": "Non-Energy Minerals",
    "Oil Gas & Consumable Fuels": "Energy Minerals",
    "Power": "Utilities",
    "Realty": "Finance",
    "Services": "Commercial Services",
    "Telecommunication": "Communications",
    "Textiles": "Process Industries",
}

_SCREENER_FIELD = re.compile(
    r'title="(Broad Sector|Sector|Broad Industry|Industry)"[^>]*>\s*([^<]+?)\s*<')


def from_tradingview(symbols: list[str], post=requests.post) -> dict[str, tuple[str, str]]:
    """{symbol: (sector, industry)} for the symbols TradingView knows."""
    if not symbols:
        return {}
    # TradingView writes NSE's hyphen as an underscore (BAJAJ-AUTO -> BAJAJ_AUTO).
    tv_name = {s.replace("-", "_"): s for s in symbols}
    body = {"symbols": {"tickers": [f"NSE:{t}" for t in tv_name], "query": {"types": []}},
            "columns": ["name", "sector", "industry"]}
    resp = post(TV_SCAN, json=body, timeout=30, headers=UA)
    resp.raise_for_status()
    out = {}
    for row in resp.json().get("data") or []:
        sym = tv_name.get(str(row.get("s", "")).split(":")[-1])
        _name, sector, industry = (row.get("d") or [None, None, None])[:3]
        if sym and sector in TV_SECTORS:
            out[sym] = (sector, industry or sector)
    return out


def parse_screener(html: str) -> tuple[str, str] | None:
    """(TradingView sector, industry) from a Screener.in company page."""
    fields = dict(_SCREENER_FIELD.findall(html))
    tv = SCREENER_TO_TV.get((fields.get("Sector") or "").strip())
    if not tv:
        return None
    return tv, (fields.get("Industry") or fields.get("Broad Industry") or tv).strip()


def from_screener(symbols: list[str], get=requests.get, pause=1.0) -> dict[str, tuple[str, str]]:
    out = {}
    for sym in symbols:
        try:
            resp = get(SCREENER_PAGE.format(sym), timeout=30, headers=UA)
            got = parse_screener(resp.text) if resp.status_code == 200 else None
        except requests.RequestException:
            got = None
        if got:
            out[sym] = got
        time.sleep(pause)
    return out


def targets(classification: pd.DataFrame, nano: pd.DataFrame) -> list[str]:
    unclassified = nano.loc[nano["Industry"].eq(UNCLASSIFIED), "Symbol"].tolist()
    foreign = classification.loc[~classification["TV_Sector"].isin(TV_SECTORS), "Symbol"].tolist()
    return sorted(set(unclassified) | set(foreign))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cls = pd.read_csv(TV_CLASSIFICATION_FILE)
    cls["Symbol"] = cls["Symbol"].astype(str).str.strip().str.upper()
    nano = pd.read_csv(LIST_PATH) if os.path.exists(LIST_PATH) else pd.DataFrame(columns=["Symbol", "Industry"])
    todo = targets(cls, nano)
    print(f"To classify: {len(todo)}")
    found = from_tradingview(todo)
    rest = [s for s in todo if s not in found]
    print(f"TradingView: {len(found)}; asking Screener.in for {len(rest)}")
    screener = from_screener(rest)
    found.update(screener)
    missing = [s for s in todo if s not in found]
    for sym in todo:
        src = "tradingview" if sym in found and sym not in screener else ("screener" if sym in screener else "none")
        print(f"  {sym:<12} {src:<11} {found.get(sym, (UNCLASSIFIED, ''))[0]}")
    print(f"Classified {len(found)} of {len(todo)}; still unclassified: {', '.join(missing) or 'none'}")
    if args.dry_run or not found:
        return 0

    new = pd.DataFrame([{"Symbol": s, "TV_Sector": sec, "TV_Industry": ind}
                        for s, (sec, ind) in found.items()])
    cls = pd.concat([cls[~cls["Symbol"].isin(found)], new], ignore_index=True)
    cls.sort_values("Symbol").to_csv(TV_CLASSIFICATION_FILE, index=False)
    if not nano.empty:
        nano["Industry"] = [found[s][0] if s in found else ind
                            for s, ind in zip(nano["Symbol"], nano["Industry"])]
        nano.to_csv(LIST_PATH, index=False)
    print(f"Wrote {TV_CLASSIFICATION_FILE} and {LIST_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
