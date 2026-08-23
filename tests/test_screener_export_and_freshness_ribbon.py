"""Screener CSV exports every column; the freshness ribbon reports every source.

The CSV previously exported only DISPLAY_COLS -- a screen-layout list -- so the
file silently omitted Score, the raw composite the entire ranking is sorted by,
along with Composite Rank, Rank (-1M)/(-3M), 52W High, ATR, ATR %, Persistence
and Exp Rank. A spreadsheet without the score behind the rank cannot be audited.
"""
import numpy as np
import pandas as pd
import pytest

from src.engine.momentum import MomentumEngine
from src.ui import components
from src.ui.views.ranking_view import DISPLAY_COLS


@pytest.fixture
def ranked():
    n, cols = 400, 8
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    rng = np.random.default_rng(4)
    px = pd.DataFrame(
        100 + np.cumsum(rng.normal(0, 1, (n, cols)), axis=0),
        index=idx, columns=[f"S{i}" for i in range(cols)],
    )
    info = pd.DataFrame({
        "Symbol": [f"S{i}" for i in range(cols)],
        "Industry": ["IT", "Bank"] * (cols // 2),
        "Indices": ["NIFTY"] * cols,
    })
    calc = MomentumEngine(
        px, high_df=px * 1.01, low_df=px * 0.99, close_df=px,
        volume_df=pd.DataFrame(1e5, index=idx, columns=px.columns),
    )
    return calc.get_rankings(
        info, pd.Series(1e4, index=px.columns),
        close_prices_df=px, high_prices_df=px * 1.01,
    )


def _export_cols(view):
    """Mirror of the export selection in render_ranking_view."""
    active = [c for c in DISPLAY_COLS if c in view.columns]
    return active + [c for c in view.columns if c not in active]


def test_export_includes_every_ranking_column(ranked):
    assert set(_export_cols(ranked)) == set(ranked.columns)


def test_export_is_strictly_wider_than_the_display_list(ranked):
    active = [c for c in DISPLAY_COLS if c in ranked.columns]
    assert len(_export_cols(ranked)) > len(active)


@pytest.mark.parametrize("col", [
    "Score", "Composite Rank", "Rank (-1M)", "Rank (-3M)",
    "52W High", "ATR", "ATR %", "Persistence",
])
def test_previously_dropped_columns_are_exported(ranked, col):
    if col not in ranked.columns:
        pytest.skip(f"{col} not produced by this fixture")
    assert col in _export_cols(ranked)


def test_export_has_no_duplicate_columns(ranked):
    cols = _export_cols(ranked)
    assert len(cols) == len(set(cols))


def test_display_columns_still_lead_the_export(ranked):
    """Familiar columns first so the file opens looking like the screen."""
    active = [c for c in DISPLAY_COLS if c in ranked.columns]
    assert _export_cols(ranked)[: len(active)] == active


def test_export_round_trips_through_csv(ranked):
    import io
    csv = ranked[_export_cols(ranked)].to_csv(index=False)
    back = pd.read_csv(io.StringIO(csv))
    assert list(back.columns) == _export_cols(ranked)
    assert len(back) == len(ranked)


# ── Freshness ribbon ────────────────────────────────────────────────────────

def test_ribbon_renders_nothing_when_no_source_reported(monkeypatch):
    monkeypatch.setattr(components, "data_freshness", lambda: [])
    captured = []
    monkeypatch.setattr(components.st, "markdown", lambda *a, **k: captured.append(a))
    components.render_freshness_ribbon()
    assert captured == []


def test_ribbon_lists_prices_and_market_caps(monkeypatch):
    monkeypatch.setattr(components, "data_freshness", lambda: [
        {"label": "Prices", "as_of": "17 Aug", "behind": 1, "stale": False, "source": None},
        {"label": "Market caps", "as_of": "14 Aug", "behind": 3, "stale": True, "source": None},
    ])
    captured = []
    monkeypatch.setattr(components.st, "markdown", lambda *a, **k: captured.append(a[0]))
    components.render_freshness_ribbon()

    html_out = captured[0]
    assert "Prices: 17 Aug" in html_out
    assert "Market caps: 14 Aug" in html_out
    assert "3 trading days behind" in html_out


def test_ribbon_puts_stale_sources_first(monkeypatch):
    monkeypatch.setattr(components, "data_freshness", lambda: [
        {"label": "Prices", "as_of": "18 Aug", "behind": 0, "stale": False, "source": None},
        {"label": "Market caps", "as_of": "11 Aug", "behind": 5, "stale": True, "source": None},
    ])
    captured = []
    monkeypatch.setattr(components.st, "markdown", lambda *a, **k: captured.append(a[0]))
    components.render_freshness_ribbon()

    html_out = captured[0]
    assert html_out.index("Market caps") < html_out.index("Prices")


def test_ribbon_marks_stale_amber_and_current_green(monkeypatch):
    monkeypatch.setattr(components, "data_freshness", lambda: [
        {"label": "Prices", "as_of": "18 Aug", "behind": 0, "stale": False, "source": None},
        {"label": "Market caps", "as_of": "11 Aug", "behind": 5, "stale": True, "source": None},
    ])
    captured = []
    monkeypatch.setattr(components.st, "markdown", lambda *a, **k: captured.append(a[0]))
    components.render_freshness_ribbon()

    html_out = captured[0]
    assert "#d97706" in html_out   # amber, the stale source
    assert "#059669" in html_out   # green, the current one


def test_ribbon_says_today_rather_than_zero_days(monkeypatch):
    """A same-day reading. behind == 0 on a weekend means the latest SESSION,
    not today, and is covered in test_freshness_wording_and_sync_refresh."""
    monkeypatch.setattr(components, "data_freshness", lambda: [
        {"label": "Prices", "as_of": "18 Aug", "behind": 0, "is_today": True,
         "stale": False, "source": None},
    ])
    captured = []
    monkeypatch.setattr(components.st, "markdown", lambda *a, **k: captured.append(a[0]))
    components.render_freshness_ribbon()
    assert "today" in captured[0]
    assert "0 trading days" not in captured[0]
