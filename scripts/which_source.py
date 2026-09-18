"""What is live right now: which history ranked it, how complete, how old.

The served page deliberately does not name a data vendor, which also means the
OPERATOR cannot read it off the screen. This is the other channel. It reads the
published artifacts the way production reads them and reports what they say.

Run it from anywhere:  python scripts/which_source.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd  # noqa: E402
import requests  # noqa: E402

from src.core.config import (  # noqa: E402
    MOMENTUM_MONTHS,
    PRICE_SNAPSHOT_URL,
    RANKING_PRICE_SOURCE,
    RANKINGS_SNAPSHOT_URL,
    SCREENER_STORE_URL,
)

META_KEY = b"umiya_ranking_contract"
INTRADAY_COLS = ("ATR", "ATR %", "Stop Loss", "Chandelier Exit")


def _get(url: str, dest: str) -> bool:
    try:
        r = requests.get(url, timeout=60, stream=True)
        if r.status_code != 200:
            print(f"   HTTP {r.status_code}")
            return False
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(1 << 18):
                fh.write(chunk)
        return True
    except Exception as exc:
        print(f"   {type(exc).__name__}: {exc}")
        return False


def _coverage(frame: pd.DataFrame, level_name="Close") -> pd.Series | None:
    try:
        c = frame.xs(level_name, axis=1, level=-1)
    except Exception:
        c = frame
    if c.empty:
        return None
    return c.notna().sum(axis=1) / float(c.shape[1])


def main() -> int:
    tmp = os.environ.get("TMPDIR", "/tmp")
    print(f"configured preference : {RANKING_PRICE_SOURCE}\n")

    # ── What actually ranked the live table ─────────────────────────────────
    print("PUBLISHED RANKING")
    rank_path = os.path.join(tmp, "_which_rank.parquet")
    if _get(RANKINGS_SNAPSHOT_URL, rank_path):
        import pyarrow.parquet as pq

        rank = pd.read_parquet(rank_path)
        meta = pq.read_table(rank_path).schema.metadata or {}
        terms = json.loads(meta[META_KEY].decode()) if META_KEY in meta else {}
        src = terms.get("price_source") or "(not recorded — predates the field)"
        print(f"   ranked from      : {src}")
        print(f"   as of            : {terms.get('price_as_of', '?')}")
        print(f"   rows             : {len(rank)}")
        has_atr = [c for c in INTRADAY_COLS if c in rank.columns]
        print(f"   ATR columns      : {'present' if has_atr else 'absent'}"
              f"  -> 52-week high measured on "
              f"{'intraday highs' if has_atr else 'CLOSING PRICES'}")
        print(f"   pipeline version : {terms.get('pipeline_version', '?')}")

    # ── The two histories, side by side ─────────────────────────────────────
    for label, url, dest in (
        ("SCREENER STORE", SCREENER_STORE_URL, "_which_scr.parquet"),
        ("YAHOO SNAPSHOT", PRICE_SNAPSHOT_URL, "_which_yah.parquet"),
    ):
        print(f"\n{label}")
        path = os.path.join(tmp, dest)
        if not _get(url, path):
            continue
        frame = pd.read_parquet(path)
        cov = _coverage(frame)
        if cov is None:
            print("   unreadable")
            continue
        idx = pd.DatetimeIndex(cov.index)
        print(f"   range            : {idx[0].date()} -> {idx[-1].date()} "
              f"({len(idx)} sessions)")
        want = max(MOMENTUM_MONTHS)
        target = idx[-1] - pd.DateOffset(months=want)
        ok = target >= idx[0]
        print(f"   {want}M lookback     : {'OK' if ok else 'TOO SHORT'} "
              f"(needs {target.date()}, has from {idx[0].date()})")
        print("   last 5 sessions  :")
        for d in idx[-5:]:
            print(f"      {d.date()}  {cov.loc[d] * 100:5.1f}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
