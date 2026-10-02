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


def _frames(primary):
    return ps.PriceFrames(adj_close=primary, close=primary, high=None, low=None,
                          volume=primary * 0 + 1, source="screener", intraday=False, notes=[])


def test_nse_fills_before_yahoo_and_a_drifting_stock_is_left_to_yahoo():
    idx = pd.bdate_range("2026-08-03", periods=30)
    base = pd.DataFrame({"OK": 100.0, "DRIFT": 100.0}, index=idx)
    base["OK"] *= 1.001 ** np.arange(30)
    base["DRIFT"] *= 1.001 ** np.arange(30)
    primary = base.copy()
    primary.iloc[20] = np.nan                              # the same session missing for both
    nse = base.copy()
    nse.iloc[10:, nse.columns.get_loc("DRIFT")] *= 1.5     # NSE disagrees with Screener by 50%
    nse["OK"] *= 1.0003 ** np.arange(30)                   # a different move, to tell the sources apart
    yahoo = base.copy()
    yahoo["OK"] *= 1.0006 ** np.arange(30)
    out = ps.keep_and_fill(_frames(primary), ["OK", "DRIFT"], yahoo, nse).close
    step_nse = nse["OK"].iloc[20] / nse["OK"].iloc[19]
    step_yahoo = yahoo["DRIFT"].iloc[20] / yahoo["DRIFT"].iloc[19]
    assert np.isclose(out["OK"].iloc[20], primary["OK"].iloc[19] * step_nse)
    assert np.isclose(out["DRIFT"].iloc[20], primary["DRIFT"].iloc[19] * step_yahoo)


def test_without_a_middle_source_the_order_is_unchanged():
    primary = pd.DataFrame({"A": [100, 102, np.nan, 104, 105.0]}, index=IDX)
    yahoo = pd.DataFrame({"A": [95, 96.9, 98.8, 98.8, 100.776]}, index=IDX)
    a = ps.keep_and_fill(_frames(primary.copy()), ["A"], yahoo).close
    b = ps.keep_and_fill(_frames(primary.copy()), ["A"], yahoo, None).close
    assert a.equals(b) and a.loc[IDX[2], "A"] == 102 * 98.8 / 96.9
