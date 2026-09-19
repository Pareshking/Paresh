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


class ResearchDomain(str, Enum):
    COMPANY = "company"
    FINANCIALS = "financials"
    MANAGEMENT = "management"
    ORDERS = "orders"
    CAPACITY = "capacity"
    CUSTOMERS_SUPPLIERS = "customers_suppliers"
    PEERS = "peers"
    INDUSTRY = "industry"
    SECTOR = "sector"
    GOVERNMENT_REGULATION = "government_regulation"
    INPUTS_ENERGY = "inputs_energy"
    FX = "fx"
    TARIFF_TRADE = "tariff_trade"
    MACRO_GEOPOLITICS = "macro_geopolitics"
    TECHNOLOGY_IP = "technology_ip"
    CAPITAL_MARKETS = "capital_markets"
    LEGAL_COMPLIANCE = "legal_compliance"
    MARKET_REACTION = "market_reaction"
    SCHEDULED_EVENTS = "scheduled_events"
    CONTRADICTIONS = "contradictions"
    UNKNOWN_QUESTIONS = "unknown_questions"


@dataclass(frozen=True)
class ResearchPlan:
    """Company-specific research lens selected before evidence collection."""
    symbol: str
    company_archetype: str
    economic_drivers: tuple[str, ...]
    material_domains: tuple[ResearchDomain, ...]
    hypotheses: tuple[str, ...]
    exclusions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("research plan symbol is required")
        if not self.company_archetype.strip():
            raise ValueError("research plan company_archetype is required")
        if not self.economic_drivers:
            raise ValueError("research plan requires economic drivers")
        if not self.material_domains:
            raise ValueError("research plan requires material domains")
        if not self.hypotheses:
            raise ValueError("research plan requires hypotheses/questions")
        if not self.exclusions:
            raise ValueError(
                "research plan requires explicit exclusions (item 23): a plan "
                "that names nothing out of scope has not demonstrated the "
                "domain library was applied selectively rather than as a "
                "checklist"
            )


@dataclass(frozen=True)
class QuantSnapshot:
    as_of: date
    benchmark: str
    universe: str
    model: str
    config_fingerprint: str
    rows: tuple[dict[str, Any], ...] = ()
    pipeline_version: str = ""
    price_source: str = ""
    price_as_of: date | None = None
    source_artifact: str = ""


@dataclass(frozen=True)
class Evidence:
    entity: str
    kind: EvidenceKind
    claim: str
    source: str
    source_tier: SourceTier
    published_on: date | None = None
    retrieved_on: date | None = None
    event_date: date | None = None
    domain: ResearchDomain = ResearchDomain.COMPANY
    materiality: str = "material"
    hypothesis: str = ""
    confidence: float | None = None
    notes: str = ""
    undated_primary_source: bool = False
    """Explicit, narrow escape from the published_on requirement in
    validate_evidence_set (tracker item 1 / A1) for a source that genuinely
    carries no publication date -- an evergreen page (e.g. a static "about
    us" page) or a live site showing only an "as of" data date, as opposed
    to a dated document or article. Defaults to False so a missing date
    fails closed by default; it must be set deliberately, per item, after
    confirming (e.g. by fetching the live source) that no date exists to
    record. When True, event_date must still be set -- there must be some
    verifiable temporal anchor, even if it is not a publication date."""

    def __post_init__(self) -> None:
        if not self.entity.strip():
            raise ValueError("evidence entity is required")
        if not self.claim.strip():
            raise ValueError("evidence claim is required")
        if not self.source.strip():
            raise ValueError("evidence source is required")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if self.published_on and self.retrieved_on and self.published_on > self.retrieved_on:
            raise ValueError("published_on cannot be after retrieved_on")
        if (
            self.event_date
            and self.retrieved_on
            and self.event_date > self.retrieved_on
            and self.domain is not ResearchDomain.SCHEDULED_EVENTS
        ):
            raise ValueError("event_date cannot be after retrieved_on")
        if not self.materiality.strip():
            raise ValueError("materiality is required")
        if self.undated_primary_source and self.event_date is None:
            raise ValueError(
                "undated_primary_source requires event_date as a temporal anchor"
            )


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


def validate_report(report: WeeklyReport) -> None:
    """Fail closed on structural inconsistencies before a report is emitted."""
    validate_snapshot(
        QuantSnapshot(
            as_of=report.as_of,
            benchmark=report.benchmark,
            universe=report.universe,
            model=report.model,
            config_fingerprint="report-validation",
        )
    )
    symbols = [item.symbol.strip() for item in report.items]
    if any(not symbol for symbol in symbols):
        raise ValueError("report contains an empty symbol")
    if len(symbols) != len(set(symbols)):
        raise ValueError("report contains duplicate symbols")

    for item in report.items:
        if item.rank is not None and item.rank < 1:
            raise ValueError("rank must be positive")
        for field_name, expected in (
            ("positive_evidence", EvidenceKind.POSITIVE),
            ("negative_evidence", EvidenceKind.NEGATIVE),
            ("unknowns", EvidenceKind.UNKNOWN),
        ):
            for evidence in getattr(item, field_name):
                if evidence.kind is not expected:
                    raise ValueError(f"{field_name} contains mismatched evidence kind")

    known = set(symbols)
    for review in report.reviews:
        if review.symbol not in known:
            raise ValueError(f"review symbol not present in report: {review.symbol}")


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
    if snapshot.price_as_of and snapshot.price_as_of > snapshot.as_of:
        raise ValueError("price_as_of cannot be after snapshot as_of")
