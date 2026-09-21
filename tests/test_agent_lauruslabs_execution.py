"""Executable Stage-4B Batch-1 acceptance test for LAURUSLABS."""
from datetime import date

from agent.company_research import ResearchCandidate
from agent.contracts import QuantSnapshot, ResearchDomain
from agent.research_execution import evidence_ref, execute_research, judge_dossier
from agent.lauruslabs_research_packet import CUTOFF, lauruslabs_packet, lauruslabs_plan


def _snapshot():
    # Contract fixture only: production execution obtains rank/score from the
    # canonical System-1 hand-off. This test deliberately does not invent a
    # quantitative rank as a research input.
    return QuantSnapshot(
        as_of=CUTOFF,
        benchmark="^CRSLDX",
        universe="NIFTY TOTAL MARKET",
        model="system-1",
        config_fingerprint="test",
        rows=({"Symbol": "LAURUSLABS", "Rank": 1, "Score": 0.0},),
    )


def test_lauruslabs_packet_is_executable():
    packet = lauruslabs_packet()
    dossier = execute_research(
        _snapshot(),
        ResearchCandidate("LAURUSLABS", 1, 0.0, {"Symbol": "LAURUSLABS", "Rank": 1, "Score": 0.0}),
        packet,
    )
    judge_dossier(dossier)
    assert dossier.audit.evidence_count == len(packet.evidence)
    assert dossier.audit.causal_finding_count == 4
    assert dossier.audit.contradiction_count == 0
    assert dossier.audit.counter_evidence_count == 4


def test_lauruslabs_packet_uses_every_evidence_record():
    packet = lauruslabs_packet()
    all_refs = {evidence_ref(item) for item in packet.evidence}
    used_refs = {
        ref
        for finding in (*packet.causal_findings, *packet.contradictions)
        for ref in finding.evidence_refs
    }
    assert all_refs <= used_refs


def test_lauruslabs_plan_has_explicit_exclusions_and_material_domains():
    plan = lauruslabs_plan()
    assert plan.exclusions
    assert any("valuation" in item for item in plan.exclusions)
    assert any("System-1" in item for item in plan.exclusions)
    assert len(plan.material_domains) == 5
