"""Calendar returns: the year-by-year table above the monthly grids (owner, 9 Oct 2026).

Every number must be the one the year's own block prints in its CY column, so
the summary is read from the grid and never recomputed.
"""

import numpy as np
import pandas as pd

from src.engine.track_record import build_combined_grid, ledger_from_curves
from src.ui.components import yearly_summary


def _curves():
    idx = pd.bdate_range("2023-03-15", "2025-06-30")
    rng = np.random.default_rng(3)
    strat = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0008, 0.012, len(idx)))), index=idx)
    bench = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0003, 0.010, len(idx)))), index=idx)
    return strat, bench


def test_each_year_reads_the_grids_cy_cells():
    strat, bench = _curves()
    grid = build_combined_grid(ledger_from_curves(strat, bench), alpha_as_difference=True)
    table = yearly_summary(grid)
    assert table["YEAR"].tolist() == [2023, 2024, 2025]
    for row in table.itertuples(index=False):
        block = grid[grid["YEAR"] == row.YEAR].set_index("SERIES")["CY RETURN"]
        assert row.STRATEGY == block["Strategy"]
        assert row.BENCHMARK == block["Nifty 500"]
        assert row.ALPHA == block["Alpha"]
        assert np.isclose(row.ALPHA, row.STRATEGY - row.BENCHMARK)


def test_part_years_say_which_months_they_cover():
    strat, bench = _curves()
    table = yearly_summary(build_combined_grid(ledger_from_curves(strat, bench)))
    by_year = table.set_index("YEAR")
    assert by_year.loc[2024, "MONTHS"] == 12
    assert by_year.loc[2025, "MONTHS"] == 6 and by_year.loc[2025, "LAST"] == "JUN"
    assert by_year.loc[2023, "MONTHS"] < 12


def test_an_empty_grid_gives_an_empty_table():
    assert yearly_summary(pd.DataFrame()).empty


def test_the_backtest_page_shows_it_above_the_monthly_grids():
    src = open("src/ui/views/backtest_view.py", encoding="utf-8").read()
    assert src.index("_render_yearly_summary(_grid, bench_name)") < src.index("_render_calendar_returns(_grid)")
