"""Screener first; a missing Screener price is chained from Yahoo's daily move."""
import numpy as np
import pandas as pd

from src.loaders import price_source as ps

IDX = pd.bdate_range("2026-09-21", periods=5)


def test_a_gap_is_chained_from_the_backups_move_not_its_level():
    primary = pd.DataFrame({"A": [100, 102, np.nan, 104, np.nan]}, index=IDX, dtype=float)
    # Yahoo's level is 5% lower (dividend adjustment); its moves are what count.
    backup = pd.DataFrame({"A": [95, 96.9, 98.8, 98.8, 100.776]}, index=IDX)
    out, cells, added = ps.fill_from_backup(primary, backup)
    assert cells == 2 and added == []
    assert out.loc[IDX[2], "A"] == 102 * 98.8 / 96.9
    assert out.loc[IDX[3], "A"] == 104                      # Screener's own price stays
    assert out.loc[IDX[4], "A"] == 104 * 100.776 / 98.8


def test_nothing_before_a_stocks_first_primary_price():
    primary = pd.DataFrame({"NEW": [np.nan, np.nan, 50, 51, 52]}, index=IDX, dtype=float)
    backup = pd.DataFrame({"NEW": [40, 45, 50, 51, 52]}, index=IDX, dtype=float)
    out, cells, _ = ps.fill_from_backup(primary, backup)
    assert cells == 0 and out["NEW"].isna().sum() == 2


def test_a_newer_session_comes_from_the_backup_only_when_it_is_nearly_complete():
    primary = pd.DataFrame({"A": [1.0] * 5, "B": [1.0] * 5}, index=IDX)
    nxt = IDX[-1] + pd.offsets.BDay()
    full = pd.DataFrame({"A": [1.0] * 5 + [1.1], "B": [1.0] * 5 + [0.9]}, index=IDX.append(pd.DatetimeIndex([nxt])))
    out, _, added = ps.fill_from_backup(primary, full)
    assert added == [nxt] and out.loc[nxt, "A"] == 1.1
    half = full.copy()
    half.loc[nxt, "B"] = np.nan
    _, _, added = ps.fill_from_backup(primary, half)
    assert added == []                                    # 50% is not a session


def test_old_gaps_outside_the_ranking_window_are_left_alone():
    idx = pd.bdate_range("2024-01-01", "2026-09-25")
    primary = pd.DataFrame({"A": 100.0}, index=idx)
    primary.iloc[10] = np.nan                             # early 2024
    backup = pd.DataFrame({"A": 100.0}, index=idx)
    out, cells, _ = ps.fill_from_backup(primary, backup)
    assert cells == 0 and np.isnan(out.iloc[10, 0])
