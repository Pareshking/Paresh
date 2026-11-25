"""NSE's quarterly earnings growth for the broad indices (S171), read from
`data/reference/nse_earnings_review.csv` (built by `scripts/nse_earnings_review.py`
from NSE's Corporate Earnings Review PDFs; every figure carries its PDF, page and quote).

The Indices page shows the latest quarter NSE published, from that quarter's own issue
only: a figure filled in from a later issue (a quarter NSE skipped) is history, not "latest".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pandas as pd

PATH = Path(__file__).resolve().parents[2] / "data" / "reference" / "nse_earnings_review.csv"
INDICES = ("Nifty 50", "Nifty Next 50", "Nifty Midcap 150", "Nifty Smallcap 250", "Nifty 500")
MEASURES = ("pat_agg_yoy", "pat_median_yoy", "sales_agg_yoy", "sales_median_yoy")


@dataclass(frozen=True)
class Latest:
    quarter: str                      # "Q1FY27"
    published: pd.Timestamp
    pdf_url: str
    values: dict[str, dict[str, float | None]] = field(default_factory=dict)   # index -> measure -> % YoY


def quarter_label(q: str) -> str:
    """"Q1FY27" -> "Q1 FY27"."""
    return f"{q[:2]} {q[2:]}" if len(q) >= 4 else q


def _order(q: str) -> tuple[int, int]:
    return int(q[4:]), int(q[1])      # "Q1FY27" -> (27, 1)


@lru_cache(maxsize=4)
def _read(path: str, mtime: float) -> pd.DataFrame:
    return pd.read_csv(path)


def load(path: Path = PATH) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return _read(str(path), path.stat().st_mtime)


def latest(df: pd.DataFrame | None = None) -> Latest | None:
    """The newest quarter with its own NSE issue, and its figures by index and measure."""
    df = load() if df is None else df
    if df is None or df.empty:
        return None
    own = df[df["issue"] == df["quarter"]]
    if own.empty:
        return None
    q = max(own["quarter"].unique(), key=_order)
    rows = own[own["quarter"] == q]
    vals = {i: {m: None for m in MEASURES} for i in INDICES}
    for r in rows.itertuples():
        if r.index in vals and r.measure in vals[r.index] and pd.notna(r.value_pct):
            vals[r.index][r.measure] = float(r.value_pct)
    return Latest(quarter=q, published=pd.Timestamp(rows["published"].iloc[0]),
                  pdf_url=str(rows["pdf_url"].iloc[0]), values=vals)
