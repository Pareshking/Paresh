"""Research rule: kept holdings keep their drifted weight up to a cap (owner, 8 Nov 2026)."""
import pandas as pd
import pytest

from src.engine.backtester import _let_winners_run


def _target(names):
    return pd.Series(1.0 / len(names), index=names)


def test_kept_names_keep_their_weight_and_buys_share_what_sells_freed():
    standing = pd.Series({"WIN": 0.12, "MID": 0.05, "LOSE": 0.03, "SOLD": 0.80})
    w = _let_winners_run(_target(["WIN", "MID", "LOSE", "NEW1", "NEW2"]), standing, ["WIN", "MID", "LOSE", "SOLD"], 0.15)
    assert w["WIN"] == pytest.approx(0.12) and w["LOSE"] == pytest.approx(0.03)   # no trim, no top-up
    assert w["NEW1"] == pytest.approx(0.15) and w["NEW2"] == pytest.approx(0.15)  # 0.80 freed, capped at 15%
    assert w.max() <= 0.15 + 1e-12
    assert w.attrs["cash"] == pytest.approx(0.80 - 0.30)                          # the rest cannot be placed


def test_a_winner_above_the_cap_is_trimmed_to_it_and_the_excess_goes_to_buys():
    standing = pd.Series({"BIG": 0.25, "B": 0.05, "SOLD": 0.70})
    w = _let_winners_run(_target(["BIG", "B", "NEW"]), standing, ["BIG", "B", "SOLD"], 0.15)
    assert w["BIG"] == pytest.approx(0.15)
    assert w["NEW"] == pytest.approx(0.15)


def test_with_no_buys_freed_money_goes_to_kept_names_in_proportion():
    standing = pd.Series({"A": 0.40, "B": 0.10, "C": 0.10, "SOLD": 0.40})
    w = _let_winners_run(_target(["A", "B", "C"]), standing, ["A", "B", "C", "SOLD"], 1.0)
    assert w.sum() == pytest.approx(1.0)
    assert w["A"] / w["B"] == pytest.approx(4.0)


def test_a_fresh_book_is_equal_weight():
    w = _let_winners_run(_target(["A", "B", "C", "D"]), pd.Series(dtype=float), [], 0.15)
    assert w.tolist() == pytest.approx([0.15, 0.15, 0.15, 0.15])
    assert w.attrs["cash"] == pytest.approx(0.40)
