"""Executable acceptance test for the YATHARTH Stage-4B packet.

Mirrors tests/test_agent_anandrathi_execution.py and
tests/test_agent_sansera_execution.py: this exercises the real executable
path (packet -> execute_research -> judge_dossier), not just declarative
plan assertions, per improvement-tracker item 17 (E4).
"""
from datetime import date

from agent.company_research import ResearchCandidate
from agent.contracts import QuantSnapshot, ResearchDomain
from agent.research_execution import evidence_ref, execute_research, judge_dossier
from agent.yatharth_research_packet import CUTOFF, yatharth_packet, yatharth_plan


def _snapshot():
    return QuantSnapshot(
        as_of=CUTOFF,
        benchmark="^CRSLDX",
        universe="NIFTY TOTAL MARKET",
        model="system-1",
        config_fingerprint="test",
        rows=(
            {"Symbol": "YATHARTH", "Rank": 17, "Score": 1.852871},
        ),
    )


def test_yatharth_packet_is_executable():
    packet = yatharth_packet()
    dossier = execute_research(
        _snapshot(),
        ResearchCandidate(
            "YATHARTH",
            17,
            1.852871,
            {"Symbol": "YATHARTH", "Rank": 17, "Score": 1.852871},
        ),
        packet,
    )
    judge_dossier(dossier)
    assert dossier.audit.evidence_count == 21
    assert dossier.audit.causal_finding_count == 5
    assert dossier.audit.contradiction_count == 4


def test_yatharth_packet_uses_every_evidence_record():
    packet = yatharth_packet()
    all_refs = {evidence_ref(item) for item in packet.evidence}
    used_refs = {
        ref
        for finding in (*packet.causal_findings, *packet.contradictions)
        for ref in finding.evidence_refs
    }
    assert all_refs <= used_refs


def test_yatharth_plan_exclusions_are_explicit_and_material():
    """Item 23: every archetype must declare what it deliberately did not
    research, mirroring the ANANDRATHI/SANSERA exclusions tests. A hospital
    operator is a different archetype from an industrial exporter (SANSERA)
    or a wealth manager (ANANDRATHI), so its exclusions should say so.
    """
    plan = yatharth_plan()
    assert plan.exclusions
    assert any("NIM" in item or "GNPA" in item for item in plan.exclusions)
    assert any("tariff" in item.lower() for item in plan.exclusions)
    assert any("valuation" in item for item in plan.exclusions)
    assert any("System-1" in item for item in plan.exclusions)
    # A hospital operator's material domains should not include the
    # manufacturing-specific ORDERS domain SANSERA declares material.
    assert ResearchDomain.ORDERS not in plan.material_domains
    assert ResearchDomain.CAPACITY in plan.material_domains
    assert ResearchDomain.CUSTOMERS_SUPPLIERS in plan.material_domains
