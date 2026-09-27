"""The sample-year checks: coverage and corporate-action steps."""
from datetime import date

import numpy as np
import pandas as pd

from scripts import nse_sample_check as sc


def test_coverage_splits_missing_days_into_holidays_and_gaps():
    cal = [date(2026, 9, d) for d in (21, 22, 23, 24, 25)]
    have = {date(2026, 9, 21), date(2026, 9, 25), date(2026, 9, 26)}
    cov = sc.coverage(cal, have, date(2026, 9, 21), closed={date(2026, 9, 23)})
    assert cov["missing_closed"] == [date(2026, 9, 23)]
    assert cov["missing_open"] == [date(2026, 9, 22), date(2026, 9, 24)]
    assert cov["not_in_calendar"] == [date(2026, 9, 26)]


def test_a_bonus_shows_in_nse_prev_close_and_in_a_restated_screener():
    days = pd.DatetimeIndex(["2026-09-24", "2026-09-25"])
    nse_close = pd.DataFrame({"ABC": [200.0, 101.0], "XYZ": [50.0, 26.0]}, index=days)
    # NSE adjusts the previous close on the ex-date: 200 x 0.5.
    nse_prev = pd.DataFrame({"ABC": [199.0, 100.0], "XYZ": [49.0, 25.0]}, index=days)
    # Screener restated ABC's history, not XYZ's.
    screener = pd.DataFrame({"ABC": [100.0, 101.0], "XYZ": [50.0, 26.0]}, index=days)
    actions = pd.DataFrame({
        "symbol": ["ABC", "XYZ"], "ex_date": pd.to_datetime(["2026-09-25", "2026-09-25"]),
        "kind": ["bonus", "split"], "purpose": ["BONUS 1:1", "SPLIT"],
        "price_factor": [0.5, 0.5]})
    steps = sc.action_steps(actions, nse_close, nse_prev, screener, None,
                            log_keys={("2026-09-25", "ABC")}).set_index("symbol")
    assert steps.at["ABC", "nse_step"] == 0.5 and steps.at["ABC", "nse_step_ok"]
    assert steps.at["ABC", "screener_step_ok"] and steps.at["ABC", "in_log"]
    assert not steps.at["XYZ", "screener_step_ok"]
    assert steps.at["XYZ", "raw_move"] == 26 / 50
    assert np.isnan(steps.at["ABC", "yahoo_step"]) and steps.at["ABC", "yahoo_step_ok"] is None


def test_table_renders_without_tabulate():
    text = sc._table(pd.DataFrame({"a": [1.5], "b": ["x|y"]}))
    assert "| a | b |" in text and "1.5000" in text and "x/y" in text
    assert sc._table(pd.DataFrame()) == "_none_\n"


def test_same_day_actions_multiply():
    acts = pd.DataFrame({
        "symbol": ["BAJFINANCE", "BAJFINANCE", "OTHER"],
        "ex_date": pd.to_datetime(["2025-06-16", "2025-06-16", "2025-06-16"]),
        "kind": ["bonus", "split", "bonus"], "purpose": ["BONUS 4:1", "FVSPLT FRM RS 2 TO RE 1", "BONUS 1:1"],
        "price_factor": [0.2, 0.5, 0.5]})
    out = sc.combine_same_day(acts).set_index("symbol")
    assert abs(out.at["BAJFINANCE", "price_factor"] - 0.1) < 1e-12
    assert out.at["BAJFINANCE", "kind"] == "bonus+split"
    assert out.at["OTHER", "price_factor"] == 0.5
