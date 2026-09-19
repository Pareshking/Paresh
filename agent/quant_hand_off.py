"""Stage-2 read-only hand-off from the canonical ranking artifact.

This module deliberately stops at the boundary between Paresh's deterministic
System-1 artifact and the research-agent layer. It never downloads prices,
builds the ranking engine, or recalculates any quantitative value.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from agent.contracts import QuantSnapshot, validate_snapshot
from agent.fingerprint import config_fingerprint
from src.core import config
from src.engine import pipeline
from src.loaders import ranking_store


class QuantHandoffError(ValueError):
    """Raised when the canonical ranking artifact cannot be trusted."""


_REQUIRED_CONTRACT_FIELDS = (
    "pipeline_version",
    "price_source",
    "price_as_of",
    "weights",
    "universe",
)
_REQUIRED_COLUMNS = ("Symbol", "Rank", "Score")


def _as_date(value: Any, field: str) -> date:
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError) as exc:
        raise QuantHandoffError(f"{field} is missing or invalid: {text!r}") from exc


def _canonical_weights() -> list[float]:
    weights = tuple(float(w) for w in config.DEFAULT_LOOKBACK_WEIGHTS)
    total = sum(weights)
    if total <= 0:
        raise QuantHandoffError("canonical lookback weights are invalid")
    return [round(w / total, 6) for w in weights]


def _validate_contract(published: dict[str, Any] | None) -> tuple[date, set[str]]:
    if not published:
        raise QuantHandoffError("ranking artifact has no embedded contract")

    missing = [
        field
        for field in _REQUIRED_CONTRACT_FIELDS
        if field not in published or published[field] in (None, "", [])
    ]
    if missing:
        raise QuantHandoffError(
            "ranking artifact contract missing: " + ", ".join(missing)
        )

    if published["pipeline_version"] != pipeline.PIPELINE_VERSION:
        raise QuantHandoffError("ranking artifact pipeline_version differs")

    artifact_source = str(published["price_source"]).strip().lower()
    preferred_source = str(config.RANKING_PRICE_SOURCE or "yahoo").strip().lower()
    # The canonical producer prefers screener but explicitly falls back to
    # Yahoo when screener is unavailable/too short. Accept either source only
    # in that documented configuration; otherwise the producer uses Yahoo.
    allowed_sources = {"screener", "yahoo"} if preferred_source == "screener" else {"yahoo"}
    if artifact_source not in allowed_sources:
        raise QuantHandoffError("ranking artifact price_source is not a canonical source")

    price_as_of = _as_date(published["price_as_of"], "price_as_of")

    try:
        stored_weights = [round(float(w), 6) for w in published["weights"]]
    except (TypeError, ValueError) as exc:
        raise QuantHandoffError("ranking artifact weights are invalid") from exc

    if stored_weights != _canonical_weights():
        raise QuantHandoffError("ranking artifact weights differ from canonical weights")

    universe = published["universe"]
    if not isinstance(universe, list) or not universe:
        raise QuantHandoffError("ranking artifact universe is empty")
    symbols = [str(symbol).strip().upper() for symbol in universe]
    if any(not symbol for symbol in symbols):
        raise QuantHandoffError("ranking artifact universe contains an empty symbol")
    if len(symbols) != len(set(symbols)):
        raise QuantHandoffError("ranking artifact universe contains duplicate symbols")

    return price_as_of, set(symbols)


def _validate_rows(frame: pd.DataFrame, universe_symbols: set[str]) -> None:
    if frame is None or frame.empty:
        raise QuantHandoffError("ranking artifact contains no rows")

    missing = [column for column in _REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise QuantHandoffError(
            "ranking artifact missing required columns: " + ", ".join(missing)
        )

    symbols = frame["Symbol"].astype(str).str.strip()
    if symbols.eq("").any():
        raise QuantHandoffError("ranking artifact contains an empty Symbol")
    normalized = symbols.str.upper()
    if normalized.duplicated().any():
        raise QuantHandoffError("ranking artifact contains duplicate Symbol rows")
    if not normalized.isin(universe_symbols).all():
        raise QuantHandoffError("ranking artifact contains Symbol outside contract universe")

    ranks = pd.to_numeric(frame["Rank"], errors="coerce")
    if ranks.isna().any() or (ranks < 1).any():
        raise QuantHandoffError("ranking artifact contains invalid Rank values")


def load_quant_snapshot(
    artifact_url: str | None = None,
    *,
    expected_as_of: date | None = None,
) -> QuantSnapshot:
    """Load and validate the published ranking without recalculating it.

    expected_as_of is an explicit audit constraint, not a date filter.
    When omitted, the artifact's own price_as_of becomes the snapshot as-of.
    """
    frame, published = ranking_store.fetch_snapshot(artifact_url)
    if frame is None:
        raise QuantHandoffError("canonical ranking artifact is unavailable")

    price_as_of, universe_symbols = _validate_contract(published)
    if expected_as_of is not None and price_as_of != expected_as_of:
        raise QuantHandoffError(
            f"ranking artifact as-of differs: {price_as_of.isoformat()} "
            f"!= {expected_as_of.isoformat()}"
        )

    _validate_rows(frame, universe_symbols)

    snapshot = QuantSnapshot(
        as_of=price_as_of,
        benchmark=config.BENCHMARK_SYMBOL,
        universe="NIFTY TOTAL MARKET",
        model="System-1",
        config_fingerprint=config_fingerprint(),
        rows=tuple(row.to_dict() for _, row in frame.iterrows()),
        pipeline_version=str(published["pipeline_version"]),
        price_source=str(published["price_source"]),
        price_as_of=price_as_of,
        source_artifact=artifact_url or config.RANKINGS_SNAPSHOT_URL,
    )
    validate_snapshot(snapshot)
    return snapshot
