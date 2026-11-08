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


def test_the_industry_cap_stays_hard_at_the_rebalance():
    sec = {"A": "Pharma", "B": "Pharma", "C": "Pharma", "D": "IT", "NEW": "Pharma", "NEW2": "IT"}
    standing = pd.Series({"A": 0.15, "B": 0.15, "C": 0.15, "D": 0.05, "SOLD": 0.50})
    w = _let_winners_run(_target(["A", "B", "C", "D", "NEW", "NEW2"]), standing,
                         ["A", "B", "C", "D", "SOLD"], 0.15, sec, 0.40)
    pharma = w[["A", "B", "C", "NEW"]].sum()
    assert pharma <= 0.40 + 1e-9                     # 45% kept was scaled to 40%, NEW gets no Pharma room
    assert w["NEW"] == pytest.approx(0.0, abs=1e-9)
    assert w["NEW2"] == pytest.approx(0.15)          # IT had room
    assert w.max() <= 0.15 + 1e-12


def test_the_rule_starts_at_the_30_nov_signal_and_frozen_months_keep_their_fingerprints():
    from src.engine.backtester import _hold_cap_on
    from src.engine.track_record import TRACK_RECORD_CONFIG as cfg
    from src.engine.track_record import config_fingerprint, config_for_month

    assert cfg["hold_cap"] == 0.15 and cfg["hold_cap_from"] == "2026-11-30"
    old = {k: v for k, v in cfg.items() if k not in ("hold_cap", "hold_cap_from", "members_only_scoring_from")}
    for month in ("2026-01", "2026-10", "2026-11"):                # governed by signals before 30 Nov
        assert config_for_month(cfg, month) == old
        assert config_fingerprint(**config_for_month(cfg, month)) == config_fingerprint(**old)
    dec = config_for_month(cfg, "2026-12")
    assert dec["hold_cap"] == 0.15 and dec["hold_cap_from"] == "2026-11-30"
    assert not _hold_cap_on(0.15, "2026-11-30", "2026-10-30")
    assert _hold_cap_on(0.15, "2026-11-30", "2026-11-30")
    assert not _hold_cap_on(None, "2026-11-30", "2027-01-29")
