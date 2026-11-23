"""ledger_from_curves: a ledger-shaped dict of calendar-month returns from two equity curves."""

import numpy as np
import pandas as pd

from src.engine.track_record import ledger_from_curves


def _curve(start: str, end: str, daily: float, base: float = 100.0) -> pd.Series:
    idx = pd.bdate_range(start, end)
    return pd.Series(base * (1 + daily) ** np.arange(len(idx)), index=idx)


def test_the_ledger_starts_in_the_first_month_of_the_run_not_the_records_inception():
    eq = _curve("2010-02-01", "2011-03-31", 0.0005)
    assert ledger_from_curves(eq, eq * 0.9)["inception"] == "2010-02"


def test_alpha_is_the_months_difference():
    eq = _curve("2010-02-01", "2011-12-30", 0.0006)
    bm = _curve("2010-02-01", "2011-12-30", 0.0003)
    for entry in ledger_from_curves(eq, bm)["months"].values():
        assert abs(entry["alpha"] - (entry["strategy"] - entry["benchmark"])) < 1e-12


def test_a_run_with_no_benchmark_has_no_benchmark_months():
    eq = _curve("2010-02-01", "2010-12-31", 0.0005)
    assert all("benchmark" not in m for m in ledger_from_curves(eq, None)["months"].values())


def test_an_empty_curve_gives_an_empty_ledger():
    assert ledger_from_curves(pd.Series(dtype=float), pd.Series(dtype=float))["months"] == {}
