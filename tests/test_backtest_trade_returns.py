"""The blotter and the equity curve must describe the same trades.

The backtest reports a strategy return and, beside it, the entry price, exit
price and return of every position that produced it. Those two accounts were
computed over different windows: the tradebook logged a fill at T+1 and an exit
at T'+1, while the return series compounded from T to T'. It therefore credited
the portfolio the move between the session it ranked on and the session it
claimed to buy on -- look-ahead, in an engine whose docstring promises none --
and a single-stock portfolio could report +0.46% for a month in which its only
holding, by the prices printed next to it, lost 2.06%.
"""
import numpy as np
import pandas as pd
import pytest

from src.engine.backtester import (
    _fill_price,
    _round_trip_return,
    completed_month_window,
    run_backtest,
)


def _prices(seed: int = 11, n: int = 900, cols: int = 12, end: str = "2026-08-18"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=end, periods=n)
    return pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0.0006, 0.02, (n, cols)), axis=0)),
        index=idx,
        columns=[f"S{i}" for i in range(cols)],
    )


def _single_stock_run(tag: str, px: pd.DataFrame):
    """One holding, no costs: the period return IS that stock's return."""
    return run_backtest(
        tag, px, top_n=1, rebal_freq=21, ema_period=20, high_pct=0.0,
        cost_bps=0.0, buffer_n=1,
    )


def test_period_return_is_the_move_between_the_two_fills():
    px = _prices()
    res = _single_stock_run("fills", px)
    assert res is not None

    tradebook = res["tradebook"]
    for _, period in res["monthly"].iterrows():
        held = tradebook[
            (tradebook["Period"] == period["Period"])
            & tradebook["Action"].str.contains("BUY|HOLD")
        ]
        symbol = held["Symbol"].iloc[0]
        entry = px.loc[period["Period Start"], symbol]
        exit_ = px.loc[period["Period End"], symbol]
        assert period["Strategy Net"] == pytest.approx(exit_ / entry - 1, rel=1e-9)


def test_closed_trade_return_matches_the_period_that_held_it():
    """The realised-trades tab and the monthly tab cannot disagree."""
    px = _prices()
    res = _single_stock_run("agree", px)
    closed = res["closed_trades"]
    monthly = res["monthly"]

    assert len(closed) == len(monthly), "one holding per period, closed or open"
    for (_, trade), (_, period) in zip(closed.iterrows(), monthly.iterrows()):
        assert trade["Return %"] == pytest.approx(period["Strategy Net"], rel=1e-9)
        assert trade["Entry Price"] == pytest.approx(
            px.loc[period["Period Start"], trade["Symbol"]]
        )
        assert trade["Exit Price"] == pytest.approx(
            px.loc[period["Period End"], trade["Symbol"]]
        )


def test_no_return_is_credited_before_the_fill():
    """Nothing accrues between the signal close (T) and the fill close (T+1).

    The equity curve's first date is T+2. Starting it at T+1 booked the
    T -> T+1 move, which is the return of a position bought at the close of the
    very session whose prices produced the ranking.
    """
    px = _prices()
    res = _single_stock_run("causal", px)
    equity = res["equity_curve"]
    tradebook = res["tradebook"]

    first_fill = res["monthly"]["Period Start"].iloc[0]
    fill_pos = px.index.get_loc(first_fill)
    symbol = tradebook["Symbol"].iloc[0]

    # The curve is based at the fill; its first move is the fill -> next
    # session move, never the signal -> fill move that preceded ownership.
    assert equity.index[1] == px.index[fill_pos + 1]
    first_move = equity.iloc[1] / equity.iloc[0] - 1
    held = px[symbol]
    assert first_move == pytest.approx(
        held.iloc[fill_pos + 1] / held.iloc[fill_pos] - 1, rel=1e-9
    )
    assert first_move != pytest.approx(
        held.iloc[fill_pos] / held.iloc[fill_pos - 1] - 1, rel=1e-9
    )


def test_open_positions_are_marked_inside_the_reported_window():
    """A position still open at the end is marked at the window's last session.

    It used to be marked at prices.index[-1] -- a date in the month still in
    progress, which the backtest explicitly excludes -- so the blotter showed a
    return over a period the equity curve never covered.
    """
    px = _prices()
    res = _single_stock_run("openmark", px)
    _, window_end = completed_month_window(pd.DatetimeIndex(px.index), 6)

    open_rows = res["closed_trades"][res["closed_trades"]["Status"] == "Open"]
    assert not open_rows.empty, "fixture must leave a position open"
    last_session = res["equity_curve"].index[-1]
    assert last_session <= window_end

    for _, row in open_rows.iterrows():
        assert f"{last_session:%d %b %Y}" in row["Exit Date"]
        assert row["Exit Price"] == pytest.approx(px.loc[last_session, row["Symbol"]])


def test_total_return_is_every_period_compounded():
    """No day is dropped -- least of all the first, which carries the cost of
    establishing the portfolio at 100% turnover."""
    px = _prices()
    res = run_backtest("total", px, top_n=5, rebal_freq=21, ema_period=20,
                       high_pct=0.0, cost_bps=30.0, buffer_n=8)
    periods = res["monthly"]["Strategy Net"]
    assert res["stats"]["total_return"] == pytest.approx(
        float(np.prod(1 + periods) - 1), rel=1e-9
    )


def test_equity_curve_is_indexed_at_one_on_the_fill_date():
    px = _prices()
    res = _single_stock_run("base", px)
    equity = res["equity_curve"]
    assert equity.iloc[0] == pytest.approx(1.0)
    assert equity.index[0] == res["monthly"]["Period Start"].iloc[0]


def test_establishment_cost_is_charged_against_the_reported_return():
    """A free run and a costed run must differ by the friction, not by zero."""
    px = _prices()
    free = run_backtest("free", px, top_n=5, rebal_freq=21, ema_period=20,
                        high_pct=0.0, cost_bps=0.0, buffer_n=8)
    costed = run_backtest("costed", px, top_n=5, rebal_freq=21, ema_period=20,
                          high_pct=0.0, cost_bps=30.0, buffer_n=8)
    assert costed["stats"]["total_return"] < free["stats"]["total_return"]
    # The first rebalance establishes the whole book: 100% turnover at 30 bps.
    assert costed["monthly"]["Cost Drag %"].iloc[0] == pytest.approx(0.30)


def test_equity_dates_are_unique_and_ordered():
    """Recorded as the loop runs, so a skipped period cannot shift the curve."""
    res = _single_stock_run("dates", _prices())
    idx = res["equity_curve"].index
    assert idx.is_monotonic_increasing
    assert not idx.duplicated().any()


# ── Fill prices ─────────────────────────────────────────────────────────────

def test_fill_price_carries_the_last_real_print_over_a_holed_session():
    px = pd.DataFrame(
        {"A": [10.0, np.nan, 12.0]}, index=pd.bdate_range("2026-01-01", periods=3)
    )
    assert _fill_price(px, "A", 1) == 10.0


def test_fill_price_is_nan_when_the_stock_has_never_traded():
    px = pd.DataFrame(
        {"A": [np.nan, np.nan, 12.0]}, index=pd.bdate_range("2026-01-01", periods=3)
    )
    assert np.isnan(_fill_price(px, "A", 1))
    assert np.isnan(_fill_price(px, "MISSING", 1))


@pytest.mark.parametrize("entry,exit_", [(np.nan, 10.0), (10.0, np.nan), (0.0, 10.0)])
def test_a_trade_without_prices_reports_nan_not_a_flat_zero(entry, exit_):
    """A fabricated 0.00% round trip lands in the win rate as a real trade."""
    assert np.isnan(_round_trip_return(entry, exit_))


def test_round_trip_return_is_the_plain_ratio():
    assert _round_trip_return(157.65, 168.40) == pytest.approx(168.40 / 157.65 - 1)
