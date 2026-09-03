"""The backtest answers "how did it do"; this answers "what do I do on Monday".

The reported window deliberately stops at the last completed month, so the
month-end signal that a person actually has to trade on -- the one filling on
the first session of the current month -- is filtered out of every table on the
page. The live book and pending action list put it back, WITHOUT letting live
marks leak into the performance figures.
"""
import numpy as np
import pandas as pd
import pytest

from src.engine.backtester import (
    _select_holdings,
    completed_month_window,
    run_backtest,
)


def _prices(end: str = "2026-09-03", periods: int = 760, cols: int = 40, seed: int = 7):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=end, periods=periods)
    return pd.DataFrame(
        100 + np.cumsum(rng.normal(0, 1, (periods, cols)), axis=0),
        index=idx,
        columns=[f"S{i}" for i in range(cols)],
    )


def _run(prices, tag, **kw):
    return run_backtest(
        tag, prices, top_n=20, rebal_freq=21,
        ema_period=20, high_pct=0.0, cost_bps=30.0, buffer_n=30, **kw,
    )


# ── The live book ────────────────────────────────────────────────────────────

def test_live_book_lists_every_open_position_with_its_entry_date():
    px = _prices()
    res = _run(px, "lb_basic")
    lb = res["live_book"]
    assert not lb.empty
    for col in ("Symbol", "Entry Date", "Entry Price", "Price Now",
                "Return %", "Holding (Days)", "Weight %"):
        assert col in lb.columns
    assert lb["Entry Date"].notna().all()


def test_live_book_marks_at_the_latest_close_not_the_window_end():
    """The whole point: the blotter is frozen at the window, this is not.

    The realised-trade blotter marks open positions at the last session of the
    completed-month window (a rule its own test pins). A person holding the
    portfolio needs today's price, so the live book marks at the latest close --
    a strictly later date, and a different number.
    """
    px = _prices()
    res = _run(px, "lb_mark")
    _, window_end = completed_month_window(pd.DatetimeIndex(px.index), 6)
    as_of = res["live_meta"]["as_of"]

    assert as_of == px.index[-1]
    assert as_of > window_end, "fixture must run past the completed-month window"

    for _, row in res["live_book"].iterrows():
        assert row["Price Now"] == pytest.approx(px.loc[as_of, row["Symbol"]])


def test_live_marks_never_leak_into_the_reported_performance():
    """Adding the live view must not move a single performance figure."""
    px = _prices()
    res = _run(px, "lb_leak")
    _, window_end = completed_month_window(pd.DatetimeIndex(px.index), 6)

    assert res["equity_curve"].index[-1] <= window_end
    assert res["monthly"]["Period End"].max() <= window_end
    open_rows = res["closed_trades"][res["closed_trades"]["Status"] == "Open"]
    for _, row in open_rows.iterrows():
        assert row["Exit Price"] == pytest.approx(
            px.loc[res["equity_curve"].index[-1], row["Symbol"]]
        )


def test_open_position_label_states_its_mark_date():
    """"Active (Aug-2026)" read as "August is the current month"; it never was."""
    px = _prices()
    res = _run(px, "lb_label")
    last_session = res["equity_curve"].index[-1]
    open_rows = res["closed_trades"][res["closed_trades"]["Status"] == "Open"]
    assert not open_rows.empty
    for _, row in open_rows.iterrows():
        assert f"{last_session:%d %b %Y}" in row["Month"]


# ── The pending rebalance ────────────────────────────────────────────────────

def test_pending_signal_is_the_month_end_the_window_excluded():
    px = _prices()
    res = _run(px, "pend_sig")
    _, window_end = completed_month_window(pd.DatetimeIndex(px.index), 6)
    meta = res["live_meta"]

    assert meta["has_pending"]
    # The signal is struck AT the window's last close; it is the FILL that
    # falls outside, which is exactly why the window filter (which tests the
    # fill date) drops this rebalance from every reported table.
    assert meta["signal_date"] <= window_end
    assert meta["fill_date"] > window_end
    # It is a month end: no later session shares its calendar month.
    same_month = px.index[
        (px.index.to_period("M") == meta["signal_date"].to_period("M"))
    ]
    assert meta["signal_date"] == same_month.max()
    assert meta["fill_date"] > meta["signal_date"]
    assert meta["fill_date"] in px.index, "the fill session must actually exist"


def test_pending_signal_is_a_closed_month_end_not_the_trailing_edge():
    """The in-progress month's last available session is not a month end.

    `last_by_month` returns the final AVAILABLE session per calendar month, so
    for the running month it returns whatever date the tape stops on -- 3 Sep on
    this fixture. Treating that as a signal invents a rebalance on an arbitrary
    Thursday, and leaves it with no session to fill on.
    """
    px = _prices(end="2026-09-03")
    res = _run(px, "pend_edge")
    meta = res["live_meta"]

    assert meta["signal_date"].to_period("M") < px.index[-1].to_period("M")
    assert meta["signal_date"] != px.index[-1]
    assert meta["signal_date"] == pd.Timestamp("2026-08-31")
    assert meta["fill_date"] == pd.Timestamp("2026-09-01")


def test_action_list_reconciles_current_book_to_target_book():
    """SELLs leave, BUYs arrive, HOLDs stay -- and the arithmetic closes."""
    px = _prices()
    res = _run(px, "pend_recon")
    pending, target = res["pending_actions"], res["target_book"]
    current = set(res["live_book"]["Symbol"])

    sells = set(pending[pending["Action"] == "🔴 SELL"]["Symbol"])
    buys = set(pending[pending["Action"] == "🟢 BUY"]["Symbol"])
    holds = set(pending[pending["Action"] == "⚪ HOLD"]["Symbol"])

    assert sells <= current, "cannot sell what is not held"
    assert not (buys & current), "cannot buy what is already held"
    assert holds == current - sells
    assert set(target["Symbol"]) == (current - sells) | buys
    assert len(target) <= 20


def test_target_weights_sum_to_one_book():
    px = _prices()
    res = _run(px, "pend_wts")
    total = res["target_book"]["Target Weight %"].sum()
    assert total == pytest.approx(100.0, abs=1e-6)


def test_every_sell_states_why():
    px = _prices()
    res = _run(px, "pend_why")
    sells = res["pending_actions"][res["pending_actions"]["Action"] == "🔴 SELL"]
    for _, row in sells.iterrows():
        assert row["Reason"].strip()
        assert row["Target Weight %"] == 0.0


def test_pending_uses_the_same_buffer_rule_as_the_backtest():
    """A preview that sold a name the engine would have retained is worse than none.

    Selection runs through one shared helper; this pins the behaviour that
    matters -- an incumbent inside the buffer but outside the top N is kept,
    and a fresh name at the same rank is not taken.
    """
    ranked = pd.Series(
        np.linspace(3.0, -3.0, 40), index=[f"S{i}" for i in range(40)]
    )
    incumbent = "S24"  # rank 25: outside top 20, inside a 30-wide buffer
    kept = _select_holdings(ranked, [incumbent], top_n=20, effective_buffer=30)
    assert incumbent in kept
    assert len(kept) == 20

    fresh = _select_holdings(ranked, [], top_n=20, effective_buffer=30)
    assert incumbent not in fresh


def test_incumbent_past_the_buffer_is_dropped():
    ranked = pd.Series(
        np.linspace(3.0, -3.0, 40), index=[f"S{i}" for i in range(40)]
    )
    assert "S35" not in _select_holdings(
        ranked, ["S35"], top_n=20, effective_buffer=30
    )


def test_a_name_that_fails_its_filters_is_sold_not_silently_kept():
    """Dropping out of the ranked frame entirely must surface as a SELL."""
    px = _prices()
    res = _run(px, "pend_filter")
    pending = res["pending_actions"]
    assert set(pending["Action"]) <= {"🟢 BUY", "🔴 SELL", "⚪ HOLD"}
    # Every currently-held name is accounted for by exactly one row.
    held = set(res["live_book"]["Symbol"])
    accounted = set(
        pending[pending["Action"].isin(["🔴 SELL", "⚪ HOLD"])]["Symbol"]
    )
    assert accounted == held


def test_counts_in_meta_match_the_action_list():
    px = _prices()
    res = _run(px, "pend_counts")
    pending, meta = res["pending_actions"], res["live_meta"]
    assert meta["n_buys"] == (pending["Action"] == "🟢 BUY").sum()
    assert meta["n_sells"] == (pending["Action"] == "🔴 SELL").sum()
    assert meta["n_holds"] == (pending["Action"] == "⚪ HOLD").sum()


def test_tape_ending_on_a_month_end_previews_the_prior_month_signal():
    """Data through 31 Aug: Aug has not closed as far as the window is concerned.

    The window covers Feb-Jul, so the 31 Jul signal (filling 3 Aug) is the one
    excluded from every reported table and therefore the one to preview. The
    31 Aug session itself is the tape's trailing edge and must not be used.
    """
    px = _prices(end="2026-08-31")
    res = _run(px, "pend_month_end")
    meta = res["live_meta"]

    assert meta["has_pending"]
    assert meta["signal_date"] == pd.Timestamp("2026-07-31")
    assert meta["fill_date"] == pd.Timestamp("2026-08-03")
    assert not res["live_book"].empty
