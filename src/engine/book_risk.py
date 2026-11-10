"""How risky is the book? Beta, volatility, size tilt, drawdown and exit time.

Owner, 8 Nov 2026 (TODO S110, item 3): the Dashboard's "Book at risk" lists
the holdings nearest a rule; this describes the whole book's exposure.

- Beta and volatility: the book as it stands, at today's weights, held over
  the last 126 sessions, against the Nifty 500's daily returns. Standard
  definitions (beta = covariance / the index's variance), annualised with
  sqrt(252).
- Size tilt: each holding's weight by its NSE index tier on the latest lists
  in data/indices (Nifty 100 = Nifty 50 + Next 50, Midcap 150, Smallcap 250,
  Microcap 250); a holding in none of them is "outside".
- Drawdown: the live record's equity curve, now and worst since it began,
  beside the Nifty 500's over the same dates.
- Days to exit: a position's value at the model book's capital, divided by
  PARTICIPATION of its 20-day average traded value (close x volume, the
  ranking's own source). PARTICIPATION is an assumption -- a common rule of
  thumb for trading without moving the price much -- not a sourced figure;
  the page says so.

Data checks, not silent drops: a holding with fewer than MIN_SESSIONS of
returns in the window, or no traded value, is named in `gaps`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from src.core.config import MODEL_BOOK_CAPITAL
from src.engine.metrics import drawdown

WINDOW = 126
MIN_SESSIONS = 60
PARTICIPATION = 0.10
VALUE_WINDOW = 20
CRORE = 1e7
INDEX_DIR = Path(__file__).resolve().parents[2] / "data" / "indices"
TIERS = (("Nifty 100", ("ind_nifty50list.csv", "ind_niftynext50list.csv")),
         ("Midcap 150", ("ind_niftymidcap150list.csv",)),
         ("Smallcap 250", ("ind_niftysmallcap250list.csv",)),
         ("Microcap 250", ("ind_niftymicrocap250_list.csv",)))


@dataclass(frozen=True)
class BookRisk:
    beta: float | None
    vol: float | None
    bench_vol: float | None
    tiers: dict[str, float]                 # tier -> share of weight
    drawdown: float | None                  # now, from the record's peak
    max_drawdown: float | None
    bench_drawdown: float | None            # the Nifty 500 now, from its peak since the record began
    exit_days: pd.Series                    # symbol -> days to exit, slowest first
    gaps: list[str] = field(default_factory=list)
    sessions: int = 0
    cash: float = 0.0                       # share of the book not in stocks


def tier_of(symbols, index_dir: Path = INDEX_DIR) -> dict[str, str]:
    out: dict[str, str] = {}
    for tier, files in TIERS:
        for f in files:
            path = index_dir / f
            if not path.exists():
                continue
            frame = pd.read_csv(path)
            frame.columns = [str(c).strip() for c in frame.columns]
            for s in frame.get("Symbol", pd.Series(dtype=str)).astype(str).str.strip():
                out.setdefault(s, tier)
    return {s: out.get(s, "Outside") for s in symbols}


def _drawdown(curve: pd.Series) -> tuple[float, float]:
    c = pd.to_numeric(curve, errors="coerce").dropna()
    dd = drawdown(c)
    return float(dd.iloc[-1]), float(dd.min())


def book_risk(weights: pd.Series, prices: pd.DataFrame, bench: pd.Series | None,
              equity: pd.Series | None = None, volume: pd.DataFrame | None = None,
              capital: float = MODEL_BOOK_CAPITAL, index_dir: Path = INDEX_DIR) -> BookRisk:
    """`weights`: symbol -> weight, as fractions or percent of the book.

    Cash is kept (audit C-L2, 8 Nov 2026). The weights used to be divided by
    their own sum, so a book 75% invested was measured as if fully invested:
    its beta and volatility came out a third too high, and its size tiers
    summed to the whole book. Only the scale is normalised here -- percent to
    fractions -- and whatever is left over is cash, which earns nothing and so
    damps both. It mattered from the six-monthly reset (S111): between resets
    a buy is paid from cash, and short of cash the book simply holds it.
    """
    w = pd.to_numeric(weights, errors="coerce").dropna()
    w = w[w > 0]
    total = float(w.sum())
    if total > 1.5:                 # percent, not fractions
        w = w / 100.0
        total = float(w.sum())
    cash = max(0.0, 1.0 - total)
    if total > 1.0:                 # rounding, or a caller that over-allocates
        w = w / total
        cash = 0.0
    gaps: list[str] = []
    px = prices.reindex(columns=w.index)
    rets = px.pct_change(fill_method=None).iloc[-WINDOW:]
    short = [s for s in w.index if rets[s].notna().sum() < MIN_SESSIONS]
    if short:
        gaps.append("too little price history for beta and volatility: " + ", ".join(short))
    usable = w.drop(short)
    beta = vol = bench_vol = None
    if len(usable) and bench is not None:
        b = pd.to_numeric(bench, errors="coerce").dropna()
        b.index = pd.to_datetime(b.index).normalize()
        r = rets[usable.index].copy()
        r.index = pd.to_datetime(r.index).normalize()
        # Missing days count as unchanged for that stock: a gap in one name must not drop the session.
        # The weights as they stand, not renormalised: cash (and any name
        # with too little history) contributes nothing, which is the point.
        port = r.fillna(0.0).mul(usable, axis=1).sum(axis=1)
        br = b.pct_change().reindex(port.index)
        both = pd.concat([port, br], axis=1, keys=["p", "b"]).dropna()
        # A flat or stale index has no variance: no beta rather than a division by zero.
        if len(both) >= MIN_SESSIONS and both["b"].var() > 0:
            beta = float(both["p"].cov(both["b"]) / both["b"].var())
            vol = float(both["p"].std() * np.sqrt(252))
            bench_vol = float(both["b"].std() * np.sqrt(252))
    tiers_map = tier_of(w.index, index_dir)
    tiers: dict[str, float] = {}
    for s, t in tiers_map.items():
        tiers[t] = tiers.get(t, 0.0) + float(w[s])
    if cash > 0.0005:
        tiers["Cash"] = tiers.get("Cash", 0.0) + cash
    dd = mdd = bdd = None
    if equity is not None and len(pd.Series(equity).dropna()) > 1:
        eq = pd.Series(equity).dropna()
        dd, mdd = _drawdown(eq)
        if bench is not None:
            b = pd.to_numeric(bench, errors="coerce").dropna()
            b.index = pd.to_datetime(b.index)
            # The same dates as the record: its curve ends at a month-end, the index runs to today.
            bseg = b.loc[pd.Timestamp(eq.index[0]):pd.Timestamp(eq.index[-1])]
            if len(bseg) > 1:
                bdd, _ = _drawdown(bseg)
    exit_days = pd.Series(dtype=float)
    if volume is not None:
        vol_frame = volume.reindex(columns=w.index)
        value = (px * vol_frame.reindex(index=px.index)).iloc[-VALUE_WINDOW:].mean()
        no_value = [s for s in w.index if not (value.get(s, np.nan) > 0)]
        if no_value:
            gaps.append("no traded value: " + ", ".join(no_value))
        ok = value.drop(no_value, errors="ignore")
        exit_days = (w.reindex(ok.index) * capital / (ok * PARTICIPATION)).sort_values(ascending=False)
    return BookRisk(beta, vol, bench_vol, tiers, dd, mdd, bdd, exit_days, gaps,
                    int(rets.shape[0]), cash)
