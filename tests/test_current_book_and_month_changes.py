"""The backtest answers "how did it do"; this answers "what do I hold today".

The reported window stops at the last completed month, so the rebalance that
fills on the first session of THIS month is filtered out of every table on the
page. That rebalance has already executed by the time anyone looks -- on 3 Sep
the 1 Sep fill is two days old -- so the current book is the book AFTER it, and
the change list is what it did, not what it might do. Live marks must still
never leak into the performance figures.
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

def test_rebalance_signal_is_the_month_end_the_window_excluded():
    px = _prices()
    res = _run(px, "reb_sig")
    _, window_end = completed_month_window(pd.DatetimeIndex(px.index), 6)
    meta = res["live_meta"]

    assert meta["rebalanced"]
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


def test_rebalance_signal_is_a_closed_month_end_not_the_trailing_edge():
    """The in-progress month's last available session is not a month end.

    `last_by_month` returns the final AVAILABLE session per calendar month, so
    for the running month it returns whatever date the tape stops on -- 3 Sep on
    this fixture. Treating that as a signal invents a rebalance on an arbitrary
    Thursday, and leaves it with no session to fill on.
    """
    px = _prices(end="2026-09-03")
    res = _run(px, "reb_edge")
    meta = res["live_meta"]

    assert meta["signal_date"].to_period("M") < px.index[-1].to_period("M")
    assert meta["signal_date"] != px.index[-1]
    assert meta["signal_date"] == pd.Timestamp("2026-08-31")
    assert meta["fill_date"] == pd.Timestamp("2026-09-01")


def test_the_current_book_is_the_book_after_this_months_fill():
    """The headline correction: "current" means post-rebalance, not pre.

    Showing the pre-rebalance book under "Current Holdings" showed last
    month's portfolio -- the names sold on the 1st were still listed and the
    names bought on the 1st were missing entirely.
    """
    px = _prices()
    res = _run(px, "reb_current")
    book = set(res["live_book"]["Symbol"])
    ch = res["month_changes"]

    sold = set(ch[ch["Action"] == "🔴 SOLD"]["Symbol"])
    bought = set(ch[ch["Action"] == "🟢 BOUGHT"]["Symbol"])
    held = set(ch[ch["Action"] == "⚪ HELD"]["Symbol"])

    assert not (sold & book), "a name sold this month is still in the book"
    assert bought <= book, "a name bought this month is missing from the book"
    assert book == held | bought


def test_a_name_bought_this_month_is_dated_to_this_months_fill():
    px = _prices()
    res = _run(px, "reb_dates")
    fill = res["live_meta"]["fill_date"]
    ch = res["month_changes"]
    bought = set(ch[ch["Action"] == "🟢 BOUGHT"]["Symbol"])
    assert bought, "fixture must buy something"

    lb = res["live_book"].set_index("Symbol")
    for s in bought:
        assert pd.Timestamp(lb.loc[s, "Entry Date"]) == fill
        assert lb.loc[s, "Entry Price"] == pytest.approx(px.loc[fill, s])


def test_a_retained_name_keeps_its_original_entry_date():
    """Buffer retention is not a re-entry; the holding period is continuous."""
    px = _prices()
    res = _run(px, "reb_retain")
    fill = res["live_meta"]["fill_date"]
    ch = res["month_changes"]
    held = set(ch[ch["Action"] == "⚪ HELD"]["Symbol"])
    assert held, "fixture must retain something"

    lb = res["live_book"].set_index("Symbol")
    for s in held:
        assert pd.Timestamp(lb.loc[s, "Entry Date"]) < fill


def test_current_book_weights_sum_to_one_book():
    px = _prices()
    res = _run(px, "reb_wts")
    assert res["live_book"]["Weight %"].sum() == pytest.approx(100.0, abs=1e-6)


def test_every_sale_states_why_and_reports_a_realised_return():
    px = _prices()
    res = _run(px, "reb_why")
    ch = res["month_changes"]
    sold = ch[ch["Action"] == "🔴 SOLD"]
    assert not sold.empty
    for _, row in sold.iterrows():
        assert row["Reason"].strip()
        assert row["Weight %"] == 0.0
        # Realised at the fill, not marked at today's close.
        assert row["Exit Price"] == pytest.approx(
            px.loc[res["live_meta"]["fill_date"], row["Symbol"]]
        )


def test_the_rebalance_uses_the_same_buffer_rule_as_the_backtest():
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


def test_every_name_in_the_prior_book_is_accounted_for():
    """Nothing may silently vanish: each prior holding is SOLD or HELD."""
    px = _prices()
    res = _run(px, "reb_account")
    ch = res["month_changes"]
    assert set(ch["Action"]) <= {"🟢 BOUGHT", "🔴 SOLD", "⚪ HELD"}
    assert not ch["Symbol"].duplicated().any(), "a name appears twice"


def test_counts_in_meta_match_the_change_list():
    px = _prices()
    res = _run(px, "reb_counts")
    ch, meta = res["month_changes"], res["live_meta"]
    assert meta["n_bought"] == (ch["Action"] == "🟢 BOUGHT").sum()
    assert meta["n_sold"] == (ch["Action"] == "🔴 SOLD").sum()
    assert meta["n_held"] == (ch["Action"] == "⚪ HELD").sum()
    assert meta["n_held"] + meta["n_bought"] == len(res["live_book"])


def test_tape_ending_on_a_month_end_previews_the_prior_month_signal():
    """Data through 31 Aug: Aug has not closed as far as the window is concerned.

    The window covers Feb-Jul, so the 31 Jul signal (filling 3 Aug) is the one
    excluded from every reported table and therefore the one to preview. The
    31 Aug session itself is the tape's trailing edge and must not be used.
    """
    px = _prices(end="2026-08-31")
    res = _run(px, "reb_month_end")
    meta = res["live_meta"]

    assert meta["rebalanced"]
    assert meta["signal_date"] == pd.Timestamp("2026-07-31")
    assert meta["fill_date"] == pd.Timestamp("2026-08-03")
    assert not res["live_book"].empty
