"""Executable Stage-4B Batch-1 acceptance test for SHILPAMED."""
from datetime import date

from agent.company_research import ResearchCandidate
from agent.contracts import QuantSnapshot, ResearchDomain
from agent.research_execution import evidence_ref, execute_research, judge_dossier
from agent.shilpamed_research_packet import CUTOFF, shilpamed_packet, shilpamed_plan


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
        rows=({"Symbol": "SHILPAMED", "Rank": 1, "Score": 0.0},),
    )


def test_shilpamed_packet_is_executable():
    packet = shilpamed_packet()
    dossier = execute_research(
        _snapshot(),
        ResearchCandidate("SHILPAMED", 1, 0.0, {"Symbol": "SHILPAMED", "Rank": 1, "Score": 0.0}),
        packet,
    )
    judge_dossier(dossier)
    assert dossier.audit.evidence_count == len(packet.evidence)
    assert dossier.audit.causal_finding_count == 4
    assert dossier.audit.contradiction_count == 0
    assert dossier.audit.counter_evidence_count == 4


def test_shilpamed_packet_uses_every_evidence_record():
    packet = shilpamed_packet()
    all_refs = {evidence_ref(item) for item in packet.evidence}
    used_refs = {
        ref
        for finding in (*packet.causal_findings, *packet.contradictions)
        for ref in finding.evidence_refs
    }
    assert all_refs <= used_refs


def test_shilpamed_plan_has_explicit_exclusions_and_material_domains():
    plan = shilpamed_plan()
    assert plan.exclusions
    assert any("valuation" in item for item in plan.exclusions)
    assert any("System-1" in item for item in plan.exclusions)
    assert len(plan.material_domains) == 7


def test_contradiction_semantics_reject_complementary_facts():
    from agent.research_execution import _claims_directly_conflict
    assert not _claims_directly_conflict("OERIS received regulatory approval.", "A USFDA inspection was conducted at the facility.")
    assert _claims_directly_conflict("OERIS was approved for marketing.", "OERIS was rejected for marketing.")
