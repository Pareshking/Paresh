from datetime import date

from agent.anandrathi_research_packet import anandrathi_packet, anandrathi_plan
from agent.company_research import ResearchCandidate
from agent.contracts import QuantSnapshot, ResearchDomain
from agent.research_execution import evidence_ref, execute_research


def _snapshot():
    return QuantSnapshot(
        as_of=date(2026, 9, 18),
        benchmark="^CRSLDX",
        universe="NIFTY TOTAL MARKET",
        model="system-1",
        config_fingerprint="test",
        rows=(
            {"Symbol": "ANANDRATHI", "Rank": 7, "Score": 2.19},
        ),
    )


def test_anandrathi_packet_is_executable():
    packet = anandrathi_packet()
    dossier = execute_research(
        _snapshot(),
        ResearchCandidate(
            "ANANDRATHI",
            7,
            2.19,
            {"Symbol": "ANANDRATHI", "Rank": 7, "Score": 2.19},
        ),
        packet,
    )
    assert dossier.audit.evidence_count == 16
    assert dossier.audit.causal_finding_count == 4
    assert dossier.audit.contradiction_count == 4


def test_anandrathi_packet_uses_every_evidence_record():
    packet = anandrathi_packet()
    all_refs = {evidence_ref(item) for item in packet.evidence}
    used_refs = {
        ref
        for finding in (*packet.causal_findings, *packet.contradictions)
        for ref in finding.evidence_refs
    }
    assert all_refs <= used_refs


def test_anandrathi_plan_exclusions_are_explicit_and_material():
    plan = anandrathi_plan()
    assert any("NIM" in item for item in plan.exclusions)
    assert any("plant-utilisation" in item for item in plan.exclusions)
    assert ResearchDomain.CAPACITY not in plan.material_domains
    assert ResearchDomain.INPUTS_ENERGY not in plan.material_domains
