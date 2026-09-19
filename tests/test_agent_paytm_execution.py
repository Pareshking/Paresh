"""Executable acceptance test for the PAYTM Stage-4B packet.

Mirrors tests/test_agent_anandrathi_execution.py and
tests/test_agent_sansera_execution.py: builds the real packet, runs it through
execute_research/judge_dossier, and asserts it passes end to end, rather than
only checking the declarative plan (see improvement-tracker item 17 / E4 --
a declarative-only test previously let a broken evidence packet pass).
"""
from datetime import date

from agent.company_research import ResearchCandidate
from agent.contracts import QuantSnapshot, ResearchDomain
from agent.research_execution import evidence_ref, execute_research, judge_dossier
from agent.paytm_research_packet import CUTOFF, paytm_packet, paytm_plan


def _snapshot():
    return QuantSnapshot(
        as_of=CUTOFF,
        benchmark="^CRSLDX",
        universe="NIFTY TOTAL MARKET",
        model="system-1",
        config_fingerprint="test",
        rows=(
            {"Symbol": "PAYTM", "Rank": 22, "Score": 1.776287},
        ),
    )


def test_paytm_packet_is_executable():
    packet = paytm_packet()
    dossier = execute_research(
        _snapshot(),
        ResearchCandidate(
            "PAYTM",
            22,
            1.776287,
            {"Symbol": "PAYTM", "Rank": 22, "Score": 1.776287},
        ),
        packet,
    )
    judge_dossier(dossier)
    assert dossier.audit.evidence_count == len(packet.evidence)
    assert dossier.audit.causal_finding_count == 4
    assert dossier.audit.contradiction_count == 4
    assert dossier.audit.hypotheses_with_causal_analysis == 4
    assert dossier.audit.hypotheses_challenged == 4


def test_paytm_packet_uses_every_evidence_record():
    packet = paytm_packet()
    all_refs = {evidence_ref(item) for item in packet.evidence}
    used_refs = {
        ref
        for finding in (*packet.causal_findings, *packet.contradictions)
        for ref in finding.evidence_refs
    }
    assert all_refs <= used_refs


def test_paytm_plan_declares_explicit_exclusions():
    """Item 23: every archetype must declare what it deliberately did not
    research. ResearchPlan.__post_init__ makes exclusions mandatory
    framework-wide; this additionally checks PAYTM's declared exclusions are
    the real, specific ones for a payments/financial-services distribution
    platform, not placeholders copied from an unrelated archetype.
    """
    plan = paytm_plan()
    assert plan.exclusions
    assert any("loan-book" in item or "NIM" in item for item in plan.exclusions)
    assert any("manufacturing capacity" in item for item in plan.exclusions)
    assert any("valuation" in item for item in plan.exclusions)
    assert any("System-1" in item for item in plan.exclusions)
    # A platform business with no lending balance sheet of its own should not
    # carry the manufacturing/capacity domain that a precision-engineering
    # exporter (SANSERA) needs.
    assert ResearchDomain.CAPACITY not in plan.material_domains
    assert ResearchDomain.ORDERS not in plan.material_domains
