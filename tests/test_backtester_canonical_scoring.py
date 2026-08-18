"""Regressions for the backtester's canonical scoring path.

Both defects covered here were present in the Industry-Relative ranking
branch only: the composite branch had already been corrected, and the two
inline copies had silently diverged.
"""
import numpy as np
import pandas as pd

from src.engine.backtester import _calendar_period_sharpe, _composite_z_score
from src.engine.calendar_momentum import _calendar_period_metrics


def _series(seed: int, n: int, cols: list[str]) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-01", periods=n)
    return pd.DataFrame(
        {c: 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.015, n))) for c in cols},
        index=dates,
    )


def test_backtester_sharpe_matches_canonical_screener_engine():
    """The backtest must reproduce the screener's Sharpe, not approximate it.

    The backtester previously used pandas' default sample SD (ddof=1) while
    the screener uses population SD. Because the in-window observation count
    differs per stock, that is not a uniform rescaling.
    """
    px = _series(3, 420, ["A", "B", "C"])
    end = len(px) - 1
    # Different in-window observation counts per stock.
    px.iloc[end - 60 : end - 20, px.columns.get_loc("B")] = np.nan
    px.iloc[end - 30 : end - 25, px.columns.get_loc("C")] = np.nan
    lr = np.log(px / px.shift(1))

    for months in (1, 3, 6, 9, 12):
        bt, _ = _calendar_period_sharpe(px, lr, end, months)
        screener, _, _, _ = _calendar_period_metrics(
            px, lr, months, latest_as_of=pd.Timestamp(px.index[-1])
        )
        pd.testing.assert_series_equal(
            bt.astype(float),
            screener.iloc[end].astype(float),
            check_names=False,
            rtol=1e-9,
            atol=1e-12,
        )


def test_composite_z_score_renormalizes_missing_windows():
    """A missing window must not shrink a stock's score toward the mean.

    Filling an unavailable window with a zero z-score assigns that stock the
    cross-sectional average for the window and never rescales, so a stock
    missing 10% of the weight has its score shrunk by 10%.
    """
    px = _series(5, 420, ["A", "B", "C", "D"])
    # D has only ~4 months of history, so its longer windows are unavailable.
    px.iloc[:-85, px.columns.get_loc("D")] = np.nan
    lr = np.log(px / px.shift(1))
    end = len(px) - 1
    windows = [1, 3, 6, 9, 12]
    weights = [0.10, 0.30, 0.30, 0.20, 0.10]

    composite = _composite_z_score(px, lr, end, windows, weights)

    # Recompute D's score from only the windows actually available to it and
    # confirm the engine renormalised rather than diluted.
    contrib, avail = 0.0, 0.0
    for w, cw in zip(windows, weights):
        raw, _ = _calendar_period_sharpe(px, lr, end, w)
        sig = float(raw.std(ddof=0))
        if not np.isfinite(sig) or sig <= 0:
            continue
        z = ((raw - float(raw.mean())) / sig).clip(-3.0, 3.0)
        if np.isfinite(z.get("D", np.nan)):
            contrib += float(z["D"]) * cw
            avail += cw
    assert avail > 0, "fixture must leave at least one window available"
    assert avail < sum(weights), "fixture must leave at least one window missing"
    assert np.isclose(float(composite["D"]), contrib / avail)


def test_missing_window_does_not_demote_a_stronger_stock():
    """Concrete selection failure the dilution bug produced."""
    windows = [1, 3, 6, 9, 12]
    weights = [0.10, 0.30, 0.30, 0.20, 0.10]
    z_by_window = {
        1: pd.Series({"IPO": 1.60, "SEASONED": 1.45}),
        3: pd.Series({"IPO": 1.60, "SEASONED": 1.45}),
        6: pd.Series({"IPO": 1.60, "SEASONED": 1.45}),
        9: pd.Series({"IPO": 1.60, "SEASONED": 1.45}),
        12: pd.Series({"IPO": np.nan, "SEASONED": 1.45}),
    }

    diluted = pd.Series(0.0, index=["IPO", "SEASONED"])
    for w, cw in zip(windows, weights):
        diluted += z_by_window[w].fillna(0) * cw

    renormalised = pd.Series(0.0, index=["IPO", "SEASONED"])
    available = pd.Series(0.0, index=["IPO", "SEASONED"])
    for w, cw in zip(windows, weights):
        renormalised += z_by_window[w].fillna(0) * cw
        available += z_by_window[w].notna().astype(float) * cw
    renormalised = renormalised.div(available.replace(0.0, np.nan))

    # IPO is stronger on every window it has; dilution demoted it.
    assert diluted.idxmax() == "SEASONED"
    assert renormalised.idxmax() == "IPO"


def test_composite_z_score_degenerate_cross_section_yields_nan():
    """A constant cross-section carries no ranking information."""
    dates = pd.bdate_range("2025-01-01", periods=420)
    px = pd.DataFrame(
        {c: 100 * np.exp(np.linspace(0, 0.4, len(dates))) for c in ["A", "B"]},
        index=dates,
    )
    lr = np.log(px / px.shift(1))
    composite = _composite_z_score(px, lr, len(px) - 1, [1, 3, 6, 9, 12],
                                   [0.10, 0.30, 0.30, 0.20, 0.10])
    # Identical series => zero dispersion => no score, rather than a
    # fabricated zero that would rank the pair arbitrarily.
    assert composite.isna().all()


def test_zero_weight_window_consumes_no_available_weight():
    px = _series(9, 420, ["A", "B", "C"])
    lr = np.log(px / px.shift(1))
    end = len(px) - 1
    all_windows = _composite_z_score(px, lr, end, [1, 3, 6, 9, 12],
                                     [0.0, 0.5, 0.5, 0.0, 0.0])
    only_active = _composite_z_score(px, lr, end, [3, 6], [0.5, 0.5])
    pd.testing.assert_series_equal(all_windows, only_active)
