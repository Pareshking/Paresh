from __future__ import annotations

from datetime import date

from agent.contracts import Evidence, EvidenceKind, ResearchDomain, ResearchPlan, SourceTier
from agent.research_execution import (
    CausalFinding,
    ContradictionFinding,
    ResearchProviderPacket,
    evidence_ref,
)

CUTOFF = date(2026, 9, 18)
RETRIEVED = date(2026, 9, 20)

def lauruslabs_plan() -> ResearchPlan:
    return ResearchPlan(
        symbol="LAURUSLABS",
        company_archetype="integrated API, formulations, CDMO and advanced-biologics pharmaceutical platform",
        economic_drivers=("CDMO project conversion", "ARV and developed-market formulations", "large-scale manufacturing/capex utilisation", "quality and regulatory execution", "pricing/tender and approval-cycle sensitivity"),
        material_domains=(ResearchDomain.FINANCIALS, ResearchDomain.CAPACITY, ResearchDomain.ORDERS, ResearchDomain.GOVERNMENT_REGULATION, ResearchDomain.UNKNOWN_QUESTIONS),
        hypotheses=("Is Laurus's FY27 growth broadening across CDMO and Affordable Medicines rather than depending on ARV/generic cycles?", "Can the large capex program translate into utilisation and commercial CDMO revenue without creating a balance-sheet drag?", "Are the CDMO pipeline, filings and quality record strong enough to support multi-year customer conversion?", "How exposed is near-term profitability to tender cycles, pricing pressure and project/approval timing?"),
        exclusions=("bank-style lending metrics and NIM", "plant-utilisation analysis unrelated to pharmaceutical capacity or qualification", "target prices or valuation recommendations", "recalculation of System-1 ranking or momentum"),
        evidence_half_life_days={ResearchDomain.FINANCIALS: 120, ResearchDomain.CAPACITY: 365, ResearchDomain.ORDERS: 180, ResearchDomain.GOVERNMENT_REGULATION: 365},
    )


def lauruslabs_evidence() -> tuple[Evidence, ...]:
    return (
        Evidence(
            entity="LAURUSLABS", kind=EvidenceKind.POSITIVE,
            claim="Laurus reported Q1 FY27 revenue of INR 2,026 crore, up 29% YoY, with EBITDA of INR 644 crore and an EBITDA margin of 31.8%.",
            source="https://www.lauruslabs.com/disclosures.html",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,7,24),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high",
            hypothesis="Is Laurus's FY27 growth broadening across CDMO and Affordable Medicines rather than depending on ARV/generic cycles?",
        ),
        Evidence(
            entity="LAURUSLABS", kind=EvidenceKind.POSITIVE,
            claim="FY26 revenue rose 23% to INR 6,813 crore, with CDMO revenue up 36% to INR 2,080 crore and Affordable Medicines up 18% to INR 4,733 crore.",
            source="https://www.lauruslabs.com/AR_FY25-26/investors.html",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,4,30),
            event_date=date(2026,3,31),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high",
            hypothesis="Is Laurus's FY27 growth broadening across CDMO and Affordable Medicines rather than depending on ARV/generic cycles?",
        ),
        Evidence(
            entity="LAURUSLABS", kind=EvidenceKind.NEGATIVE,
            claim="Laurus's FY26 business review notes that tender cycles and pricing dynamics can influence near-term FDF revenue phasing even while the overall outlook remains positive.",
            source="https://www.lauruslabs.com/AR_FY25-26/business-review.html",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,7,24),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.ORDERS, materiality="medium",
            hypothesis="Is Laurus's FY27 growth broadening across CDMO and Affordable Medicines rather than depending on ARV/generic cycles?",
        ),
        Evidence(
            entity="LAURUSLABS", kind=EvidenceKind.POSITIVE,
            claim="A September 2026 investor presentation shows Q1 FY27 capex of about INR 394 crore and more than INR 3,000 crore of proposed cumulative capex across FY27-FY28.",
            source="https://bazaarwatch.com/announcement/115630/laurus-labs-limited-investor-presentation",
            source_tier=SourceTier.SECONDARY,
            published_on=date(2026,9,18),
            event_date=date(2026,9,18),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="high",
            hypothesis="Can the large capex program translate into utilisation and commercial CDMO revenue without creating a balance-sheet drag?",
        ),
        Evidence(
            entity="LAURUSLABS", kind=EvidenceKind.NEGATIVE,
            claim="FY26 capex was INR 1,070 crore and net debt to EBITDA was 1.3x after the expansion program, so the growth plan carries ongoing funding and execution requirements.",
            source="https://www.lauruslabs.com/AR_FY25-26/investors.html",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,4,30),
            event_date=date(2026,3,31),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high",
            hypothesis="Can the large capex program translate into utilisation and commercial CDMO revenue without creating a balance-sheet drag?",
        ),
        Evidence(
            entity="LAURUSLABS", kind=EvidenceKind.POSITIVE,
            claim="Laurus reported 125+ active CDMO projects across clinical and commercial stages during FY26.",
            source="https://www.lauruslabs.com/AR_FY25-26/strategic-priorities.html",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,4,30),
            event_date=date(2026,3,31),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.ORDERS, materiality="high",
            hypothesis="Are the CDMO pipeline, filings and quality record strong enough to support multi-year customer conversion?",
        ),
        Evidence(
            entity="LAURUSLABS", kind=EvidenceKind.POSITIVE,
            claim="FY26 reporting states that 132+ quality audits were completed without critical findings and that 7 developed-market formulation dossiers were filed with 6 approvals received.",
            source="https://www.lauruslabs.com/AR_FY25-26/strategic-priorities.html",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,4,30),
            event_date=date(2026,3,31),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.GOVERNMENT_REGULATION, materiality="high",
            hypothesis="Are the CDMO pipeline, filings and quality record strong enough to support multi-year customer conversion?",
        ),
        Evidence(
            entity="LAURUSLABS", kind=EvidenceKind.POSITIVE,
            claim="FY26 business review states that dedicated CMO oral-dosage capacity at Vizag commenced operations and that the KRKA JV facility was progressing toward Phase 1 completion in mid-2027.",
            source="https://www.lauruslabs.com/AR_FY25-26/business-review.html",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,4,30),
            event_date=date(2026,3,31),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="high",
            hypothesis="Are the CDMO pipeline, filings and quality record strong enough to support multi-year customer conversion?",
        ),
        Evidence(
            entity="LAURUSLABS", kind=EvidenceKind.NEGATIVE,
            claim="Laurus explicitly flags tender cycles, pricing dynamics and approval timelines as factors that can affect near-term FDF revenue phasing.",
            source="https://www.lauruslabs.com/AR_FY25-26/business-review.html",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,4,30),
            event_date=date(2026,3,31),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.ORDERS, materiality="medium",
            hypothesis="How exposed is near-term profitability to tender cycles, pricing pressure and project/approval timing?",
        ),
        Evidence(
            entity="LAURUSLABS", kind=EvidenceKind.POSITIVE,
            claim="Independent results reporting confirms Q1 FY27 revenue of INR 2,026.31 crore and PAT of INR 362.07 crore, with PAT up about 124% YoY.",
            source="https://www.icicidirect.com/research/equity/rapid-results/laurus-labs-ltd",
            source_tier=SourceTier.SECONDARY,
            published_on=date(2026,7,24),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high",
            hypothesis="How exposed is near-term profitability to tender cycles, pricing pressure and project/approval timing?",
        ),
        Evidence(
            entity="LAURUSLABS", kind=EvidenceKind.UNKNOWN,
            claim="The reviewed disclosures do not establish the exact utilisation ramp and return profile of the full FY27-FY28 capex program.",
            source="research-window: Laurus disclosures reviewed through 2026-09-18",
            source_tier=SourceTier.DERIVED,
            published_on=date(2026,9,18),
            event_date=date(2026,9,18),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.UNKNOWN_QUESTIONS, materiality="high",
            hypothesis="Can the large capex program translate into utilisation and commercial CDMO revenue without creating a balance-sheet drag?",
        ),
        Evidence(
            entity="LAURUSLABS", kind=EvidenceKind.UNKNOWN,
            claim="The reviewed disclosures do not quantify the sensitivity of FY27 earnings to individual tender outcomes or customer approval delays.",
            source="research-window: Laurus disclosures reviewed through 2026-09-18",
            source_tier=SourceTier.DERIVED,
            published_on=date(2026,9,18),
            event_date=date(2026,9,18),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.UNKNOWN_QUESTIONS, materiality="medium",
            hypothesis="How exposed is near-term profitability to tender cycles, pricing pressure and project/approval timing?",
        ),
    )


def lauruslabs_packet() -> ResearchProviderPacket:
    evidence = lauruslabs_evidence()
    by_claim = {e.claim: e for e in evidence}
    def ref(claim: str) -> str:
        if claim not in by_claim:
            raise ValueError(f"unknown evidence claim: {claim}")
        return evidence_ref(by_claim[claim])
    plan = lauruslabs_plan()
    return ResearchProviderPacket(
        plan=plan,
        evidence=evidence,
        causal_findings=(
            CausalFinding(
                hypothesis="Is Laurus's FY27 growth broadening across CDMO and Affordable Medicines rather than depending on ARV/generic cycles?",
                finding="FY26 and Q1FY27 show growth across CDMO and Affordable Medicines, while tender/pricing effects remain a source of phasing risk.",
                mechanism="Diversification reduces reliance on one business, but the mature FDF portfolio still carries tender and pricing exposure.",
                timing="Quarterly to multi-year",
                uncertainty="The reviewed disclosures do not provide a single bridge attributing Q1 growth across all businesses.",
                evidence_refs=(ref("Laurus reported Q1 FY27 revenue of INR 2,026 crore, up 29% YoY, with EBITDA of INR 644 crore and an EBITDA margin of 31.8%."), ref("FY26 revenue rose 23% to INR 6,813 crore, with CDMO revenue up 36% to INR 2,080 crore and Affordable Medicines up 18% to INR 4,733 crore."), ref("Laurus's FY26 business review notes that tender cycles and pricing dynamics can influence near-term FDF revenue phasing even while the overall outlook remains positive.")),
            ),
            CausalFinding(
                hypothesis="Can the large capex program translate into utilisation and commercial CDMO revenue without creating a balance-sheet drag?",
                finding="The capex cycle is substantial relative to the existing asset base, while the current balance sheet remains supportive but not risk-free.",
                mechanism="New capacity can lift revenue and operating leverage if qualified and filled; until then it absorbs capital and may add depreciation/debt pressure.",
                timing="FY27-FY28+",
                uncertainty="Exact utilisation and return timing remain unresolved.",
                evidence_refs=(ref("A September 2026 investor presentation shows Q1 FY27 capex of about INR 394 crore and more than INR 3,000 crore of proposed cumulative capex across FY27-FY28."), ref("FY26 capex was INR 1,070 crore and net debt to EBITDA was 1.3x after the expansion program, so the growth plan carries ongoing funding and execution requirements."), ref("The reviewed disclosures do not establish the exact utilisation ramp and return profile of the full FY27-FY28 capex program.")),
            ),
            CausalFinding(
                hypothesis="Are the CDMO pipeline, filings and quality record strong enough to support multi-year customer conversion?",
                finding="A large active CDMO project base, strong audit record and capacity additions provide evidence of pipeline depth and execution infrastructure.",
                mechanism="Projects progress from development to validation to commercial supply; quality and capacity are prerequisites for conversion.",
                timing="Multi-year",
                uncertainty="Project count does not by itself disclose customer concentration or revenue conversion timing.",
                evidence_refs=(ref("Laurus reported 125+ active CDMO projects across clinical and commercial stages during FY26."), ref("FY26 reporting states that 132+ quality audits were completed without critical findings and that 7 developed-market formulation dossiers were filed with 6 approvals received."), ref("FY26 business review states that dedicated CMO oral-dosage capacity at Vizag commenced operations and that the KRKA JV facility was progressing toward Phase 1 completion in mid-2027.")),
            ),
            CausalFinding(
                hypothesis="How exposed is near-term profitability to tender cycles, pricing pressure and project/approval timing?",
                finding="Q1 profitability was strong, but the company itself identifies tender, pricing and approval timing as variables that can interrupt the path.",
                mechanism="Quarterly product mix and external pricing/tender outcomes affect revenue phasing and margin even with a growing underlying pipeline.",
                timing="Quarterly",
                uncertainty="No quantitative sensitivity to specific tender or approval outcomes was found.",
                evidence_refs=(ref("Laurus explicitly flags tender cycles, pricing dynamics and approval timelines as factors that can affect near-term FDF revenue phasing."), ref("Independent results reporting confirms Q1 FY27 revenue of INR 2,026.31 crore and PAT of INR 362.07 crore, with PAT up about 124% YoY."), ref("The reviewed disclosures do not quantify the sensitivity of FY27 earnings to individual tender outcomes or customer approval delays.")),
            ),
        ),
        contradictions=(
            ContradictionFinding(
                hypothesis="Is Laurus's FY27 growth broadening across CDMO and Affordable Medicines rather than depending on ARV/generic cycles?",
                original_claim="FY26 revenue rose 23% to INR 6,813 crore, with CDMO revenue up 36% to INR 2,080 crore and Affordable Medicines up 18% to INR 4,733 crore.",
                counter_evidence="Laurus's FY26 business review notes that tender cycles and pricing dynamics can influence near-term FDF revenue phasing even while the overall outlook remains positive.",
                resolution="Business diversification is documented, but FDF tender/pricing cycles remain a separate phasing risk.",
                original_claim_refs=("FY26 revenue rose 23% to INR 6,813 crore, with CDMO revenue up 36% to INR 2,080 crore and Affordable Medicines up 18% to INR 4,733 crore.",),
                counter_evidence_refs=("Laurus's FY26 business review notes that tender cycles and pricing dynamics can influence near-term FDF revenue phasing even while the overall outlook remains positive.",),
            ),
            ContradictionFinding(
                hypothesis="Can the large capex program translate into utilisation and commercial CDMO revenue without creating a balance-sheet drag?",
                original_claim="A September 2026 investor presentation shows Q1 FY27 capex of about INR 394 crore and more than INR 3,000 crore of proposed cumulative capex across FY27-FY28.",
                counter_evidence="The reviewed disclosures do not establish the exact utilisation ramp and return profile of the full FY27-FY28 capex program.",
                resolution="The company is committing significant capital, but the commercial ramp remains explicitly unresolved.",
                original_claim_refs=("A September 2026 investor presentation shows Q1 FY27 capex of about INR 394 crore and more than INR 3,000 crore of proposed cumulative capex across FY27-FY28.",),
                counter_evidence_refs=("The reviewed disclosures do not establish the exact utilisation ramp and return profile of the full FY27-FY28 capex program.",),
            ),
            ContradictionFinding(
                hypothesis="Are the CDMO pipeline, filings and quality record strong enough to support multi-year customer conversion?",
                original_claim="Laurus reported 125+ active CDMO projects across clinical and commercial stages during FY26.",
                counter_evidence="FY26 business review states that dedicated CMO oral-dosage capacity at Vizag commenced operations and that the KRKA JV facility was progressing toward Phase 1 completion in mid-2027.",
                resolution="Pipeline depth and capacity are positive evidence, while facility completion and qualification timing remain part of execution risk.",
                original_claim_refs=("Laurus reported 125+ active CDMO projects across clinical and commercial stages during FY26.",),
                counter_evidence_refs=("FY26 business review states that dedicated CMO oral-dosage capacity at Vizag commenced operations and that the KRKA JV facility was progressing toward Phase 1 completion in mid-2027.",),
            ),
            ContradictionFinding(
                hypothesis="How exposed is near-term profitability to tender cycles, pricing pressure and project/approval timing?",
                original_claim="Independent results reporting confirms Q1 FY27 revenue of INR 2,026.31 crore and PAT of INR 362.07 crore, with PAT up about 124% YoY.",
                counter_evidence="The reviewed disclosures do not quantify the sensitivity of FY27 earnings to individual tender outcomes or customer approval delays.",
                resolution="Reported earnings are strong, but the absence of quantified tender/approval sensitivity limits forward extrapolation.",
                original_claim_refs=("Independent results reporting confirms Q1 FY27 revenue of INR 2,026.31 crore and PAT of INR 362.07 crore, with PAT up about 124% YoY.",),
                counter_evidence_refs=("The reviewed disclosures do not quantify the sensitivity of FY27 earnings to individual tender outcomes or customer approval delays.",),
            ),
        ),
        unresolved_questions=(
"The exact revenue conversion timing of the 125+ CDMO projects is not disclosed.",
            "The full FY27-FY28 capex return profile remains unresolved."
        ),
        monitoring_questions=(
            "Re-run the packet at the next canonical snapshot and separate newly disclosed facts from unchanged background evidence.",
            "Re-check regulatory, customer and capacity claims against the next issuer filing before treating the current mechanism as persistent.",
        ),
    )
