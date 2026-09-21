from __future__ import annotations

from datetime import date

from agent.contracts import Evidence, EvidenceKind, ResearchDomain, ResearchPlan, SourceTier
from agent.research_execution import (
    CausalFinding,
    ContradictionFinding,
    CounterEvidenceFinding,
    ResearchProviderPacket,
    evidence_ref,
)

CUTOFF = date(2026, 9, 18)
RETRIEVED = date(2026, 9, 20)

def shilpamed_plan() -> ResearchPlan:
    return ResearchPlan(
        symbol="SHILPAMED",
        company_archetype="oncology/API/formulations/CDMO pharmaceutical platform with complex injectables and emerging peptide/biologics programs",
        economic_drivers=("oncology APIs and formulations", "CDMO program conversion", "peptide and complex injectable capacity", "regulatory approvals and customer partnerships", "utilisation and operating leverage"),
        material_domains=(ResearchDomain.FINANCIALS, ResearchDomain.CAPACITY, ResearchDomain.ORDERS, ResearchDomain.CUSTOMERS_SUPPLIERS, ResearchDomain.GOVERNMENT_REGULATION, ResearchDomain.TECHNOLOGY_IP, ResearchDomain.UNKNOWN_QUESTIONS),
        hypotheses=("Is FY27 growth broadening across commercial formulations, APIs and CDMO rather than being driven by a small number of launches?", "Can new peptide, oncology and complex-injectable capacity convert into durable commercial revenue?", "Do regulatory approvals and partner programs reduce execution risk, or do inspection/approval dependencies remain material?", "Is the current margin improvement supported by utilisation and mix, or is it vulnerable to under-utilised capacity and program timing?"),
        exclusions=("bank-style lending metrics and NIM because this is not a bank/NBFC", "manufacturing analysis unrelated to pharma capacity or regulatory execution", "target prices or valuation recommendations", "recalculation of System-1 ranking or momentum"),
        evidence_half_life_days={ResearchDomain.FINANCIALS: 120, ResearchDomain.CAPACITY: 365, ResearchDomain.ORDERS: 180, ResearchDomain.CUSTOMERS_SUPPLIERS: 365, ResearchDomain.GOVERNMENT_REGULATION: 180, ResearchDomain.TECHNOLOGY_IP: 365},
    )


def shilpamed_evidence() -> tuple[Evidence, ...]:
    return (
        Evidence(
            entity="SHILPAMED", kind=EvidenceKind.POSITIVE,
            claim="Q1FY27 consolidated revenue from operations was INR 465.78 crore, up 44.89% YoY, while consolidated PAT was INR 100.88 crore, up 115.19% YoY.",
            source="https://www.icicidirect.com/research/equity/rapid-results/shilpa-medicare-ltd",
            source_tier=SourceTier.SECONDARY,
            published_on=date(2026,8,5),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high",
            hypothesis="Is FY27 growth broadening across commercial formulations, APIs and CDMO rather than being driven by a small number of launches?",
        ),
        Evidence(
            entity="SHILPAMED", kind=EvidenceKind.NEGATIVE,
            claim="Q1FY27 net profit of INR 100.88 crore was 6.40% below Q4FY26 profit of INR 107.78 crore despite the strong YoY increase.",
            source="https://www.icicidirect.com/research/equity/rapid-results/shilpa-medicare-ltd",
            source_tier=SourceTier.SECONDARY,
            published_on=date(2026,8,5),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high",
            hypothesis="Is FY27 growth broadening across commercial formulations, APIs and CDMO rather than being driven by a small number of launches?",
        ),
        Evidence(
            entity="SHILPAMED", kind=EvidenceKind.POSITIVE,
            claim="Management said large-scale peptide manufacturing capacity was under construction with completion planned for the second half of FY27.",
            source="https://www.vbshilpa.com/pdf/Investor%20call%20transcript%2006.02.2026.pdf",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,2,6),
            event_date=date(2026,2,6),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="high",
            hypothesis="Can new peptide, oncology and complex-injectable capacity convert into durable commercial revenue?",
        ),
        Evidence(
            entity="SHILPAMED", kind=EvidenceKind.POSITIVE,
            claim="Management reported firm Q4 orders for the newly launched NorUDCA formulation and expected significant potential in the following financial year.",
            source="https://www.vbshilpa.com/pdf/Investor%20call%20transcript%2006.02.2026.pdf",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,2,6),
            event_date=date(2026,2,6),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.ORDERS, materiality="high",
            hypothesis="Can new peptide, oncology and complex-injectable capacity convert into durable commercial revenue?",
        ),
        Evidence(
            entity="SHILPAMED", kind=EvidenceKind.POSITIVE,
            claim="Management reported development of injectable and oral semaglutide formulations plus synthetic and semisynthetic API programs, with scale-up and validation targeted around Q4FY26/Q1FY27.",
            source="https://www.vbshilpa.com/pdf/Investor%20call%20transcript%2006.02.2026.pdf",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,2,6),
            event_date=date(2026,2,6),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.TECHNOLOGY_IP, materiality="high",
            hypothesis="Can new peptide, oncology and complex-injectable capacity convert into durable commercial revenue?",
        ),
        Evidence(
            entity="SHILPAMED", kind=EvidenceKind.POSITIVE,
            claim="Management said a new complex injectable had completed scale-up batches, with registration batches targeted for Q4 FY26 and a plan to file the product globally.",
            source="https://www.vbshilpa.com/pdf/Investor%20call%20transcript%2006.02.2026.pdf",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,2,6),
            event_date=date(2026,2,6),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.GOVERNMENT_REGULATION, materiality="high",
            hypothesis="Do regulatory approvals and partner programs reduce execution risk, or do inspection/approval dependencies remain material?",
        ),
        Evidence(
            entity="SHILPAMED", kind=EvidenceKind.POSITIVE,
            claim="The company disclosed a co-development and supply agreement involving Shilpa Biologicals and Orion Corporation, Finland.",
            source="https://vbshilpa.com/stock-exchange-intimations.php",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,6,3),
            event_date=date(2026,6,3),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.CUSTOMERS_SUPPLIERS, materiality="high",
            hypothesis="Do regulatory approvals and partner programs reduce execution risk, or do inspection/approval dependencies remain material?",
        ),
        Evidence(
            entity="SHILPAMED", kind=EvidenceKind.NEGATIVE,
            claim="The company's 2026 exchange-intimation record also shows a USFDA inspection at Unit VI, Dabaspet, demonstrating that regulatory inspection remains an active execution dependency.",
            source="https://vbshilpa.com/stock-exchange-intimations.php",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,6,3),
            event_date=date(2026,6,3),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.GOVERNMENT_REGULATION, materiality="medium",
            hypothesis="Do regulatory approvals and partner programs reduce execution risk, or do inspection/approval dependencies remain material?",
        ),
        Evidence(
            entity="SHILPAMED", kind=EvidenceKind.POSITIVE,
            claim="FY26 investor materials stated that substantial gross block remained under-utilised and that improved utilisation was expected to drive revenue and EBITDA-margin improvement.",
            source="https://www.vbshilpa.com/pdf/Investor%20presentation%20for%20the%20quarter%20ended%2031%20March%202026.pdf",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,3,31),
            event_date=date(2026,3,31),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="high",
            hypothesis="Is the current margin improvement supported by utilisation and mix, or is it vulnerable to under-utilised capacity and program timing?",
        ),
        Evidence(
            entity="SHILPAMED", kind=EvidenceKind.POSITIVE,
            claim="FY26 investor materials linked expected operating leverage and margin improvement to higher utilisation across higher-margin biosimilar, CDMO and NDDS activities.",
            source="https://www.vbshilpa.com/pdf/Investor%20presentation%20for%20the%20quarter%20ended%2031%20March%202026.pdf",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,3,31),
            event_date=date(2026,3,31),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="medium",
            hypothesis="Is the current margin improvement supported by utilisation and mix, or is it vulnerable to under-utilised capacity and program timing?",
        ),
        Evidence(
            entity="SHILPAMED", kind=EvidenceKind.NEGATIVE,
            claim="Q1FY27 PBT was INR 98.06 crore versus INR 120.44 crore in Q4FY26, showing that sequential profitability did not rise with revenue.",
            source="https://www.icicidirect.com/research/equity/rapid-results/shilpa-medicare-ltd",
            source_tier=SourceTier.SECONDARY,
            published_on=date(2026,8,5),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high",
            hypothesis="Is the current margin improvement supported by utilisation and mix, or is it vulnerable to under-utilised capacity and program timing?",
        ),
        Evidence(
            entity="SHILPAMED", kind=EvidenceKind.POSITIVE,
            claim="The company's exchange-intimation page records final approval from the Subject Expert Committee (SEC) under CDSCO for grant of marketing authorization for OERIS (Ondansetron Extended-Release Injection, 100 mg/mL).",
            source="https://www.vbshilpa.com/pdf/OERIS%20final%20approval%20from%20SEC.pdf",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,9,11),
            event_date=date(2026,9,11),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.GOVERNMENT_REGULATION, materiality="high",
            hypothesis="Do regulatory approvals and partner programs reduce execution risk, or do inspection/approval dependencies remain material?",
        ),
        Evidence(
            entity="SHILPAMED", kind=EvidenceKind.UNKNOWN,
            claim="The reviewed disclosures do not establish the eventual commercial contribution, utilisation ramp or economics of the new peptide capacity after commissioning.",
            source="research-window: Q1FY27 disclosures reviewed through 2026-09-18",
            source_tier=SourceTier.DERIVED,
            published_on=date(2026,9,18),
            event_date=date(2026,9,18),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.UNKNOWN_QUESTIONS, materiality="high",
            hypothesis="Can new peptide, oncology and complex-injectable capacity convert into durable commercial revenue?",
        ),
    )


def shilpamed_packet() -> ResearchProviderPacket:
    evidence = shilpamed_evidence()
    by_claim = {e.claim: e for e in evidence}
    def ref(claim: str) -> str:
        if claim not in by_claim:
            raise ValueError(f"unknown evidence claim: {claim}")
        return evidence_ref(by_claim[claim])
    plan = shilpamed_plan()
    return ResearchProviderPacket(
        plan=plan,
        evidence=evidence,
        causal_findings=(
            CausalFinding(
                hypothesis="Is FY27 growth broadening across commercial formulations, APIs and CDMO rather than being driven by a small number of launches?",
                finding="Q1FY27 shows a large YoY step-up, but the sequential profit decline means breadth and persistence of growth still need follow-through.",
                mechanism="Revenue growth can come from launches, product mix and CDMO programs; durable earnings require those contributors to recur rather than simply compare against a weak base.",
                timing="Quarterly",
                uncertainty="The reviewed set does not isolate the contribution of each business line to Q1 growth.",
                evidence_refs=(ref("Q1FY27 consolidated revenue from operations was INR 465.78 crore, up 44.89% YoY, while consolidated PAT was INR 100.88 crore, up 115.19% YoY."), ref("Q1FY27 net profit of INR 100.88 crore was 6.40% below Q4FY26 profit of INR 107.78 crore despite the strong YoY increase."), ref("Management reported firm Q4 orders for the newly launched NorUDCA formulation and expected significant potential in the following financial year.")),
            ),
            CausalFinding(
                hypothesis="Can new peptide, oncology and complex-injectable capacity convert into durable commercial revenue?",
                finding="The pipeline contains concrete peptide, oncology and complex-injectable programs, but the new capacity is not yet evidence of realised revenue.",
                mechanism="Scale-up, validation, approval and customer conversion precede commercial utilisation.",
                timing="FY27-FY28",
                uncertainty="Commercial ramp and utilisation after commissioning remain unresolved.",
                evidence_refs=(ref("Management said large-scale peptide manufacturing capacity was under construction with completion planned for the second half of FY27."), ref("Management reported development of injectable and oral semaglutide formulations plus synthetic and semisynthetic API programs, with scale-up and validation targeted around Q4FY26/Q1FY27."), ref("The reviewed disclosures do not establish the eventual commercial contribution, utilisation ramp or economics of the new peptide capacity after commissioning.")),
            ),
            CausalFinding(
                hypothesis="Do regulatory approvals and partner programs reduce execution risk, or do inspection/approval dependencies remain material?",
                finding="Recent approval and partnership disclosures provide evidence of regulatory and customer progress, while the active USFDA inspection shows the pathway remains execution-sensitive.",
                mechanism="Approvals unlock products and partner programs, while inspections can affect timing or remediation requirements.",
                timing="Ongoing",
                uncertainty="The reviewed material does not quantify the financial impact of any inspection outcome.",
                evidence_refs=(ref("The company's exchange-intimation page records final approval from the Subject Expert Committee (SEC) under CDSCO for grant of marketing authorization for OERIS (Ondansetron Extended-Release Injection, 100 mg/mL)."), ref("The company disclosed a co-development and supply agreement involving Shilpa Biologicals and Orion Corporation, Finland."), ref("The company's 2026 exchange-intimation record also shows a USFDA inspection at Unit VI, Dabaspet, demonstrating that regulatory inspection remains an active execution dependency."), ref("Management said a new complex injectable had completed scale-up batches, with registration batches targeted for Q4 FY26 and a plan to file the product globally.")),
            ),
            CausalFinding(
                hypothesis="Is the current margin improvement supported by utilisation and mix, or is it vulnerable to under-utilised capacity and program timing?",
                finding="Management explicitly links margin expansion to utilisation, but Q1 sequential PBT declined, so operating leverage is not yet a monotonic quarter-to-quarter process.",
                mechanism="Fixed-cost absorption and mix can improve margins as capacity fills, but launch timing and product mix can cause sequential volatility.",
                timing="Quarterly",
                uncertainty="The disclosures do not provide a normalised utilisation-to-margin bridge.",
                evidence_refs=(ref("FY26 investor materials stated that substantial gross block remained under-utilised and that improved utilisation was expected to drive revenue and EBITDA-margin improvement."), ref("FY26 investor materials linked expected operating leverage and margin improvement to higher utilisation across higher-margin biosimilar, CDMO and NDDS activities."), ref("Q1FY27 PBT was INR 98.06 crore versus INR 120.44 crore in Q4FY26, showing that sequential profitability did not rise with revenue.")),
            ),
        ),
        counter_evidence=(
            CounterEvidenceFinding(
                hypothesis="Is FY27 growth broadening across commercial formulations, APIs and CDMO rather than being driven by a small number of launches?",
                original_claim="Q1FY27 consolidated revenue from operations was INR 465.78 crore, up 44.89% YoY, while consolidated PAT was INR 100.88 crore, up 115.19% YoY.",
                counter_evidence="Q1FY27 net profit of INR 100.88 crore was 6.40% below Q4FY26 profit of INR 107.78 crore despite the strong YoY increase.",
                resolution="YoY growth is established, but sequential profitability is a counter-signal; both should remain in the dossier.",
                original_claim_refs=(ref("Q1FY27 consolidated revenue from operations was INR 465.78 crore, up 44.89% YoY, while consolidated PAT was INR 100.88 crore, up 115.19% YoY."),),
                counter_evidence_refs=(ref("Q1FY27 net profit of INR 100.88 crore was 6.40% below Q4FY26 profit of INR 107.78 crore despite the strong YoY increase."),),
            ),
            ContradictionFinding(
                hypothesis="Can new peptide, oncology and complex-injectable capacity convert into durable commercial revenue?",
                original_claim="Management said large-scale peptide manufacturing capacity was under construction with completion planned for the second half of FY27.",
                counter_evidence="The reviewed disclosures do not establish the eventual commercial contribution, utilisation ramp or economics of the new peptide capacity after commissioning.",
                resolution="Capacity expansion is a documented initiative, not yet a demonstrated commercial earnings stream.",
                original_claim_refs=(ref("Management said large-scale peptide manufacturing capacity was under construction with completion planned for the second half of FY27."),),
                counter_evidence_refs=(ref("The reviewed disclosures do not establish the eventual commercial contribution, utilisation ramp or economics of the new peptide capacity after commissioning."),),
            ),
            ContradictionFinding(
                hypothesis="Do regulatory approvals and partner programs reduce execution risk, or do inspection/approval dependencies remain material?",
                original_claim="The company's exchange-intimation page records final approval from the Subject Expert Committee (SEC) under CDSCO for grant of marketing authorization for OERIS (Ondansetron Extended-Release Injection, 100 mg/mL).",
                counter_evidence="The company's 2026 exchange-intimation record also shows a USFDA inspection at Unit VI, Dabaspet, demonstrating that regulatory inspection remains an active execution dependency.",
                resolution="Approval progress and inspection dependency coexist; the evidence supports neither a fully de-risked nor a failed regulatory thesis.",
                original_claim_refs=(ref("The company's exchange-intimation page records final approval from the Subject Expert Committee (SEC) under CDSCO for grant of marketing authorization for OERIS (Ondansetron Extended-Release Injection, 100 mg/mL)."),),
                counter_evidence_refs=(ref("The company's 2026 exchange-intimation record also shows a USFDA inspection at Unit VI, Dabaspet, demonstrating that regulatory inspection remains an active execution dependency."),),
            ),
            ContradictionFinding(
                hypothesis="Is the current margin improvement supported by utilisation and mix, or is it vulnerable to under-utilised capacity and program timing?",
                original_claim="FY26 investor materials linked expected operating leverage and margin improvement to higher utilisation across higher-margin biosimilar, CDMO and NDDS activities.",
                counter_evidence="Q1FY27 PBT was INR 98.06 crore versus INR 120.44 crore in Q4FY26, showing that sequential profitability did not rise with revenue.",
                resolution="Management expects utilisation-led operating leverage, while Q1 sequential PBT shows timing/mix can interrupt that mechanism.",
                original_claim_refs=(ref("FY26 investor materials linked expected operating leverage and margin improvement to higher utilisation across higher-margin biosimilar, CDMO and NDDS activities."),),
                counter_evidence_refs=(ref("Q1FY27 PBT was INR 98.06 crore versus INR 120.44 crore in Q4FY26, showing that sequential profitability did not rise with revenue."),),
            ),
        ),
        unresolved_questions=(
"The commercial ramp of new peptide capacity is not yet quantified.",
            "The contribution of individual product launches to Q1 growth remains insufficiently disclosed."
        ),
        monitoring_questions=(
            "Re-run the packet at the next canonical snapshot and separate newly disclosed facts from unchanged background evidence.",
            "Re-check regulatory, customer and capacity claims against the next issuer filing before treating the current mechanism as persistent.",
        ),
    )
