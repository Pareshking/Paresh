from agent.anandrathi_research_packet import anandrathi_plan
from agent.contracts import ResearchDomain


def test_anandrathi_uses_wealth_management_lens():
    plan = anandrathi_plan()
    assert plan.company_archetype.startswith("wealth-management")
    assert "AUM growth from net client inflows and market performance" in plan.economic_drivers
    assert ResearchDomain.CUSTOMERS_SUPPLIERS in plan.material_domains
    assert ResearchDomain.GOVERNMENT_REGULATION in plan.material_domains
    assert ResearchDomain.TECHNOLOGY_IP in plan.material_domains
    assert ResearchDomain.CAPACITY not in plan.material_domains
    assert ResearchDomain.INPUTS_ENERGY not in plan.material_domains
    assert any("AUM" in hypothesis for hypothesis in plan.hypotheses)


def test_anandrathi_explicitly_excludes_manufacturing_and_bank_lenses():
    plan = anandrathi_plan()
    assert any("plant-utilisation" in item for item in plan.exclusions)
    assert any("NIM" in item for item in plan.exclusions)


from datetime import date

from agent.company_research import ResearchCandidate
from agent.contracts import QuantSnapshot
from agent.anandrathi_research_packet import anandrathi_packet
from agent.research_execution import execute_research, judge_dossier


def test_anandrathi_packet_executes_end_to_end():
    """The executable archetype packet must be exercised, not only its plan."""
    snapshot = QuantSnapshot(
        as_of=date(2026, 9, 18),
        benchmark="^CRSLDX",
        universe="NIFTY TOTAL MARKET",
        model="system-1",
        config_fingerprint="test",
        rows=(("Symbol", "Rank", "Score"),),
    )
    candidate = ResearchCandidate(
        symbol="ANANDRATHI",
        rank=7,
        score=2.0,
        quantitative_facts={"Symbol": "ANANDRATHI", "Rank": 7, "Score": 2.0},
    )
    dossier = execute_research(snapshot, candidate, anandrathi_packet())
    judge_dossier(dossier)
    assert dossier.audit.evidence_count == 16
    assert dossier.audit.causal_finding_count == 4
    assert dossier.audit.contradiction_count == 4
