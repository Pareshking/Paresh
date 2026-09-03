"""Who was in the index, and when — so a backtest cannot buy the future.

Scoring January against today's constituent list lets the strategy hold names
it could not have known to hold. Index additions skew toward recent strong
performers and a momentum screen preferentially buys exactly those, so the bias
runs one way: it flatters.

The data to fix this was never bought. The daily sync has been committing
data/indices/*.csv all along; these tests cover turning those snapshots into a
timeline and holding the backtest to it.
"""
import json

import numpy as np
import pandas as pd
import pytest

from src.core.tickers import is_tradeable_symbol
from src.engine.backtester import run_backtest
from src.engine.membership import (
    coverage,
    describe,
    empty_history,
    load_history,
    members_on,
    record_snapshot,
    save_history,
)


# ── The store ────────────────────────────────────────────────────────────────

def test_a_baseline_is_recorded_verbatim():
    h, changed = record_snapshot(empty_history(), "2026-08-19", ["BBB", "AAA"])
    assert changed
    assert members_on(h, "2026-08-19") == {"AAA", "BBB"}


def test_an_unchanged_day_writes_nothing():
    """Membership rarely moves. A full list per day would be repetition."""
    h, _ = record_snapshot(empty_history(), "2026-08-19", ["AAA", "BBB"])
    h, changed = record_snapshot(h, "2026-08-20", ["BBB", "AAA"])
    assert changed is False
    assert h["changes"] == []


def test_diffs_reconstruct_membership_at_any_date():
    h, _ = record_snapshot(empty_history(), "2026-01-05", ["AAA", "BBB", "CCC"])
    h, _ = record_snapshot(h, "2026-04-01", ["AAA", "CCC", "DDD"])
    h, _ = record_snapshot(h, "2026-09-30", ["AAA", "DDD", "EEE"])

    assert members_on(h, "2026-01-05") == {"AAA", "BBB", "CCC"}
    assert members_on(h, "2026-03-31") == {"AAA", "BBB", "CCC"}
    assert members_on(h, "2026-04-01") == {"AAA", "CCC", "DDD"}
    assert members_on(h, "2026-09-29") == {"AAA", "CCC", "DDD"}
    assert members_on(h, "2026-09-30") == {"AAA", "DDD", "EEE"}
    assert members_on(h, "2027-06-01") == {"AAA", "DDD", "EEE"}


def test_a_date_before_coverage_is_unknown_not_guessed():
    """None must never be silently replaced by today's list.

    That substitution is the exact bias this module removes, and it would look
    from the outside as though it had been removed.
    """
    h, _ = record_snapshot(empty_history(), "2026-08-19", ["AAA"])
    assert members_on(h, "2026-08-18") is None
    assert members_on(empty_history(), "2026-08-19") is None


def test_history_is_append_only_and_chronological():
    h, _ = record_snapshot(empty_history(), "2026-08-19", ["AAA"])
    h, _ = record_snapshot(h, "2026-09-01", ["AAA", "BBB"])
    with pytest.raises(ValueError, match="append-only"):
        record_snapshot(h, "2026-08-25", ["AAA", "CCC"])
    with pytest.raises(ValueError, match="append-only"):
        record_snapshot(h, "2026-09-01", ["ZZZ"])


def test_placeholders_are_not_constituents():
    """DUMMY rows come and go; they must not register as membership churn."""
    h, _ = record_snapshot(empty_history(), "2026-08-19", ["AAA", "DUMMYTRVN"])
    assert members_on(h, "2026-08-19") == {"AAA"}
    h, changed = record_snapshot(h, "2026-08-20", ["AAA", "DUMMYINGL1", "DUMMYINGL2"])
    assert changed is False, "placeholder churn is not membership churn"
    assert not is_tradeable_symbol("DUMMYTRVN")


def test_an_empty_snapshot_is_refused():
    """A failed download must not erase the index."""
    with pytest.raises(ValueError):
        record_snapshot(empty_history(), "2026-08-19", [])


def test_round_trip_and_corrupt_file(tmp_path):
    h, _ = record_snapshot(empty_history(), "2026-08-19", ["AAA", "BBB"])
    h, _ = record_snapshot(h, "2026-09-30", ["AAA", "CCC"])
    path = tmp_path / "membership.json"
    save_history(h, path)
    assert load_history(path)["changes"] == h["changes"]
    assert members_on(load_history(path), "2026-09-30") == {"AAA", "CCC"}

    bad = tmp_path / "bad.json"
    bad.write_text('{"nope": 1}')
    with pytest.raises(ValueError):
        load_history(bad)


def test_coverage_and_describe():
    h, _ = record_snapshot(empty_history(), "2026-08-19", ["AAA", "BBB"])
    h, _ = record_snapshot(h, "2026-09-30", ["AAA", "CCC"])
    first, last = coverage(h)
    assert (first.isoformat(), last.isoformat()) == ("2026-08-19", "2026-09-30")
    info = describe(h)
    assert info["snapshots_with_changes"] == 1
    assert info["total_churn"] == 2      # BBB out, CCC in
    assert info["current_size"] == 2


def test_the_shipped_history_is_readable():
    h = load_history()
    if h.get("baseline"):
        first, last = coverage(h)
        assert first is not None and last >= first
        assert len(members_on(h, last)) > 100


# ── The backtest ─────────────────────────────────────────────────────────────

def _prices(cols=40, periods=760, end="2026-09-03", seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=end, periods=periods)
    names = [f"S{i}" for i in range(cols)]
    return pd.DataFrame(
        100 + np.cumsum(rng.normal(0, 1, (periods, cols)), axis=0),
        index=idx, columns=names,
    )


def _run(px, tag, **kw):
    return run_backtest(
        tag, px, top_n=20, rebal_freq=21, ema_period=20,
        high_pct=0.0, cost_bps=30.0, buffer_n=30, **kw,
    )


@pytest.fixture
def joined_in_july():
    """S0-S9 join the index on 1 Jul 2026; before that they are not members."""
    px = _prices()
    cols = list(px.columns)
    h, _ = record_snapshot(empty_history(), "2026-01-02", cols[10:])
    h, _ = record_snapshot(h, "2026-07-01", cols)
    return px, h, set(cols[:10])


def test_a_stock_cannot_be_traded_before_it_joined_the_index(joined_in_july):
    px, history, newcomers = joined_in_july
    res = _run(px, "pit_excl", _membership=history)
    tb = res["tradebook"]
    early = tb[pd.to_datetime(tb["Period Start"]) < "2026-07-01"]
    assert not (set(early["Symbol"]) & newcomers), (
        "the backtest traded a stock before it was in the index"
    )


def test_without_membership_the_same_run_does_trade_them(joined_in_july):
    """The control: the bias is real and this fixture exhibits it."""
    px, _, newcomers = joined_in_july
    res = _run(px, "pit_control")
    tb = res["tradebook"]
    early = tb[pd.to_datetime(tb["Period Start"]) < "2026-07-01"]
    assert set(early["Symbol"]) & newcomers, (
        "fixture no longer demonstrates survivorship bias; the comparison "
        "test above would pass trivially"
    )


def test_the_run_reports_how_much_of_it_was_survivorship_free(joined_in_july):
    px, history, _ = joined_in_july
    with_pit = _run(px, "pit_count", _membership=history)["stats"]
    without = _run(px, "pit_count_off")["stats"]

    assert with_pit["pit_periods"] > 0
    assert with_pit["current_universe_periods"] == 0
    assert with_pit["pit_from"] is not None

    assert without["pit_periods"] == 0
    assert without["current_universe_periods"] > 0
    assert without["pit_from"] is None


def test_membership_starting_mid_run_is_reported_as_partial():
    """Coverage that begins inside the window must not claim the whole run."""
    px = _prices()
    h, _ = record_snapshot(empty_history(), "2026-07-01", list(px.columns))
    stats = _run(px, "pit_partial", _membership=h)["stats"]
    assert stats["pit_periods"] > 0
    assert stats["current_universe_periods"] > 0, (
        "rebalances before coverage must be counted as current-universe"
    )
    assert pd.Timestamp(stats["pit_from"]) >= pd.Timestamp("2026-07-01")


def test_membership_does_not_disturb_a_run_that_has_none(joined_in_july):
    """Passing no membership must behave exactly as before the feature."""
    px, _, _ = joined_in_july
    a = _run(px, "pit_noop_a")["stats"]["total_return"]
    b = _run(px, "pit_noop_b", _membership=None)["stats"]["total_return"]
    assert a == pytest.approx(b)
