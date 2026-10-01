from __future__ import annotations

import inspect

import pandas as pd
import pytest

from src.engine.track_record import summary_stats
from src.ui.views import backtest_view


def test_canonical_account_stats_use_frozen_ledger_and_live_mark():
    ledger = {
        "months": {
            "2026-01": {"strategy": 0.05, "benchmark": 0.02, "origin": "recorded"},
            "2026-02": {"strategy": -0.01, "benchmark": 0.01, "origin": "recorded"},
        }
    }
    live_meta = {
        "mtd_period": "2026-03",
        "strategy_mtd": 0.03,
        "benchmark_mtd": -0.005,
        "as_of": pd.Timestamp("2026-03-16"),
    }
    actual = backtest_view._canonical_account_stats(ledger, live_meta)
    expected = summary_stats(
        ledger,
        mtd={
            "period": pd.Period("2026-03", freq="M"),
            "strategy": 0.03,
            "benchmark": -0.005,
            "as_of": pd.Timestamp("2026-03-16"),
        },
    )
    assert actual["total_return"] == pytest.approx(expected["total_return"])
    assert actual["bench_return"] == pytest.approx(expected["bench_return"])
    assert actual["alpha"] == pytest.approx(expected["alpha"])
    assert actual["includes_mtd"] is True


def test_backtest_separates_canonical_account_from_configurable_research():
    source = inspect.getsource(backtest_view._backtest_body)
    assert 'kit.card(\n            "Canonical account performance"' in source
    assert "load_ledger(ledger_path(SYSTEM_750), inception(SYSTEM_750))" in source
    assert "current_book(" in source
    assert "Historical performance, trade history and parameter sweeps below use " in source
    assert 'kit.readings([' in source
