"""Read-only market hierarchy adapters for the research agent.

Stage 3 does not own market calculations or taxonomy. It accepts outputs already
produced by Paresh canonical loaders/engines and makes their identity explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Sequence

import pandas as pd

from src.core.types import RegimeData
from agent.contracts import QuantSnapshot, validate_snapshot


@dataclass(frozen=True)
class MarketContext:
    """Canonical market context supplied by existing Paresh owners."""
    as_of: date
    benchmark: str
    regime: RegimeData
    breadth: tuple[dict[str, Any], ...] = ()
    breadth_as_of: date | None = None
    source_owners: tuple[str, ...] = ()


@dataclass(frozen=True)
class HierarchyRow:
    """One symbol's existing classification plus deterministic peer membership."""
    symbol: str
    sector: str | None
    industry: str | None
    peer_taxonomy: str
    peer_group: tuple[str, ...]


@dataclass(frozen=True)
class MarketHierarchyContext:
    """Read-only Stage-3 context for market -> sector -> industry -> peer research."""
    as_of: date
    benchmark: str
    universe: str
    taxonomy: str
    market: MarketContext
    rows: tuple[HierarchyRow, ...]
    industry_rankings: tuple[dict[str, Any], ...] = ()


_TAXONOMY_COLUMNS: Mapping[str, str] = {
    "NSE Industry": "Industry",
    "TV Industry (119)": "TV_Industry",
    "TV Sector (20)": "TV_Sector",
}


def _clean_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def _validate_symbols(snapshot: QuantSnapshot) -> tuple[str, ...]:
    validate_snapshot(snapshot)
    symbols = tuple(str(row.get("Symbol", "")).strip().upper() for row in snapshot.rows)
    if not symbols or any(not s for s in symbols):
        raise ValueError("Stage-3 hierarchy requires non-empty snapshot symbols")
    if len(symbols) != len(set(symbols)):
        raise ValueError("Stage-3 hierarchy snapshot contains duplicate symbols")
    return symbols


def build_market_context(
    snapshot: QuantSnapshot,
    regime: RegimeData,
    breadth: pd.DataFrame | None = None,
    *,
    source_owners: Sequence[str] = (
        "src/loaders/price_loader.py::get_market_regime",
        "src/engine/breadth.py",
    ),
) -> MarketContext:
    """Wrap existing market outputs without recalculating them."""
    _validate_symbols(snapshot)
    if regime is None:
        raise ValueError("market regime is required; unknown must be explicit")
    if not isinstance(regime, RegimeData):
        raise TypeError("regime must be canonical RegimeData")

    records: list[dict[str, Any]] = []
    breadth_as_of: date | None = None
    if breadth is not None:
        if not isinstance(breadth, pd.DataFrame):
            raise TypeError("breadth must be a pandas DataFrame when supplied")
        if not breadth.empty:
            records = [
                {"date": str(idx), **{str(k): v for k, v in row.items()}}
                for idx, row in breadth.iterrows()
            ]
            try:
                parsed = pd.to_datetime(breadth.index, errors="raise")
                breadth_as_of = parsed.max().date()
            except (TypeError, ValueError):
                raise ValueError("breadth index must contain parseable dates")
            if breadth_as_of > snapshot.as_of:
                raise ValueError("breadth_as_of cannot be after snapshot as_of")

    return MarketContext(
        as_of=snapshot.as_of,
        benchmark=snapshot.benchmark,
        regime=regime,
        breadth=tuple(records),
        breadth_as_of=breadth_as_of,
        source_owners=tuple(source_owners),
    )


def build_hierarchy_context(
    snapshot: QuantSnapshot,
    market: MarketContext,
    rank_df: pd.DataFrame,
    *,
    taxonomy: str = "TV Industry (119)",
    industry_rankings: pd.DataFrame | None = None,
) -> MarketHierarchyContext:
    """Build context from existing rows; peers are only taxonomy groups."""
    symbols = _validate_symbols(snapshot)
    if market.as_of != snapshot.as_of or market.benchmark != snapshot.benchmark:
        raise ValueError("market context identity does not match QuantSnapshot")
    if not isinstance(rank_df, pd.DataFrame) or rank_df.empty:
        raise ValueError("rank_df is required and cannot be empty")

    if taxonomy not in _TAXONOMY_COLUMNS:
        raise ValueError(
            f"unsupported taxonomy {taxonomy!r}; choose one of "
            f"{', '.join(_TAXONOMY_COLUMNS)}"
        )
    tax_col = _TAXONOMY_COLUMNS[taxonomy]
    required = {"Symbol", tax_col}
    missing = sorted(required - set(rank_df.columns))
    if missing:
        raise ValueError(
            f"rank_df missing required Stage-3 columns: {', '.join(missing)}"
        )

    frame = rank_df.copy()
    frame["Symbol"] = frame["Symbol"].astype(str).str.strip().str.upper()
    if frame["Symbol"].duplicated().any():
        raise ValueError("rank_df contains duplicate symbols")
    frame = frame.set_index("Symbol", drop=False)

    missing_symbols = [s for s in symbols if s not in frame.index]
    if missing_symbols:
        raise ValueError(
            "rank_df is missing snapshot symbols: " + ", ".join(missing_symbols[:10])
        )

    # Build peers from the full supplied canonical ranking frame so a
    # candidate sees all same-taxonomy peers already present in the universe.
    peer_map: dict[str, list[str]] = {}
    for symbol, row in frame.iterrows():
        group = _clean_text(row[tax_col])
        if group is not None:
            peer_map.setdefault(group, []).append(symbol)

    rows: list[HierarchyRow] = []
    for symbol in symbols:
        sector = _clean_text(frame.at[symbol, "TV_Sector"]) if "TV_Sector" in frame.columns else None
        industry = _clean_text(frame.at[symbol, "TV_Industry"]) if "TV_Industry" in frame.columns else None
        if taxonomy == "NSE Industry":
            industry = _clean_text(frame.at[symbol, "Industry"])
        elif taxonomy == "TV Sector (20)":
            industry = _clean_text(frame.at[symbol, "TV_Industry"]) if "TV_Industry" in frame.columns else None

        group_value = _clean_text(frame.at[symbol, tax_col])
        peers = tuple(sorted(peer_map.get(group_value, []))) if group_value else ()
        rows.append(
            HierarchyRow(
                symbol=symbol,
                sector=sector,
                industry=industry,
                peer_taxonomy=taxonomy if group_value else "unknown",
                peer_group=peers,
            )
        )

    agg_records: list[dict[str, Any]] = []
    if industry_rankings is not None:
        if not isinstance(industry_rankings, pd.DataFrame):
            raise TypeError("industry_rankings must be a pandas DataFrame when supplied")
        if not industry_rankings.empty:
            agg_records = industry_rankings.to_dict("records")

    return MarketHierarchyContext(
        as_of=snapshot.as_of,
        benchmark=snapshot.benchmark,
        universe=snapshot.universe,
        taxonomy=taxonomy,
        market=market,
        rows=tuple(rows),
        industry_rankings=tuple(agg_records),
    )


def membership_as_of(history: dict[str, Any], on: date) -> frozenset[str] | None:
    """Read point-in-time membership from the canonical membership timeline.

    The canonical owner deliberately returns None outside its coverage. That
    uncertainty is preserved here; this adapter never substitutes current
    constituents for a historical date.
    """
    from src.engine.membership import members_on

    members = members_on(history, on)
    return frozenset(members) if members is not None else None
