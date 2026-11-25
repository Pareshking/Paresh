"""Quarterly earnings growth for the broad indices (S171). The page reads ours (`ours`, bottom); NSE's, read from
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


def quarter_end(q: str) -> pd.Timestamp:
    """"Q1FY27" -> 30 Jun 2026 (India's fiscal year starts in April)."""
    n, fy = int(q[1]), 2000 + int(q[4:])
    month, year = {1: (6, fy - 1), 2: (9, fy - 1), 3: (12, fy - 1), 4: (3, fy)}[n]
    return pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd(0)


def history(index: str, measure: str, df: pd.DataFrame | None = None) -> pd.Series:
    """One figure per quarter, oldest first, indexed by quarter end. A quarter NSE skipped carries the next
    issue's figure for it; Q3 FY26 excludes Tata Motors (owner, 25 Nov 2026), as the file stores it."""
    df = load() if df is None else df
    if df is None or df.empty:
        return pd.Series(dtype=float)
    rows = df[(df["index"] == index) & (df["measure"] == measure)].dropna(subset=["value_pct"])
    out = pd.Series({quarter_end(q): float(v) for q, v in zip(rows["quarter"], rows["value_pct"])}, dtype=float)
    return out.sort_index()


# ── Ours: Screener's company results added up (S171 (2); owner, 25 Nov 2026: "We will use Screener data only") ──

OURS_PATH = PATH.parent / "screener_earnings.csv"     # built weekly by scripts/screener_earnings.py
OUR_INDICES = INDICES[:4] + ("Nifty Microcap 250", "Nifty 500")
# The profit the page shows: "pat" is net profit as companies report it; "pat_xoi" leaves out other income after tax
# for companies other than banks and lenders (the one-off gains sit there: Vodafone Idea Mar 2026, Tata Motors Sep 2025).
PROFIT = "pat_xoi"


def _measure(m: str) -> str:
    """The page's measure name ("pat_agg_yoy") as the Screener file stores it."""
    return m.replace("pat_", f"{PROFIT}_", 1) if m.startswith("pat_") else m


def ours(df: pd.DataFrame | None = None) -> Latest | None:
    """The newest complete quarter of our calculation, with the date its pages were read."""
    df = load(OURS_PATH) if df is None else df
    if df is None or df.empty:
        return None
    q = max(df["quarter"].unique(), key=_order)
    rows = df[df["quarter"] == q]
    vals = {i: {m: None for m in MEASURES} for i in OUR_INDICES}
    for i in OUR_INDICES:
        for m in MEASURES:
            hit = rows[(rows["index"] == i) & (rows["measure"] == _measure(m))]["value_pct"].dropna()
            if len(hit):
                vals[i][m] = float(hit.iloc[0])
    return Latest(quarter=q, published=pd.Timestamp(rows["as_of"].iloc[0]), pdf_url="", values=vals)


def ours_history(index: str, measure: str, df: pd.DataFrame | None = None) -> pd.Series:
    """Our figure each quarter, oldest first, indexed by quarter end."""
    df = load(OURS_PATH) if df is None else df
    if df is None or df.empty:
        return pd.Series(dtype=float)
    return history(index, _measure(measure), df)


# ── One company's quarters, for the Stock page's results table ───────────────

QUARTERS_PATH = PATH.parent / "screener_quarters.csv"   # built weekly by scripts/screener_earnings.py
RESULT_ROWS = 8


@dataclass(frozen=True)
class Quarter:
    end: pd.Timestamp
    label: str                          # "Q2 FY27"
    values: dict[str, float | None]     # sales, profit (operating, or before tax for a lender), net_profit, eps
    growth: dict[str, float | None]     # the same keys, % on the same quarter a year earlier; None on a base <= 0


@dataclass(frozen=True)
class Results:
    symbol: str
    lender: bool                        # Screener's first row is "Revenue": banks and lenders
    basis: str                          # "consolidated", "standalone" or "consolidated and standalone"
    read: pd.Timestamp
    quarters: list[Quarter]             # newest first


def _label_of(d: pd.Timestamp) -> str:
    n = {6: 1, 9: 2, 12: 3, 3: 4}[d.month]
    return f"Q{n} FY{(d.year + (0 if n == 4 else 1)) % 100:02d}"


def _yoy(now, base) -> float | None:
    if now is None or base is None or pd.isna(now) or pd.isna(base) or base <= 0:
        return None
    return (float(now) / float(base) - 1) * 100


def company(symbol: str, df: pd.DataFrame | None = None, rows: int = RESULT_ROWS) -> Results | None:
    """The last `rows` quarters, newest first, each with its year-earlier quarter on the same basis; the run stops at
    the first quarter without one, so the table has no gaps and one basis; a new listing (fewer than five quarters)
    shows the quarters it has, its growth "–". A lender's
    "Financing Profit" (revenue less interest and every expense, provisions included, before other income) is no
    operating profit a reader knows, so a lender shows profit before tax in its place."""
    df = load(QUARTERS_PATH) if df is None else df
    if df is None or df.empty:
        return None
    mine = df[df["symbol"] == symbol]
    if mine.empty:
        return None
    lender = str(mine["sales_label"].iloc[-1]).lower().startswith("revenue")
    by = {pd.Timestamp(r["quarter_end"]): r for r in mine.to_dict("records")}
    keys = {"sales": "sales", "profit": "pbt" if lender else "operating_profit", "net_profit": "net_profit",
            "eps": "eps"}
    out = []
    for d in sorted(by, reverse=True):
        base = by.get(d - pd.DateOffset(years=1) + pd.offsets.MonthEnd(0))
        if base is not None and base["basis"] != by[d]["basis"]:
            break                       # one basis in the table: stop at the first quarter compared across bases
        if base is None and len(by) >= 5:
            break                       # a year-earlier quarter we should have and do not: no gaps in the table
        base = base or {}               # a new listing: its quarters, growth "–" until a year has passed
        now = by[d]
        val = {k: (None if pd.isna(now.get(c)) else float(now.get(c))) for k, c in keys.items()}
        out.append(Quarter(end=d, label=_label_of(d), values=val,
                           growth={k: _yoy(now.get(c), base.get(c)) for k, c in keys.items()}))
        if len(out) == rows:
            break
    if not out:
        return None
    bases = sorted({str(by[q.end]["basis"]) for q in out})
    return Results(symbol=symbol, lender=lender, basis=" and ".join(bases), read=pd.Timestamp(mine["fetched"].max()),
                   quarters=out)
