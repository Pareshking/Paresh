"""TODO S126 (owner, 11 Nov 2026: "why live and old backtest missing recent month?"):
the Backtest's calendar grid shows the month in progress to date, after the last
completed month, and only when the run reaches the latest session."""

import pandas as pd

from src.engine.track_record import build_combined_grid
from src.ui.views.backtest_view import _running_month

LEDGER = {"inception": "2026-09", "months": {
    "2026-09": {"strategy": 0.01, "benchmark": 0.02, "alpha": -0.01},
    "2026-10": {"strategy": -0.04, "benchmark": -0.008, "alpha": -0.032},
}}
META = {"mtd_period": "2026-11", "strategy_mtd": 0.025, "benchmark_mtd": 0.071,
        "as_of": pd.Timestamp("2026-11-06")}


def test_running_month_follows_the_last_completed_month():
    mtd = _running_month(LEDGER, META, allowed=True)
    assert mtd["period"] == pd.Period("2026-11", freq="M")
    assert mtd["values"]["alpha"] == 0.025 - 0.071
    grid = build_combined_grid(LEDGER, alpha_as_difference=True,
                               mtd_period=mtd["period"], mtd_values=mtd["values"])
    strat = grid[grid["SERIES"] == "Strategy"].iloc[0]
    assert strat["NOV"] == 0.025 and strat["OCT"] == -0.04
    assert abs(strat["CY RETURN"] - (1.01 * 0.96 * 1.025 - 1)) < 1e-12


def test_no_running_month_when_the_run_ends_earlier_or_has_none():
    assert _running_month(LEDGER, META, allowed=False) is None           # History ending before the latest month
    assert _running_month(LEDGER, {**META, "strategy_mtd": None}, True) is None
    assert _running_month(LEDGER, {**META, "mtd_period": "2026-12"}, True) is None  # a gap: not the next month
    assert _running_month(LEDGER, None, True) is None
    assert _running_month({"months": {}}, META, True) is None


def test_missing_benchmark_leaves_alpha_blank():
    mtd = _running_month(LEDGER, {**META, "benchmark_mtd": None}, True)
    assert mtd["values"]["benchmark"] is None and mtd["values"]["alpha"] is None


def test_year_table_names_the_day_a_running_month_reached(monkeypatch):
    from src.ui import components

    shown = []
    monkeypatch.setattr(components.st, "html", lambda body, **_: shown.append(body))
    mtd = _running_month(LEDGER, META, allowed=True)
    grid = build_combined_grid(LEDGER, alpha_as_difference=True,
                               mtd_period=mtd["period"], mtd_values=mtd["values"])
    components._render_yearly_summary(grid, "Nifty 500", through="6 Nov")
    assert any("Sep–6 Nov" in body for body in shown)
    shown.clear()
    components._render_yearly_summary(grid, "Nifty 500")
    assert any("Sep–Nov" in body for body in shown)
