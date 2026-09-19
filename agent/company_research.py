"""Stage-4 evidence-first company research boundary.

This module validates research records and converts an accepted QuantSnapshot
Top-N into immutable research candidates. It does not fetch prices, calculate
rankings, or assign qualitative investment scores.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from agent.contracts import Evidence, EvidenceKind, QuantSnapshot, ResearchItem, validate_snapshot


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


def validate_evidence_set(
    candidates: Iterable[ResearchCandidate],
    evidence: Iterable[Evidence],
) -> None:
    allowed = {candidate.symbol for candidate in candidates}
    ids: set[tuple[str, str, str]] = set()

    for item in evidence:
        symbol = item.entity.strip().upper()
        if symbol not in allowed:
            raise ValueError(f"evidence entity is outside research candidate set: {symbol}")
        if item.published_on and item.published_on > date.today():
            raise ValueError("evidence publication date cannot be in the future")

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
    validate_evidence_set(candidates, evidence_tuple)

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
