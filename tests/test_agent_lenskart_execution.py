from datetime import date

from agent.company_research import ResearchCandidate
from agent.contracts import QuantSnapshot, ResearchDomain
from agent.research_execution import evidence_ref, execute_research
from agent.lenskart_research_packet import CUTOFF, lenskart_packet, lenskart_plan


def _snapshot():
    return QuantSnapshot(
        as_of=CUTOFF,
        benchmark="^CRSLDX",
        universe="NIFTY TOTAL MARKET",
        model="system-1",
        config_fingerprint="test",
        rows=(
            {"Symbol": "LENSKART", "Rank": 11, "Score": 2.0519887521211624},
        ),
    )


def test_lenskart_packet_is_executable():
    packet = lenskart_packet()
    dossier = execute_research(
        _snapshot(),
        ResearchCandidate(
            "LENSKART",
            11,
            2.0519887521211624,
            {"Symbol": "LENSKART", "Rank": 11, "Score": 2.0519887521211624},
        ),
        packet,
    )
    assert dossier.audit.evidence_count == 26
    assert dossier.audit.causal_finding_count == 6
    assert dossier.audit.contradiction_count == 4


def test_lenskart_packet_uses_every_evidence_record():
    """Mirrors test_anandrathi_packet_uses_every_evidence_record (Stage-4B
    improvement tracker item 18/E5): every evidence item this packet ships
    should be cited by at least one causal finding or contradiction, not left
    as unreferenced padding.
    """
    packet = lenskart_packet()
    all_refs = {evidence_ref(item) for item in packet.evidence}
    used_refs = {
        ref
        for finding in (*packet.causal_findings, *packet.contradictions)
        for ref in finding.evidence_refs
    }
    assert all_refs <= used_refs


def test_lenskart_plan_exclusions_are_explicit_and_material():
    """Mirrors test_anandrathi_plan_exclusions_are_explicit_and_material and
    test_sansera_plan_declares_explicit_exclusions (item 23): a consumer D2C
    retail brand is not a lending institution, so bank-style credit analysis
    is explicitly out of scope, and this research does not adopt any
    brokerage's own target price as its view.
    """
    plan = lenskart_plan()
    assert plan.exclusions
    assert any("NIM" in item for item in plan.exclusions)
    assert any("valuation" in item for item in plan.exclusions)
    assert any("System-1" in item for item in plan.exclusions)
    assert ResearchDomain.GOVERNMENT_REGULATION not in plan.material_domains
