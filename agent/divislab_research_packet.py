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

def divislab_plan() -> ResearchPlan:
    return ResearchPlan(
        symbol="DIVISLAB",
        company_archetype="large-scale API, custom-synthesis and nutraceutical manufacturing platform",
        economic_drivers=("Custom Synthesis demand and project conversion", "capex commissioning and regulatory/customer qualification", "backward integration and supply resilience", "solvent/input-cost and margin normalisation"),
        material_domains=(ResearchDomain.FINANCIALS, ResearchDomain.CUSTOMERS_SUPPLIERS, ResearchDomain.CAPACITY, ResearchDomain.GOVERNMENT_REGULATION, ResearchDomain.INPUTS_ENERGY, ResearchDomain.UNKNOWN_QUESTIONS),
        hypotheses=("Is the current growth rate supported by durable Custom Synthesis and nutraceutical demand rather than a single-quarter mix effect?", "Can the major capex programs convert validation activity into commercial supply on the expected timeline?", "Are backward integration and manufacturing capacity improving supply resilience without creating excessive inventory or working-capital drag?", "How sensitive is near-term profitability to solvent costs, logistics and the normalisation of unusually high Q1 margins?"),
        exclusions=("bank-style lending metrics and NIM", "hospital/consumer distribution analysis", "target prices or valuation recommendations", "recalculation of System-1 ranking or momentum"),
        evidence_half_life_days={ResearchDomain.FINANCIALS: 120, ResearchDomain.CUSTOMERS_SUPPLIERS: 180, ResearchDomain.CAPACITY: 365, ResearchDomain.GOVERNMENT_REGULATION: 180, ResearchDomain.INPUTS_ENERGY: 90},
    )


def divislab_evidence() -> tuple[Evidence, ...]:
    return (
        Evidence(
            entity="DIVISLAB", kind=EvidenceKind.POSITIVE,
            claim="Divi's consolidated Q1 FY27 revenue from operations was INR 3,080 crore and PAT was INR 902 crore, up 27.8% and 65.5% YoY respectively.",
            source="https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_181441_01082026130515_iXBRL_WEB.html",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,8,1),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high",
            hypothesis="Is the current growth rate supported by durable Custom Synthesis and nutraceutical demand rather than a single-quarter mix effect?",
        ),
        Evidence(
            entity="DIVISLAB", kind=EvidenceKind.POSITIVE,
            claim="Independent reporting on Q1 FY27 stated that Custom Synthesis contributed about 60% of revenue and supported the strong quarter.",
            source="https://www.business-standard.com/markets/capital-market-news/divi-s-lab-q1-pat-climbs-66-yoy-to-rs-902-crore-126080100629_1.html",
            source_tier=SourceTier.SECONDARY,
            published_on=date(2026,8,1),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.CUSTOMERS_SUPPLIERS, materiality="high",
            hypothesis="Is the current growth rate supported by durable Custom Synthesis and nutraceutical demand rather than a single-quarter mix effect?",
        ),
        Evidence(
            entity="DIVISLAB", kind=EvidenceKind.NEGATIVE,
            claim="Independent earnings-call reporting noted that management cautioned against extrapolating the unusually strong Q1 gross margin because business mix is lumpy.",
            source="https://quartermark.in/companies/DIVISLAB/earnings-calls/Q1-FY27/earnings",
            source_tier=SourceTier.SECONDARY,
            published_on=date(2026,8,1),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="medium",
            hypothesis="Is the current growth rate supported by durable Custom Synthesis and nutraceutical demand rather than a single-quarter mix effect?",
        ),
        Evidence(
            entity="DIVISLAB", kind=EvidenceKind.POSITIVE,
            claim="Q1 earnings-call reporting states that three major capex programs were nearing completion with validations underway.",
            source="https://quartermark.in/companies/DIVISLAB/earnings-calls/Q1-FY27/earnings",
            source_tier=SourceTier.SECONDARY,
            published_on=date(2026,8,1),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="high",
            hypothesis="Can the major capex programs convert validation activity into commercial supply on the expected timeline?",
        ),
        Evidence(
            entity="DIVISLAB", kind=EvidenceKind.NEGATIVE,
            claim="The same earnings-call reporting states that commercial revenues from the capex projects depend on customer qualification and regulatory approvals, making timing uncertain.",
            source="https://quartermark.in/companies/DIVISLAB/earnings-calls/Q1-FY27/earnings",
            source_tier=SourceTier.SECONDARY,
            published_on=date(2026,8,1),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.GOVERNMENT_REGULATION, materiality="high",
            hypothesis="Can the major capex programs convert validation activity into commercial supply on the expected timeline?",
        ),
        Evidence(
            entity="DIVISLAB", kind=EvidenceKind.POSITIVE,
            claim="Q1 reporting states that Unit 3 is being used for backward integration and phased transfers from Units 1 and 2 to support critical-intermediate supply assurance.",
            source="https://quartermark.in/companies/DIVISLAB/earnings-calls/Q1-FY27/earnings",
            source_tier=SourceTier.SECONDARY,
            published_on=date(2026,8,1),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.INPUTS_ENERGY, materiality="high",
            hypothesis="Are backward integration and manufacturing capacity improving supply resilience without creating excessive inventory or working-capital drag?",
        ),
        Evidence(
            entity="DIVISLAB", kind=EvidenceKind.NEGATIVE,
            claim="Q1 reporting also notes elevated solvent costs and global logistics pressure, with inventory at about INR 4,413 crore after maintaining a strategic three-month buffer.",
            source="https://www.investorstack.in/earnings-calls/divislab",
            source_tier=SourceTier.SECONDARY,
            published_on=date(2026,8,1),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.INPUTS_ENERGY, materiality="high",
            hypothesis="Are backward integration and manufacturing capacity improving supply resilience without creating excessive inventory or working-capital drag?",
        ),
        Evidence(
            entity="DIVISLAB", kind=EvidenceKind.POSITIVE,
            claim="NSE's consolidated filing shows Q1 FY27 revenue from operations of INR 3,080 crore and cost of materials consumed of INR 1,503 crore, providing a direct filing anchor for the input-cost context.",
            source="https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_181441_01082026130515_iXBRL_WEB.html",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,8,1),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="high",
            hypothesis="Are backward integration and manufacturing capacity improving supply resilience without creating excessive inventory or working-capital drag?",
        ),
        Evidence(
            entity="DIVISLAB", kind=EvidenceKind.NEGATIVE,
            claim="Q1 reporting says management expected full-year gross margin to normalise toward about 60% versus the unusually high Q1 level, alongside elevated solvent costs.",
            source="https://www.investorstack.in/earnings-calls/divislab",
            source_tier=SourceTier.SECONDARY,
            published_on=date(2026,8,1),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.INPUTS_ENERGY, materiality="medium",
            hypothesis="How sensitive is near-term profitability to solvent costs, logistics and the normalisation of unusually high Q1 margins?",
        ),
        Evidence(
            entity="DIVISLAB", kind=EvidenceKind.POSITIVE,
            claim="NSE's Q1 filing reports consolidated PBT of INR 1,180 crore and PAT of INR 902 crore, with no exceptional item in the quarter.",
            source="https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_181441_01082026130515_iXBRL_WEB.html",
            source_tier=SourceTier.PRIMARY,
            published_on=date(2026,8,1),
            event_date=date(2026,6,30),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high",
            hypothesis="How sensitive is near-term profitability to solvent costs, logistics and the normalisation of unusually high Q1 margins?",
        ),
        Evidence(
            entity="DIVISLAB", kind=EvidenceKind.UNKNOWN,
            claim="The reviewed material does not establish the exact date and revenue contribution of commercialisation for each major capex program.",
            source="research-window: Divi's disclosures reviewed through 2026-09-18",
            source_tier=SourceTier.DERIVED,
            published_on=date(2026,9,18),
            event_date=date(2026,9,18),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.UNKNOWN_QUESTIONS, materiality="high",
            hypothesis="Can the major capex programs convert validation activity into commercial supply on the expected timeline?",
        ),
        Evidence(
            entity="DIVISLAB", kind=EvidenceKind.UNKNOWN,
            claim="The reviewed material does not quantify the full-year earnings sensitivity to solvent-cost and logistics scenarios.",
            source="research-window: Divi's disclosures reviewed through 2026-09-18",
            source_tier=SourceTier.DERIVED,
            published_on=date(2026,9,18),
            event_date=date(2026,9,18),
            retrieved_on=RETRIEVED,
            domain=ResearchDomain.UNKNOWN_QUESTIONS, materiality="medium",
            hypothesis="How sensitive is near-term profitability to solvent costs, logistics and the normalisation of unusually high Q1 margins?",
        ),
    )


def divislab_packet() -> ResearchProviderPacket:
    evidence = divislab_evidence()
    by_claim = {e.claim: e for e in evidence}
    def ref(claim: str) -> str:
        if claim not in by_claim:
            raise ValueError(f"unknown evidence claim: {claim}")
        return evidence_ref(by_claim[claim])
    plan = divislab_plan()
    return ResearchProviderPacket(
        plan=plan,
        evidence=evidence,
        causal_findings=(
            CausalFinding(
                hypothesis="Is the current growth rate supported by durable Custom Synthesis and nutraceutical demand rather than a single-quarter mix effect?",
                finding="Q1 growth is supported by strong reported financials and a large Custom Synthesis contribution, but mix-driven margin strength is explicitly described as potentially non-repeatable.",
                mechanism="Custom Synthesis can lift mix and margins, while project timing can make individual quarters unusually strong.",
                timing="Quarterly to annual",
                uncertainty="The reviewed material does not isolate the durability of the current mix beyond management commentary.",
                evidence_refs=(ref("Divi's consolidated Q1 FY27 revenue from operations was INR 3,080 crore and PAT was INR 902 crore, up 27.8% and 65.5% YoY respectively."), ref("Independent reporting on Q1 FY27 stated that Custom Synthesis contributed about 60% of revenue and supported the strong quarter."), ref("Independent earnings-call reporting noted that management cautioned against extrapolating the unusually strong Q1 gross margin because business mix is lumpy.")),
            ),
            CausalFinding(
                hypothesis="Can the major capex programs convert validation activity into commercial supply on the expected timeline?",
                finding="The capex projects are physically advanced enough for validation, but customer qualification and regulatory approval remain gates to commercial revenue.",
                mechanism="Capacity becomes revenue only after validation, qualification, approvals and customer supply activation.",
                timing="FY27-FY28",
                uncertainty="Program-level commercial dates are not established.",
                evidence_refs=(ref("Q1 earnings-call reporting states that three major capex programs were nearing completion with validations underway."), ref("The same earnings-call reporting states that commercial revenues from the capex projects depend on customer qualification and regulatory approvals, making timing uncertain."), ref("The reviewed material does not establish the exact date and revenue contribution of commercialisation for each major capex program.")),
            ),
            CausalFinding(
                hypothesis="Are backward integration and manufacturing capacity improving supply resilience without creating excessive inventory or working-capital drag?",
                finding="Backward integration is being used to improve supply assurance, while the business is simultaneously carrying high inventory and elevated solvent/logistics exposure.",
                mechanism="Internal intermediate capacity can reduce external dependency, but buffers and higher input costs consume working capital.",
                timing="Ongoing",
                uncertainty="The reviewed evidence does not quantify the net economic benefit of the integration versus inventory cost.",
                evidence_refs=(ref("Q1 reporting states that Unit 3 is being used for backward integration and phased transfers from Units 1 and 2 to support critical-intermediate supply assurance."), ref("Q1 reporting also notes elevated solvent costs and global logistics pressure, with inventory at about INR 4,413 crore after maintaining a strategic three-month buffer."), ref("NSE's consolidated filing shows Q1 FY27 revenue from operations of INR 3,080 crore and cost of materials consumed of INR 1,503 crore, providing a direct filing anchor for the input-cost context.")),
            ),
            CausalFinding(
                hypothesis="How sensitive is near-term profitability to solvent costs, logistics and the normalisation of unusually high Q1 margins?",
                finding="Q1 profitability is exceptionally strong on reported numbers, but management's own full-year margin framing implies normalisation and external-cost sensitivity.",
                mechanism="Product mix, solvent costs and logistics can move gross margin materially between quarters.",
                timing="Quarterly",
                uncertainty="A full-year cost sensitivity was not disclosed.",
                evidence_refs=(ref("Q1 reporting says management expected full-year gross margin to normalise toward about 60% versus the unusually high Q1 level, alongside elevated solvent costs."), ref("NSE's Q1 filing reports consolidated PBT of INR 1,180 crore and PAT of INR 902 crore, with no exceptional item in the quarter."), ref("The reviewed material does not quantify the full-year earnings sensitivity to solvent-cost and logistics scenarios.")),
            ),
        ),
        counter_evidence=(
            CounterEvidenceFinding(
                hypothesis="Is the current growth rate supported by durable Custom Synthesis and nutraceutical demand rather than a single-quarter mix effect?",
                original_claim="Divi's consolidated Q1 FY27 revenue from operations was INR 3,080 crore and PAT was INR 902 crore, up 27.8% and 65.5% YoY respectively.",
                counter_evidence="Independent earnings-call reporting noted that management cautioned against extrapolating the unusually strong Q1 gross margin because business mix is lumpy.",
                resolution="The earnings result is real, but the Q1 margin/mix should not be treated as a straight-line forecast.",
                original_claim_refs=(ref("Divi's consolidated Q1 FY27 revenue from operations was INR 3,080 crore and PAT was INR 902 crore, up 27.8% and 65.5% YoY respectively."),),
                counter_evidence_refs=(ref("Independent earnings-call reporting noted that management cautioned against extrapolating the unusually strong Q1 gross margin because business mix is lumpy."),),
            ),
            ContradictionFinding(
                hypothesis="Can the major capex programs convert validation activity into commercial supply on the expected timeline?",
                original_claim="Q1 earnings-call reporting states that three major capex programs were nearing completion with validations underway.",
                counter_evidence="The same earnings-call reporting states that commercial revenues from the capex projects depend on customer qualification and regulatory approvals, making timing uncertain.",
                resolution="Physical project progress is positive; revenue timing remains conditional on qualification and approvals.",
                original_claim_refs=(ref("Q1 earnings-call reporting states that three major capex programs were nearing completion with validations underway."),),
                counter_evidence_refs=(ref("The same earnings-call reporting states that commercial revenues from the capex projects depend on customer qualification and regulatory approvals, making timing uncertain."),),
            ),
            ContradictionFinding(
                hypothesis="Are backward integration and manufacturing capacity improving supply resilience without creating excessive inventory or working-capital drag?",
                original_claim="Q1 reporting states that Unit 3 is being used for backward integration and phased transfers from Units 1 and 2 to support critical-intermediate supply assurance.",
                counter_evidence="Q1 reporting also notes elevated solvent costs and global logistics pressure, with inventory at about INR 4,413 crore after maintaining a strategic three-month buffer.",
                resolution="Backward integration improves supply resilience while the current environment still carries meaningful input-cost and working-capital pressure.",
                original_claim_refs=(ref("Q1 reporting states that Unit 3 is being used for backward integration and phased transfers from Units 1 and 2 to support critical-intermediate supply assurance."),),
                counter_evidence_refs=(ref("Q1 reporting also notes elevated solvent costs and global logistics pressure, with inventory at about INR 4,413 crore after maintaining a strategic three-month buffer."),),
            ),
            ContradictionFinding(
                hypothesis="How sensitive is near-term profitability to solvent costs, logistics and the normalisation of unusually high Q1 margins?",
                original_claim="NSE's Q1 filing reports consolidated PBT of INR 1,180 crore and PAT of INR 902 crore, with no exceptional item in the quarter.",
                counter_evidence="Q1 reporting says management expected full-year gross margin to normalise toward about 60% versus the unusually high Q1 level, alongside elevated solvent costs.",
                resolution="Q1 profitability is strong, but management's own normalisation commentary argues against assuming the quarter's margin is the steady state.",
                original_claim_refs=(ref("NSE's Q1 filing reports consolidated PBT of INR 1,180 crore and PAT of INR 902 crore, with no exceptional item in the quarter."),),
                counter_evidence_refs=(ref("Q1 reporting says management expected full-year gross margin to normalise toward about 60% versus the unusually high Q1 level, alongside elevated solvent costs."),),
            ),
        ),
        unresolved_questions=(
"Commercial timing of the major capex programs remains unresolved.",
            "The earnings sensitivity to solvent and logistics scenarios is not quantified."
        ),
        monitoring_questions=(
            "Re-run the packet at the next canonical snapshot and separate newly disclosed facts from unchanged background evidence.",
            "Re-check regulatory, customer and capacity claims against the next issuer filing before treating the current mechanism as persistent.",
        ),
    )
