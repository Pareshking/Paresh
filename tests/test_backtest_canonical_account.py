from __future__ import annotations

import inspect

import pandas as pd
import pytest

from src.engine.track_record import summary_stats
from src.ui import canonical_book
from src.ui.views import backtest_view


def test_backtest_canonical_stats_use_track_record_monthly_ledger_and_live_mark():
    ledger = {
        "months": {
            "2026-01": {
                "strategy": 0.05,
                "benchmark": 0.02,
                "origin": "recorded",
                "universe": "point_in_time",
            },
            "2026-02": {
                "strategy": -0.01,
                "benchmark": 0.01,
                "origin": "recorded",
                "universe": "point_in_time",
            },
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
    assert actual["mtd_period"] == "2026-03"


def test_backtest_page_defaults_to_shared_canonical_book_not_research_book():
    source = inspect.getsource(backtest_view._backtest_body)

    # Actions and Portfolio already consume this adapter. The Backtest page
    # must default to the same adapter for its canonical book and expose its
    # configurable run under a separately labelled research view.
    assert "current_book(canonical_prices, benchmark_close, system)" in source
    assert 'default="Canonical book"' in source
    assert 'canonical_view = view in ("Canonical book", "Canonical changes")' in source
    assert 'research_book = bt_res.get("live_book", pd.DataFrame())' in source
    assert "Canonical account performance" in source
    assert "Research backtest returns" in source


def test_canonical_book_adapter_is_the_shared_portfolio_book_contract():
    source = inspect.getsource(canonical_book.current_book)
    assert "record_run(adj_close, benchmark_close, system)" in source
    assert "duplicate symbols" in source
    assert "REQUIRED_BOOK_COLUMNS" in source
