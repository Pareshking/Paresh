from __future__ import annotations

from datetime import date
import ast
from pathlib import Path

import pandas as pd
import pytest

from agent.contracts import QuantSnapshot
from agent.market_hierarchy import (
    build_hierarchy_context,
    build_market_context,
)
from src.core.types import MarketRegime, RegimeData


def _snapshot(rows=None, *, as_of=date(2026, 9, 18), benchmark="^CRSLDX"):
    return QuantSnapshot(
        as_of=as_of,
        benchmark=benchmark,
        universe="NIFTY TOTAL MARKET",
        model="System-1",
        config_fingerprint="fp",
        rows=tuple(rows or [{"Symbol": "AAA"}, {"Symbol": "BBB"}]),
        pipeline_version="v4_calendar_periods_cbab8da9",
        price_source="screener",
        price_as_of=as_of,
        source_artifact="rankings.parquet",
    )


def _regime():
    return RegimeData(
        status=MarketRegime.BULLISH,
        current_price=100.0,
        dma_200=95.0,
        distance_pct=5.2631579,
    )


def test_market_context_wraps_canonical_outputs_without_recalculation():
    snapshot = _snapshot()
    breadth = pd.DataFrame({"50D": [40.0, 55.0]}, index=pd.to_datetime(["2026-09-17", "2026-09-18"]))
    context = build_market_context(snapshot, _regime(), breadth)

    assert context.as_of == snapshot.as_of
    assert context.benchmark == "^CRSLDX"
    assert context.regime is _regime() or context.regime == _regime()
    assert len(context.breadth) == 2
    assert context.breadth[-1]["50D"] == 55.0
    assert "src/engine/breadth.py" in context.source_owners


def test_market_context_rejects_noncanonical_regime_object():
    with pytest.raises(TypeError, match="canonical RegimeData"):
        build_market_context(_snapshot(), {"status": "BULLISH"})  # type: ignore[arg-type]


def test_hierarchy_uses_explicit_tv_industry_and_full_universe_for_peers():
    snapshot = _snapshot([{"Symbol": "AAA"}, {"Symbol": "BBB"}])
    market = build_market_context(snapshot, _regime())
    frame = pd.DataFrame(
        [
            {"Symbol": "AAA", "TV_Sector": "Technology Services", "TV_Industry": "Packaged Software", "Industry": "IT"},
            {"Symbol": "BBB", "TV_Sector": "Technology Services", "TV_Industry": "Packaged Software", "Industry": "IT"},
            {"Symbol": "CCC", "TV_Sector": "Technology Services", "TV_Industry": "Semiconductors", "Industry": "IT"},
        ]
    )

    out = build_hierarchy_context(snapshot, market, frame, taxonomy="TV Industry (119)")
    rows = {r.symbol: r for r in out.rows}

    assert out.taxonomy == "TV Industry (119)"
    assert rows["AAA"].peer_taxonomy == "TV Industry (119)"
    assert rows["AAA"].peer_group == ("AAA", "BBB")
    assert rows["AAA"].sector == "Technology Services"
    assert rows["AAA"].industry == "Packaged Software"
    assert rows["BBB"].peer_group == ("AAA", "BBB")


def test_nse_industry_is_not_conflated_with_tv_industry():
    snapshot = _snapshot([{"Symbol": "AAA"}])
    market = build_market_context(snapshot, _regime())
    frame = pd.DataFrame(
        [{"Symbol": "AAA", "TV_Sector": "Finance", "TV_Industry": "Investment Managers", "Industry": "Banks"}]
    )

    out = build_hierarchy_context(snapshot, market, frame, taxonomy="NSE Industry")
    assert out.rows[0].industry == "Banks"
    assert out.rows[0].peer_taxonomy == "NSE Industry"


def test_tv_sector_peer_group_is_explicitly_sector_based():
    snapshot = _snapshot([{"Symbol": "AAA"}])
    market = build_market_context(snapshot, _regime())
    frame = pd.DataFrame(
        [
            {"Symbol": "AAA", "TV_Sector": "Finance", "TV_Industry": "Banks"},
            {"Symbol": "BBB", "TV_Sector": "Finance", "TV_Industry": "Investment Managers"},
        ]
    )

    out = build_hierarchy_context(snapshot, market, frame, taxonomy="TV Sector (20)")
    assert out.rows[0].peer_group == ("AAA", "BBB")
    assert out.rows[0].industry == "Banks"


def test_missing_taxonomy_is_unknown_and_not_a_peer():
    snapshot = _snapshot([{"Symbol": "AAA"}])
    market = build_market_context(snapshot, _regime())
    frame = pd.DataFrame([{"Symbol": "AAA", "TV_Sector": "Finance", "TV_Industry": None}])

    out = build_hierarchy_context(snapshot, market, frame, taxonomy="TV Industry (119)")
    row = out.rows[0]
    assert row.peer_taxonomy == "unknown"
    assert row.peer_group == ()


def test_duplicate_snapshot_symbols_fail_closed():
    snapshot = _snapshot([{"Symbol": "AAA"}, {"Symbol": "AAA"}])
    with pytest.raises(ValueError, match="duplicate symbols"):
        build_market_context(snapshot, _regime())


def test_duplicate_rank_rows_fail_closed():
    snapshot = _snapshot([{"Symbol": "AAA"}])
    market = build_market_context(snapshot, _regime())
    frame = pd.DataFrame(
        [{"Symbol": "AAA", "TV_Industry": "Banks"}, {"Symbol": "AAA", "TV_Industry": "Banks"}]
    )
    with pytest.raises(ValueError, match="duplicate symbols"):
        build_hierarchy_context(snapshot, market, frame)


def test_missing_snapshot_symbol_fails_closed():
    snapshot = _snapshot([{"Symbol": "AAA"}, {"Symbol": "BBB"}])
    market = build_market_context(snapshot, _regime())
    frame = pd.DataFrame([{"Symbol": "AAA", "TV_Industry": "Banks"}])
    with pytest.raises(ValueError, match="missing snapshot symbols"):
        build_hierarchy_context(snapshot, market, frame)


def test_unsupported_taxonomy_fails_closed():
    snapshot = _snapshot([{"Symbol": "AAA"}])
    market = build_market_context(snapshot, _regime())
    frame = pd.DataFrame([{"Symbol": "AAA", "TV_Industry": "Banks"}])
    with pytest.raises(ValueError, match="unsupported taxonomy"):
        build_hierarchy_context(snapshot, market, frame, taxonomy="Made Up")


def test_market_identity_mismatch_fails_closed():
    snapshot = _snapshot([{"Symbol": "AAA"}])
    other = _snapshot([{"Symbol": "AAA"}], as_of=date(2026, 9, 17))
    market = build_market_context(other, _regime())
    frame = pd.DataFrame([{"Symbol": "AAA", "TV_Industry": "Banks"}])
    with pytest.raises(ValueError, match="identity"):
        build_hierarchy_context(snapshot, market, frame)


def test_industry_aggregation_is_preserved_not_recalculated():
    snapshot = _snapshot([{"Symbol": "AAA"}])
    market = build_market_context(snapshot, _regime())
    frame = pd.DataFrame([{"Symbol": "AAA", "TV_Industry": "Banks"}])
    agg = pd.DataFrame([{"Industry": "Banks", "Stocks": 7, "3M Return": 0.12, "Rank": 2}])

    out = build_hierarchy_context(snapshot, market, frame, industry_rankings=agg)
    assert out.industry_rankings == tuple(agg.to_dict("records"))


def test_input_frame_is_not_mutated():
    snapshot = _snapshot([{"Symbol": "AAA"}])
    market = build_market_context(snapshot, _regime())
    frame = pd.DataFrame([{"Symbol": "AAA", "TV_Industry": "Banks"}])
    before = frame.copy(deep=True)

    build_hierarchy_context(snapshot, market, frame)
    pd.testing.assert_frame_equal(frame, before)


def test_hierarchy_module_has_no_price_or_ranking_engine_imports():
    source = Path("agent/market_hierarchy.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any(name == "yfinance" or name.startswith("yfinance.") for name in imported)
    assert not any(name == "src.engine.pipeline" for name in imported)
    assert not any(name == "src.loaders.price_loader" for name in imported)
    assert "src/loaders/price_loader.py::get_market_regime" in source


def test_membership_as_of_preserves_canonical_unknown_before_coverage():
    from agent.market_hierarchy import membership_as_of

    history = {
        "baseline": {"date": "2026-09-01", "symbols": ["AAA", "BBB"]},
        "changes": [{"date": "2026-09-10", "added": ["CCC"], "removed": ["BBB"]}],
    }
    assert membership_as_of(history, date(2026, 8, 31)) is None
    assert membership_as_of(history, date(2026, 9, 5)) == frozenset({"AAA", "BBB"})
    assert membership_as_of(history, date(2026, 9, 12)) == frozenset({"AAA", "CCC"})
