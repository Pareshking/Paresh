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
                evidence_refs=(refs[0], refs[1]),
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
