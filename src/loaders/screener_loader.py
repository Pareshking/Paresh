"""Daily closes and volume from screener.in, accumulated into our own history.

WHY THIS EXISTS. Yahoo publishes an Indian session over a day and a half and
sometimes never finishes: 2026-09-17 sat at 378 of 750 symbols for more than
two days and did not move. Screener had every one of the missing names the
morning after. Checked against Yahoo on sessions both carry, they agree to the
paisa -- ABB 6980.00, AAVAS 1282.50, 3MINDIA 31935.00 on 2026-09-16.

WHAT IT CANNOT DO, stated up front because the caller has to plan around it:

  * CLOSE AND VOLUME ONLY. The API serves Price, DMA50, DMA200 and Volume;
    Price-High-Low, High-Low and OHLC all 404. There is no intraday high here
    and no way to derive one. A 52-week high computed from this source is a
    high of CLOSES, which is a different quantity -- on the live universe it
    moves the "within 5% of the 52-week high" gate from 22 names to 50.

  * ONE YEAR OF DAILY. Beyond roughly a year the series is downsampled to
    weekly (248 points at days=365, but only 522 across ten years and 1121
    across twenty). Asking for more than the daily window buys nothing. Depth
    comes from accumulating, which is why this file merges rather than replaces.

  * A DIFFERENT ADJUSTMENT BASIS FROM YAHOO. Screener carries corporate-action
    adjustments back through the history; yfinance does not adjust demergers at
    all. HEG spans its 2026-09-07 event at 266.60 -> 272.20 here and
    728.25 -> 272.20 there. Never merge the two frames. See SCREENER_PRICES_FILE.

BEING A GOOD CLIENT. One request per symbol per night with a pause between
them, so the whole universe generates less traffic than one person browsing the
site. A 429 or a 403 is treated as the site saying stop: the run aborts and
keeps what it already has, rather than retrying into a block.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Iterable, Sequence

import pandas as pd
import requests

from src.core import startup_metrics as metrics
from src.core.config import (
    SCREENER_DAYS,
    SCREENER_DELAY_S,
    SCREENER_IDS_FILE,
    SCREENER_PRICES_FILE,
)
from src.core.logger import logger

BASE = "https://www.screener.in"
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
_ID_RE = re.compile(r"/api/company/(\d+)/")


class ScreenerBlocked(RuntimeError):
    """The site asked us to stop. Never retried into."""


# ── The symbol -> company id map ─────────────────────────────────────────────
#
# Resolved once per symbol and committed, because it is stable and because
# re-deriving it would double every night's request count for no new
# information. A random sample of 30 NSE symbols resolved 30/30.


def load_ids(path: str | None = None) -> dict[str, str]:
    target = path or SCREENER_IDS_FILE
    if not os.path.exists(target):
        return {}
    try:
        with open(target, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (ValueError, OSError):
        logger.warning("Screener id map unreadable; every symbol will be re-resolved.")
        return {}
    ids = payload.get("ids") if isinstance(payload, dict) else None
    return {str(k): str(v) for k, v in ids.items()} if isinstance(ids, dict) else {}


def save_ids(ids: dict[str, str], path: str | None = None) -> None:
    target = path or SCREENER_IDS_FILE
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"source": f"{BASE}/company/<symbol>/", "ids": dict(sorted(ids.items()))},
                  fh, indent=1)
        fh.write("\n")
    os.replace(tmp, target)


def resolve_id(symbol: str, session: requests.Session) -> str | None:
    """The company id behind an NSE symbol, or None if the page has no id.

    None means "screener does not know this symbol", which is ordinary for a
    freshly listed name and must not stop the run.
    """
    resp = session.get(f"{BASE}/company/{symbol}/", headers=HTTP_HEADERS, timeout=25)
    if resp.status_code in (403, 429):
        raise ScreenerBlocked(f"HTTP {resp.status_code} on /company/{symbol}/")
    if resp.status_code != 200:
        return None
    found = _ID_RE.search(resp.text)
    return found.group(1) if found else None


# ── One symbol's series ──────────────────────────────────────────────────────


def fetch_series(
    company_id: str, session: requests.Session, days: int = SCREENER_DAYS
) -> tuple[pd.Series, pd.Series] | None:
    """(close, volume) indexed by date, or None when the chart has no price."""
    url = f"{BASE}/api/company/{company_id}/chart/?q=Price-DMA50-Volume&days={days}"
    resp = session.get(url, headers=HTTP_HEADERS, timeout=25)
    if resp.status_code in (403, 429):
        raise ScreenerBlocked(f"HTTP {resp.status_code} on chart {company_id}")
    if resp.status_code != 200:
        return None
    try:
        payload = resp.json()
    except ValueError:
        return None

    frames: dict[str, pd.Series] = {}
    for dataset in payload.get("datasets", []):
        metric = str(dataset.get("metric", "")).lower()
        if metric not in ("price", "volume"):
            continue
        pairs = [(v[0], v[1]) for v in dataset.get("values", []) if len(v) >= 2]
        if not pairs:
            continue
        idx = pd.to_datetime([p[0] for p in pairs], errors="coerce")
        vals = pd.to_numeric([p[1] for p in pairs], errors="coerce")
        s = pd.Series(vals, index=idx, dtype="float64")
        frames[metric] = s[~s.index.isna()]

    if "price" not in frames:
        return None
    close = frames["price"]
    volume = frames.get("volume", pd.Series(dtype="float64").reindex(close.index))
    return close, volume.reindex(close.index)


# ── The whole universe ───────────────────────────────────────────────────────


def fetch_universe(
    symbols: Sequence[str],
    days: int = SCREENER_DAYS,
    delay_s: float = SCREENER_DELAY_S,
    ids: dict[str, str] | None = None,
    session: requests.Session | None = None,
) -> tuple[pd.DataFrame, dict[str, str], list[str]]:
    """Close and volume for every symbol screener knows.

    Returns (frame, id map, symbols it could not serve). The frame has a
    two-level column index (symbol, field) with fields 'Close' and 'Volume', so
    it is shaped like the Yahoo frame WITHOUT pretending to carry its missing
    fields -- a caller asking for 'High' gets a KeyError here rather than a
    close wearing a high's name.

    A block aborts the walk and returns what was already collected. A partial
    night is worth keeping; hammering a site that just said no is not.
    """
    sess = session or requests.Session()
    known = dict(ids or load_ids())
    closes: dict[str, pd.Series] = {}
    volumes: dict[str, pd.Series] = {}
    unresolved: list[str] = []
    blocked = False

    for i, sym in enumerate(symbols):
        try:
            cid = known.get(sym)
            if not cid:
                cid = resolve_id(sym, sess)
                if cid:
                    known[sym] = cid
                    time.sleep(delay_s)
                else:
                    unresolved.append(sym)
                    time.sleep(delay_s)
                    continue
            got = fetch_series(cid, sess, days=days)
            if got is None:
                unresolved.append(sym)
            else:
                closes[sym], volumes[sym] = got
        except ScreenerBlocked as exc:
            # Stop, and say how far we got. Silence here would look identical
            # to "screener has no data for the rest of the universe".
            logger.warning(
                "screener.in asked us to stop after %d/%d symbols (%s); keeping "
                "what we have and leaving the rest for the next run.",
                i, len(symbols), exc,
            )
            metrics.note("screener_blocked_after", i)
            blocked = True
            break
        except requests.RequestException as exc:
            unresolved.append(sym)
            logger.debug("screener %s: %s", sym, type(exc).__name__)
        time.sleep(delay_s)

    metrics.note("screener_symbols_fetched", len(closes))
    metrics.note("screener_symbols_unresolved", len(unresolved))
    metrics.note("screener_run_complete", "no" if blocked else "yes")

    if not closes:
        return pd.DataFrame(), known, unresolved

    frame = pd.concat(
        {sym: pd.DataFrame({"Close": closes[sym], "Volume": volumes[sym]})
         for sym in closes},
        axis=1,
    )
    frame.index = pd.DatetimeIndex(frame.index).normalize()
    frame = frame[~frame.index.duplicated(keep="last")].sort_index()
    return frame, known, unresolved


# ── Accumulation: the whole point ────────────────────────────────────────────


def merge_into_store(
    fresh: pd.DataFrame, path: str | None = None
) -> tuple[pd.DataFrame, int, int]:
    """Fold tonight's year into the stored history. Returns (frame, new rows, repaired cells).

    CELL level, not row level. A symbol screener could not serve tonight must
    not blank the value it served last night, and a row present in both must
    keep every cell either one has. The Yahoo cache lost 572 closes across 337
    symbols to exactly this mistake, by taking whole vendor rows on a duplicated
    date.

    Nothing here ever shortens the stored history. That is what makes a rolling
    one-year window accumulate into an archive instead of sliding along.
    """
    target = path or SCREENER_PRICES_FILE
    if fresh is None or fresh.empty:
        return (pd.read_parquet(target) if os.path.exists(target) else pd.DataFrame()), 0, 0

    previous = None
    if os.path.exists(target):
        try:
            previous = pd.read_parquet(target)
        except Exception as exc:
            logger.warning("Screener store unreadable (%s); starting fresh.", type(exc).__name__)

    if previous is None or previous.empty:
        merged, new_rows, repaired = fresh, len(fresh), 0
    else:
        before_cells = int(previous.notna().sum().sum())
        merged = fresh.combine_first(previous)
        merged = merged.sort_index()
        new_rows = len(merged.index.difference(previous.index))
        # Cells the store had and tonight's response did not, which survived.
        #
        # Reindexed onto the MERGED columns first. A symbol screener skipped
        # entirely is absent from `fresh` as a column, not present-and-NaN, so
        # comparing the two frames as they arrive counts it as nothing -- which
        # under-reports precisely the case this number exists to report.
        overlap = previous.index.intersection(fresh.index)
        if len(overlap):
            f = fresh.reindex(index=overlap, columns=merged.columns)
            pv = previous.reindex(index=overlap, columns=merged.columns)
            repaired = int((f.isna() & pv.notna()).to_numpy().sum())
        else:
            repaired = 0
        after_cells = int(merged.notna().sum().sum())
        if after_cells < before_cells:
            logger.warning(
                "Screener store shrank (%d -> %d cells); refusing to write.",
                before_cells, after_cells,
            )
            metrics.note("screener_store_refused", 1)
            return previous, 0, 0

    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    merged.to_parquet(target, compression="zstd")
    metrics.note("screener_store_rows", len(merged))
    metrics.note("screener_store_new_rows", int(new_rows))
    metrics.note("screener_cells_preserved", int(repaired))
    return merged, int(new_rows), int(repaired)


def load_store(path: str | None = None) -> pd.DataFrame:
    target = path or SCREENER_PRICES_FILE
    if not os.path.exists(target):
        return pd.DataFrame()
    try:
        return pd.read_parquet(target)
    except Exception as exc:
        logger.warning("Screener store unreadable (%s).", type(exc).__name__)
        return pd.DataFrame()


def closes(frame: pd.DataFrame) -> pd.DataFrame:
    """Just the closes, symbol-per-column."""
    if frame is None or frame.empty:
        return pd.DataFrame()
    return frame.xs("Close", axis=1, level=-1)


def volumes(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    return frame.xs("Volume", axis=1, level=-1)
