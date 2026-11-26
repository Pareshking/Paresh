"""NSE indices the site reads beside the Nifty 500 and Nifty 50 (S148, S149).

    data/benchmark_indices.csv:  date, index, close, source

One row per index per session. The series:

- Nifty Total Market: NSE's index of the Nifty 500 and the Microcap 250, the
  same 750 stocks this site ranks; the live benchmark from Jan 2026 (owner,
  20 Nov 2026). The backtest and momentum health, which need history from
  2010, stay on the Nifty 500 (data/benchmarks.csv): this index starts at
  its launch, 14 Oct 2021.
- NSE's momentum indices, one per size: Nifty200 Momentum 30, Nifty500
  Momentum 50, Nifty Midcap150 Momentum 50, Nifty Smallcap250 Momentum
  Quality 100 (also screens for quality), and Nifty Total Market Momentum
  Quality 50, which picks from the same 750 stocks.
- Nifty 200, the size index the large-cap momentum index is drawn from.

Source: NSE's own daily all-indices file (S168's store, read through the app's
copy `data/nse_indices_history.parquet` + `data/nse_indices_recent.csv`) for every
session it holds, from each index's launch; Screener's index chart only for the
sessions after the store's last one (NSE's file lands at night, the daily sync
may run before it). Before 21 Nov 2026 this file was Screener alone, weekly
before 16 Oct 2025 (S167 (b)). Checked 21 Nov 2026 on every shared row, all 11
indices: Screener's weekly and daily closes equal NSE's (3,304 rows, largest
gap 0.003%), so the switch changes no figure, only fills the weeks between.
Nifty Total Market is daily from its launch, 14 Oct 2021; NSE's archive holds
no back-calculated years for it (S165). Each index also has an ETF that tracks
it; `etf_check` compares their returns so a broken series is caught by a
second, independent price (`scripts/build_benchmark_indices.py` prints it
every night, and any NSE/Screener close that differs).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core.logger import logger
from src.loaders.app_pack import resolve as _pack

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
        frame = pd.read_csv(_pack(path), parse_dates=["date"])
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


# NSE's own close beats everything; a close NSE published no file for, worked
# out from the next session's close and points change (S168, owner decision B),
# comes next; then Screener, daily beating weekly. Between rows of one source a
# newer fetch beats an older one (a late correction replaces the row).
NSE = "nse_close_all"
NSE_DERIVED = "nse_close_all_derived"
SOURCE_RANK = {NSE: 0, NSE_DERIVED: 1, "screener_daily": 2, "screener_weekly": 3}
# A Screener close further than this from NSE's for the same session is reported.
CROSS_CHECK_PCT = 0.05


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


def nse_key(key: str) -> str:
    """The key of one of SERIES in NSE's store: its NSE name as a slug."""
    from src.loaders.nse_indices import slug
    return slug(SERIES[key][0])


def nse_rows(store: pd.DataFrame) -> pd.DataFrame:
    """Rows for every index in SERIES from NSE's store (live rows only), in this
    file's shape; a derived close keeps its own source label."""
    from src.loaders.nse_indices import series
    parts = []
    derived = store.get("derived")
    for key in SERIES:
        close = series(store, nse_key(key))
        if close.empty:
            continue
        flag = pd.Series(False, index=close.index)
        if derived is not None:
            g = store[store["key"] == nse_key(key)]
            d = pd.Series(g["derived"].astype(bool).to_numpy(), index=pd.DatetimeIndex(g["date"]))
            flag = d[~d.index.duplicated(keep="last")].reindex(close.index, fill_value=False)
        parts.append(pd.DataFrame({"date": close.index, "index": key, "close": close.to_numpy(),
                                   "source": [NSE_DERIVED if f else NSE for f in flag]}))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=FIELDS)


def cross_check(nse: pd.DataFrame, other: pd.DataFrame, pct: float = CROSS_CHECK_PCT) -> pd.DataFrame:
    """(date, index, nse, other, diff_pct) where both hold a close and they differ
    by more than `pct` percent. Derived NSE closes are left out."""
    a = nse[nse["source"] == NSE][["date", "index", "close"]].rename(columns={"close": "nse"})
    b = other[["date", "index", "close"]].rename(columns={"close": "other"})
    j = a.merge(b, on=["date", "index"])
    j["diff_pct"] = (j["other"] / j["nse"] - 1).abs() * 100
    return j[j["diff_pct"] > pct].reset_index(drop=True)


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
