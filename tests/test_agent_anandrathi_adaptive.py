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
