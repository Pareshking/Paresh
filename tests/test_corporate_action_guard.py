"""A -79% session is not a price move. NSE does not permit one.

Circuit limits cap almost every NSE stock at 5%, 10% or 20% a session, so a
move far past that is a stock split, a bonus issue or a demerger showing up in
the price series as though money had evaporated. A momentum backtest reads it
as a catastrophic loss that never occurred -- and the live 2-year frame carries
twelve of them across 750 symbols, one of them dated yesterday.
"""
import numpy as np
import pandas as pd
import pytest

from src.engine.corporate_actions import (
    COMMON_ACTIONS,
    IMPLAUSIBLE_MOVE,
    RATIO_TOLERANCE,
    classify_ratio,
    detect,
    summarise,
)


def _frame(moves: dict[str, dict[int, float]], n: int = 40) -> pd.DataFrame:
    """Flat price series at 100, with a multiplicative jump on chosen rows."""
    idx = pd.bdate_range("2026-01-01", periods=n)
    data = {}
    for sym, jumps in moves.items():
        series = np.full(n, 100.0)
        for row, ratio in jumps.items():
            series[row:] *= ratio
        data[sym] = series
    return pd.DataFrame(data, index=idx)


# ── Detection ────────────────────────────────────────────────────────────────

def test_a_split_sized_drop_is_flagged():
    found = detect(_frame({"AAA": {20: 0.2}}))
    assert len(found) == 1
    row = found.iloc[0]
    assert row["Symbol"] == "AAA"
    assert row["Ratio"] == pytest.approx(0.2)
    assert row["Looks Like"] == "1:5 split"
    assert row["Kind"] == "split/bonus"


def test_an_ordinary_move_is_not_flagged():
    """Within circuit limits is a real price move, however unpleasant."""
    assert detect(_frame({"AAA": {20: 0.82}})).empty   # -18%
    assert detect(_frame({"AAA": {20: 1.19}})).empty   # +19%


def test_a_move_that_matches_no_split_is_reported_as_possible_demerger():
    """Demergers leave no clean ratio, and yfinance does not adjust for them.

    Forcing one into the nearest split label would invite a "correction" that
    corrupts the data further, so it stays explicitly unclassified.
    """
    found = detect(_frame({"AAA": {20: 0.351}}))       # VEDL-shaped
    assert found.iloc[0]["Kind"] == "unclassified"
    assert "demerger" in found.iloc[0]["Looks Like"]


def test_a_reverse_split_is_flagged_too():
    found = detect(_frame({"AAA": {20: 5.0}}))
    assert found.iloc[0]["Looks Like"] == "5:1 reverse split"
    assert found.iloc[0]["Move %"] == pytest.approx(4.0)


def test_results_are_worst_first():
    found = detect(_frame({"AAA": {10: 0.5}, "BBB": {10: 0.2}, "CCC": {10: 0.45}}))
    assert list(found["Symbol"]) == ["BBB", "CCC", "AAA"]


def test_every_flagged_row_carries_the_prices_behind_it():
    """A flag nobody can verify is a flag nobody will act on."""
    found = detect(_frame({"AAA": {20: 0.25}}))
    row = found.iloc[0]
    assert row["Prev Close"] == pytest.approx(100.0)
    assert row["Close"] == pytest.approx(25.0)
    assert row["Close"] / row["Prev Close"] == pytest.approx(row["Ratio"])


def test_missing_prices_do_not_raise_or_flag():
    frame = _frame({"AAA": {20: 1.0}})
    frame.iloc[10] = np.nan
    assert detect(frame).empty


def test_a_threshold_can_be_tightened():
    frame = _frame({"AAA": {20: 0.7}})     # -30%, inside the default
    assert detect(frame).empty
    assert len(detect(frame, threshold=0.25)) == 1


def test_since_limits_the_scan_window():
    frame = _frame({"AAA": {5: 0.2}})
    assert len(detect(frame)) == 1
    assert detect(frame, since="2026-02-01").empty


def test_empty_input_is_handled():
    assert detect(pd.DataFrame()).empty
    assert detect(None).empty
    assert summarise(pd.DataFrame())["total"] == 0


# ── Classification ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("ratio,expected", list(COMMON_ACTIONS.items()))
def test_every_known_action_classifies_exactly(ratio, expected):
    label, gap = classify_ratio(ratio)
    assert label == expected
    assert gap == pytest.approx(0.0, abs=1e-9)


def test_a_near_miss_still_classifies():
    """Real data drifts: TDPOWERSYS came in at 0.5083, not 0.5000."""
    label, gap = classify_ratio(0.5083)
    assert label == "1:2 split or 1:1 bonus"
    assert gap <= RATIO_TOLERANCE


def test_a_clear_miss_does_not_classify():
    label, _ = classify_ratio(0.2125)   # INDIAGLYCO
    assert "demerger" in label


def test_an_unusable_ratio_is_named_as_such():
    assert classify_ratio(0.0)[0] == "unusable price"
    assert classify_ratio(float("nan"))[0] == "unusable price"
    assert classify_ratio(-1.0)[0] == "unusable price"


def test_the_threshold_sits_clear_of_nse_circuit_limits():
    """20% is the widest ordinary band; the threshold must not catch one."""
    assert IMPLAUSIBLE_MOVE > 0.20


def test_summary_counts_by_kind():
    found = detect(_frame({"AAA": {10: 0.5}, "BBB": {10: 0.351}}))
    info = summarise(found)
    assert info["total"] == 2
    assert info["split_like"] == 1
    assert info["unclassified"] == 1
    assert info["symbols"] == ["AAA", "BBB"]
    assert info["worst"]["symbol"] == "BBB"
