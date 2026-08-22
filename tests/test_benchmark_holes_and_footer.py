"""A hole in the index series must not become alpha.

fetch_benchmark_history returns the index already dropna()'d, from its own
yfinance call. Reindexing that onto the price calendar without carrying values
forward left NaN on every session the index lacked; pct_change then produced
NaN on the hole AND on the session after it, and run_backtest reads a NaN
benchmark day as 0.0%. One missing index print therefore deleted two days of
benchmark return -- and since the strategy's own days were untouched, every
deleted day landed in the alpha the dashboard reports.
"""
import numpy as np
import pandas as pd
import pytest

from src.engine.backtester import run_backtest
from src.ui import components


def _prices(n=900, cols=12, end="2026-08-18", seed=11):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=end, periods=n)
    return pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0.0006, 0.02, (n, cols)), axis=0)),
        index=idx, columns=[f"S{i}" for i in range(cols)],
    )


def _benchmark(index, seed=4):
    rng = np.random.default_rng(seed)
    return pd.Series(
        100 * np.exp(np.cumsum(rng.normal(0.0009, 0.009, len(index)))), index=index
    )


def test_a_holed_benchmark_still_reports_its_true_return():
    """Drop sessions from the index only; the reported figure must not move."""
    px = _prices()
    full = _benchmark(px.index)
    holed = full.drop(px.index[[300, 480, 610, 700, 780, 850]])

    kw = dict(top_n=5, rebal_freq=21, ema_period=20, high_pct=0.0,
              cost_bps=0.0, buffer_n=8)
    complete = run_backtest("bench-full", px, _benchmark_close=full, **kw)
    gappy = run_backtest("bench-holed", px, _benchmark_close=holed, **kw)

    assert complete["stats"]["bench_return"] == pytest.approx(
        gappy["stats"]["bench_return"], rel=1e-9
    )
    assert complete["stats"]["alpha"] == pytest.approx(
        gappy["stats"]["alpha"], rel=1e-9
    )


def test_the_strategy_is_unaffected_by_benchmark_gaps():
    px = _prices()
    full = _benchmark(px.index)
    holed = full.drop(px.index[[300, 480, 610]])
    kw = dict(top_n=5, rebal_freq=21, ema_period=20, high_pct=0.0,
              cost_bps=0.0, buffer_n=8)
    a = run_backtest("strat-a", px, _benchmark_close=full, **kw)
    b = run_backtest("strat-b", px, _benchmark_close=holed, **kw)
    assert a["stats"]["total_return"] == pytest.approx(b["stats"]["total_return"])


def test_a_benchmark_starting_late_does_not_crash_or_invent_returns():
    """Leading gaps have no earlier print to carry; they must read as flat."""
    px = _prices()
    late = _benchmark(px.index).iloc[400:]
    res = run_backtest("bench-late", px, _benchmark_close=late,
                       top_n=5, rebal_freq=21, ema_period=20, high_pct=0.0,
                       cost_bps=0.0, buffer_n=8)
    assert res is not None
    assert np.isfinite(res["stats"]["bench_return"])


# ── Footer / ribbon ─────────────────────────────────────────────────────────

def _footer_html(monkeypatch, items):
    captured = {}
    monkeypatch.setattr(components, "data_freshness", lambda: items)
    monkeypatch.setattr(components.st, "markdown", lambda *a, **k: captured.setdefault("ribbon", a[0]))
    monkeypatch.setattr(components.st, "html", lambda h, **k: captured.setdefault("footer", h))
    components.render_data_quality_footer(total_stocks=750, gap_count=69, short_count=0)
    return captured


ITEMS = [
    {"label": "Prices", "as_of": "21 Aug", "behind": 0, "stale": False, "source": None},
    {"label": "Market caps", "as_of": "21 Aug", "behind": 0, "stale": False, "source": None},
    {"label": "All-time highs", "as_of": "21 Aug", "behind": 0, "stale": False, "source": None},
]


def test_as_of_dates_appear_once_not_twice(monkeypatch):
    """The ribbon owns the dates; the bar below it used to restate all three."""
    out = _footer_html(monkeypatch, ITEMS)
    for label in ("Prices", "Market caps", "All-time highs"):
        assert label in out["ribbon"]
        assert label not in out["footer"]


def test_the_footer_keeps_what_only_it_reports(monkeypatch):
    out = _footer_html(monkeypatch, ITEMS)
    assert "750" in out["footer"]
    assert "Gap-filled" in out["footer"]
    assert "Short history" in out["footer"]
    assert "Stop Loss" in out["footer"]


def test_a_stale_source_is_flagged_once_in_the_ribbon(monkeypatch):
    stale = [dict(ITEMS[0]), {"label": "Market caps", "as_of": "11 Aug",
                              "behind": 5, "stale": True, "source": None}]
    out = _footer_html(monkeypatch, stale)
    assert "5 trading days behind" in out["ribbon"]
    assert "behind" not in out["footer"]
