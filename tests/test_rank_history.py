"""Each month's book with the rank and gates it was struck on, at its start and its end."""
from __future__ import annotations

import numpy as np
import pandas as pd

import src.engine.pipeline  # noqa: F401  (pipeline first: it and momentum import each other)
from src.engine.rank_history import month_books, snapshots

IDX = pd.bdate_range("2024-10-01", "2026-03-31")
rng = np.random.default_rng(3)


def _prices():
    n, cols = len(IDX), [f"S{c}" for c in "ABCDEFGH"]
    drift = np.linspace(0.0012, 0.0002, len(cols))          # SA strongest, SH weakest
    r = rng.normal(0, 0.004, (n, len(cols))) + drift
    return pd.DataFrame(100 * np.exp(np.cumsum(r, axis=0)), index=IDX, columns=cols)


def test_ranks_run_one_to_n_among_qualifiers_and_nan_for_the_rest():
    p = _prices()
    s = snapshots(p, [IDX[-1]])
    q = s[s["qualifies"]]
    assert sorted(q["rank"]) == list(range(1, len(q) + 1))
    assert s.loc[~s["qualifies"], "rank"].isna().all()
    assert (q.sort_values("rank")["score"].diff().dropna() <= 1e-12).all()


def test_a_snapshot_reads_nothing_after_its_date():
    p = _prices()
    d = IDX[330]
    a = snapshots(p, [d])
    b = snapshots(p.iloc[:331], [d])
    pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True))


def test_a_month_book_carries_start_and_end_ranks_and_the_next_decision():
    p = _prices()
    fills = [IDX[IDX.get_loc(pd.Timestamp("2026-01-30")) + 1], IDX[IDX.get_loc(pd.Timestamp("2026-02-27")) + 1]]
    tb = pd.DataFrame([
        {"Period Start": fills[0], "Action": "🟢 BUY (Entry)", "Symbol": "SA", "Weight %": 50.0,
         "Reason / Signal": "New Momentum Leader (Rank #1)"},
        {"Period Start": fills[0], "Action": "🟢 BUY (Entry)", "Symbol": "SB", "Weight %": 50.0,
         "Reason / Signal": "New Momentum Leader (Rank #2)"},
        {"Period Start": fills[1], "Action": "⚪ HOLD (Retained)", "Symbol": "SA", "Weight %": 50.0,
         "Reason / Signal": "Buffer Zone Retention (Rank #1)"},
        {"Period Start": fills[1], "Action": "🔴 SELL (Exit)", "Symbol": "SB", "Weight %": 0.0,
         "Reason / Signal": "Trend Breakdown (< 50 EMA)"},
    ])
    books = month_books(p, tb)
    jan = books["2026-02"]
    assert jan.attrs["start"] == "2026-01-30" and jan.attrs["end"] == "2026-02-27"
    row = jan.set_index("Symbol")
    assert row.loc["SA", "Next rebalance"] == "Held on" and row.loc["SB", "Next rebalance"] == "Sold"
    assert row.loc["SB", "Why"].startswith("Trend Breakdown")
    s = snapshots(p, [pd.Timestamp("2026-01-30")]).set_index("symbol")
    assert row.loc["SA", "Rank at start"] == s.loc["SA", "rank"]
    # the month in progress ends at the latest session
    assert books["2026-03"].attrs["in_progress"] and books["2026-03"].attrs["end"] == str(IDX[-1].date())
