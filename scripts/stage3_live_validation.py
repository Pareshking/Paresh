"""Live Stage-3 hierarchy verification against the published production ranking.

This is an audit harness, not a second quant/taxonomy implementation. It consumes
the Stage-2 QuantSnapshot, the canonical TradingView classification owner, and
the canonical market-regime owner, then calls the Stage-3 read-only hierarchy
adapter and writes the actual Top-25 hierarchy to an audit artifact.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from agent.market_hierarchy import MarketContext, build_hierarchy_context
from agent.quant_hand_off import load_quant_snapshot
from src.core.config import BENCHMARK_SYMBOL
from src.loaders.price_loader import get_market_regime
from src.loaders.tv_loader import load_tv_classification


OUTPUT = Path("artifacts/stage3_live_hierarchy.md")
TAXONOMY = "TV Industry (119)"


def main() -> None:
    snapshot = load_quant_snapshot()

    rows = pd.DataFrame(list(snapshot.rows))
    if rows.empty:
        raise AssertionError("published QuantSnapshot is empty")

    tv_map = load_tv_classification()
    rows["Symbol"] = rows["Symbol"].astype(str).str.strip().str.upper()
    rows["TV_Sector"] = rows["Symbol"].map(
        lambda s: tv_map.get(s, {}).get("TV_Sector", "")
    )
    rows["TV_Industry"] = rows["Symbol"].map(
        lambda s: tv_map.get(s, {}).get("TV_Industry", "")
    )

    if snapshot.benchmark != BENCHMARK_SYMBOL:
        raise AssertionError(
            f"snapshot benchmark {snapshot.benchmark!r} differs from canonical "
            f"{BENCHMARK_SYMBOL!r}"
        )

    regime = get_market_regime(BENCHMARK_SYMBOL)
    market = MarketContext(
        as_of=snapshot.as_of,
        benchmark=snapshot.benchmark,
        regime=regime,
        source_owners=("src/loaders/price_loader.py::get_market_regime",),
    )

    context = build_hierarchy_context(
        snapshot,
        market=market,
        rank_df=rows,
        taxonomy=TAXONOMY,
    )

    if len(snapshot.rows) != 750:
        raise AssertionError(
            f"live Stage-2 snapshot row count changed: {len(snapshot.rows)} != 750"
        )
    if len(context.rows) != 750:
        raise AssertionError(
            f"live Stage-3 hierarchy row count changed: {len(context.rows)} != 750"
        )

    rank_by_symbol = {
        str(row["Symbol"]).strip().upper(): int(row["Rank"]) for row in snapshot.rows
    }
    score_by_symbol = {
        str(row["Symbol"]).strip().upper(): float(row["Score"]) for row in snapshot.rows
    }
    if len(rank_by_symbol) != 750:
        raise AssertionError("live ranking contains duplicate symbols")

    top25 = sorted(context.rows, key=lambda r: rank_by_symbol[r.symbol])[:25]
    if len(top25) != 25:
        raise AssertionError("live Top-25 hierarchy did not contain 25 rows")

    lines = [
        "# Stage-3 Live Hierarchy Verification",
        "",
        "- Verification run: CI on current branch",
        f"- Snapshot as-of: {snapshot.as_of.isoformat()}",
        f"- Snapshot rows: {len(snapshot.rows)}",
        f"- Benchmark: {snapshot.benchmark}",
        f"- Market regime: {regime.status}",
        f"- Benchmark price: {regime.current_price:.4f}",
        f"- Benchmark 200DMA: {regime.dma_200:.4f}",
        f"- Benchmark distance to 200DMA: {regime.distance_pct:.4f}%",
        f"- Universe: {snapshot.universe}",
        f"- Pipeline: {snapshot.pipeline_version}",
        f"- Price source: {snapshot.price_source}",
        f"- Source artifact: {snapshot.source_artifact}",
        f"- Taxonomy: {TAXONOMY}",
        f"- Taxonomy rows loaded: {len(tv_map)}",
        "",
        "## Actual Top-25 hierarchy",
        "",
        "| Rank | Symbol | Score | TV Sector | TV Industry | Peer count | Top peers by rank |",
        "|---:|---|---:|---|---|---:|---|",
    ]

    for row in top25:
        peers = [
            symbol
            for symbol in sorted(
                row.peer_group,
                key=lambda s: rank_by_symbol.get(s, 10**9),
            )
            if symbol != row.symbol
        ]
        top_peers = peers[:10]
        peer_text = ", ".join(top_peers) if top_peers else "—"
        lines.append(
            f"| {rank_by_symbol[row.symbol]} | {row.symbol} | "
            f"{score_by_symbol[row.symbol]:.6f} | "
            f"{row.sector or 'UNKNOWN'} | {row.industry or 'UNKNOWN'} | "
            f"{len(row.peer_group)} | {peer_text} |"
        )

    classified = sum(1 for row in context.rows if row.peer_taxonomy != "unknown")
    unknown = len(context.rows) - classified
    lines.extend(
        [
            "",
            "## Verification assertions",
            "",
            "- SNAPSHOT_ROWS=750: PASS",
            "- HIERARCHY_ROWS=750: PASS",
            "- TOP25_ROWS=25: PASS",
            "- DUPLICATE_SYMBOLS=0: PASS",
            f"- CLASSIFIED_BY_TV_INDUSTRY_119={classified}",
            f"- UNKNOWN_CLASSIFICATION_ROWS={unknown}",
            "- Peer groups are derived from the full 750-row supplied ranking frame.",
            "- No new ranking calculation or taxonomy was introduced.",
            "",
            "## Status",
            "",
            "VERIFIED — actual live Stage-3 hierarchy executed against the current published ranking artifact.",
            "",
        ]
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
