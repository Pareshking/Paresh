"""Parameter sweep: correct grid, honest verdict.

Searching many combinations over one window and keeping the winner is data
mining. The sweep is only defensible if it reports the whole distribution and
says how far the winner sits from the pack, so those properties are tested as
hard as the arithmetic.
"""
import numpy as np
import pandas as pd
import pytest

from src.engine.parameter_sweep import (
    OBJECTIVES,
    SWEEPABLE,
    assess_overfitting,
    count_combinations,
    run_parameter_sweep,
)


@pytest.fixture(scope="module")
def prices():
    n, cols = 760, 40
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    rng = np.random.default_rng(21)
    drift = np.linspace(0.0009, -0.0003, cols)
    return pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(drift, 0.013, (n, cols)), axis=0)),
        index=idx, columns=[f"S{i}" for i in range(cols)],
    )


BASE = {"rebal_freq": 21, "cost_bps": 30.0}


def test_count_combinations_is_the_cartesian_product():
    assert count_combinations({"Holdings": [10, 20], "EMA filter": [20, 50, 100]}) == 6
    assert count_combinations({"Holdings": [10]}) == 1
    assert count_combinations({}) == 0


def test_every_sweepable_name_maps_to_a_real_backtest_argument():
    import inspect

    from src.engine.backtester import run_backtest

    params = set(inspect.signature(run_backtest).parameters)
    for friendly, kwarg in SWEEPABLE.items():
        assert kwarg in params, f"{friendly} -> {kwarg} is not a run_backtest argument"


def test_every_objective_maps_to_a_real_stat(prices):
    res = run_parameter_sweep(prices, {"Holdings": [10, 20]}, base=BASE)
    assert res.best is not None
    from src.engine.backtester import run_backtest

    bt = run_backtest("obj-check", prices, top_n=10, **BASE)
    for name, key in OBJECTIVES.items():
        assert key in bt["stats"], f"objective {name} -> missing stat {key}"


def test_sweep_returns_one_row_per_combination(prices):
    space = {"Holdings": [10, 20, 30], "EMA filter": [20, 50]}
    res = run_parameter_sweep(prices, space, base=BASE)
    assert res.combinations_tested == 6
    assert len(res.table) == 6 - res.combinations_failed


def test_results_are_ranked_best_first(prices):
    res = run_parameter_sweep(prices, {"Holdings": [10, 20, 30]}, base=BASE)
    scores = res.table["Score"].dropna().tolist()
    assert scores == sorted(scores, reverse=True)
    assert res.table["Rank"].tolist() == list(range(1, len(res.table) + 1))


def test_best_matches_the_top_row(prices):
    res = run_parameter_sweep(prices, {"Holdings": [10, 20, 30]}, base=BASE)
    assert res.best["Rank"] == 1
    assert res.best["Score"] == res.table["Score"].iloc[0]


def test_objective_actually_changes_the_ordering(prices):
    space = {"Holdings": [5, 10, 20, 30, 50]}
    by_sharpe = run_parameter_sweep(prices, space, objective="Sharpe", base=BASE)
    by_dd = run_parameter_sweep(
        prices, space, objective="Max drawdown (least bad)", base=BASE
    )
    assert by_sharpe.table["Score"].tolist() != by_dd.table["Score"].tolist()


def test_a_grid_that_is_too_large_is_refused_rather_than_run(prices):
    space = {"Holdings": [5, 10, 15, 20, 30, 50], "EMA filter": [20, 50, 100, 200],
             "52W high floor": [0.0, 0.7, 0.8, 0.9], "Cost (bps)": [0.0, 15.0, 30.0, 50.0]}
    with pytest.raises(ValueError, match="exceeds max_combinations"):
        run_parameter_sweep(prices, space, base=BASE, max_combinations=50)


def test_empty_space_returns_empty_not_an_error(prices):
    res = run_parameter_sweep(prices, {}, base=BASE)
    assert res.table.empty
    assert res.warnings


def test_insufficient_history_is_reported_not_raised():
    short = pd.DataFrame(
        {f"S{i}": np.linspace(100, 120, 60) for i in range(5)},
        index=pd.bdate_range(end="2026-08-18", periods=60),
    )
    res = run_parameter_sweep(short, {"Holdings": [10, 20]}, base=BASE)
    assert res.table.empty
    assert res.combinations_failed == 2
    assert any("failed" in w or "history" in w for w in res.warnings)


# ── The honesty guards ──────────────────────────────────────────────────────

def test_a_winner_inside_the_noise_is_flagged_high_risk():
    """Winner barely above the median relative to the spread of the field."""
    table = pd.DataFrame({"Score": [1.10, 1.05, 1.00, 0.95, 0.40, 0.30]})
    risk, detail = assess_overfitting(table, n_combinations=6)
    assert risk == "high"
    assert "noise" in detail.lower()


def test_a_tight_field_with_a_clear_top_is_only_moderate():
    """A small absolute margin over a very tight field is suggestive, not noise."""
    table = pd.DataFrame({"Score": [1.02, 1.00, 0.99, 0.98, 0.97, 0.96]})
    risk, _ = assess_overfitting(table, n_combinations=6)
    assert risk == "moderate"


def test_a_wide_margin_is_flagged_low_risk():
    table = pd.DataFrame({"Score": [5.0, 1.0, 0.9, 0.8, 0.7, 0.6]})
    risk, _ = assess_overfitting(table, n_combinations=6)
    assert risk == "low"


def test_identical_scores_report_that_parameters_did_nothing():
    table = pd.DataFrame({"Score": [1.0] * 5})
    risk, detail = assess_overfitting(table, n_combinations=5)
    assert risk == "none"
    assert "did nothing" in detail


def test_large_grids_are_called_out_in_the_verdict():
    table = pd.DataFrame({"Score": np.linspace(3.0, 1.0, 120)})
    _, detail = assess_overfitting(table, n_combinations=120)
    assert "120 combinations" in detail
    assert "chance" in detail.lower()


def test_too_few_results_to_judge_says_so():
    risk, _ = assess_overfitting(pd.DataFrame({"Score": [1.0, 2.0]}), 2)
    assert risk == "unknown"


def test_sweep_attaches_a_verdict_to_every_real_result(prices):
    res = run_parameter_sweep(prices, {"Holdings": [10, 20, 30, 50]}, base=BASE)
    assert res.overfitting_risk in {"high", "moderate", "low", "none", "unknown"}
    assert res.risk_detail
    assert res.window_months > 0
