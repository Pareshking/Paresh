"""The ranking as it stood at each month start and end, for the record's own book.

A Track Record month says what the book returned. This says why it held what it
held: for every name in a month's book, its rank and its entry gates (above the
50-day EMA, within 20% of its 52-week high, in the index) on the signal date that
opened the month, and again on the date that closed it, with what the next
rebalance then did with it. The scores are the backtester's own
(`_composite_z_score`) read at the same dates from the same prices, so a rank here
is the rank the book was struck on. Nothing is scored on a later date than it is
labelled with.

A month starts at its signal date (the last session of the month before, filled at
the next close) and ends at the next signal date, which is also the next month's
start. The month in progress ends at the latest session.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from src.core.config import MOMENTUM_WINDOWS
from src.engine.backtester import _composite_z_score, _index_mask
from src.engine.calendar_momentum import anchor_frame

COLUMNS = ["date", "symbol", "rank", "score", "above_ema", "pct_of_high", "in_index", "qualifies"]


def snapshots(prices: pd.DataFrame, dates: Sequence[pd.Timestamp], *, membership=None,
              ema_period: int = 50, high_pct: float = 0.80,
              config_weights: Sequence[float] = (0.10, 0.30, 0.30, 0.20, 0.10)) -> pd.DataFrame:
    """One row per (signal date, stock): rank among qualifiers, score, gates.

    `rank` is NaN for a stock that fails a gate (it is not in the ranking that day).
    """
    prices = prices.dropna(axis=1, how="all")
    total = float(sum(config_weights))
    weights = [w / total for w in config_weights] if total > 0 else [0.2] * len(config_weights)
    anchor = anchor_frame(prices)
    log_ret = np.log(prices / prices.shift(1).replace(0, np.nan))
    ema = prices.ewm(span=ema_period).mean()
    high = prices.rolling(252, min_periods=126).max()
    out = []
    for d in dict.fromkeys(pd.Timestamp(x) for x in dates):
        pos = prices.index.searchsorted(d, side="right") - 1
        if pos < 0:
            continue
        day = prices.index[pos]
        p, e, h = prices.iloc[pos], ema.iloc[pos], high.iloc[pos]
        above = p > e
        near = p >= h * high_pct
        idx_mask = _index_mask(membership, prices.columns, day)
        in_idx = idx_mask if idx_mask is not None else pd.Series(True, index=prices.columns)
        qualifies = above & near & (p > 0) & in_idx
        score = _composite_z_score(prices, log_ret, pos, MOMENTUM_WINDOWS, weights, prices_anchor=anchor)
        ranked = score[qualifies & score.notna()].sort_values(ascending=False)
        rank = pd.Series(np.arange(1, len(ranked) + 1), index=ranked.index, dtype=float)
        frame = pd.DataFrame({
            "date": day, "symbol": prices.columns,
            "rank": rank.reindex(prices.columns).to_numpy(),
            "score": score.reindex(prices.columns).to_numpy(),
            "above_ema": above.to_numpy(), "pct_of_high": (p / h).to_numpy(),
            "in_index": in_idx.reindex(prices.columns).fillna(False).to_numpy(),
            "qualifies": qualifies.to_numpy(),
        })
        out.append(frame)
    return pd.concat(out, ignore_index=True)[COLUMNS] if out else pd.DataFrame(columns=COLUMNS)


def _signal_dates(prices: pd.DataFrame, tradebook: pd.DataFrame) -> dict[pd.Timestamp, pd.Timestamp]:
    """{period start (the fill) -> its signal date, the session before}."""
    out = {}
    for start in sorted(pd.to_datetime(tradebook["Period Start"]).dropna().unique()):
        pos = prices.index.searchsorted(pd.Timestamp(start))
        if 0 < pos < len(prices.index):
            out[pd.Timestamp(start)] = prices.index[pos - 1]
    return out


def month_books(prices: pd.DataFrame, tradebook: pd.DataFrame, *, membership=None, **kw
                ) -> dict[str, pd.DataFrame]:
    """{"2026-03": the book that month with start and end ranks and gates}.

    Rows: every name bought or retained at the month's signal date. Columns hold the
    start and end rank, whether each gate held at start and end, and what the next
    rebalance did (HOLD, SELL, or "Held to date" for the month in progress).
    """
    if tradebook is None or tradebook.empty:
        return {}
    tb = tradebook.copy()
    tb["Period Start"] = pd.to_datetime(tb["Period Start"])
    sig = _signal_dates(prices, tb)
    starts = sorted(sig)
    last_day = prices.index[-1]
    snap = snapshots(prices, list(sig.values()) + [last_day], membership=membership, **kw)
    at = {d: g.set_index("symbol") for d, g in snap.groupby("date")}
    ends = {s: (sig[starts[i + 1]] if i + 1 < len(starts) else last_day) for i, s in enumerate(starts)}
    out: dict[str, pd.DataFrame] = {}
    for i, s in enumerate(starts):
        rows = tb[tb["Period Start"] == s]
        book = rows[rows["Action"].str.contains("BUY|HOLD", na=False)]
        nxt = tb[tb["Period Start"] == starts[i + 1]] if i + 1 < len(starts) else tb.iloc[0:0]
        a, b = at[sig[s]], at[ends[s]]
        recs = []
        for _, r in book.iterrows():
            sym = r["Symbol"]
            fate = nxt[nxt["Symbol"] == sym]
            recs.append({
                "Symbol": sym,
                "Action": "Bought" if "BUY" in r["Action"] else "Retained",
                "Weight %": r.get("Weight %"),
                "Rank at start": a["rank"].get(sym, np.nan),
                "Rank at end": b["rank"].get(sym, np.nan),
                "Above EMA start": bool(a["above_ema"].get(sym, False)),
                "Above EMA end": bool(b["above_ema"].get(sym, False)),
                "% of 52w high start": a["pct_of_high"].get(sym, np.nan),
                "% of 52w high end": b["pct_of_high"].get(sym, np.nan),
                "In index end": bool(b["in_index"].get(sym, False)),
                "Next rebalance": (("Held on" if "HOLD" in fate["Action"].iloc[0] else "Sold")
                                   if len(fate) else ("Held to date" if i + 1 >= len(starts) else "—")),
                "Why": (fate["Reason / Signal"].iloc[0] if len(fate) else ""),
            })
        key = f"{pd.Timestamp(s):%Y-%m}"
        out[key] = pd.DataFrame(recs)
        out[key].attrs.update(start=str(sig[s].date()), end=str(ends[s].date()),
                              in_progress=i + 1 >= len(starts))
    return out
