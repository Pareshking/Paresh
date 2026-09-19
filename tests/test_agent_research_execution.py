from datetime import date

import pytest

from agent.company_research import ResearchCandidate
from agent.contracts import Evidence, EvidenceKind, QuantSnapshot, ResearchDomain, ResearchPlan, SourceTier
from agent.research_execution import (
    CausalFinding,
    ContradictionFinding,
    ResearchProviderPacket,
    evidence_ref,
    execute_research,
    judge_dossier,
)


def snapshot():
    return QuantSnapshot(
        as_of=date(2026, 9, 18),
        benchmark="^CRSLDX",
        universe="NIFTY TOTAL MARKET",
        model="system-1",
        config_fingerprint="x",
        rows=(
            {"Symbol": "AAA", "Rank": 1, "Score": 3.0},
            {"Symbol": "BBB", "Rank": 2, "Score": 2.0},
        ),
    )


def plan():
    return ResearchPlan(
        symbol="BBB",
        company_archetype="industrial",
        economic_drivers=("order conversion", "capacity utilisation"),
        material_domains=(ResearchDomain.ORDERS, ResearchDomain.CAPACITY),
        hypotheses=(
            "Can order growth convert into revenue?",
            "Can capacity support the order pipeline?",
        ),
        exclusions=("target prices and valuation recommendations",),
    )


def evidence_set():
    return (
        Evidence(
            entity="BBB",
            kind=EvidenceKind.POSITIVE,
            claim="New orders were disclosed.",
            source="https://primary.example/orders",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026, 9, 10),
            event_date=date(2026, 9, 9),
            retrieved_on=date(2026, 9, 19),
            domain=ResearchDomain.ORDERS,
            hypothesis="Can order growth convert into revenue?",
        ),
        Evidence(
            entity="BBB",
            kind=EvidenceKind.UNKNOWN,
            claim="Current utilisation was not disclosed.",
            source="research-window",
            source_tier=SourceTier.DERIVED,
            retrieved_on=date(2026, 9, 19),
            domain=ResearchDomain.CAPACITY,
            hypothesis="Can capacity support the order pipeline?",
        ),
    )


def packet():
    evidence = evidence_set()
    refs = tuple(evidence_ref(e) for e in evidence)
    return ResearchProviderPacket(
        plan=plan(),
        evidence=evidence,
        causal_findings=(
            CausalFinding(
                hypothesis="Can order growth convert into revenue?",
                finding="Order growth can support future revenue if execution capacity is available.",
                mechanism="Orders must pass through production and customer qualification before revenue.",
                timing="Near-to-medium term; exact timing remains dependent on execution.",
                uncertainty="Conversion timing is not fully disclosed.",
                evidence_refs=(refs[0],),
            ),
            CausalFinding(
                hypothesis="Can capacity support the order pipeline?",
                finding="Capacity adequacy is unresolved.",
                mechanism="Undisclosed utilisation prevents a firm conversion estimate.",
                timing="Monitoring is required as new orders are executed.",
                uncertainty="Utilisation and bottleneck data are unknown.",
                evidence_refs=(refs[1],),
            ),
        ),
        contradictions=(
            ContradictionFinding(
                hypothesis="Can order growth convert into revenue?",
                original_claim="Orders imply future revenue growth.",
                counter_evidence="Execution capacity may constrain conversion.",
                resolution="Treat revenue timing as conditional rather than completed.",
                original_claim_refs=(refs[0],),
                counter_evidence_refs=(refs[1],),
            ),
        ),
        unresolved_questions=("What is current utilisation?",),
        monitoring_questions=("Track order conversion and utilisation next quarter.",),
    )


def test_execution_preserves_non_top_rank_candidate():
    dossier = execute_research(snapshot(), ResearchCandidate("BBB", 2, 2.0, {"Symbol": "BBB", "Rank": 2, "Score": 2.0}), packet())
    assert dossier.candidate.symbol == "BBB"
    assert dossier.item.symbol == "BBB"
    assert dossier.item.rank == 2
    assert dossier.item.quantitative_facts["Score"] == 2.0


def test_execution_rejects_unknown_hypothesis_reference():
    p = packet()
    bad = ResearchProviderPacket(
        plan=p.plan,
        evidence=p.evidence,
        causal_findings=p.causal_findings
        + (
            CausalFinding(
                hypothesis="not in plan",
                finding="x",
                mechanism="y",
                timing="z",
                uncertainty="u",
                evidence_refs=(evidence_ref(p.evidence[0]),),
            ),
        ),
        contradictions=p.contradictions,
        unresolved_questions=p.unresolved_questions,
        monitoring_questions=p.monitoring_questions,
    )
    with pytest.raises(ValueError, match="unknown hypothesis"):
        execute_research(snapshot(), ResearchCandidate("BBB", 2, 2.0, {}), bad)


def test_execution_requires_provenance_for_causal_finding():
    p = packet()
    bad = ResearchProviderPacket(
        plan=p.plan,
        evidence=p.evidence,
        causal_findings=(
            CausalFinding(
                hypothesis=p.plan.hypotheses[0],
                finding="x",
                mechanism="y",
                timing="z",
                uncertainty="u",
                evidence_refs=(),
            ),
        ),
        contradictions=p.contradictions,
        unresolved_questions=p.unresolved_questions,
        monitoring_questions=p.monitoring_questions,
    )
    with pytest.raises(ValueError, match="requires evidence provenance"):
        execute_research(snapshot(), ResearchCandidate("BBB", 2, 2.0, {}), bad)


def test_execution_requires_hypothesis_coverage():
    p = packet()
    evidence = (p.evidence[0],)
    bad_plan = ResearchPlan(
        symbol="BBB",
        company_archetype="industrial",
        economic_drivers=p.plan.economic_drivers,
        material_domains=(ResearchDomain.ORDERS,),
        hypotheses=p.plan.hypotheses,
        exclusions=("target prices and valuation recommendations",),
    )
    bad = ResearchProviderPacket(plan=bad_plan, evidence=evidence)
    with pytest.raises(ValueError, match="lack evidence"):
        execute_research(snapshot(), ResearchCandidate("BBB", 2, 2.0, {}), bad)


def test_judge_rejects_no_contradiction_challenge():
    p = packet()
    no_challenge = ResearchProviderPacket(
        plan=p.plan,
        evidence=p.evidence,
        causal_findings=p.causal_findings,
        unresolved_questions=p.unresolved_questions,
        monitoring_questions=p.monitoring_questions,
    )
    dossier = execute_research(snapshot(), ResearchCandidate("BBB", 2, 2.0, {}), no_challenge)
    with pytest.raises(ValueError, match="no contradiction challenge"):
        judge_dossier(dossier)


def test_judge_accepts_complete_packet():
    dossier = execute_research(snapshot(), ResearchCandidate("BBB", 2, 2.0, {}), packet())
    judge_dossier(dossier)
    assert dossier.audit.primary_evidence_count == 1
    assert dossier.audit.contradiction_count == 1


def test_post_cutoff_evidence_is_rejected():
    p = packet()
    later = Evidence(
        entity="BBB",
        kind=EvidenceKind.POSITIVE,
        claim="Later event",
        source="https://primary.example/later",
        source_tier=SourceTier.PRIMARY,
        published_on=date(2026, 9, 10),
        event_date=date(2026, 9, 19),
        retrieved_on=date(2026, 9, 19),
        domain=ResearchDomain.ORDERS,
        hypothesis=p.plan.hypotheses[0],
    )
    bad = ResearchProviderPacket(
        plan=p.plan,
        evidence=p.evidence + (later,),
        causal_findings=p.causal_findings,
        contradictions=p.contradictions,
        unresolved_questions=p.unresolved_questions,
        monitoring_questions=p.monitoring_questions,
    )
    with pytest.raises(ValueError, match="after the information cutoff"):
        execute_research(snapshot(), ResearchCandidate("BBB", 2, 2.0, {}), bad)


def test_execution_rejects_string_evidence_refs_in_contradiction():
    p = packet()
    bad_finding = ContradictionFinding(
        hypothesis=p.plan.hypotheses[0],
        original_claim="x",
        counter_evidence="y",
        resolution="z",
        original_claim_refs=evidence_ref(p.evidence[0]),
        counter_evidence_refs=(evidence_ref(p.evidence[1]),),
    )
    bad = ResearchProviderPacket(
        plan=p.plan,
        evidence=p.evidence,
        causal_findings=p.causal_findings,
        contradictions=(bad_finding,),
        unresolved_questions=p.unresolved_questions,
        monitoring_questions=p.monitoring_questions,
    )
    with pytest.raises(ValueError, match="must be a tuple"):
        execute_research(snapshot(), ResearchCandidate("BBB", 2, 2.0, {}), bad)


def test_evidence_window_gap_uses_newest_published_on():
    """Item 20 (Report 2 F4): the evidence-window gap is max(published_on)
    vs snapshot.as_of, not a per-item age check (items 11/12)."""
    dossier = execute_research(
        snapshot(), ResearchCandidate("BBB", 2, 2.0, {}), packet()
    )
    # fixture's only dated (non-DERIVED) item is published_on=2026-09-10;
    # snapshot as_of is 2026-09-18.
    assert dossier.audit.newest_evidence_anchor == date(2026, 9, 10)
    assert dossier.evidence_window_gap_days == 8


def test_evidence_window_gap_falls_back_to_event_date_for_undated_primary_source():
    """An item that legitimately has no publication date (a live/evergreen
    source, undated_primary_source=True) should still count toward window
    freshness via its event_date -- excluding it would understate how fresh
    the evidence set actually is."""
    p = packet()
    fresher_undated = Evidence(
        entity="BBB",
        kind=EvidenceKind.POSITIVE,
        claim="A live page shows a more recent as-of figure.",
        source="https://issuer.example/",
        source_tier=SourceTier.SECONDARY,
        undated_primary_source=True,
        event_date=date(2026, 9, 17),
        retrieved_on=date(2026, 9, 19),
        domain=ResearchDomain.ORDERS,
        hypothesis="Can order growth convert into revenue?",
    )
    bad = ResearchProviderPacket(
        plan=p.plan,
        evidence=p.evidence + (fresher_undated,),
        causal_findings=p.causal_findings,
        contradictions=p.contradictions,
        unresolved_questions=p.unresolved_questions,
        monitoring_questions=p.monitoring_questions,
    )
    dossier = execute_research(snapshot(), ResearchCandidate("BBB", 2, 2.0, {}), bad)
    assert dossier.audit.newest_evidence_anchor == date(2026, 9, 17)
    assert dossier.evidence_window_gap_days == 1


def test_evidence_window_gap_ignores_derived_items():
    """A DERIVED absence-of-evidence record must never set the freshness
    anchor, even if it happens to carry an event_date -- it is not
    information, so it should not count as current information."""
    p = packet()
    derived_with_date = Evidence(
        entity="BBB",
        kind=EvidenceKind.UNKNOWN,
        claim="We looked but found nothing newer.",
        source="research-window",
        source_tier=SourceTier.DERIVED,
        event_date=date(2026, 9, 18),
        retrieved_on=date(2026, 9, 19),
        domain=ResearchDomain.CAPACITY,
        hypothesis="Can capacity support the order pipeline?",
    )
    bad = ResearchProviderPacket(
        plan=p.plan,
        evidence=p.evidence + (derived_with_date,),
        causal_findings=p.causal_findings,
        contradictions=p.contradictions,
        unresolved_questions=p.unresolved_questions,
        monitoring_questions=p.monitoring_questions,
    )
    dossier = execute_research(snapshot(), ResearchCandidate("BBB", 2, 2.0, {}), bad)
    # Still 2026-09-10 (the PRIMARY item), NOT 2026-09-18 from the DERIVED one.
    assert dossier.audit.newest_evidence_anchor == date(2026, 9, 10)
    assert dossier.evidence_window_gap_days == 8


def test_evidence_window_gap_is_none_without_any_anchor():
    """No evidence item carries a usable temporal anchor -> None, not a
    crash and not a misleading 0."""
    minimal_plan = ResearchPlan(
        symbol="BBB",
        company_archetype="industrial",
        economic_drivers=("capacity utilisation",),
        material_domains=(ResearchDomain.CAPACITY,),
        hypotheses=("Can capacity support the order pipeline?",),
        exclusions=("target prices and valuation recommendations",),
    )
    only_derived = ResearchProviderPacket(
        plan=minimal_plan,
        evidence=(
            Evidence(
                entity="BBB",
                kind=EvidenceKind.UNKNOWN,
                claim="Current utilisation was not disclosed.",
                source="research-window",
                source_tier=SourceTier.DERIVED,
                retrieved_on=date(2026, 9, 19),
                domain=ResearchDomain.CAPACITY,
                hypothesis="Can capacity support the order pipeline?",
            ),
        ),
        causal_findings=(),
        contradictions=(),
        unresolved_questions=("What is current utilisation?",),
        monitoring_questions=(),
    )
    # execute_research itself does not require causal/contradiction presence
    # (that is judge_dossier's job), so this should still construct a dossier.
    dossier = execute_research(snapshot(), ResearchCandidate("BBB", 2, 2.0, {}), only_derived)
    assert dossier.audit.newest_evidence_anchor is None
    assert dossier.evidence_window_gap_days is None


def test_numeric_disagreement_detects_linked_headline_figures_differing():
    """Item 8 (Report 1 B1): SANSERA's real ADS-backlog case -- one claim's
    headline figure (44,368) is explicitly restated inside a second claim
    that also gives a materially different headline figure (57,500). The
    smaller figure appearing verbatim in the other claim is what proves they
    describe the same quantity; that is what makes this safe to flag without
    any keyword/topic matching."""
    p = packet()
    evidence = p.evidence + (
        Evidence(
            entity="BBB",
            kind=EvidenceKind.POSITIVE,
            claim="Backlog was INR 44,368 million at June 2026.",
            source="https://primary.example/backlog-1",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026, 8, 1),
            retrieved_on=date(2026, 9, 19),
            domain=ResearchDomain.ORDERS,
            hypothesis="Can order growth convert into revenue?",
        ),
        Evidence(
            entity="BBB",
            kind=EvidenceKind.POSITIVE,
            claim="A later update put backlog at INR 57,500 million, up from INR 44,368 million.",
            source="https://secondary.example/backlog-2",
            source_tier=SourceTier.SECONDARY,
            published_on=date(2026, 9, 1),
            retrieved_on=date(2026, 9, 19),
            domain=ResearchDomain.ORDERS,
            hypothesis="Can order growth convert into revenue?",
        ),
    )
    bad = ResearchProviderPacket(
        plan=p.plan,
        evidence=evidence,
        causal_findings=p.causal_findings,
        contradictions=p.contradictions,
        unresolved_questions=p.unresolved_questions,
        monitoring_questions=p.monitoring_questions,
    )
    dossier = execute_research(snapshot(), ResearchCandidate("BBB", 2, 2.0, {}), bad)
    assert len(dossier.audit.numeric_disagreements) == 1
    assert "44368" in dossier.audit.numeric_disagreements[0]
    assert "57500" in dossier.audit.numeric_disagreements[0]


def test_numeric_disagreement_ignores_unrelated_co_occurring_figures():
    """A same-domain false positive found while prototyping this detector:
    two different metrics (e.g. AUM and a separate net-inflow figure quoted
    two sentences apart) must NOT be flagged just because they sit in the
    same domain. Only each claim's own maximum figure is compared, and only
    when the smaller one is explicitly linked by appearing in the other
    claim too."""
    p = packet()
    evidence = p.evidence + (
        Evidence(
            entity="BBB",
            kind=EvidenceKind.POSITIVE,
            claim="AUM was INR 1,06,300 crore and net inflows were INR 2,743 crore.",
            source="https://primary.example/aum",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026, 8, 1),
            retrieved_on=date(2026, 9, 19),
            domain=ResearchDomain.ORDERS,
            hypothesis="Can order growth convert into revenue?",
        ),
        Evidence(
            entity="BBB",
            kind=EvidenceKind.NEGATIVE,
            claim="Net inflows were INR 2,743 crore versus INR 3,824 crore a year earlier.",
            source="https://secondary.example/inflows",
            source_tier=SourceTier.SECONDARY,
            published_on=date(2026, 8, 2),
            retrieved_on=date(2026, 9, 19),
            domain=ResearchDomain.ORDERS,
            hypothesis="Can order growth convert into revenue?",
        ),
    )
    bad = ResearchProviderPacket(
        plan=p.plan,
        evidence=evidence,
        causal_findings=p.causal_findings,
        contradictions=p.contradictions,
        unresolved_questions=p.unresolved_questions,
        monitoring_questions=p.monitoring_questions,
    )
    dossier = execute_research(snapshot(), ResearchCandidate("BBB", 2, 2.0, {}), bad)
    assert dossier.audit.numeric_disagreements == ()
