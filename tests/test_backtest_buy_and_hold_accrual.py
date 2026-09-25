"""Between fills the book is held, not rebalanced back to target every day.

The accrual loop used to apply the TARGET weights to every session's returns,
which is a portfolio rebalanced to target daily at zero cost. Nothing else in
the engine models that: `_drift_holdings` charges turnover on a book that drifts
between fills, the month-to-date figure marks each name from its fill, and the
tradebook records one entry and one exit. A multi-name period return must
therefore equal the weighted buy-and-hold return of its book.
"""
import numpy as np
import pandas as pd
import pytest

from src.engine.backtester import run_backtest


def _prices(seed: int = 5, n: int = 900, cols: int = 12, end: str = "2026-08-18"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=end, periods=n)
    return pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0.0006, 0.02, (n, cols)), axis=0)),
        index=idx,
        columns=[f"S{i}" for i in range(cols)],
    )


def _book_for(tradebook: pd.DataFrame, period: str) -> dict[str, float]:
    rows = tradebook[
        (tradebook["Period"] == period)
        & tradebook["Action"].str.contains("BUY|HOLD")
    ]
    return dict(zip(rows["Symbol"], rows["Weight %"] / 100.0))


def test_multi_name_period_return_is_weighted_buy_and_hold():
    px = _prices()
    res = run_backtest(
        "bnh-multi", px, top_n=4, rebal_freq=21, ema_period=20, high_pct=0.0,
        cost_bps=0.0, buffer_n=4, stock_cap=1.0, sector_cap=1.0,
    )
    assert res is not None
    checked = 0
    for _, period in res["monthly"].iterrows():
        book = _book_for(res["tradebook"], period["Period"])
        start, end = period["Period Start"], period["Period End"]
        expected = sum(
            w * (px.loc[end, s] / px.loc[start, s]) for s, w in book.items()
        ) + (1.0 - sum(book.values())) - 1.0
        assert period["Strategy Net"] == pytest.approx(expected, rel=1e-9, abs=1e-12)
        checked += 1
    assert checked >= 3


def test_a_holed_session_does_not_delete_the_move_across_it():
    """Valued at the last real print, so the move across a hole is booked."""
    px = _prices(seed=7)
    single = dict(top_n=1, rebal_freq=21, ema_period=20, high_pct=0.0,
                  cost_bps=0.0, buffer_n=1)
    clean = run_backtest("hole-clean", px, **single)
    period = clean["monthly"].iloc[-2]
    held = clean["tradebook"][
        (clean["tradebook"]["Period"] == period["Period"])
        & clean["tradebook"]["Action"].str.contains("BUY|HOLD")
    ]["Symbol"].iloc[0]
    inside = px.index[
        (px.index > period["Period Start"]) & (px.index < period["Period End"])
    ]
    holed = px.copy()
    holed.loc[inside[len(inside) // 2], held] = np.nan

    res = run_backtest("hole-holed", holed, **single)
    same = res["monthly"].set_index("Period").loc[period["Period"]]
    assert same["Strategy Net"] == pytest.approx(period["Strategy Net"], rel=1e-9)


def test_an_empty_ranking_liquidates_the_book_and_records_it():
    """Nothing qualifies -> the book is sold, charged for, and sits in cash."""
    px = _prices(seed=3)
    base = dict(top_n=3, rebal_freq=21, ema_period=20, cost_bps=30.0, buffer_n=3)
    normal = run_backtest("empty-normal", px, high_pct=0.0, **base)
    assert normal is not None and len(normal["monthly"]) >= 3

    # A 52-week-high floor no price can reach empties every ranking.
    empty = run_backtest("empty-none", px, high_pct=10.0, **base)
    assert empty is not None
    assert (empty["monthly"]["Holdings"] == 0).all()
    assert (empty["monthly"]["Strategy Net"] == 0.0).all()
    assert empty["closed_trades"].empty or (
        empty["closed_trades"]["Status"] != "Open"
    ).all()
