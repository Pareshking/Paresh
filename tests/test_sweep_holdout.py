"""The holdout split the module docstring has always promised.

`SweepResult.holdout` was declared, documented as one of three guards against
data mining, and never computed -- it was always None. The guard that actually
catches a fitted winner was the one not running: the shared window and the
z-score badge both judge a sweep by its own results, and a setting fitted to
the window scores well on the window by construction.
"""
import numpy as np
import pandas as pd
import pytest

from src.engine.backtester import completed_month_window
from src.engine.parameter_sweep import (
    _holdout_frames,
    assess_holdout,
    run_parameter_sweep,
)

BASE = dict(
    weight_method="Equal Weight", config_weights=(0.10, 0.30, 0.30, 0.20, 0.10),
    rebal_freq=21, top_n=20, ema_period=20, high_pct=0.0, cost_bps=30.0,
)


@pytest.fixture
def prices():
    rng = np.random.default_rng(5)
    n, cols = 900, 25
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    return pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0.0005, 0.018, (n, cols)), axis=0)),
        index=idx, columns=[f"S{i}" for i in range(cols)],
    )


# ── The split itself ────────────────────────────────────────────────────────

def test_the_two_halves_tile_the_window_exactly(prices):
    """No overlap and no gap: leakage either way would void the check."""
    dates = pd.DatetimeIndex(prices.index)
    full_start, full_end = completed_month_window(dates, 6)

    is_frame, is_months, oos_months = _holdout_frames(prices, 6)
    is_start, is_end = completed_month_window(pd.DatetimeIndex(is_frame.index), is_months)
    oos_start, oos_end = completed_month_window(dates, oos_months)

    assert is_months + oos_months == 6
    assert is_start == full_start
    assert oos_end == full_end
    assert is_end < oos_start                      # no overlap
    assert (oos_start - is_end).days == 1          # no gap


def test_the_in_sample_frame_keeps_its_formation_history(prices):
    """Only the reported window is cut; the lookback before it is untouched."""
    is_frame, _, _ = _holdout_frames(prices, 6)
    assert is_frame.index[0] == prices.index[0]
    assert len(is_frame) > 700


def test_an_odd_window_gives_the_extra_month_to_the_in_sample_half(prices):
    _, is_months, oos_months = _holdout_frames(prices, 5)
    assert (is_months, oos_months) == (3, 2)


def test_a_window_too_short_to_split_returns_nothing(prices):
    assert _holdout_frames(prices, 1) is None


def test_a_one_month_window_is_reported_not_silently_skipped(prices):
    res = run_parameter_sweep(prices, {"Holdings": [10, 20]}, base=BASE,
                              backtest_months=1, holdout=True)
    assert res.holdout is None
    assert any("cannot be split" in w for w in res.warnings)


# ── The verdict ─────────────────────────────────────────────────────────────

def _table(ranks_and_scores):
    rows = [{"Holdings": h, "Rank": r, "Score": s} for h, r, s in ranks_and_scores]
    return pd.DataFrame(rows)


def test_a_winner_that_stays_on_top_is_reported_as_holding_up():
    same = [(10, 1, 3.0), (20, 2, 2.0), (30, 3, 1.0), (40, 4, 0.0)]
    _, detail, rho = assess_holdout(_table(same), _table(same))
    assert "held up" in detail
    assert rho == pytest.approx(1.0)


def test_a_winner_that_sinks_out_of_sample_is_called_fitted():
    in_s = [(10, 1, 3.0), (20, 2, 2.0), (30, 3, 1.0), (40, 4, 0.0)]
    out_s = [(10, 4, 0.0), (20, 3, 1.0), (30, 2, 2.0), (40, 1, 3.0)]
    _, detail, rho = assess_holdout(_table(in_s), _table(out_s))
    assert "fitted to the first half" in detail
    assert rho == pytest.approx(-1.0)


def test_an_uncorrelated_grid_says_treat_any_winner_as_noise():
    in_s = [(10, 1, 3.0), (20, 2, 2.0), (30, 3, 1.0), (40, 4, 0.0)]
    out_s = [(10, 2, 2.0), (20, 4, 0.0), (30, 1, 3.0), (40, 3, 1.0)]
    _, detail, rho = assess_holdout(_table(in_s), _table(out_s))
    assert abs(rho) < 0.5
    assert "treat ANY winner here as noise" in detail or "weak" in detail


def test_too_few_shared_combinations_says_so():
    one = [(10, 1, 3.0)]
    _, detail, rho = assess_holdout(_table(one), _table(one))
    assert "too few to judge" in detail
    assert rho is None


def test_an_empty_half_is_reported_not_crashed():
    _, detail, _ = assess_holdout(_table([(10, 1, 3.0)]), pd.DataFrame())
    assert "nothing to compare" in detail


# ── End to end ──────────────────────────────────────────────────────────────

def test_holdout_is_off_by_default(prices):
    res = run_parameter_sweep(prices, {"Holdings": [10, 20]}, base=BASE)
    assert res.holdout is None
    assert res.holdout_detail == ""


def test_holdout_reports_both_ranks_for_every_surviving_combination(prices):
    res = run_parameter_sweep(prices, {"Holdings": [5, 10, 15, 20, 30]},
                              base=BASE, holdout=True)
    ho = res.holdout
    assert ho is not None and not ho.empty
    for col in ("Holdings", "In-sample Rank", "In-sample Score",
                "Out-of-sample Rank", "Out-of-sample Score"):
        assert col in ho.columns
    assert ho["In-sample Rank"].tolist() == sorted(ho["In-sample Rank"].tolist())
    assert res.holdout_rho is not None
    assert "in sample" in res.holdout_detail


def test_the_main_table_still_describes_the_full_window(prices):
    """The holdout is a check on the headline result, not a replacement."""
    plain = run_parameter_sweep(prices, {"Holdings": [10, 20, 30]}, base=BASE)
    with_ho = run_parameter_sweep(prices, {"Holdings": [10, 20, 30]},
                                  base=BASE, holdout=True)
    pd.testing.assert_frame_equal(plain.table, with_ho.table)
    assert with_ho.window_months == plain.window_months


# ── Display ─────────────────────────────────────────────────────────────────

def test_percentage_columns_are_scaled_for_display():
    """The sweep table holds fractions; rendered raw they printed as decimals,
    so a 12.3% return and a 0.12 ratio looked the same on screen."""
    from src.ui.views.backtest_view import _sweep_display_frame

    raw = pd.DataFrame({
        "Total Return": [0.1234], "Alpha": [-0.0456], "Max DD": [-0.0789],
        "Win Rate": [0.6667], "Turnover": [45.0], "Sharpe": [1.23],
        "52W high floor": [0.8],
    })
    disp = _sweep_display_frame(raw)

    assert disp["Total Return"].iloc[0] == pytest.approx(12.34)
    assert disp["Alpha"].iloc[0] == pytest.approx(-4.56)
    assert disp["Max DD"].iloc[0] == pytest.approx(-7.89)
    assert disp["Win Rate"].iloc[0] == pytest.approx(66.67)
    assert disp["52W high floor"].iloc[0] == pytest.approx(80.0)
    # Turnover is already a percentage at source, and Sharpe is a ratio.
    assert disp["Turnover"].iloc[0] == pytest.approx(45.0)
    assert disp["Sharpe"].iloc[0] == pytest.approx(1.23)


def test_display_scaling_leaves_the_source_table_untouched():
    """The CSV download must keep the raw numbers."""
    from src.ui.views.backtest_view import _sweep_display_frame

    raw = pd.DataFrame({"Total Return": [0.1234]})
    _sweep_display_frame(raw)
    assert raw["Total Return"].iloc[0] == pytest.approx(0.1234)


def test_every_percentage_column_carries_a_percent_format():
    from src.ui.views.backtest_view import _sweep_column_config

    cfg = _sweep_column_config()
    for col in ("Total Return", "Alpha", "Max DD", "Win Rate", "Turnover",
                "52W high floor"):
        assert "%%" in str(cfg[col]), f"{col} renders without a % sign"


def test_missing_or_null_stats_do_not_break_the_display():
    from src.ui.views.backtest_view import _sweep_display_frame

    disp = _sweep_display_frame(pd.DataFrame({"Total Return": [None, 0.1], "Rank": [1, 2]}))
    assert pd.isna(disp["Total Return"].iloc[0])
    assert disp["Total Return"].iloc[1] == pytest.approx(10.0)
