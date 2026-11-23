"""S211's one date rule is forward-dated for the live record (TRACK_RECORD_CONFIG["window_rule_from"]).

A replay of a month signalled before the go-live keeps the rule the month was struck under
(first session on or after; the last 252 rows for the 52-week high), so frozen months replay
unchanged and the parity gate keeps guarding them. Everything else uses on or before.
"""
import numpy as np
import pandas as pd

from src.engine.backtester import _rolling_high_at
from src.engine.calendar_momentum import period_sharpe_at
from src.engine.track_record import TRACK_RECORD_CONFIG, config_for_month


def _frame():
    # Sessions skip 20 Oct 2026 (a holiday), so a one-month window from 20 Nov opens on it.
    idx = pd.bdate_range("2025-01-01", "2026-11-20")
    idx = idx[idx != pd.Timestamp("2026-10-20")]
    rng = np.random.default_rng(0)
    px = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.01, (len(idx), 3)), axis=0)),
                      index=idx, columns=["A", "B", "C"])
    return px, np.log(px).diff()


def test_legacy_start_opens_on_or_after_and_default_on_or_before():
    px, lr = _frame()
    end = len(px) - 1
    _, new = period_sharpe_at(px, lr, end, 1)
    _, old = period_sharpe_at(px, lr, end, 1, legacy_start=True)
    assert px.index[new] == pd.Timestamp("2026-10-19")
    assert px.index[old] == pd.Timestamp("2026-10-21")


def test_legacy_high_is_the_last_252_rows():
    px, _ = _frame()
    end = len(px) - 1
    px.iloc[end - 255, 0] = 10_000.0          # inside 12 calendar months, outside 252 rows
    assert _rolling_high_at(px, end)["A"] == 10_000.0
    assert _rolling_high_at(px, end, legacy=True)["A"] < 10_000.0


def test_record_months_before_go_live_do_not_carry_the_rule():
    assert TRACK_RECORD_CONFIG["window_rule_from"] == "2026-12-31"
    assert "window_rule_from" not in config_for_month(TRACK_RECORD_CONFIG, "2026-12")
    assert config_for_month(TRACK_RECORD_CONFIG, "2027-01")["window_rule_from"] == "2026-12-31"
