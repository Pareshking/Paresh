from datetime import date, timedelta

import pytest

from agent.company_research import (
    build_research_items,
    top_candidates,
    validate_evidence_set,
    validate_research_coverage,
    research_domain_summary,
    validate_research_plan,
)
from agent.contracts import Evidence, EvidenceKind, QuantSnapshot, ResearchDomain, ResearchPlan, SourceTier


def snapshot(rows):
    return QuantSnapshot(
        as_of=date(2026, 9, 18),
        benchmark="^CRSLDX",
        universe="NIFTY TOTAL MARKET",
        model="system-1",
        config_fingerprint="x",
        rows=tuple(rows),
    )


def test_top_candidates_is_deterministic_and_read_only():
    rows = (
        {"Symbol": "BBB", "Rank": 2, "Score": 2.0},
        {"Symbol": "AAA", "Rank": 1, "Score": 3.0},
    )
    out = top_candidates(snapshot(rows))
    assert [x.symbol for x in out] == ["AAA", "BBB"]
    assert [x.rank for x in out] == [1, 2]
    assert out[0].score == 3.0


def test_duplicate_candidates_fail():
    with pytest.raises(ValueError, match="duplicate research candidate"):
        top_candidates(snapshot((
            {"Symbol": "AAA", "Rank": 1, "Score": 3.0},
            {"Symbol": "AAA", "Rank": 2, "Score": 2.0},
        )))


def test_evidence_outside_candidate_set_fails():
    candidates = top_candidates(snapshot(({"Symbol": "AAA", "Rank": 1, "Score": 3.0},)))
    evidence = Evidence(
        entity="BBB",
        kind=EvidenceKind.UNKNOWN,
        claim="Unverified",
        source="https://example.com",
        source_tier=SourceTier.SECONDARY,
        retrieved_on=date(2026, 9, 19),
    )
    with pytest.raises(ValueError, match="outside research candidate set"):
        validate_evidence_set(candidates, (evidence,))


def test_future_publication_date_fails():
    candidates = top_candidates(snapshot(({"Symbol": "AAA", "Rank": 1, "Score": 3.0},)))
    evidence = Evidence(
        entity="AAA",
        kind=EvidenceKind.POSITIVE,
        claim="Future event",
        source="https://example.com",
        source_tier=SourceTier.PRIMARY,
        published_on=date.today() + timedelta(days=1),
        retrieved_on=date.today(),
    )
    with pytest.raises(ValueError, match="after the information cutoff"):
        validate_evidence_set(candidates, (evidence,))


def test_duplicate_evidence_claim_fails():
    candidates = top_candidates(snapshot(({"Symbol": "AAA", "Rank": 1, "Score": 3.0},)))
    evidence = Evidence(
        entity="AAA",
        kind=EvidenceKind.POSITIVE,
        claim="Same claim",
        source="https://example.com",
        source_tier=SourceTier.PRIMARY,
        retrieved_on=date(2026, 9, 19),
    )
    with pytest.raises(ValueError, match="duplicate evidence claim"):
        validate_evidence_set(candidates, (evidence, evidence))


def test_unknown_is_preserved():
    snap = snapshot(({"Symbol": "AAA", "Rank": 1, "Score": 3.0},))
    evidence = Evidence(
        entity="AAA",
        kind=EvidenceKind.UNKNOWN,
        claim="No verified material event was established in the searched sources.",
        source="research-window",
        source_tier=SourceTier.DERIVED,
        retrieved_on=date(2026, 9, 19),
    )
    result = build_research_items(snap, (evidence,))
    assert len(result.items[0].unknowns) == 1
    assert not result.items[0].negative_evidence


def test_research_does_not_change_rank_or_score():
    snap = snapshot(({"Symbol": "AAA", "Rank": 1, "Score": 3.0},))
    evidence = Evidence(
        entity="AAA",
        kind=EvidenceKind.POSITIVE,
        claim="Verified event",
        source="https://example.com",
        source_tier=SourceTier.PRIMARY,
        retrieved_on=date(2026, 9, 19),
    )
    result = build_research_items(snap, (evidence,))
    assert result.items[0].rank == 1
    assert result.items[0].quantitative_facts["Score"] == 3.0


def test_research_coverage_requires_explicit_domain_states():
    evidence = (
        Evidence(
            entity="AAA", kind=EvidenceKind.UNKNOWN, claim="Industry not established",
            source="research-window", source_tier=SourceTier.DERIVED,
            retrieved_on=date(2026, 9, 19), domain=ResearchDomain.INDUSTRY,
        ),
    )
    with pytest.raises(ValueError, match="missing domains"):
        validate_research_coverage(evidence, (ResearchDomain.INDUSTRY, ResearchDomain.PEERS))


def test_research_coverage_requires_selected_domains_explicitly():
    evidence = (
        Evidence(
            entity="AAA", kind=EvidenceKind.UNKNOWN, claim="Only selected domain checked",
            source="research-window", source_tier=SourceTier.DERIVED,
            retrieved_on=date(2026, 9, 19), domain=ResearchDomain.CAPACITY,
        ),
    )
    with pytest.raises(TypeError):
        validate_research_coverage(evidence)


def test_research_coverage_accepts_unknown_as_a_valid_state():
    evidence = (
        Evidence(
            entity="AAA", kind=EvidenceKind.UNKNOWN, claim="Industry context unresolved",
            source="research-window", source_tier=SourceTier.DERIVED,
            retrieved_on=date(2026, 9, 19), domain=ResearchDomain.INDUSTRY,
        ),
        Evidence(
            entity="AAA", kind=EvidenceKind.POSITIVE, claim="Peer evidence",
            source="https://example.com", source_tier=SourceTier.SECONDARY,
            retrieved_on=date(2026, 9, 19), domain=ResearchDomain.PEERS,
        ),
    )
    validate_research_coverage(evidence, (ResearchDomain.INDUSTRY, ResearchDomain.PEERS))


def test_research_domain_summary_preserves_direction():
    evidence = (
        Evidence(entity="AAA", kind=EvidenceKind.POSITIVE, claim="A", source="x", source_tier=SourceTier.PRIMARY, retrieved_on=date(2026, 9, 19), domain=ResearchDomain.CAPACITY),
        Evidence(entity="AAA", kind=EvidenceKind.NEGATIVE, claim="B", source="y", source_tier=SourceTier.SECONDARY, retrieved_on=date(2026, 9, 19), domain=ResearchDomain.CAPACITY),
        Evidence(entity="AAA", kind=EvidenceKind.UNKNOWN, claim="C", source="z", source_tier=SourceTier.DERIVED, retrieved_on=date(2026, 9, 19), domain=ResearchDomain.CAPACITY),
    )
    assert research_domain_summary(evidence)["capacity"] == {"positive": 1, "negative": 1, "unknown": 1}


def test_event_date_after_snapshot_cutoff_fails():
    candidates = top_candidates(snapshot(({"Symbol": "AAA", "Rank": 1, "Score": 3.0},)))
    evidence = Evidence(
        entity="AAA", kind=EvidenceKind.POSITIVE, claim="Later event",
        source="https://example.com", source_tier=SourceTier.PRIMARY,
        event_date=date(2026, 9, 19), retrieved_on=date(2026, 9, 19),
    )
    with pytest.raises(ValueError, match="after the information cutoff"):
        validate_evidence_set(candidates, (evidence,), information_cutoff=date(2026, 9, 18))


def test_company_specific_research_plan_requires_drivers_and_hypotheses():
    plan = ResearchPlan(
        symbol="AAA", company_archetype="CDMO",
        economic_drivers=("capacity utilisation", "customer pipeline"),
        material_domains=(ResearchDomain.CAPACITY, ResearchDomain.CUSTOMERS_SUPPLIERS),
        hypotheses=("Is new capacity supported by customer commitments?",),
        exclusions=("retail store metrics",),
    )
    validate_research_plan(plan)


def test_company_specific_research_plan_rejects_duplicate_domains():
    plan = ResearchPlan(
        symbol="AAA", company_archetype="bank",
        economic_drivers=("NIM",),
        material_domains=(ResearchDomain.FINANCIALS, ResearchDomain.FINANCIALS),
        hypotheses=("Is funding cost changing?",),
    )
    with pytest.raises(ValueError, match="duplicate material domains"):
        validate_research_plan(plan)
