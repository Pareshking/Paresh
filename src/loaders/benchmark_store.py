"""The benchmark indices, read from a small committed file instead of Yahoo.

Owner, 2026-10-02: no Yahoo anywhere -- Screener first, NSE second. The
Nifty 500 (the V1 benchmark, ^CRSLDX) and Nifty 50 (^NSEI) closes live in
data/benchmarks.csv, one row per session:

    date, nifty500, nifty50, source

`source` says where each row came from: "nse" (NSE's own daily bundle, the
index rows of Pd<ddmmyy>.csv), "ss" (its index chart, daily back to
the index's start), "kaggle" (the public-domain Kaggle dataset "NSE India
Stock Data 1990-2021", daily index closes from 1999), or "screener" (Screener's index chart, daily for the
last year and weekly before it). Checked on 2026-10-01: NSE
printed Nifty 500 at 21857.75 and Screener's CNX500 the same.

scripts/build_benchmarks.py builds and extends it; the daily sync commits it
with the rest of data/. Reading it costs one local file read -- no network.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FILE = Path(__file__).resolve().parents[2] / "data" / "benchmarks.csv"

# The symbols callers already pass (the Yahoo tickers they used to download)
# and the column each one reads.
COLUMNS: dict[str, str] = {
    "^CRSLDX": "nifty500",
    "^NSEI": "nifty50",
}
# NSE's name for each column in the bundle's index rows, and Screener's id.
NSE_NAMES: dict[str, str] = {"nifty500": "NIFTY 500", "nifty50": "NIFTY 50"}
SCREENER_IDS: dict[str, str] = {"nifty500": "CNX500", "nifty50": "NIFTY"}
SS_IDS: dict[str, str] = {"nifty500": "CNX500", "nifty50": "NIFTY"}
FIELDS = ["date", "nifty500", "nifty50", "source"]


def read(path: Path = FILE) -> pd.DataFrame:
    """The whole file, indexed by date; empty (with the columns) when absent."""
    try:
        frame = pd.read_csv(path, parse_dates=["date"])
    except (OSError, ValueError):
        return pd.DataFrame(columns=FIELDS[1:], index=pd.DatetimeIndex([], name="date"))
    return frame.set_index("date").sort_index()


def _period_start(last: pd.Timestamp, period: str | None) -> pd.Timestamp | None:
    text = str(period or "").strip().lower()
    if not text or text == "max":
        return None
    for suffix, unit in (("mo", "months"), ("y", "years"), ("d", "days")):
        n = text[: -len(suffix)]
        if text.endswith(suffix) and n.isdigit():
            return last - pd.DateOffset(**{unit: int(n)})
    return None


def history(period: str = "2y", symbol: str = "^CRSLDX", path: Path = FILE) -> pd.Series:
    """A benchmark close series, like the Yahoo download it replaces.

    Unknown symbols and a missing file return an empty series named after the
    symbol, which every caller already treats as "benchmark unavailable".
    """
    column = COLUMNS.get(symbol)
    frame = read(path)
    if column is None or column not in frame.columns or frame.empty:
        return pd.Series(dtype=float, name=symbol)
    series = pd.to_numeric(frame[column], errors="coerce").dropna()
    if series.empty:
        return pd.Series(dtype=float, name=symbol)
    start = _period_start(series.index[-1], period)
    if start is not None:
        series = series[series.index >= start]
    series.name = symbol
    return series


def index_closes(prices: pd.DataFrame) -> dict[str, float]:
    """{column: close} from one day's parsed NSE price table (nse_bundle.parse_prices)."""
    rows = prices[prices["mkt"].astype(str).str.upper() == "Y"]
    names = rows["security"].astype(str).str.strip().str.upper()
    out = {}
    for column, nse_name in NSE_NAMES.items():
        hit = rows.loc[names == nse_name, "close"]
        if len(hit) and pd.notna(hit.iloc[0]) and float(hit.iloc[0]) > 0:
            out[column] = float(hit.iloc[0])
    return out


# Which row wins for the same date: NSE's own bundle, then SS (daily
# back to the index's start), then the Kaggle "NSE India Stock Data" index
# files (daily 1999 - Jun 2021; equal to the SS/NSE rows on all 1,418 shared
# days, 2 Oct 2026), then Screener (weekly beyond its last year).
SOURCE_RANK = {"nse": 0, "ss": 1, "kaggle": 2, "screener": 3}


def merge(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Rows of `new` added to `existing`; for one date the better-ranked source wins."""
    both = pd.concat([existing, new])
    rank = both["source"].map(SOURCE_RANK).fillna(len(SOURCE_RANK)).astype(int)
    both = both.assign(_rank=rank.values).sort_values("_rank", kind="stable")
    both = both[~both.index.duplicated(keep="first")].drop(columns="_rank")
    return both.sort_index()


def write(frame: pd.DataFrame, path: Path = FILE) -> None:
    out = frame.reset_index()[FIELDS]
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, date_format="%Y-%m-%d", float_format="%.2f")
