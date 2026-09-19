"""Read-only contracts for the Paresh research agent.

These types deliberately contain no ranking mathematics. They define the boundary
between deterministic quantitative facts and qualitative research.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class EvidenceKind(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class SourceTier(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    DERIVED = "derived"


@dataclass(frozen=True)
class QuantSnapshot:
    as_of: date
    benchmark: str
    universe: str
    model: str
    config_fingerprint: str
    rows: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class Evidence:
    entity: str
    kind: EvidenceKind
    claim: str
    source: str
    source_tier: SourceTier
    published_on: date | None = None
    retrieved_on: date | None = None
    confidence: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")


@dataclass(frozen=True)
class ResearchItem:
    symbol: str
    rank: int | None
    quantitative_facts: dict[str, Any] = field(default_factory=dict)
    positive_evidence: tuple[Evidence, ...] = ()
    negative_evidence: tuple[Evidence, ...] = ()
    unknowns: tuple[Evidence, ...] = ()


@dataclass(frozen=True)
class AdversarialReview:
    symbol: str
    original_claims: tuple[str, ...]
    challenged_claims: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
    reviewer_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class WeeklyReport:
    as_of: date
    model: str
    universe: str
    benchmark: str
    items: tuple[ResearchItem, ...]
    reviews: tuple[AdversarialReview, ...] = ()
    methodology_notes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


def validate_snapshot(snapshot: QuantSnapshot) -> None:
    """Fail closed on missing identity fields before research is started."""
    required = {
        "benchmark": snapshot.benchmark,
        "universe": snapshot.universe,
        "model": snapshot.model,
        "config_fingerprint": snapshot.config_fingerprint,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError("quant snapshot missing: " + ", ".join(missing))
