"""The screener must price a split the same way the backtester does.

Two defects, found by measuring the published snapshot rather than by reading
the code, which looked right.

ONE. ``adjust_prices`` applied every logged event unconditionally. Its own
docstring promised the opposite -- "if the vendor later restates the series
itself, the jump disappears, the guard stops flagging it, and nothing is
applied" -- but the events come from a COMMITTED LOG, not from a live scan, so
nothing ever re-checked them against the prices in hand. Yahoo restates a
split-adjusted Indian series one to four weeks after the action, which is
precisely the window this log exists to cover. On the day that landed, a 1:3
split would have been divided by three a second time and read as 1:9.

TWO. ``run_backtest`` neutralised these events. The SCREENER did not. The same
stock was therefore priced two different ways by two tabs of one app. Measured
against the snapshot on 2026-09-15: all fourteen logged events were still
present in the prices, and eight of them sat inside a live momentum lookback --
PGIL, HEG, INDIAGLYCO and TDPOWERSYS inside all five, so every weight in those
four scores was drawn across a crash that never happened.
"""

import numpy as np
import pandas as pd
import pytest

from src.engine.corporate_actions import adjust_ohlc, adjust_prices

SPLIT = {"symbol": "AAA", "date": "2026-06-15", "ratio": 0.3333, "kind": "split/bonus"}


def _series_with_a_split():
    """A stock that drifts up, then shows an unadjusted 1:3 split step."""
    idx = pd.date_range("2026-05-01", "2026-07-31", freq="B")
    before = idx < pd.Timestamp("2026-06-15")
    values = np.where(before, np.linspace(300.0, 330.0, len(idx)),
                      np.linspace(300.0, 330.0, len(idx)) * 0.3333)
    return pd.DataFrame({"AAA": values}, index=idx)


def _restated():
    """The same stock after the vendor has adjusted the history itself."""
    idx = pd.date_range("2026-05-01", "2026-07-31", freq="B")
    return pd.DataFrame({"AAA": np.linspace(100.0, 110.0, len(idx))}, index=idx)


def _worst_daily_move(frame):
    r = frame["AAA"] / frame["AAA"].shift(1)
    return float((r - 1.0).abs().max())


# ── The step is removed when it is really there ──────────────────────────────

def test_an_unrestated_split_is_neutralised():
    raw = _series_with_a_split()
    assert _worst_daily_move(raw) > 0.35, "fixture is not showing a split step"

    out, applied = adjust_prices(raw, [SPLIT])
    assert len(applied) == 1
    assert _worst_daily_move(out) < 0.05, "the phantom crash survived adjustment"


def test_the_adjustment_leaves_the_current_price_alone():
    """Only history is rescaled. CMP on the page must stay the traded price."""
    raw = _series_with_a_split()
    out, _ = adjust_prices(raw, [SPLIT])
    assert out["AAA"].iloc[-1] == pytest.approx(raw["AAA"].iloc[-1])


# ── ...and NOT applied a second time once the vendor catches up ──────────────

def test_a_restated_series_is_left_alone():
    """The defect: the log outlives the jump, and the ratio was applied anyway."""
    restated = _restated()
    out, applied = adjust_prices(restated, [SPLIT])
    assert applied == [], "re-applied a split the vendor had already adjusted"
    pd.testing.assert_frame_equal(out, restated)


def test_double_adjustment_would_have_been_a_one_to_nine_split():
    """Name the damage, so nobody 'simplifies' the check away.

    Without the re-verification, a restated 1:3 comes back divided by three
    again -- the history sits at a ninth of where it belongs and the stock
    reads as the best momentum name in the universe.
    """
    restated = _restated()
    out, _ = adjust_prices(restated, [SPLIT])
    early = out["AAA"].iloc[0]
    assert early == pytest.approx(restated["AAA"].iloc[0]), (
        f"history was rescaled to {early:.1f} against a correct {restated['AAA'].iloc[0]:.1f}"
    )


def test_an_event_for_an_absent_symbol_is_ignored():
    frame = _restated().rename(columns={"AAA": "BBB"})
    out, applied = adjust_prices(frame, [SPLIT])
    assert applied == []
    pd.testing.assert_frame_equal(out, frame)


def test_an_event_before_the_frame_starts_is_ignored():
    raw = _series_with_a_split()
    old = {**SPLIT, "date": "2020-01-01"}
    _, applied = adjust_prices(raw, [old])
    assert applied == []


# ── Every price frame moves together ─────────────────────────────────────────

def test_adjust_ohlc_rescales_close_high_and_low_alike():
    """A close adjusted against an unadjusted high is worse than doing nothing.

    It leaves the stock permanently far below a 52-week high it never actually
    fell from, so the Near-52W-High gate excludes it forever.
    """
    close = _series_with_a_split()
    high = close * 1.02
    low = close * 0.98
    frames, applied = adjust_ohlc(
        {"adj_close": close, "close": close, "high": high, "low": low}, [SPLIT]
    )
    assert len(applied) == 1, "applied should be reported once, not once per frame"
    for name, frame in frames.items():
        assert _worst_daily_move(frame) < 0.05, f"{name} still carries the split step"

    # And the relationship between them is preserved.
    assert (frames["high"]["AAA"] >= frames["close"]["AAA"] - 1e-9).all()
    assert (frames["low"]["AAA"] <= frames["close"]["AAA"] + 1e-9).all()


def test_adjust_ohlc_with_no_events_is_a_faithful_passthrough():
    close = _series_with_a_split()
    frames, applied = adjust_ohlc({"close": close}, [])
    assert applied == []
    pd.testing.assert_frame_equal(frames["close"], close)


# ── The real log, against the real shipped data ──────────────────────────────

def test_every_logged_event_carries_a_usable_ratio():
    """adjust_prices silently skips an event it cannot read. Catch that here."""
    from src.engine.corporate_actions import load_events

    events = load_events()
    assert events, "the corporate action log is empty"
    for event in events:
        ratio = float(event["ratio"])
        assert np.isfinite(ratio) and 0 < ratio < 20, f"{event['symbol']}: {ratio}"
        pd.Timestamp(event["date"])  # raises if unparseable


# ── The all-time high is a SEPARATE download and needs its own fix ───────────
#
# Adjusting the price frame fixes the 52-week high, because that number is
# computed from the frame. It does NOT fix the all-time high, which arrives as
# a per-symbol CSV the nightly job rebuilds from its own ten-year download.
#
# momentum.py takes max(snapshot_ath, window_high), and a high left on a
# pre-split scale is by construction the LARGER one -- so it wins that max and
# defeats the frame adjustment beside it. ABFRL read -86.5% from a high of
# 364.4 against a close of 49.0. "At ATH" is an entry gate, so that is a
# permanent lockout.
#
# THE OBVIOUS FIX IS WRONG, and the shipped CSV proves it. That file is MIXED:
# of the fourteen flagged names, eleven highs sat on the pre-action scale and
# three -- PGIL, PARAS, TDPOWERSYS -- were already restated, because the
# nightly job re-downloads afresh and Yahoo restates some symbols and not
# others. Rescaling every pre-action high by its ratio would have halved those
# three. So the untrustworthy entries are dropped instead, and the max() falls
# through to a window high this codebase adjusted itself.

from src.engine.corporate_actions import trustworthy_ath


def test_a_high_recorded_before_the_action_is_dropped():
    highs = pd.Series({"AAA": 300.0})
    peaks = pd.Series({"AAA": "2026-01-10"})   # before the 2026-06-15 split
    assert pd.isna(trustworthy_ath(highs, peaks, [SPLIT])["AAA"])


def test_a_high_recorded_after_the_action_is_kept():
    """It was printed on the current scale, so it is still the best number."""
    highs = pd.Series({"AAA": 120.0})
    peaks = pd.Series({"AAA": "2026-07-01"})
    assert trustworthy_ath(highs, peaks, [SPLIT])["AAA"] == pytest.approx(120.0)


def test_untouched_symbols_are_never_disturbed():
    highs = pd.Series({"AAA": 300.0, "BBB": 50.0})
    peaks = pd.Series({"AAA": "2026-01-10", "BBB": "2026-01-10"})
    out = trustworthy_ath(highs, peaks, [SPLIT])
    assert out["BBB"] == pytest.approx(50.0)


def test_no_events_means_the_highs_pass_through_untouched():
    highs = pd.Series({"AAA": 300.0, "BBB": 50.0})
    pd.testing.assert_series_equal(
        trustworthy_ath(highs, pd.Series({"AAA": "2026-01-10"}), []), highs
    )


def test_dropping_lets_the_adjusted_window_high_win_the_max():
    """Reproduce momentum.py's max() to show the defect and the repair."""
    window_high = pd.Series({"AAA": 110.0})      # adjusted, vouched for
    stale = pd.Series({"AAA": 300.0})            # pre-split, from the CSV
    peaks = pd.Series({"AAA": "2026-01-10"})

    naive = pd.concat([stale, window_high], axis=1).max(axis=1)
    assert naive["AAA"] == pytest.approx(300.0), "fixture does not show the defect"

    fixed = trustworthy_ath(stale, peaks, [SPLIT])
    together = pd.concat([fixed, window_high], axis=1).max(axis=1)
    assert together["AAA"] == pytest.approx(110.0)


def test_rescaling_by_ratio_would_have_broken_an_already_restated_high():
    """Why this drops rather than rescales -- PGIL's shape, in miniature.

    A peak printed BEFORE the action whose recorded value is ALREADY on the
    post-action scale. The date rule says "pre-action, so rescale"; doing so
    halves a correct number. Dropping it costs only the fallback.
    """
    already_restated = pd.Series({"AAA": 110.0})
    peaks = pd.Series({"AAA": "2026-01-10"})
    window_high = pd.Series({"AAA": 110.0})

    would_have_been = already_restated["AAA"] * SPLIT["ratio"]
    assert would_have_been < window_high["AAA"], "fixture does not show the trap"

    out = trustworthy_ath(already_restated, peaks, [SPLIT])
    together = pd.concat([out, window_high], axis=1).max(axis=1)
    assert together["AAA"] == pytest.approx(110.0), "lost a correct high"


def test_the_engine_carries_the_applied_events():
    """The wiring: app.py hands them in, the engine must hold them."""
    from src.engine.momentum import MomentumEngine

    idx = pd.date_range("2026-01-01", periods=70, freq="B")
    prices = pd.DataFrame({"AAA": np.linspace(100, 120, len(idx))}, index=idx)
    assert MomentumEngine(prices, corporate_actions=[SPLIT]).corporate_actions == [SPLIT]
    # Empty, not None, so callers can iterate it unconditionally.
    assert MomentumEngine(prices).corporate_actions == []
