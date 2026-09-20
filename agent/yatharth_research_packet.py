"""Acceptance research packet for the hospital-operator ("bed-based healthcare
services") archetype execution test.

Company: YATHARTH (Yatharth Hospital & Trauma Care Services Limited)
Archetype: multi-specialty/super-specialty private hospital chain in North India
scaling bed capacity through greenfield builds and hospital acquisitions
Snapshot cutoff: 2026-09-18
Retrieved: 2026-09-19

This packet demonstrates that a hospital operator selects a different research
lens from an auto-components exporter (SANSERA), a wealth-management platform
(ANANDRATHI) or a fintech platform (PAYTM): its economic drivers are bed
capacity/occupancy, ARPOB, payer mix (cash/TPA vs. government schemes such as
CGHS), new-hospital ramp-up curves, doctor/specialist retention, clinical
accreditation (NABH/JCI), and capital allocation for a capex-heavy expansion
plan -- not order backlogs, tariffs, AUM flows or lending economics.

Every evidence item below was fetched from a real, dated primary source: the
company's own Q1FY27 press release, Q1FY27 investor presentation, Q1FY27
earnings-call transcript (all filed with NSE/BSE under SEBI LODR Regulations
and hosted at yatharthhospitals.com/uploads/investors/), and the 17-September-
2026 board-meeting outcome and press release announcing the Advent
International preferential investment -- all fetched and read in full on
2026-09-19, before the 2026-09-18 snapshot's information cutoff for anything
dated on or before that day.
"""

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
RETRIEVED = date(2026, 9, 19)

# Hypotheses are defined once as module-level constants so the plan, the
# evidence set and the causal/contradiction findings all reference the exact
# same string -- avoiding the positional-index and retyped-string mismatches
# this pipeline was hardened against (see agent/STAGE_4B_IMPROVEMENT_TRACKER.md).
_H1_MARGIN_QUALITY = (
    "Is Yatharth's revenue and margin growth being driven by durable occupancy "
    "and ARPOB gains at mature hospitals, or mainly by the ramp-up of newly "
    "acquired and greenfield hospitals that have not yet reached steady-state "
    "profitability?"
)
_H2_RAMP_EXECUTION = (
    "Can the newer hospitals (Greater Faridabad, New Delhi Model Town, "
    "Faridabad Sector-20, Agra) and the upcoming Gurugram hospital reach the "
    "occupancy, ARPOB and EBITDA-breakeven milestones management has guided, "
    "without material execution delay?"
)
_H3_PAYER_MIX_REGULATION = (
    "Is the shift toward a cash/TPA-heavy payer mix at new hospitals durable, "
    "or does the group's payer mix and profitability remain exposed to "
    "government actions such as CGHS rate revisions and proposed hospital "
    "room-rent regulation?"
)
_H4_CAPITAL_ALLOCATION = (
    "Does the Advent International preferential investment materially change "
    "Yatharth's capital availability and governance, and can the ~5,000-bed "
    "capacity target be funded without excessive leverage, dilution or "
    "execution risk?"
)
_H5_TALENT_DIFFERENTIATION = (
    "Can Yatharth retain doctors and specialists and sustain clinical "
    "differentiation (accreditation, robotics, oncology, transplants) as it "
    "rapidly scales bed capacity into new clusters and geographies?"
)


def yatharth_plan() -> ResearchPlan:
    return ResearchPlan(
        symbol="YATHARTH",
        company_archetype=(
            "multi-specialty and super-specialty private hospital chain in North "
            "India (Uttar Pradesh, Haryana/NCR, Madhya Pradesh, Delhi) scaling bed "
            "capacity through greenfield builds and hospital acquisitions"
        ),
        economic_drivers=(
            "bed capacity growth and occupancy ramp-up at new/acquired hospitals",
            "ARPOB (average revenue per occupied bed) and case-mix/specialty upgrade",
            "payer mix between cash/private-insurance/TPA and government schemes "
            "(CGHS and other empanelments)",
            "new-hospital integration speed and EBITDA-breakeven timelines",
            "doctor/specialist recruitment, retention and brand-driven patient volumes",
            "capital allocation for a capex-heavy expansion plan (internal accruals, "
            "debt and, as of September 2026, primary equity)",
            "clinical accreditation and quality (NABH/JCI) supporting premium ARPOB",
        ),
        material_domains=(
            ResearchDomain.FINANCIALS,
            ResearchDomain.MANAGEMENT,
            ResearchDomain.CAPACITY,
            ResearchDomain.CUSTOMERS_SUPPLIERS,
            ResearchDomain.GOVERNMENT_REGULATION,
            ResearchDomain.CAPITAL_MARKETS,
        ),
        hypotheses=(
            _H1_MARGIN_QUALITY,
            _H2_RAMP_EXECUTION,
            _H3_PAYER_MIX_REGULATION,
            _H4_CAPITAL_ALLOCATION,
            _H5_TALENT_DIFFERENTIATION,
        ),
        exclusions=(
            "auto-components/industrial-manufacturing style analysis (export mix, "
            "tariff/trade exposure, machine-tool capacity, order-book conversion) "
            "because Yatharth is a domestic hospital operator, not an exporter or "
            "manufacturer",
            "bank/NBFC-style loan-book, net interest margin, GNPA/NNPA or "
            "capital-adequacy analysis because Yatharth is a healthcare services "
            "provider, not a lending business",
            "wealth-management/broking-style AUM, trail-commission or "
            "relationship-manager-productivity analysis because Yatharth has no "
            "comparable distribution or asset-management business",
            "clinical/medical-outcome quality metrics such as mortality, "
            "complication or hospital-acquired-infection rates, since the company "
            "does not publicly disclose hospital-level clinical audit data beyond "
            "confirming NABH/JCI accreditation status",
            "target prices and valuation recommendations",
            "qualitative investment scoring",
            "recalculation of System-1 ranking or momentum",
        ),
    )


# Source documents actually cited below (all fetched and read in full on
# 2026-09-19). Two further primary documents were also fetched and read in
# full during research -- the Q1FY27 press release
# (yatharth_33155954.pdf) and the Advent press release (yatharth_62339516.pdf)
# -- but every fact they state is already covered, with more granularity, by
# the investor presentation and board-meeting outcome cited here, so they are
# not cited a second time as separate evidence items (avoiding redundant,
# near-duplicate citations for the same underlying facts).
_INVESTOR_PRESENTATION_Q1FY27 = (
    "https://www.yatharthhospitals.com/uploads/investors/yatharth_49161125.pdf"
)
_EARNINGS_CALL_TRANSCRIPT_Q1FY27 = (
    "https://www.yatharthhospitals.com/uploads/investors/yatharth_13589302.pdf"
)
_BOARD_OUTCOME_ADVENT = (
    "https://www.yatharthhospitals.com/uploads/investors/yatharth_20573744.pdf"
)

_CLAIM_FIN_Q1 = (
    "Q1FY27 consolidated revenue was INR 3,927 million, up 51% YoY and 15% QoQ; "
    "EBITDA was INR 917 million, up 39% YoY; consolidated EBITDA margin was "
    "23.3%, down 209 bps from 25.4% a year earlier, while EBITDA margin "
    "adjusted to exclude ramp-up losses at Faridabad Sector-20 and New Delhi "
    "stood at 28.1%; PAT was INR 454 million, up 8% YoY, with PAT margin "
    "falling to 11.6% from 16.2% a year earlier."
)
_CLAIM_REVMIX = (
    "New hospitals (Greater Faridabad, New Delhi Model Town, Faridabad "
    "Sector-20 and Agra) contributed INR 1,067 million, or 27% of Q1FY27 group "
    "revenue, up from 22% in Q4FY26 and 9% in Q1FY26, while the existing Noida "
    "and Jhansi-Orchha hospitals grew revenue 22% YoY to INR 2,862 million."
)
_CLAIM_5YR_GROWTH = (
    "Per the Q1FY27 investor presentation's five-year summary, FY21-26 "
    "revenue grew at a 39% CAGR, EBITDA at a 34% CAGR and PAT at a 54% CAGR, "
    "with operating cash flow reaching INR 2,866 million in FY26."
)
_CLAIM_ROCE_DEBT = (
    "The same five-year summary shows return on capital employed fell from "
    "27-29% in FY22-FY24 to 19% in FY25 and 16% in FY26, which the company "
    "attributes to fund-raising and capex for acquisitions and infrastructure "
    "upgrades, even as net debt turned net-cash with a net debt/EBITDA ratio "
    "of -0.4x in FY26."
)
_CLAIM_CAP_OVERVIEW = (
    "As of Q1FY27, Yatharth's operational bed capacity was 2,555 census beds "
    "(2,800+ including the under-construction Gurugram hospital); group "
    "occupancy on operational census beds was 68%, up from 65% in Q1FY26; "
    "group ARPOB reached an all-time high of INR 34,758, up 7% YoY; and "
    "average length of stay fell to 3.73 days from 4.1 days a year earlier."
)
_CLAIM_PERHOSP_OCC = (
    "On the Q1FY27 earnings call, management gave Q1FY27 occupancy by "
    "hospital as: Noida 91%, Jhansi-Orchha 91%, Greater Noida 74%, Noida "
    "Extension 56%, Greater Faridabad 63%, Faridabad Sector-20 49%, Agra 89%, "
    "and New Delhi Model Town 29% -- the lowest in the network -- while "
    "noting the Model Town census-bed base used to compute occupancy had "
    "risen from 100 to 150 beds quarter-on-quarter."
)
_CLAIM_FBD20 = (
    "Faridabad Sector-20 (400 beds) achieved EBITDA breakeven in a record 9 "
    "months of operation; Q1FY27 revenue was INR 33 crore (~9% of group "
    "revenue) at a latest monthly run-rate of INR 12-13 crore, with ARPOB "
    "near INR 40,000 and a payer mix of over 90% cash/TPA."
)
_CLAIM_DELHI = (
    "New Delhi Model Town (300 beds) generated Q1FY27 revenue of INR 19 crore "
    "at a monthly run-rate of about INR 8 crore, with ARPOB approaching INR "
    "50,000 and a payer mix of over 90% cash/private insurance; management "
    "guided EBITDA breakeven for this hospital to H2 FY27, i.e. about 15-17 "
    "months after launch, versus Faridabad Sector-20's 9-month breakeven."
)
_CLAIM_AGRA = (
    "Agra hospital (250 beds), in its first full quarter of integration, "
    "delivered a Q1FY27 EBITDA margin above 20% on revenue of INR 24 crore "
    "and ARPOB above INR 30,000, operating on a 110-bed census out of 250 "
    "total beds at 89% occupancy on that census."
)
_CLAIM_GURUGRAM = (
    "Yatharth acquired 100% of an under-construction 250-bed super-speciality "
    "hospital in Sector 40, Gurugram for INR 100 crore, with an additional "
    "INR 100 crore planned for medical equipment; the hospital is expected to "
    "commence operations by Q1FY28 with ARPOB potential of INR 50,000-plus."
)
_CLAIM_BEDROADMAP = (
    "Management said announced bed capacity -- including the Gurugram "
    "acquisition and about 450 brownfield beds planned at Noida Extension and "
    "Greater Noida -- was 'already upwards of 3,200 beds' against a targeted "
    "~5,000-bed network, and that the company expects to reach 5,000 beds in "
    "'around two and a half years,' earlier than the originally announced "
    "3-year timeline."
)
_CLAIM_CGHS_PAYERMIX = (
    "On the Q1FY27 earnings call, management said the government payer mix "
    "rose to 'close to 40%' of group revenue in Q1FY27 from about 36% in the "
    "prior quarter, while volumes on government schemes were 'constantly "
    "decreasing quarter-on-quarter'; management attributed roughly 1-2 "
    "percentage points of the increase to a recent CGHS rate revision that "
    "raised realizations on the shrinking government-patient base."
)
_CLAIM_GOVT_RESTRICT = (
    "Management said a deliberate strategy to 'restrict the government's "
    "business' caused a quarter-on-quarter dip in Noida Extension occupancy, "
    "and that New Delhi Model Town and Faridabad Sector-20 were built to run "
    "at 'close to 90% cash and private insurance business,' with Faridabad "
    "Sector-20 reaching EBITDA breakeven with 'less than 10% government "
    "business.'"
)
_CLAIM_ROOMRENT = (
    "On the same call, management confirmed awareness of a government-panel "
    "recommendation to link private hospital room charges to three-star "
    "hotel tariffs, stating 'as of now, there's no comment' and that it is "
    "'just a proposal' far from implementation; management separately noted "
    "that CGHS rates 'were also revised' for the first time in years, and "
    "recalled past instances in which the government capped cardiac stent "
    "and orthopaedic implant prices."
)
_CLAIM_NABH_JCI = (
    "As of Q1FY27, all Yatharth hospitals held NABH accreditation and leading "
    "hospitals held NABL accreditation, with the Noida Extension hospital "
    "holding Joint Commission International (JCI) accreditation; the group "
    "reported over 1,200 robotic surgeries and more than 260 organ "
    "transplants since inception, using 8 robotic surgical systems (Da Vinci "
    "and orthopaedic robots) across the network."
)
_CLAIM_SPECIALTY_MIX = (
    "The share of group revenue from Internal Medicine fell from 56% in "
    "FY2021 to 19% in FY2026 and 16% in Q1FY2027, while Neurosciences, "
    "Nephrology & Urology, Oncology, Cardiology, Orthopaedics/Spine/"
    "Rheumatology and Gastroenterology collectively gained share, with the "
    "group operating 1 LINAC radiotherapy machine (2 more planned) alongside "
    "the robotic-surgery infrastructure."
)
_CLAIM_ATTRITION = (
    "On the Q1FY27 earnings call, management reported group-level doctor "
    "attrition of 'nearly 7%,' with senior-doctor attrition below 3-4%, "
    "attributing the improvement partly to DNB training programmes that "
    "retain junior doctors longer; the Board separately approved the "
    "company's first ESOP grant under ESOP Scheme 2024 and launched ESOP "
    "Scheme 2026 to attract and retain clinical and non-clinical talent."
)
_CLAIM_CAPEX_DEBT = (
    "Management guided capex per bed of INR 75-80 lakh for the next 1,800 "
    "planned beds, up from INR 30.7 lakh three years earlier and INR 61.4 "
    "lakh most recently, citing higher land and equipment costs; the CFO said "
    "net debt had risen from about INR 210 crore in March 2026 to about INR "
    "300 crore following the Gurugram acquisition, and management said it "
    "was comfortable funding the remaining capex from internal accruals, "
    "cash and debt headroom of up to about 2x trailing-twelve-month EBITDA."
)
_CLAIM_ADVENT = (
    "On 17 September 2026, Yatharth's board approved a preferential issue to "
    "Rasmalai Limited (an Advent International vehicle incorporated in "
    "Cyprus) of up to 1,30,26,516 equity shares and 1,89,47,664 warrants at "
    "INR 985.17 each, for aggregate consideration of up to INR 3,150 crore, "
    "representing a 24.87% fully-diluted post-issue stake; the transaction is "
    "subject to shareholder approval at an EGM convened for 15 October 2026 "
    "and regulatory approvals including the Competition Commission of India, "
    "and the Tyagi-family promoters (55.80% pre-issue) retain majority board "
    "nomination rights and are subject to a 3-year lock-in."
)
_CLAIM_UNK_PAYER_GRANULARITY = (
    "The reviewed Q1FY27 primary disclosures (press release, investor "
    "presentation, earnings-call transcript) give only an aggregate ~40% "
    "government payer share and a qualitative '1-2 percentage point' CGHS "
    "impact; they do not break down government revenue by specific scheme "
    "(e.g. CGHS vs. Ayushman Bharat/PMJAY vs. state schemes) or quantify "
    "group revenue/EBITDA sensitivity to further government rate action."
)
_CLAIM_UNK_ADVENT_CLOSE = (
    "As of the 18 September 2026 information cutoff, the Advent International "
    "preferential issue had not closed: it remained subject to shareholder "
    "approval at the 15 October 2026 EGM, Competition Commission of India "
    "clearance, and other conditions precedent, so the transaction's final "
    "terms, board-composition changes and use of proceeds cannot yet be "
    "confirmed as completed facts."
)


def yatharth_evidence() -> tuple[Evidence, ...]:
    return (
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.POSITIVE,
            claim=_CLAIM_FIN_Q1,
            source=_INVESTOR_PRESENTATION_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 10),
            event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high",
            hypothesis=_H1_MARGIN_QUALITY,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.POSITIVE,
            claim=_CLAIM_REVMIX,
            source=_INVESTOR_PRESENTATION_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 10),
            event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="high",
            hypothesis=_H1_MARGIN_QUALITY,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.POSITIVE,
            claim=_CLAIM_5YR_GROWTH,
            source=_INVESTOR_PRESENTATION_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 10),
            event_date=date(2026, 3, 31), retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="medium",
            hypothesis=_H1_MARGIN_QUALITY,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.NEGATIVE,
            claim=_CLAIM_ROCE_DEBT,
            source=_INVESTOR_PRESENTATION_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 10),
            event_date=date(2026, 3, 31), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPITAL_MARKETS, materiality="high",
            hypothesis=_H4_CAPITAL_ALLOCATION,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.POSITIVE,
            claim=_CLAIM_CAP_OVERVIEW,
            source=_INVESTOR_PRESENTATION_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 10),
            event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="high",
            hypothesis=_H2_RAMP_EXECUTION,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.NEGATIVE,
            claim=_CLAIM_PERHOSP_OCC,
            source=_EARNINGS_CALL_TRANSCRIPT_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 18),
            event_date=date(2026, 8, 11), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="high",
            hypothesis=_H2_RAMP_EXECUTION,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.POSITIVE,
            claim=_CLAIM_FBD20,
            source=_INVESTOR_PRESENTATION_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 10),
            event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="high",
            hypothesis=_H2_RAMP_EXECUTION,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.POSITIVE,
            claim=_CLAIM_DELHI,
            source=_INVESTOR_PRESENTATION_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 10),
            event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="high",
            hypothesis=_H2_RAMP_EXECUTION,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.POSITIVE,
            claim=_CLAIM_AGRA,
            source=_INVESTOR_PRESENTATION_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 10),
            event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="medium",
            hypothesis=_H2_RAMP_EXECUTION,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.POSITIVE,
            claim=_CLAIM_GURUGRAM,
            source=_INVESTOR_PRESENTATION_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 10),
            event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="medium",
            hypothesis=_H4_CAPITAL_ALLOCATION,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.POSITIVE,
            claim=_CLAIM_BEDROADMAP,
            source=_EARNINGS_CALL_TRANSCRIPT_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 18),
            event_date=date(2026, 8, 11), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="medium",
            hypothesis=_H4_CAPITAL_ALLOCATION,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.NEGATIVE,
            claim=_CLAIM_CGHS_PAYERMIX,
            source=_EARNINGS_CALL_TRANSCRIPT_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 18),
            event_date=date(2026, 8, 11), retrieved_on=RETRIEVED,
            domain=ResearchDomain.GOVERNMENT_REGULATION, materiality="high",
            hypothesis=_H3_PAYER_MIX_REGULATION,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.POSITIVE,
            claim=_CLAIM_GOVT_RESTRICT,
            source=_EARNINGS_CALL_TRANSCRIPT_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 18),
            event_date=date(2026, 8, 11), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CUSTOMERS_SUPPLIERS, materiality="high",
            hypothesis=_H3_PAYER_MIX_REGULATION,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.NEGATIVE,
            claim=_CLAIM_ROOMRENT,
            source=_EARNINGS_CALL_TRANSCRIPT_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 18),
            event_date=date(2026, 8, 11), retrieved_on=RETRIEVED,
            domain=ResearchDomain.GOVERNMENT_REGULATION, materiality="medium",
            hypothesis=_H3_PAYER_MIX_REGULATION,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.POSITIVE,
            claim=_CLAIM_NABH_JCI,
            source=_INVESTOR_PRESENTATION_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 10),
            event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.GOVERNMENT_REGULATION, materiality="medium",
            hypothesis=_H5_TALENT_DIFFERENTIATION,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.POSITIVE,
            claim=_CLAIM_SPECIALTY_MIX,
            source=_INVESTOR_PRESENTATION_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 10),
            event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CUSTOMERS_SUPPLIERS, materiality="medium",
            hypothesis=_H1_MARGIN_QUALITY,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.POSITIVE,
            claim=_CLAIM_ATTRITION,
            source=_EARNINGS_CALL_TRANSCRIPT_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 18),
            event_date=date(2026, 8, 11), retrieved_on=RETRIEVED,
            domain=ResearchDomain.MANAGEMENT, materiality="high",
            hypothesis=_H5_TALENT_DIFFERENTIATION,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.POSITIVE,
            claim=_CLAIM_CAPEX_DEBT,
            source=_EARNINGS_CALL_TRANSCRIPT_Q1FY27,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 8, 18),
            event_date=date(2026, 8, 11), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPITAL_MARKETS, materiality="high",
            hypothesis=_H4_CAPITAL_ALLOCATION,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.POSITIVE,
            claim=_CLAIM_ADVENT,
            source=_BOARD_OUTCOME_ADVENT,
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 9, 17),
            event_date=date(2026, 9, 17), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPITAL_MARKETS, materiality="high",
            hypothesis=_H4_CAPITAL_ALLOCATION,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.UNKNOWN,
            claim=_CLAIM_UNK_PAYER_GRANULARITY,
            source="research-window: Q1FY27 primary disclosure review "
                   "(press release, investor presentation, earnings-call "
                   "transcript dated 10-18 August 2026)",
            source_tier=SourceTier.DERIVED, retrieved_on=RETRIEVED,
            domain=ResearchDomain.GOVERNMENT_REGULATION, materiality="high",
            hypothesis=_H3_PAYER_MIX_REGULATION,
        ),
        Evidence(
            entity="YATHARTH", kind=EvidenceKind.UNKNOWN,
            claim=_CLAIM_UNK_ADVENT_CLOSE,
            source="research-window: 17 September 2026 board-meeting outcome "
                   "and press release review",
            source_tier=SourceTier.DERIVED, retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPITAL_MARKETS, materiality="high",
            hypothesis=_H4_CAPITAL_ALLOCATION,
        ),
    )


def yatharth_packet() -> ResearchProviderPacket:
    evidence = yatharth_evidence()
    refs = {e.claim: evidence_ref(e) for e in evidence}

    def ref(claim: str) -> str:
        try:
            return refs[claim]
        except KeyError as exc:
            raise ValueError(f"unknown evidence claim: {claim}") from exc

    return ResearchProviderPacket(
        plan=yatharth_plan(),
        evidence=evidence,
        causal_findings=(
            CausalFinding(
                hypothesis=_H1_MARGIN_QUALITY,
                finding=(
                    "Revenue and margin growth in Q1FY27 came from both durable "
                    "gains at mature hospitals (the Noida cluster grew 22% YoY, "
                    "five-year revenue/EBITDA/PAT CAGR of 39%/34%/54%, and a real "
                    "specialty-mix upgrade away from Internal Medicine) and from "
                    "newer hospitals still absorbing ramp-up losses, so "
                    "consolidated margin and the underlying mature-hospital "
                    "trend moved in opposite directions this quarter."
                ),
                mechanism=(
                    "Mature hospitals monetise an improving, higher-value "
                    "specialty mix into rising ARPOB and stable occupancy, while "
                    "newly acquired or greenfield hospitals add revenue at low "
                    "initial occupancy and thin or negative unit economics until "
                    "each individually reaches breakeven, which mechanically "
                    "drags consolidated margin even as the mature business "
                    "strengthens."
                ),
                timing=(
                    "Already visible in Q1FY27 and over the trailing five years "
                    "for the mature base; management expects the newer-hospital "
                    "drag to fade over the next 12-18 months as each asset "
                    "reaches its own guided breakeven."
                ),
                uncertainty=(
                    "The reviewed materials do not disclose a segment-level "
                    "(mature vs. new) EBITDA margin split net of corporate "
                    "overhead, only revenue mix and blended margins, so the "
                    "precise durability of the mature-hospital margin trend "
                    "cannot be fully isolated."
                ),
                evidence_refs=(
                    ref(_CLAIM_FIN_Q1),
                    ref(_CLAIM_REVMIX),
                    ref(_CLAIM_5YR_GROWTH),
                    ref(_CLAIM_SPECIALTY_MIX),
                ),
            ),
            CausalFinding(
                hypothesis=_H2_RAMP_EXECUTION,
                finding=(
                    "New-hospital integration is delivering genuine, "
                    "differentiated results (Faridabad Sector-20 breakeven in 9 "
                    "months; Agra above 20% EBITDA margin in its first full "
                    "quarter) but occupancy ramp-up is uneven, with New Delhi "
                    "Model Town still at only 29% occupancy and the 5,000-bed "
                    "target dependent on beds not yet built (Gurugram, "
                    "brownfield additions)."
                ),
                mechanism=(
                    "A newly opened or acquired hospital's revenue and EBITDA "
                    "depend on filling census beds with a favourable case/payer "
                    "mix; management's playbook of recruiting reputed doctors "
                    "and restricting government-scheme growth accelerates ARPOB "
                    "but can slow headline occupancy relative to a strategy that "
                    "filled beds faster with lower-paying patients. This "
                    "playbook is common to both Faridabad Sector-20 and New "
                    "Delhi Model Town, so it explains why new hospitals in "
                    "general may show slower headline occupancy than a "
                    "volume-first strategy would -- it does NOT by itself "
                    "explain why these two specific hospitals, running the same "
                    "playbook, diverge so sharply on breakeven timing (9 months "
                    "vs. 15-17 months guided); some hospital-specific factor "
                    "not identified in the reviewed materials must also be at "
                    "work."
                ),
                timing=(
                    "Faridabad Sector-20 and Agra have already inflected; New "
                    "Delhi is guided to breakeven in H2 FY27; Gurugram is "
                    "expected to open Q1 FY28 and the remaining beds toward the "
                    "5,000-bed target over roughly the next two to three years."
                ),
                uncertainty=(
                    "Occupancy at New Delhi and Faridabad Sector-20 is measured "
                    "against a rising census-bed denominator that management "
                    "adjusts quarter to quarter, which the reviewed materials do "
                    "not reconcile into a single like-for-like ramp-up curve. "
                    "Separately: no disclosed, hospital-specific factor (e.g. "
                    "differing capex vintage, case mix, catchment competition "
                    "density, or doctor roster) is identified to explain the "
                    "Faridabad-vs-Delhi breakeven-timing divergence beyond the "
                    "shared group-level playbook, which cannot itself account "
                    "for a difference between two hospitals both running it."
                ),
                evidence_refs=(
                    ref(_CLAIM_CAP_OVERVIEW),
                    ref(_CLAIM_PERHOSP_OCC),
                    ref(_CLAIM_FBD20),
                    ref(_CLAIM_DELHI),
                    ref(_CLAIM_AGRA),
                ),
            ),
            CausalFinding(
                hypothesis=_H3_PAYER_MIX_REGULATION,
                # Loop 14 adversarial council: management's own figure
                # attributes only ~1-2 of the observed ~4-point (36%->~40%)
                # rise to the CGHS repricing -- "because" overstated a partial
                # explanation as the full cause. Reworded, and the ~2-3-point
                # residual is now named explicitly rather than only appearing
                # as a future-looking uncertainty.
                finding=(
                    "Yatharth's payer-mix strategy at new hospitals (over 90% "
                    "cash/TPA) is real and evidenced at the hospital level, but "
                    "at the group level the government-payer revenue share still "
                    "rose quarter-on-quarter (about 36% to 'close to 40%'). "
                    "Management attributed only roughly 1-2 of those ~4 "
                    "percentage points to a CGHS rate revision lifting "
                    "realizations on a shrinking government-patient base -- so "
                    "CGHS repricing partially, not fully, explains the current "
                    "quarter's rise, and roughly 2-3 points remain unaccounted "
                    "for in the reviewed materials. A government panel has "
                    "separately floated capping private hospital room charges."
                ),
                mechanism=(
                    "Government-scheme pricing and rules are set exogenously "
                    "(CGHS package-rate revisions, potential room-rent caps, "
                    "empanelment terms), so even as Yatharth deliberately shifts "
                    "new capacity toward cash/private-insurance patients, "
                    "changes in government tariffs can still move the reported "
                    "group payer-mix percentage and represent a policy risk to "
                    "future realizations."
                ),
                timing=(
                    "The CGHS repricing effect was already visible in Q1FY27; "
                    "the room-rent-cap recommendation is, per management, an "
                    "early-stage proposal with no defined implementation "
                    "timeline as of the 18 September 2026 information cutoff."
                ),
                uncertainty=(
                    "The magnitude of a potential room-rent cap or further "
                    "CGHS/PMJAY rate changes on group revenue and margin is not "
                    "quantified in the reviewed materials. Separately, and in "
                    "the present tense rather than as a future risk: roughly "
                    "2-3 of the ~4-percentage-point rise in government payer "
                    "share this quarter is not explained by the disclosed CGHS "
                    "repricing impact, and no alternative explanation (e.g. a "
                    "mix shift within the government-patient base, or a "
                    "different scheme's repricing) is identified in the "
                    "reviewed materials."
                ),
                evidence_refs=(
                    ref(_CLAIM_CGHS_PAYERMIX),
                    ref(_CLAIM_GOVT_RESTRICT),
                    ref(_CLAIM_ROOMRENT),
                    ref(_CLAIM_UNK_PAYER_GRANULARITY),
                ),
            ),
            CausalFinding(
                hypothesis=_H4_CAPITAL_ALLOCATION,
                # Loop 14 adversarial council: the prior finding text gave the
                # "accelerated growth ambition" reading alone, relegating the
                # equally-plausible "balance-sheet strain" reading (declining
                # RoCE, a raise arranged within 5 weeks of a "sufficient"
                # comment) to the contradiction's resolution only. Both
                # readings now appear with comparable weight in the finding
                # itself, not just when a counter-argument forces it.
                finding=(
                    "The Advent International preferential investment provides "
                    "a large primary capital infusion (up to INR 3,150 crore "
                    "for a 24.87% fully-diluted stake) that goes well beyond the "
                    "internal-accrual and debt-headroom funding management "
                    "described just five weeks earlier for the already-"
                    "committed ~1,800-bed programme. Two readings are equally "
                    "available from the disclosed facts and neither is "
                    "confirmed over the other: (1) the company is capitalising "
                    "for a materially larger and/or faster expansion than "
                    "previously guided funding sources alone would support, or "
                    "(2) a large, hastily-arranged primary raise from one "
                    "sponsor -- granted board seats and reserved-matter rights, "
                    "arriving alongside already-declining RoCE (27-29% to 16% "
                    "over FY22-FY26) -- signals pressure to shore up the "
                    "balance sheet rather than confirmed growth ambition."
                ),
                mechanism=(
                    "Bed-capacity growth requires capex (guided at INR 75-80 "
                    "lakh per new bed) funded by some mix of operating cash "
                    "flow, debt (management comfortable up to about 2x trailing "
                    "EBITDA) and equity; a large primary equity raise reduces "
                    "leverage and dilution risk per rupee of capex but dilutes "
                    "existing shareholders and introduces a new investor with "
                    "board-nomination and reserved-matter rights -- the same "
                    "facts support either the expansion-acceleration or the "
                    "balance-sheet-strain reading above; nothing in the "
                    "reviewed materials confirms which is operative."
                ),
                timing=(
                    "The Investment Agreement was signed 17 September 2026; "
                    "completion is conditional on shareholder approval at the "
                    "15 October 2026 EGM and regulatory approvals including the "
                    "Competition Commission of India, so the capital has not "
                    "yet been received as of the information cutoff."
                ),
                uncertainty=(
                    "The specific use of the INR 3,150 crore proceeds (which "
                    "beds, hospitals, or further acquisitions) is not yet "
                    "disclosed, and the transaction could still be delayed or "
                    "altered before closing."
                ),
                evidence_refs=(
                    ref(_CLAIM_CAPEX_DEBT),
                    ref(_CLAIM_ADVENT),
                    ref(_CLAIM_ROCE_DEBT),
                    ref(_CLAIM_UNK_ADVENT_CLOSE),
                    ref(_CLAIM_GURUGRAM),
                    ref(_CLAIM_BEDROADMAP),
                ),
            ),
            CausalFinding(
                hypothesis=_H5_TALENT_DIFFERENTIATION,
                # Loop 14 adversarial council: the plan excludes clinical-
                # outcome metrics (mortality, complication rates) as
                # undisclosed, which is a legitimate scope limit -- but the
                # finding's own language should not then describe accreditation
                # status and volume counts as "clinical differentiation"
                # unqualified, since those are input/reputation proxies the
                # company chooses to publish favourably, not independently
                # verified outcome quality. Reworded to name that distinction
                # rather than let the hypothesis's own wording ("clinical
                # differentiation") imply more than what is actually measured.
                finding=(
                    "Yatharth reports favourable INPUT and reputational proxies "
                    "for clinical capability (universal NABH accreditation, JCI "
                    "accreditation at Noida Extension, robotic-surgery and "
                    "transplant volumes) and group doctor attrition (about 7%, "
                    "lower among senior doctors) appears controlled for now -- "
                    "but this finding answers capacity/talent inputs, not "
                    "verified clinical-outcome quality (mortality, complication "
                    "or infection rates are not disclosed and are outside this "
                    "research's scope). Neither the accreditation base nor the "
                    "attrition rate has been tested at the scale of a "
                    "five-cluster, ~5,000-bed network reaching into new "
                    "geographies."
                ),
                mechanism=(
                    "Recruiting and retaining reputed specialist doctors drives "
                    "case mix, ARPOB and brand recall in each new cluster (as "
                    "management described for both Faridabad and New Delhi); "
                    "losing that talent, or failing to replicate it in "
                    "unfamiliar cities, would directly slow the ARPOB and "
                    "margin ramp the growth plan depends on."
                ),
                timing=(
                    "Doctor-retention and accreditation performance will be "
                    "tested progressively as Gurugram, further brownfield beds, "
                    "and at least one new hospital acquisition per year are "
                    "added over the next two to three years."
                ),
                uncertainty=(
                    "The reviewed disclosures give only a group-level attrition "
                    "figure and confirm accreditation status, without "
                    "hospital-level attrition or an independent clinical-"
                    "quality audit score, so durability of this advantage as "
                    "the network scales cannot be independently verified from "
                    "company materials alone."
                ),
                evidence_refs=(
                    ref(_CLAIM_NABH_JCI),
                    ref(_CLAIM_ATTRITION),
                ),
            ),
        ),
        contradictions=(
            ContradictionFinding(
                # Loop 14 adversarial council: "durable, high-quality" was not
                # language used by any cited source -- it was this research's
                # own synthesis of the 5-year growth and revenue-mix evidence,
                # presented as if it were an external claim being rebutted.
                # Reworded to name it explicitly as a reading of the cited
                # evidence, consistent with how item 7/22 already fixed the
                # same pattern elsewhere in this pipeline.
                hypothesis=_H1_MARGIN_QUALITY,
                original_claim=(
                    "Read together, Yatharth's five-year revenue/EBITDA/PAT "
                    "CAGR and Q1FY27's rising new-hospital revenue mix would "
                    "suggest durable, high-quality growth -- this is this "
                    "research's own reading of those two data points, not a "
                    "claim quoted from management or an analyst."
                ),
                counter_evidence=(
                    "Q1FY27's own reported numbers show consolidated EBITDA "
                    "margin fell 209 bps YoY to 23.3% and PAT margin fell from "
                    "16.2% to 11.6%, precisely because the newer hospitals "
                    "driving the revenue-mix shift are still loss-making or "
                    "thin-margin, so the most recent quarter's profitability "
                    "quality moved in the opposite direction of the multi-year "
                    "growth narrative."
                ),
                resolution=(
                    "Multi-year revenue/EBITDA/PAT growth and the current "
                    "specialty-mix upgrade are real, but near-term consolidated "
                    "margins are being diluted by ramp-up losses at newly "
                    "added hospitals; the two are compatible only if those "
                    "hospitals reach their guided breakeven and margin targets "
                    "on schedule, which is not yet a completed fact."
                ),
                original_claim_refs=(ref(_CLAIM_5YR_GROWTH), ref(_CLAIM_REVMIX)),
                counter_evidence_refs=(ref(_CLAIM_FIN_Q1),),
            ),
            ContradictionFinding(
                hypothesis=_H2_RAMP_EXECUTION,
                original_claim=(
                    "Yatharth's acquisition/integration playbook is working "
                    "quickly, as shown by Faridabad Sector-20's 9-month EBITDA "
                    "breakeven and Agra's above-20% EBITDA margin in its first "
                    "full quarter."
                ),
                # Loop 14 adversarial council: the 29% figure is computed on
                # a census-bed base that itself rose 100->150 beds QoQ, a
                # disclosed denominator change that breaks like-for-like
                # comparison -- previously this caveat sat only in the
                # finding's buried "Uncertainty" field while the contradiction
                # used the bare 29% as if directly comparable. Named here
                # instead of only implied, and the resolution downgrades this
                # from a clean, decisive comparison to an observation that
                # needs a stable-denominator recomputation before being relied
                # on as proof of a materially slower ramp.
                counter_evidence=(
                    "New Delhi Model Town, the group's other 2025-vintage new "
                    "hospital, reported only 29% occupancy in Q1FY27 -- the "
                    "lowest in the network -- with EBITDA breakeven now guided "
                    "to H2 FY27 (about 15-17 months post-launch), materially "
                    "slower than Faridabad Sector-20's 9-month breakeven "
                    "despite a similar launch window and the same playbook. "
                    "This 29% figure is computed on a census-bed base that "
                    "itself rose from 100 to 150 beds quarter-on-quarter, so "
                    "it is not a clean like-for-like ramp-up metric -- the "
                    "underlying occupied-bed count, which would allow a stable "
                    "comparison, is not disclosed in the reviewed materials."
                ),
                resolution=(
                    "The playbook has clearly worked at Faridabad Sector-20 "
                    "and Agra. New Delhi's occupancy percentage is the lowest "
                    "in the network, but because its census-bed denominator "
                    "grew during the quarter, the 29% figure alone cannot "
                    "establish HOW MUCH slower the ramp genuinely is -- it "
                    "could be better, worse, or similar to what a stable "
                    "denominator would show. Treat New Delhi's execution as "
                    "genuinely uncertain rather than as a confirmed, "
                    "quantified underperformance, and monitor the breakeven "
                    "guidance itself rather than the occupancy percentage in "
                    "isolation."
                ),
                original_claim_refs=(ref(_CLAIM_FBD20), ref(_CLAIM_AGRA)),
                counter_evidence_refs=(ref(_CLAIM_PERHOSP_OCC), ref(_CLAIM_DELHI)),
            ),
            ContradictionFinding(
                hypothesis=_H3_PAYER_MIX_REGULATION,
                original_claim=(
                    "Management's deliberate strategy of restricting "
                    "government-scheme growth and building new hospitals with "
                    "over 90% cash/TPA patients is durably improving Yatharth's "
                    "payer mix."
                ),
                counter_evidence=(
                    "Despite that stated strategy, the group-level government "
                    "payer-mix share rose quarter-on-quarter to 'close to 40%' "
                    "from about 36%, because a CGHS rate revision raised "
                    "realizations on the shrinking government book faster than "
                    "the cash/TPA mix shift could dilute it, and a government "
                    "panel has separately floated capping private hospital "
                    "room charges."
                ),
                resolution=(
                    "Volume-based payer mix is genuinely improving at the "
                    "hospital level, but the group-level percentage remains "
                    "sensitive to government pricing actions outside the "
                    "company's control, so 'improving payer mix' and 'rising "
                    "government revenue share' can both be true in the same "
                    "quarter; exposure to further government tariff action is "
                    "a real, unresolved risk rather than a resolved trend."
                ),
                original_claim_refs=(ref(_CLAIM_GOVT_RESTRICT),),
                counter_evidence_refs=(ref(_CLAIM_CGHS_PAYERMIX), ref(_CLAIM_ROOMRENT)),
            ),
            ContradictionFinding(
                hypothesis=_H4_CAPITAL_ALLOCATION,
                original_claim=(
                    "On 11 August 2026, management said existing cash, "
                    "internal accruals and available debt headroom (up to "
                    "about 2x trailing EBITDA) were sufficient to fund the "
                    "remaining ~1,800-bed capex programme, implying no need "
                    "for a large near-term external capital raise."
                ),
                counter_evidence=(
                    "Five weeks later, on 17 September 2026, Yatharth's board "
                    "approved a INR 3,150 crore preferential issue to Advent "
                    "International for a 24.87% fully-diluted stake -- one of "
                    "the largest primary private-equity infusions in the "
                    "Indian hospital sector -- alongside a return on capital "
                    "employed that had already declined from 27-29% to 16% "
                    "over FY22-FY26 amid the ongoing capex cycle."
                ),
                # Loop 14 adversarial council: the prior resolution only
                # hedged around the harder reading without naming it. A
                # transaction of this size and structure (warrants, board
                # seats, reserved matters, a Cyprus SPV) plausibly requires
                # weeks-to-months of negotiation, which would place its start
                # before 11 August -- but the reviewed materials do not
                # establish exactly when Advent discussions began (the
                # earliest public signal found is the company's own 14
                # September intimation of the board meeting, just 3 days
                # before approval, which is not itself proof either way).
                # Named the harder reading explicitly rather than leaving it
                # only implied by hedged language.
                resolution=(
                    "Two readings are available and the evidence does not "
                    "confirm either: (1) the two statements are compatible -- "
                    "Advent's capital could fund an accelerated bed-capacity "
                    "target, new-cluster M&A, or balance-sheet strengthening "
                    "beyond the already-committed 1,800 beds, arising only "
                    "after 11 August; or (2) the harder reading -- a "
                    "transaction of this size and structure (warrants, board "
                    "seats, reserved-matter rights, a Cyprus SPV) plausibly "
                    "requires weeks-to-months of negotiation, meaning "
                    "discussions were quite possibly already underway when "
                    "management called existing sources 'sufficient,' making "
                    "that comment materially incomplete rather than "
                    "subsequently overtaken by events. The reviewed materials "
                    "do not establish when Advent discussions actually began "
                    "-- the earliest public signal found is the company's own "
                    "14 September intimation of the board meeting, only 3 days "
                    "before approval, which does not itself resolve the "
                    "question either way. Investors should weigh this as a "
                    "genuinely open question, not treat the funding-"
                    "sufficiency comment as already reconciled with the raise."
                ),
                original_claim_refs=(ref(_CLAIM_CAPEX_DEBT),),
                counter_evidence_refs=(ref(_CLAIM_ADVENT), ref(_CLAIM_ROCE_DEBT)),
            ),
        ),
        unresolved_questions=(
            "What is the incremental government-scheme (CGHS/PMJAY/state "
            "scheme) revenue and margin sensitivity if further government "
            "rate actions occur, given the reviewed materials disclose only "
            "an aggregate ~40% government payer share and a qualitative "
            "impact figure rather than a quantified sensitivity?",
            "Roughly 2-3 of the ~4-percentage-point rise in government payer "
            "share this quarter is not explained by the disclosed CGHS "
            "repricing impact -- what accounts for the remainder (a mix "
            "shift within government patients, a different scheme's "
            "repricing, or something else)?",
            "Will the government panel recommendation on capping hospital "
            "room charges referenced on the Q1FY27 call advance into a "
            "binding framework, and if so what would its revenue/margin "
            "impact be?",
            "Will New Delhi Model Town and the remaining new hospitals reach "
            "their guided EBITDA-breakeven and margin targets on schedule, "
            "given New Delhi's occupancy remained the lowest in the network "
            "in Q1FY27?",
            "What are the definitive terms, closing timeline and conditions "
            "(including CCI approval and the 15 October 2026 EGM outcome) of "
            "the Advent International preferential investment, and how will "
            "the ~INR 3,150 crore of primary capital be deployed against the "
            "~5,000-bed target?",
            "Can the company sustain a ~7% group-level doctor attrition rate "
            "as it scales into new geographies and competes for specialist "
            "talent, particularly at newly entered clusters like New Delhi "
            "and Gurugram?",
            # Loop 14 adversarial council additions (items #1 and #5 of the
            # Prosecution brief): every non-DERIVED item in this packet
            # traces to one publisher (the company's own investor-relations
            # filings) -- no rating-agency note, exchange-filing page,
            # sell-side report or independent press coverage was found for
            # any claim, and no competitive-landscape evidence (Max, Fortis,
            # Apollo, Manipal, Medanta -- all direct Delhi/NCR/Gurugram
            # competitors) exists anywhere despite two hypotheses (H2, H5) for
            # which competitive intensity is an obvious explanatory factor.
            # Recorded honestly as open gaps rather than left silent.
            "No evidence in this dossier is independently corroborated outside "
            "the company's own investor-relations filings (no rating-agency "
            "note, exchange-side filing page, analyst report, or independent "
            "press coverage was found) -- how would the headline figures in "
            "this dossier hold up against an independent source, and does one "
            "exist for a hospital operator of this size and listing age?",
            "How does Yatharth's occupancy, ARPOB and payer-mix profile in "
            "Delhi/NCR and Gurugram compare to established competitors (Max, "
            "Fortis, Apollo, Manipal, Medanta) operating in the same "
            "catchments -- no competitive-landscape evidence was found despite "
            "this being a plausible explanatory factor for New Delhi Model "
            "Town's comparatively weak occupancy ramp?",
        ),
        monitoring_questions=(
            "Track quarterly occupancy and ARPOB ramp-up at each new "
            "hospital (Faridabad Sector-20, New Delhi Model Town, Agra, "
            "Greater Faridabad, and the upcoming Gurugram hospital) against "
            "management's stated breakeven and margin timelines.",
            "Track group-level and per-hospital payer mix (cash/TPA vs. "
            "government) and any further CGHS/PMJAY/state-scheme rate "
            "revisions or the proposed room-rent-cap framework.",
            "Track EGM approval (15 October 2026), CCI clearance and "
            "closing of the Advent International preferential issue, and "
            "subsequent capital deployment and board-composition changes.",
            "Track consolidated EBITDA margin recovery toward management's "
            "~24% FY27 guidance as new-hospital ramp-up losses diminish.",
            "Track net debt/EBITDA, capex per bed on the next tranche of "
            "bed additions, and RoCE trajectory as the ~5,000-bed programme "
            "is executed.",
        ),
    )
