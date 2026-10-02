"""Daily OHLCV from SS, kept in a compact long-format store.

Owner, 2026-10-02: SS replaces Yahoo as the OHLCV source. Its chart
endpoint serves daily open, high, low, close and volume back to listing,
1,000 sessions a page, on Screener's basis -- splits and bonuses adjusted,
dividends not. Measured on 2026-10-02: RELIANCE identical to Screener's
closes for two years, TDPOWERSYS's 1:2 split (ex 2026-08-24) already
adjusted, every price a whole paisa.

The store, one zstd Parquet file per calendar year, sorted by (symbol, date):

    date     date32
    symbol   dictionary-encoded string
    open, high, low, close   int32 paise (exact; up to ~Rs 2.1 crore)
    volume   int64

Raw and adjusted are the same series here: the provider restates the whole
history when an action lands. So a stock whose stored history no longer
agrees with a fresh page is re-downloaded whole (needs_full_refresh), and so
is one whose latest session moved more than JUMP_LIMIT -- a split the
provider has not restated yet, or a genuine circuit move; refetching either
costs one stock's pages.

The endpoint's address comes from the SS_BASE_URL environment variable (a
repository secret in CI), so the public repository never names the source.

Pure functions plus fetch(); scripts/sync_ss.py does the I/O.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

BASE_URL_ENV = "SS_BASE_URL"  # the source's chart endpoint; kept out of the public repo
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; umiya-ohlcv/1.0)",
           "Accept": "application/json"}
PAGE_ROWS = 1000
DELAY_S = 2.5            # between requests; the owner's 2-3 seconds
RESTATE_TOLERANCE = 0.005  # a stored close off by more than 0.5% means restated history
JUMP_LIMIT = 0.20          # the owner's rule: a >20% session triggers a full refresh
INDEX_SYMBOLS = {"CNX500": "Nifty 500", "NIFTY": "Nifty 50"}
PRICE_COLUMNS = ["open", "high", "low", "close"]
COLUMNS = ["date", "symbol", *PRICE_COLUMNS, "volume"]

SCHEMA = pa.schema([
    ("date", pa.date32()),
    ("symbol", pa.dictionary(pa.int32(), pa.string())),
    ("open", pa.int32()),
    ("high", pa.int32()),
    ("low", pa.int32()),
    ("close", pa.int32()),
    ("volume", pa.int64()),
])


def base_url() -> str:
    """The endpoint, from the environment (a repository secret in CI)."""
    url = os.getenv(BASE_URL_ENV, "").strip().rstrip("/")
    if not url.startswith("https://"):
        raise SSError(f"{BASE_URL_ENV} is not set to an https:// URL")
    return url


class SSError(RuntimeError):
    """The endpoint answered with something that is not usable price history."""


class SSBlocked(SSError):
    """HTTP 403/429: stop the run rather than hammer the host."""

    retry_after: float | None = None


def _retry_after(headers) -> float | None:
    """Seconds a 429 asks us to wait, when it says (capped at five minutes)."""
    try:
        return min(float(headers.get("Retry-After")), 300.0)
    except (TypeError, ValueError):
        return None


# ── Fetching ─────────────────────────────────────────────────────────────────

def fetch_page(symbol: str, before: str | None = None, *,
               session: requests.Session | None = None, timeout: float = 30.0) -> dict:
    """One page (up to 1,000 sessions, newest first in time) for NSE:<symbol>."""
    params = {"tf": "1D"}
    if before:
        params["before"] = before
    get = (session or requests).get
    resp = get(f"{base_url()}/NSE:{symbol}", params=params, headers=HEADERS, timeout=timeout)
    if resp.status_code in (403, 429):
        exc = SSBlocked(f"HTTP {resp.status_code} for {symbol}")
        exc.retry_after = _retry_after(getattr(resp, "headers", {}) or {})
        raise exc
    if resp.status_code != 200:
        raise SSError(f"HTTP {resp.status_code} for {symbol}")
    try:
        payload = resp.json()
    except ValueError as exc:
        raise SSError(f"non-JSON answer for {symbol}") from exc
    if payload.get("companyId") != f"NSE:{symbol}":
        raise SSError(f"{symbol}: answer is for {payload.get('companyId')!r}")
    if not payload.get("prices"):
        raise SSError(f"{symbol}: no prices")
    return payload


def fetch_history(symbol: str, pages: int | None = 1, *, session=None,
                  delay_s: float = DELAY_S, sleep=time.sleep) -> tuple[pd.DataFrame, bool]:
    """(rows, more_history_available). pages=None follows the cursor to listing."""
    frames, before, n = [], None, 0
    more = False
    while pages is None or n < pages:
        if n:
            sleep(delay_s)
        payload = fetch_page(symbol, before, session=session)
        frame = to_frame(payload["prices"], symbol)
        frames.append(frame)
        n += 1
        more = bool(payload.get("hasMore"))
        oldest = payload["prices"][0][0]
        if not more or oldest == before:
            break
        before = oldest
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)
    out = out.drop_duplicates(["symbol", "date"], keep="last").sort_values("date")
    return out.reset_index(drop=True), more


# ── Shaping and checking ─────────────────────────────────────────────────────

def to_frame(prices: list, symbol: str) -> pd.DataFrame:
    """[date, open, high, low, close, volume] rows as a frame in rupees."""
    frame = pd.DataFrame(prices, columns=["date", *PRICE_COLUMNS, "volume"])
    frame["date"] = pd.to_datetime(frame["date"], format="%Y-%m-%d").dt.date
    for col in [*PRICE_COLUMNS, "volume"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame.insert(1, "symbol", symbol)
    return frame[COLUMNS]


def quality_problems(frame: pd.DataFrame) -> list[str]:
    """What makes a fetched frame unfit to store. Empty means it passes."""
    problems = []
    if frame.empty:
        return ["no rows"]
    vals = frame[[*PRICE_COLUMNS, "volume"]]
    if vals.isna().any().any() or not np.isfinite(vals.to_numpy(dtype=float)).all():
        problems.append("missing or non-finite values")
    if (frame[PRICE_COLUMNS] <= 0).any().any():
        problems.append("non-positive price")
    if (frame["volume"] < 0).any():
        problems.append("negative volume")
    hi_ok = frame["high"] >= frame[["open", "close", "low"]].max(axis=1) - 1e-9
    lo_ok = frame["low"] <= frame[["open", "close", "high"]].min(axis=1) + 1e-9
    if not (hi_ok & lo_ok).all():
        problems.append(f"{int((~(hi_ok & lo_ok)).sum())} rows with high/low outside open/close")
    if frame.duplicated(["symbol", "date"]).any():
        problems.append("duplicate (symbol, date)")
    return problems


def to_paise(frame: pd.DataFrame) -> pd.DataFrame:
    """Rupees to int32 paise; refuses a price that is not a whole paisa."""
    out = frame.copy()
    for col in PRICE_COLUMNS:
        paise = np.round(out[col].astype(float) * 100)
        if (np.abs(out[col].astype(float) * 100 - paise) > 1e-4).any():
            raise SSError(f"{col} has prices finer than a paisa")
        if (paise > np.iinfo(np.int32).max).any():
            raise SSError(f"{col} exceeds the int32 paise range")
        out[col] = paise.astype("int32")
    out["volume"] = np.round(out["volume"].astype(float)).astype("int64")
    return out


def to_rupees(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for col in PRICE_COLUMNS:
        out[col] = out[col].astype("float64") / 100.0
    return out


def needs_full_refresh(stored: pd.DataFrame, fresh: pd.DataFrame,
                       tolerance: float = RESTATE_TOLERANCE,
                       jump_limit: float = JUMP_LIMIT) -> str | None:
    """Why this stock should be re-downloaded whole, or None.

    `stored` and `fresh` are one symbol's rows in rupees. Restated history
    (an action the provider has now adjusted) shows up as stored closes that
    no longer match the fresh page; an unrestated one as a single session
    beyond the jump limit.
    """
    if fresh.empty:
        return None
    if not stored.empty:
        both = stored.set_index("date")["close"].to_frame("old").join(
            fresh.set_index("date")["close"].to_frame("new"), how="inner")
        if len(both):
            off = (both["new"] / both["old"] - 1).abs()
            if (off > tolerance).any():
                day = off.idxmax()
                return f"history restated (close on {day} moved {off.max():.1%})"
    closes = fresh.sort_values("date")["close"].astype(float)
    if len(closes) >= 2:
        move = closes.iloc[-1] / closes.iloc[-2] - 1
        if abs(move) > jump_limit:
            return f"latest session moved {move:+.1%}"
    return None


# ── The store ────────────────────────────────────────────────────────────────

def upsert(existing: pd.DataFrame, new: pd.DataFrame, replace_symbols=()) -> pd.DataFrame:
    """`new` rows win on (symbol, date); a replaced symbol keeps only its new rows."""
    keep = existing
    if len(replace_symbols) and not existing.empty:
        keep = existing[~existing["symbol"].isin(set(replace_symbols))]
    both = pd.concat([keep, new], ignore_index=True)
    both = both.drop_duplicates(["symbol", "date"], keep="last")
    return both.sort_values(["symbol", "date"]).reset_index(drop=True)


def write_store(frame: pd.DataFrame, directory: Path) -> dict[int, int]:
    """One file per year, written to a temp name then swapped in. Returns {year: bytes}."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    frame = frame.sort_values(["symbol", "date"])
    years = pd.to_datetime(frame["date"]).dt.year
    sizes = {}
    for year, part in frame.groupby(years):
        table = pa.Table.from_pandas(part[COLUMNS], schema=SCHEMA, preserve_index=False)
        target = directory / f"prices_{year}.parquet"
        tmp = target.with_suffix(".parquet.tmp")
        pq.write_table(table, tmp, compression="zstd", compression_level=9,
                       row_group_size=128_000)
        back = pq.read_table(tmp)
        if back.num_rows != len(part):
            tmp.unlink(missing_ok=True)
            raise SSError(f"{target.name}: wrote {back.num_rows} rows, expected {len(part)}")
        tmp.replace(target)
        sizes[int(year)] = target.stat().st_size
    return sizes


def read_store(directory: Path, symbols=None, start=None, end=None,
               columns=None) -> pd.DataFrame:
    """The stored rows (paise), filtered with predicate and column pushdown."""
    files = sorted(Path(directory).glob("prices_*.parquet"))
    if not files:
        return pd.DataFrame(columns=COLUMNS)
    filters = []
    if symbols is not None:
        filters.append(("symbol", "in", list(symbols)))
    if start is not None:
        filters.append(("date", ">=", pd.Timestamp(start).date()))
    if end is not None:
        filters.append(("date", "<=", pd.Timestamp(end).date()))
    cols = None if columns is None else list(dict.fromkeys(["date", "symbol", *columns]))
    table = pq.read_table([str(f) for f in files], columns=cols, filters=filters or None)
    frame = table.to_pandas()
    if "symbol" in frame:
        frame["symbol"] = frame["symbol"].astype(str)
    return frame
