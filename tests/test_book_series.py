"""One daily series for the book on every page (S154)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.engine.actions import fixed_buy_weight
from src.engine.metrics import drawdown
from src.ui.book_series import book_series


def _fixture():
    days = pd.bdate_range("2026-08-03", "2026-09-30")
    aug = days[days.month == 8]
    # The replay ends at the last month-end, as the record's does.
    replay = pd.Series(np.linspace(1_000_000, 1_100_000, len(aug)), index=aug)
    a = pd.Series(np.linspace(100, 130, len(days)), index=days)
    b = pd.Series(np.linspace(200, 150, len(days)), index=days)
    prices = pd.DataFrame({"AAA": a, "BBB": b})
    fill, as_of = pd.Timestamp("2026-09-01"), pd.Timestamp("2026-09-30")
    book = pd.DataFrame([
        {"Symbol": "AAA", "Industry": "Alpha", "Entry Date": fill, "Entry Price": float(a[fill]),
         "Price Now": float(a.iloc[-1]), "Return %": float(a.iloc[-1] / a[fill] - 1), "MTD %": 0.0,
         "Holding (Days)": 29, "Weight %": 0.5, "Rank at Entry": 1, "Rank at Rebalance": 1},
        {"Symbol": "BBB", "Industry": "Beta", "Entry Date": fill, "Entry Price": float(b[fill]),
         "Price Now": float(b.iloc[-1]), "Return %": float(b.iloc[-1] / b[fill] - 1), "MTD %": 0.0,
         "Holding (Days)": 29, "Weight %": 0.5, "Rank at Entry": 2, "Rank at Rebalance": 2},
    ])
    live = 0.5 * (a.iloc[-1] / a[fill] - 1) + 0.5 * (b.iloc[-1] / b[fill] - 1)
    record = {"equity_curve": replay, "benchmark": replay * 0 + 1_000_000,
              "closed_trades": pd.DataFrame(), "tradebook": pd.DataFrame(),
              "live_meta": {"as_of": as_of, "fill_date": fill, "mtd_period": "2026-09",
                            "strategy_mtd": float(live), "benchmark_mtd": 0.0}}
    ledger = {"months": {"2026-08": {"strategy": 0.10, "benchmark": 0.0}}}
    ranking = pd.DataFrame({"Symbol": ["AAA", "BBB"], "Industry": ["Alpha", "Beta"], "Rank": [1, 2]})
    return book, record, ledger, ranking, prices


def test_the_series_runs_to_the_records_session_not_the_last_month_end():
    book, record, ledger, ranking, prices = _fixture()
    s = book_series(book, record, ledger, ranking, prices, None, 1_000_000)
    assert record["equity_curve"].index[-1] == pd.Timestamp("2026-08-31")
    assert s.equity.index[-1] == pd.Timestamp("2026-09-30")
    assert s.equity.iloc[-1] == pytest.approx(s.value)
    assert s.uninvested == pytest.approx(s.value - s.holdings)


def test_drawdown_and_buy_sizing_read_today_not_the_replay():
    book, record, ledger, ranking, prices = _fixture()
    s = book_series(book, record, ledger, ranking, prices, None, 1_000_000)
    replay_dd = float(drawdown(record["equity_curve"]).iloc[-1])
    live_dd = float(drawdown(s.equity).iloc[-1])
    # BBB falls through September, so the book is below its August peak today;
    # the replay alone, ending 31 Aug at its high, said it was at the peak.
    assert replay_dd == pytest.approx(0.0)
    assert live_dd < 0
    w_live = fixed_buy_weight(s.equity, (3, 9), 0.05)
    w_replay = fixed_buy_weight(record["equity_curve"], (3, 9), 0.05)
    assert w_live != pytest.approx(w_replay)
