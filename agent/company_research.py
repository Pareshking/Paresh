"""Stage-4 evidence-first company research boundary.

This module validates research records and converts an accepted QuantSnapshot
Top-N into immutable research candidates. It does not fetch prices, calculate
rankings, or assign qualitative investment scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable
from urllib.parse import urlparse

from agent.contracts import (
    Evidence,
    EvidenceKind,
    QuantSnapshot,
    ResearchDomain,
    ResearchItem,
    ResearchPlan,
    SourceTier,
    validate_snapshot,
)


@dataclass(frozen=True)
class ResearchCandidate:
    symbol: str
    rank: int
    score: float | None
    quantitative_facts: dict


@dataclass(frozen=True)
class CompanyResearchSet:
    as_of: date
    candidates: tuple[ResearchCandidate, ...]
    items: tuple[ResearchItem, ...]


def top_candidates(snapshot: QuantSnapshot, limit: int = 25) -> tuple[ResearchCandidate, ...]:
    validate_snapshot(snapshot)
    if limit < 1:
        raise ValueError("limit must be positive")

    seen: set[str] = set()
    rows = sorted(snapshot.rows, key=lambda row: int(row["Rank"]))
    result: list[ResearchCandidate] = []

    for row in rows[:limit]:
        symbol = str(row.get("Symbol", "")).strip().upper()
        if not symbol:
            raise ValueError("research candidate has an empty symbol")
        if symbol in seen:
            raise ValueError(f"duplicate research candidate: {symbol}")
        seen.add(symbol)

        rank = int(row["Rank"])
        if rank < 1:
            raise ValueError("research candidate rank must be positive")

        score_raw = row.get("Score")
        score = float(score_raw) if score_raw is not None else None
        result.append(
            ResearchCandidate(
                symbol=symbol,
                rank=rank,
                score=score,
                quantitative_facts=dict(row),
            )
        )

    return tuple(result)


_UNSTABLE_PRIMARY_VIDEO_HOSTS = frozenset({
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "vimeo.com",
    "www.vimeo.com",
})


def _unstable_primary_source_reason(source: str) -> str | None:
    """Return a short reason if `source` cannot support a PRIMARY tier claim.

    Deterministic and intentionally narrow (Stage-4B improvement tracker item
    19; Report 2 findings F1/F2): a video platform is not an independently
    re-checkable document, and a bare domain root is a live, ever-changing
    page rather than a fixed, dated disclosure -- both were found tiered
    PRIMARY in the ANANDRATHI packet. This does NOT try to classify a
    "generic-looking" page that has a path (e.g. an issuer's own about-us or
    operational-highlights page): that needs an entity-relative source-tier
    policy (item 9), not a URL-shape heuristic, and guessing at it here would
    be the over-engineering the operating standard warns against.
    """
    parsed = urlparse(source)
    if parsed.netloc in _UNSTABLE_PRIMARY_VIDEO_HOSTS:
        return "a video-hosting platform, not an independently re-checkable document"
    if parsed.path in ("", "/"):
        return "a bare domain root, a live page rather than a fixed dated document"
    return None


def validate_evidence_set(
    candidates: Iterable[ResearchCandidate],
    evidence: Iterable[Evidence],
    *,
    information_cutoff: date,
) -> None:
    """Validate an evidence set against its research candidates.

    `information_cutoff` is required, not defaulted to `date.today()`. A
    caller-supplied cutoff makes cutoff enforcement reproducible regardless of
    the day the validator happens to run; a silent "today" default previously
    let a future-publication test pass or fail depending on the calendar date
    (see Stage-4B improvement tracker, item 24 / Report 0 S3).
    """
    allowed = {candidate.symbol for candidate in candidates}
    ids: set[tuple[str, str, str]] = set()

    for item in evidence:
        symbol = item.entity.strip().upper()
        if symbol not in allowed:
            raise ValueError(f"evidence entity is outside research candidate set: {symbol}")
        if (
            item.source_tier is not SourceTier.DERIVED
            and item.published_on is None
            and not item.undated_primary_source
        ):
            raise ValueError(
                "primary/secondary evidence requires published_on "
                "(or an explicit, reviewed undated_primary_source=True): "
                f"{symbol}: {item.claim.strip()[:80]!r}"
            )
        if item.source_tier is SourceTier.PRIMARY:
            reason = _unstable_primary_source_reason(item.source)
            if reason:
                raise ValueError(
                    f"source cannot be tiered primary ({reason}): "
                    f"{symbol}: {item.source}"
                )
        if (
            item.source_tier is not SourceTier.DERIVED
            and not item.source.strip().lower().startswith(("http://", "https://"))
        ):
            raise ValueError(
                "primary/secondary evidence requires a real http(s) URL "
                f"(item 4): {symbol}: {item.source!r}"
            )
        if item.published_on and item.published_on > information_cutoff:
            raise ValueError("evidence publication date is after the information cutoff")
        if (
            item.event_date
            and item.event_date > information_cutoff
            and item.domain is not ResearchDomain.SCHEDULED_EVENTS
        ):
            raise ValueError("evidence event date is after the information cutoff")

        key = (symbol, item.kind.value, item.claim.strip())
        if key in ids:
            raise ValueError(f"duplicate evidence claim: {symbol}")
        ids.add(key)


def build_research_items(
    snapshot: QuantSnapshot,
    evidence: Iterable[Evidence] = (),
) -> CompanyResearchSet:
    candidates = top_candidates(snapshot)
    evidence_tuple = tuple(evidence)
    validate_evidence_set(candidates, evidence_tuple, information_cutoff=snapshot.as_of)

    by_symbol: dict[str, list[Evidence]] = {c.symbol: [] for c in candidates}
    for item in evidence_tuple:
        by_symbol[item.entity.strip().upper()].append(item)

    items: list[ResearchItem] = []
    for candidate in candidates:
        bucket = by_symbol[candidate.symbol]
        items.append(
            ResearchItem(
                symbol=candidate.symbol,
                rank=candidate.rank,
                quantitative_facts=dict(candidate.quantitative_facts),
                positive_evidence=tuple(e for e in bucket if e.kind is EvidenceKind.POSITIVE),
                negative_evidence=tuple(e for e in bucket if e.kind is EvidenceKind.NEGATIVE),
                unknowns=tuple(e for e in bucket if e.kind is EvidenceKind.UNKNOWN),
            )
        )

    return CompanyResearchSet(
        as_of=snapshot.as_of,
        candidates=candidates,
        items=tuple(items),
    )


def validate_research_coverage(
    evidence: Iterable[Evidence],
    required_domains: Iterable[ResearchDomain],
) -> None:
    """Require explicit evidence/unknown state only for selected material domains.

    There is intentionally no universal domain checklist. The ResearchPlan is
    the company-specific source of truth for which domains are material.
    """
    evidence_tuple = tuple(evidence)
    selected = tuple(required_domains)
    if len(selected) != len(set(selected)):
        raise ValueError("research coverage contains duplicate required domains")

    covered = {item.domain for item in evidence_tuple}
    missing = [domain.value for domain in selected if domain not in covered]
    if missing:
        raise ValueError("research coverage missing domains: " + ", ".join(missing))


def research_domain_summary(evidence: Iterable[Evidence]) -> dict[str, dict[str, int]]:
    """Return counts by research domain and evidence direction for reporting."""
    summary: dict[str, dict[str, int]] = {}
    for item in evidence:
        bucket = summary.setdefault(item.domain.value, {kind.value: 0 for kind in EvidenceKind})
        bucket[item.kind.value] += 1
    return summary


def validate_research_plan(plan: ResearchPlan) -> None:
    """Validate the company-specific analytical lens before evidence collection."""
    if len(plan.material_domains) != len(set(plan.material_domains)):
        raise ValueError("research plan contains duplicate material domains")
    if any(not question.strip() for question in plan.hypotheses):
        raise ValueError("research plan contains an empty hypothesis/question")
