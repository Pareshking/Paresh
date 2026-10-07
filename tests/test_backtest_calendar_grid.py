"""The Backtest tab's calendar returns: a year-by-month grid from the equity curves.

The Portfolio page builds its grid from the frozen ledger; a backtest has only
curves. ledger_from_curves feeds build_combined_grid the same shape, so the two
pages cannot disagree about what a year or a quarter means.
"""

import numpy as np
import pandas as pd

from src.engine.track_record import build_combined_grid, ledger_from_curves


def _curve(start: str, end: str, daily: float, base: float = 100.0) -> pd.Series:
    idx = pd.bdate_range(start, end)
    return pd.Series(base * (1 + daily) ** np.arange(len(idx)), index=idx)


def test_months_compound_to_the_curves_own_total_return():
    eq = _curve("2010-02-01", "2012-06-29", 0.0007)
    bm = _curve("2010-02-01", "2012-06-29", 0.0004)
    ledger = ledger_from_curves(eq, bm)
    grid = build_combined_grid(ledger)
    strat = grid[grid.SERIES == "Strategy"].set_index("YEAR")
    total = float(np.prod([1 + strat.loc[y, "CY RETURN"] for y in strat.index]) - 1)
    assert abs(total - (eq.iloc[-1] / eq.iloc[0] - 1)) < 1e-9


def test_the_grid_starts_in_the_first_month_of_the_run_not_the_records_inception():
    eq = _curve("2010-02-01", "2011-03-31", 0.0005)
    ledger = ledger_from_curves(eq, eq * 0.9)
    assert ledger["inception"] == "2010-02"
    years = build_combined_grid(ledger).YEAR.unique().tolist()
    assert years == [2010, 2011]


def test_alpha_is_the_months_difference_and_every_year_shows_three_rows():
    eq = _curve("2010-02-01", "2011-12-30", 0.0006)
    bm = _curve("2010-02-01", "2011-12-30", 0.0003)
    ledger = ledger_from_curves(eq, bm)
    for entry in ledger["months"].values():
        assert abs(entry["alpha"] - (entry["strategy"] - entry["benchmark"])) < 1e-12
    grid = build_combined_grid(ledger)
    assert grid.groupby("YEAR").SERIES.apply(list).iloc[0] == ["Strategy", "Nifty 500", "Alpha"]


def test_a_run_with_no_benchmark_still_gives_a_strategy_grid():
    eq = _curve("2010-02-01", "2010-12-31", 0.0005)
    ledger = ledger_from_curves(eq, None)
    assert all("benchmark" not in m for m in ledger["months"].values())
    grid = build_combined_grid(ledger)
    assert grid[grid.SERIES == "Strategy"]["CY RETURN"].notna().all()


def test_an_empty_curve_gives_an_empty_grid():
    ledger = ledger_from_curves(pd.Series(dtype=float), pd.Series(dtype=float))
    assert ledger["months"] == {} and build_combined_grid(ledger).empty


def test_alpha_aggregates_are_the_plain_difference_by_default_compounding_on_request():
    eq = _curve("2010-02-01", "2010-12-31", 0.0008)
    bm = _curve("2010-02-01", "2010-12-31", 0.0003)
    ledger = ledger_from_curves(eq, bm)
    plain = build_combined_grid(ledger).set_index("SERIES")
    compounded = build_combined_grid(ledger, alpha_as_difference=False).set_index("SERIES")
    for col in ("CY RETURN", "FY RETURN", "Q1", "Q2", "Q3", "Q4"):
        a, s, b = plain.loc["Alpha", col], plain.loc["Strategy", col], plain.loc["Nifty 500", col]
        if pd.notna(s) and pd.notna(b):
            assert abs(a - (s - b)) < 1e-12
    # S40 (owner, 7 Oct): Portfolio uses the default, so every page shows the difference.
    # The monthly cells are differences either way.
    assert plain.loc["Alpha", "MAR"] == compounded.loc["Alpha", "MAR"]
    assert abs(compounded.loc["Alpha", "CY RETURN"] - (plain.loc["Strategy", "CY RETURN"] - plain.loc["Nifty 500", "CY RETURN"])) > 1e-6
