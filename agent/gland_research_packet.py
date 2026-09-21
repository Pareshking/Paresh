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

def gland_plan() -> ResearchPlan:
    return ResearchPlan(
        symbol="GLAND",
        company_archetype="sterile-injectables focused CDMO/B2B pharmaceutical manufacturer with global regulated-market exposure",
        economic_drivers=("CDMO and B2B growth", "long-cycle customer contracts and capacity expansion", "US regulatory approvals and quality execution", "geographic supply/tender sensitivity"),
        material_domains=(ResearchDomain.FINANCIALS, ResearchDomain.CUSTOMERS_SUPPLIERS, ResearchDomain.MARKET_REACTION, ResearchDomain.ORDERS, ResearchDomain.CAPACITY, ResearchDomain.GOVERNMENT_REGULATION, ResearchDomain.UNKNOWN_QUESTIONS),
        hypotheses=("Is Gland's growth becoming structurally broader through CDMO and B2B rather than relying on individual launches?", "Can the expanding CDMO pipeline and new capacity convert into material future revenue without excessive lead time?", "Does the regulated-market and quality record support continued product launches and customer retention?", "How exposed are earnings to geographic supply disruptions, tender delays and the long technology-transfer cycle?"),
        exclusions=("bank-style lending metrics and NIM", "consumer retail distribution analysis unrelated to sterile injectables", "target prices or valuation recommendations", "recalculation of System-1 ranking or momentum"),
        evidence_half_life_days={ResearchDomain.FINANCIALS: 120, ResearchDomain.CUSTOMERS_SUPPLIERS: 365, ResearchDomain.MARKET_REACTION: 90, ResearchDomain.ORDERS: 180, ResearchDomain.CAPACITY: 365, ResearchDomain.GOVERNMENT_REGULATION: 180},
    )


def gland_evidence() -> tuple[Evidence, ...]:
    return (
        Evidence(
            entity="GLAND", kind=EvidenceKind.POSITIVE,
            claim="Gland Pharma reported Q1 FY27 revenue of INR 1,800.3 crore, up 20% YoY, and PAT of INR 317.0 crore, up 47% YoY.",
            source="https://glandpharma.com/images/Press_Release_Q1_FY27.pdf",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,8,10),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high",
            hypothesis="Is Gland's growth becoming structurally broader through CDMO and B2B rather than relying on individual launches?",
        ),
        Evidence(
            entity="GLAND", kind=EvidenceKind.POSITIVE,
            claim="Q1 FY27 CDMO revenue was INR 891.5 crore, up 20% YoY, while B2B revenue was INR 908.8 crore, up 19% YoY; each contributed about half of total revenue.",
            source="https://glandpharma.com/images/Press_Release_Q1_FY27.pdf",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,8,10),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.CUSTOMERS_SUPPLIERS, materiality="high",
            hypothesis="Is Gland's growth becoming structurally broader through CDMO and B2B rather than relying on individual launches?",
        ),
        Evidence(
            entity="GLAND", kind=EvidenceKind.NEGATIVE,
            claim="Q1 revenue growth was not uniform across geographies: the company reported other core markets down 28% YoY while the US grew 32%.",
            source="https://glandpharma.com/images/Press_Release_Q1_FY27.pdf",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,8,10),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.MARKET_REACTION, materiality="medium",
            hypothesis="Is Gland's growth becoming structurally broader through CDMO and B2B rather than relying on individual launches?",
        ),
        Evidence(
            entity="GLAND", kind=EvidenceKind.POSITIVE,
            claim="Gland disclosed a strategic global-pharma manufacturing agreement covering 55 SKUs across three sites, with estimated eventual annual revenue potential of USD 90-100 million and revenue commencement expected from calendar 2029.",
            source="https://glandpharma.com/images/Press_Release_Q1_FY27.pdf",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,8,10),
            event_date=date(2026,8,10),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.ORDERS, materiality="high",
            hypothesis="Can the expanding CDMO pipeline and new capacity convert into material future revenue without excessive lead time?",
        ),
        Evidence(
            entity="GLAND", kind=EvidenceKind.POSITIVE,
            claim="Management said capacity creation was a key priority and that brownfield and greenfield expansion initiatives were progressing across the manufacturing network.",
            source="https://glandpharma.com/images/EarningsCallTranscript-Q1FY27.pdf",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,8,10),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="high",
            hypothesis="Can the expanding CDMO pipeline and new capacity convert into material future revenue without excessive lead time?",
        ),
        Evidence(
            entity="GLAND", kind=EvidenceKind.NEGATIVE,
            claim="The 55-SKU global partnership is expected to generate revenue only from calendar 2029 after technology-transfer activities planned over two years, showing a long conversion cycle.",
            source="https://glandpharma.com/images/EarningsCallTranscript-Q1FY27.pdf",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,8,10),
            event_date=date(2026,8,10),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.ORDERS, materiality="high",
            hypothesis="Can the expanding CDMO pipeline and new capacity convert into material future revenue without excessive lead time?",
        ),
        Evidence(
            entity="GLAND", kind=EvidenceKind.POSITIVE,
            claim="Gland's September 2026 exchange announcement records conclusion of the USFDA inspection at its VSEZ sterile oncology formulations and API facilities.",
            source="https://glandpharma.com/investors/stock-exchange-anouncement",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,9,1),
            event_date=date(2026,9,1),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.GOVERNMENT_REGULATION, materiality="high",
            hypothesis="Does the regulated-market and quality record support continued product launches and customer retention?",
        ),
        Evidence(
            entity="GLAND", kind=EvidenceKind.POSITIVE,
            claim="Gland disclosed USFDA approval for Sugammadex Injection 200 mg/2 mL and 500 mg/5 mL single-dose vials.",
            source="https://glandpharma.com/investors/stock-exchange-anouncement",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,7,29),
            event_date=date(2026,7,29),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.GOVERNMENT_REGULATION, materiality="high",
            hypothesis="Does the regulated-market and quality record support continued product launches and customer retention?",
        ),
        Evidence(
            entity="GLAND", kind=EvidenceKind.POSITIVE,
            claim="Gland reported four US launches in Q1 FY27 and seven ANDA approvals during the quarter, with 342 cumulative US ANDA approvals.",
            source="https://glandpharma.com/images/Press_Release_Q1_FY27.pdf",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,8,10),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.CUSTOMERS_SUPPLIERS, materiality="high",
            hypothesis="Does the regulated-market and quality record support continued product launches and customer retention?",
        ),
        Evidence(
            entity="GLAND", kind=EvidenceKind.NEGATIVE,
            claim="Gland reported that Saudi Arabia experienced supply disruptions and that NUPCO tender awards had been delayed.",
            source="https://glandpharma.com/images/EarningsCallTranscript-Q1FY27.pdf",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,8,10),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.ORDERS, materiality="medium",
            hypothesis="How exposed are earnings to geographic supply disruptions, tender delays and the long technology-transfer cycle?",
        ),
        Evidence(
            entity="GLAND", kind=EvidenceKind.NEGATIVE,
            claim="The global-pharma partnership is not expected to begin revenue generation until calendar 2029, so current earnings cannot yet include the full economics of the announced pipeline.",
            source="https://glandpharma.com/images/Press_Release_Q1_FY27.pdf",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,8,10),
            event_date=date(2026,8,10),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="medium",
            hypothesis="How exposed are earnings to geographic supply disruptions, tender delays and the long technology-transfer cycle?",
        ),
        Evidence(
            entity="GLAND", kind=EvidenceKind.UNKNOWN,
            claim="The reviewed disclosures do not quantify the earnings sensitivity to the delayed NUPCO tender outcome or Saudi supply disruption.",
            source="research-window: Gland disclosures reviewed through 2026-09-18",
            source_tier=SourceTier.DERIVED,
            published_on=date(2026,9,18),
            event_date=date(2026,9,18),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.UNKNOWN_QUESTIONS, materiality="high",
            hypothesis="How exposed are earnings to geographic supply disruptions, tender delays and the long technology-transfer cycle?",
        ),
    )


def gland_packet() -> ResearchProviderPacket:
    evidence = gland_evidence()
    by_claim = {e.claim: e for e in evidence}
    def ref(claim: str) -> str:
        if claim not in by_claim:
            raise ValueError(f"unknown evidence claim: {claim}")
        return evidence_ref(by_claim[claim])
    plan = gland_plan()
    return ResearchProviderPacket(
        plan=plan,
        evidence=evidence,
        causal_findings=(
            CausalFinding(
                hypothesis="Is Gland's growth becoming structurally broader through CDMO and B2B rather than relying on individual launches?",
                finding="Q1 shows balanced CDMO/B2B growth in aggregate, but geographic performance is uneven, so diversification is real without being uniform.",
                mechanism="Two business models contribute roughly equally while market-specific launches and supply conditions determine local growth.",
                timing="Quarterly",
                uncertainty="The reviewed evidence does not quantify customer concentration within each business.",
                evidence_refs=(ref("Gland Pharma reported Q1 FY27 revenue of INR 1,800.3 crore, up 20% YoY, and PAT of INR 317.0 crore, up 47% YoY."), ref("Q1 FY27 CDMO revenue was INR 891.5 crore, up 20% YoY, while B2B revenue was INR 908.8 crore, up 19% YoY; each contributed about half of total revenue."), ref("Q1 revenue growth was not uniform across geographies: the company reported other core markets down 28% YoY while the US grew 32%.")),
            ),
            CausalFinding(
                hypothesis="Can the expanding CDMO pipeline and new capacity convert into material future revenue without excessive lead time?",
                finding="The CDMO pipeline contains a concrete 55-SKU global agreement, but the long transfer-to-revenue cycle means pipeline value is not near-term revenue.",
                mechanism="Technology transfer, qualification and commercialisation precede recurring supply.",
                timing="2026-2029+",
                uncertainty="The timing and revenue contribution of other pipeline programs are not quantified.",
                evidence_refs=(ref("Gland disclosed a strategic global-pharma manufacturing agreement covering 55 SKUs across three sites, with estimated eventual annual revenue potential of USD 90-100 million and revenue commencement expected from calendar 2029."), ref("Management said capacity creation was a key priority and that brownfield and greenfield expansion initiatives were progressing across the manufacturing network."), ref("The 55-SKU global partnership is expected to generate revenue only from calendar 2029 after technology-transfer activities planned over two years, showing a long conversion cycle.")),
            ),
            CausalFinding(
                hypothesis="Does the regulated-market and quality record support continued product launches and customer retention?",
                finding="The company has continuing US regulatory approvals and a recent USFDA inspection milestone alongside a growing launch pipeline.",
                mechanism="Regulatory compliance enables product launches and customer confidence in sterile manufacturing.",
                timing="Ongoing",
                uncertainty="The inspection announcement itself does not disclose detailed facility-level commercial impact.",
                evidence_refs=(ref("Gland's September 2026 exchange announcement records conclusion of the USFDA inspection at its VSEZ sterile oncology formulations and API facilities."), ref("Gland disclosed USFDA approval for Sugammadex Injection 200 mg/2 mL and 500 mg/5 mL single-dose vials."), ref("Gland reported four US launches in Q1 FY27 and seven ANDA approvals during the quarter, with 342 cumulative US ANDA approvals.")),
            ),
            CausalFinding(
                hypothesis="How exposed are earnings to geographic supply disruptions, tender delays and the long technology-transfer cycle?",
                finding="Near-term earnings remain exposed to local supply/tender events even while long-term CDMO visibility improves.",
                mechanism="Geographic disruptions and tender timing can affect current revenue; long-cycle partnerships affect future rather than current earnings.",
                timing="Quarterly to multi-year",
                uncertainty="The disclosed material does not quantify the sensitivity to the delayed tender or Saudi disruption.",
                evidence_refs=(ref("Gland reported that Saudi Arabia experienced supply disruptions and that NUPCO tender awards had been delayed."), ref("The global-pharma partnership is not expected to begin revenue generation until calendar 2029, so current earnings cannot yet include the full economics of the announced pipeline."), ref("The reviewed disclosures do not quantify the earnings sensitivity to the delayed NUPCO tender outcome or Saudi supply disruption.")),
            ),
        ),
        contradictions=(
            ContradictionFinding(
                hypothesis="Is Gland's growth becoming structurally broader through CDMO and B2B rather than relying on individual launches?",
                original_claim="Q1 FY27 CDMO revenue was INR 891.5 crore, up 20% YoY, while B2B revenue was INR 908.8 crore, up 19% YoY; each contributed about half of total revenue.",
                counter_evidence="Q1 revenue growth was not uniform across geographies: the company reported other core markets down 28% YoY while the US grew 32%.",
                resolution="Business-level diversification is visible, but geographic results show that diversification does not eliminate local shocks.",
                original_claim_refs=("Q1 FY27 CDMO revenue was INR 891.5 crore, up 20% YoY, while B2B revenue was INR 908.8 crore, up 19% YoY; each contributed about half of total revenue.",),
                counter_evidence_refs=("Q1 revenue growth was not uniform across geographies: the company reported other core markets down 28% YoY while the US grew 32%.",),
            ),
            ContradictionFinding(
                hypothesis="Can the expanding CDMO pipeline and new capacity convert into material future revenue without excessive lead time?",
                original_claim="Gland disclosed a strategic global-pharma manufacturing agreement covering 55 SKUs across three sites, with estimated eventual annual revenue potential of USD 90-100 million and revenue commencement expected from calendar 2029.",
                counter_evidence="The 55-SKU global partnership is expected to generate revenue only from calendar 2029 after technology-transfer activities planned over two years, showing a long conversion cycle.",
                resolution="The partnership is concrete, but its revenue conversion is explicitly long-dated.",
                original_claim_refs=("Gland disclosed a strategic global-pharma manufacturing agreement covering 55 SKUs across three sites, with estimated eventual annual revenue potential of USD 90-100 million and revenue commencement expected from calendar 2029.",),
                counter_evidence_refs=("The 55-SKU global partnership is expected to generate revenue only from calendar 2029 after technology-transfer activities planned over two years, showing a long conversion cycle.",),
            ),
            ContradictionFinding(
                hypothesis="Does the regulated-market and quality record support continued product launches and customer retention?",
                original_claim="Gland disclosed USFDA approval for Sugammadex Injection 200 mg/2 mL and 500 mg/5 mL single-dose vials.",
                counter_evidence="Gland's September 2026 exchange announcement records conclusion of the USFDA inspection at its VSEZ sterile oncology formulations and API facilities.",
                resolution="Product approvals and inspection activity support regulatory execution, while the inspection outcome still needs its detailed interpretation from the company's filing.",
                original_claim_refs=("Gland disclosed USFDA approval for Sugammadex Injection 200 mg/2 mL and 500 mg/5 mL single-dose vials.",),
                counter_evidence_refs=("Gland's September 2026 exchange announcement records conclusion of the USFDA inspection at its VSEZ sterile oncology formulations and API facilities.",),
            ),
            ContradictionFinding(
                hypothesis="How exposed are earnings to geographic supply disruptions, tender delays and the long technology-transfer cycle?",
                original_claim="Management said capacity creation was a key priority and that brownfield and greenfield expansion initiatives were progressing across the manufacturing network.",
                counter_evidence="Gland reported that Saudi Arabia experienced supply disruptions and that NUPCO tender awards had been delayed.",
                resolution="Capacity expansion and CDMO growth coexist with short-term geographic/tender disruptions; the two horizons should not be conflated.",
                original_claim_refs=("Management said capacity creation was a key priority and that brownfield and greenfield expansion initiatives were progressing across the manufacturing network.",),
                counter_evidence_refs=("Gland reported that Saudi Arabia experienced supply disruptions and that NUPCO tender awards had been delayed.",),
            ),
        ),
        unresolved_questions=(
"The revenue timing of the wider CDMO pipeline beyond the disclosed 55-SKU agreement remains uncertain.",
            "The earnings impact of Saudi supply disruption and NUPCO tender delay is not quantified."
        ),
        monitoring_questions=(
            "Re-run the packet at the next canonical snapshot and separate newly disclosed facts from unchanged background evidence.",
            "Re-check regulatory, customer and capacity claims against the next issuer filing before treating the current mechanism as persistent.",
        ),
    )
