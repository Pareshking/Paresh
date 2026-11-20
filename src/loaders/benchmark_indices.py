"""NSE indices the site reads beside the Nifty 500 and Nifty 50 (S148, S149).

    data/benchmark_indices.csv:  date, index, close, source

One row per index per session. The series:

- Nifty Total Market: NSE's index of the Nifty 500 and the Microcap 250, the
  same 750 stocks this site ranks; the live benchmark from Jan 2026 (owner,
  20 Nov 2026). The backtest and momentum health, which need history from
  2010, stay on the Nifty 500 (data/benchmarks.csv): this index's history
  reachable from here starts in mid-2023.
- NSE's momentum indices, one per size: Nifty200 Momentum 30, Nifty500
  Momentum 50, Nifty Midcap150 Momentum 50, Nifty Smallcap250 Momentum
  Quality 100 (also screens for quality), and Nifty Total Market Momentum
  Quality 50, which picks from the same 750 stocks.
- Nifty 200, the size index the large-cap momentum index is drawn from.

Source: Screener's index chart, daily for about the last 400 days and weekly
before. NSE's daily bundle (Pd<ddmmyy>.csv), the record for the Nifty 500,
does not carry these indices, and niftyindices.com refuses requests from the
container and from the nightly job (5-7 and 20 Nov 2026). Each index has an
ETF that tracks it; `etf_check` compares their returns so a broken series is
caught by a second, independent price (`scripts/build_benchmark_indices.py`
prints it every night). Checked 20 Nov 2026: Screener's Nifty 500 equals
NSE's own close to the hundredth over November to date.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core.logger import logger

FILE = Path(__file__).resolve().parents[2] / "data" / "benchmark_indices.csv"
FIELDS = ["date", "index", "close", "source"]

TOTAL_MARKET = "nifty_total_market"

# key: (NSE's name, Screener slug, Screener slug of an ETF that tracks it or None)
SERIES: dict[str, tuple[str, str, str | None]] = {
    TOTAL_MARKET: ("Nifty Total Market", "NFTYTOTMKT", "AONETOTAL"),
    "nifty200": ("Nifty 200", "CNX200INDE", None),
    # The size indices again, here so every index figure on the Dashboard ends
    # on the same session from one source (the strip mixed 18 and 19 Nov, S148).
    "nifty50": ("Nifty 50", "NIFTY", None),
    "midcap150": ("Nifty Midcap 150", "NMIDCAP150", None),
    "smallcap250": ("Nifty Smallcap 250", "SMALLCA250", None),
    "microcap250": ("Nifty Microcap 250", "NFMICRO250", None),
    "nifty200_mom30": ("Nifty200 Momentum 30", "NI200MOM30", "MOM30IETF"),
    "nifty500_mom50": ("Nifty500 Momentum 50", "NIF500MO50", "MOMENTUM50"),
    "midcap150_mom50": ("Nifty Midcap150 Momentum 50", "NFMC150M50", "MOMIDMTM"),
    "smallcap250_mq100": ("Nifty Smallcap250 Momentum Quality 100", "NS250MQ100", "SMALLGROWW"),
    "total_market_mq50": ("Nifty Total Market Momentum Quality 50", "NFTTMMQ50", "AONETMMQ50"),
}

# An ETF and its index over the same sessions may differ by fees, cash and the
# ETF's own price; more than this many points over a month says one series is
# wrong. Observed 20 Nov 2026, November to date: 0.1 to 0.4 points.
ETF_TOLERANCE_PTS = 1.5


def read(path: Path = FILE) -> pd.DataFrame:
    """The long table, or an empty one with its columns when the file is absent."""
    try:
        frame = pd.read_csv(path, parse_dates=["date"])
    except (OSError, ValueError):
        return pd.DataFrame(columns=FIELDS)
    if not pd.api.types.is_datetime64_any_dtype(frame["date"]):
        logger.warning("benchmark_indices.csv has no usable dates; treating it as empty.")
        return pd.DataFrame(columns=FIELDS)
    return frame


def series(key: str, path: Path = FILE, frame: pd.DataFrame | None = None) -> pd.Series:
    """One index's closes by date; empty when unknown or absent."""
    frame = read(path) if frame is None else frame
    rows = frame[frame["index"] == key]
    if rows.empty:
        return pd.Series(dtype=float, name=key)
    out = pd.Series(pd.to_numeric(rows["close"], errors="coerce").values,
                    index=pd.DatetimeIndex(rows["date"]).normalize(), name=key).dropna().sort_index()
    return out[~out.index.duplicated(keep="last")]


# Daily beats weekly for the same date; a newer fetch beats an older one of
# the same kind (a late correction on Screener replaces the row).
SOURCE_RANK = {"screener_daily": 0, "screener_weekly": 1}


def merge(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Rows of `new` added to `existing`; for one (date, index) the better source wins,
    and between equal sources the newer fetch."""
    parts = [f for f in (existing, new) if f is not None and not f.empty]
    if not parts:
        return pd.DataFrame(columns=FIELDS)
    both = pd.concat([p[FIELDS] for p in parts], ignore_index=True)
    both["date"] = pd.to_datetime(both["date"]).dt.normalize()
    both["_rank"] = both["source"].map(SOURCE_RANK).fillna(len(SOURCE_RANK)).astype(int)
    both["_order"] = range(len(both))                 # later rows are newer fetches
    both = both.sort_values(["_rank", "_order"], ascending=[True, False], kind="stable")
    both = both.drop_duplicates(["date", "index"], keep="first")
    return both.drop(columns=["_rank", "_order"]).sort_values(["index", "date"]).reset_index(drop=True)


def write(frame: pd.DataFrame, path: Path = FILE) -> None:
    out = frame[FIELDS].copy()
    out["close"] = pd.to_numeric(out["close"], errors="coerce").astype(float)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, date_format="%Y-%m-%d", float_format="%.2f")


def window_return(close: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> float | None:
    """Percent from the last close on or before `start` to the last on or before `end`."""
    s = close.dropna().sort_index()
    a, b = s[s.index <= start], s[s.index <= end]
    if a.empty or b.empty or a.iloc[-1] == 0:
        return None
    return (float(b.iloc[-1]) / float(a.iloc[-1]) - 1) * 100


def etf_check(index_close: pd.Series, etf_close: pd.Series, end: pd.Timestamp,
              months: int = 1) -> tuple[float | None, float | None, bool]:
    """(index %, ETF %, agree) over the same calendar window, on shared sessions only."""
    shared = index_close.index.intersection(etf_close.index)
    if len(shared) < 5:
        return None, None, False
    i, e = index_close.loc[shared], etf_close.loc[shared]
    start = end - pd.DateOffset(months=months)
    ri, re_ = window_return(i, start, end), window_return(e, start, end)
    if ri is None or re_ is None:
        return ri, re_, False
    return ri, re_, abs(ri - re_) <= ETF_TOLERANCE_PTS
