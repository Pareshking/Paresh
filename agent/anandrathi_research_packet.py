"""Acceptance research packet for the second-archetype adaptive execution test.

Company: ANANDRATHI (Anand Rathi Wealth Limited)
Archetype: wealth-management / capital-markets services platform
Snapshot cutoff: 2026-09-18
Retrieved: 2026-09-19

This packet demonstrates that a financial-services/wealth-management company
selects a different research lens from an industrial precision manufacturer.
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


def anandrathi_plan() -> ResearchPlan:
    return ResearchPlan(
        symbol="ANANDRATHI",
        company_archetype="wealth-management and capital-markets services platform serving HNI/UHNI clients through relationship-led advice, distribution and digital channels",
        economic_drivers=(
            "AUM growth from net client inflows and market performance",
            "client retention and relationship-manager productivity",
            "recurring trail/distribution and wealth-management economics",
            "mix of private wealth, mutual-fund distribution and digital wealth",
            "employee productivity and compensation intensity",
            "regulatory/product economics and potential AMC expansion",
            "capital allocation and subsidiary/platform investment",
        ),
        material_domains=(
            ResearchDomain.FINANCIALS,
            ResearchDomain.MANAGEMENT,
            ResearchDomain.CUSTOMERS_SUPPLIERS,
            ResearchDomain.GOVERNMENT_REGULATION,
            ResearchDomain.TECHNOLOGY_IP,
            ResearchDomain.CAPITAL_MARKETS,
        ),
        hypotheses=(
            "Is AUM growth being supported by durable client acquisition and retention rather than market appreciation alone?",
            "Can relationship-manager productivity and client growth support revenue growth without proportionate employee-cost escalation?",
            "Are regulatory and product changes likely to alter the economics of distribution and the proposed AMC expansion?",
            "Is the business sufficiently diversified across clients, products and channels to remain resilient during weak capital markets?",
        ),
        exclusions=(
            "bank-style loan growth, NIM, GNPA/NNPA or capital-adequacy analysis because ANANDRATHI is not a bank/NBFC lending business",
            "manufacturing capacity, raw-material and plant-utilisation analysis unless a specific subsidiary exposure makes it material",
            "target prices and valuation recommendations",
            "qualitative investment scoring",
            "recalculation of System-1 ranking or momentum",
        ),
    )


def anandrathi_evidence() -> tuple[Evidence, ...]:
    return (
        Evidence(
            entity="ANANDRATHI", kind=EvidenceKind.POSITIVE,
            claim="FY26 consolidated total income excluding fair-value gains, ESOP expenses and related tax effects was INR 1,198.49 crore, up 22.3% YoY; adjusted PAT was INR 385.73 crore, up 28.4%.",
            source="https://www.anandrathiwealth.in/wealthpdf/27april2026/Annualreportandnoticesd.pdf",
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 4, 27),
            event_date=date(2026, 3, 31), retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high",
            hypothesis="Is AUM growth being supported by durable client acquisition and retention rather than market appreciation alone?",
        ),
        Evidence(
            entity="ANANDRATHI", kind=EvidenceKind.POSITIVE,
            claim="As of 30 June 2026, AUM was INR 1,06,300+ crore, with 417+ relationship managers and 13,941+ clients according to the company's current website.",
            source="https://www.anandrathiwealth.in/",
            # Downgraded from PRIMARY (item 19 / F2): a bare domain root is a
            # live page, not a fixed dated document.
            source_tier=SourceTier.SECONDARY,
            # Live-fetched and confirmed 2026-09-19: the homepage shows
            # "(As of 30 June 2026)" against these figures -- a data date,
            # not a publication date; the page itself is undated/evergreen.
            undated_primary_source=True,
            event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CUSTOMERS_SUPPLIERS, materiality="high",
            hypothesis="Is AUM growth being supported by durable client acquisition and retention rather than market appreciation alone?",
        ),
        Evidence(
            entity="ANANDRATHI", kind=EvidenceKind.POSITIVE,
            claim="Q1FY27 AUM rose 21% YoY to INR 1,06,300 crore and net inflows were INR 2,743 crore; active client families rose 13% YoY to 13,941.",
            source="https://economictimes.indiatimes.com/markets/stocks/earnings/anand-rathi-wealth-q1-results-profit-rises-24-to-rs-116-crore-revenue-grows-18/articleshow/132287729.cms",
            source_tier=SourceTier.SECONDARY, published_on=date(2026, 7, 9),
            event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CUSTOMERS_SUPPLIERS, materiality="high",
            hypothesis="Is AUM growth being supported by durable client acquisition and retention rather than market appreciation alone?",
        ),
        Evidence(
            entity="ANANDRATHI", kind=EvidenceKind.POSITIVE,
            claim="Q1FY27 client attrition measured by AUM lost was 0.09%; management also reported zero regret relationship-manager attrition during the quarter.",
            source="https://bazaarwatch.com/announcement/13914/anand-rathi-wealth-limited-analysts-institutional-investor-meet-con-call-updates",
            source_tier=SourceTier.SECONDARY, published_on=date(2026, 7, 10),
            event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CUSTOMERS_SUPPLIERS, materiality="high",
            hypothesis="Is AUM growth being supported by durable client acquisition and retention rather than market appreciation alone?",
        ),
        Evidence(
            entity="ANANDRATHI", kind=EvidenceKind.NEGATIVE,
            claim="Q1FY27 net inflows were INR 2,743 crore versus INR 3,824 crore in Q1FY26, so the inflow contribution was lower year over year even as AUM increased.",
            source="https://www.venturasecurities.com/news/stocks/anand-rathi-wealth-share-price-hits-all-time-high-after-q1fy27-profit-rises-24-aum-crosses-%E2%82%B91-lakh-crore/",
            source_tier=SourceTier.SECONDARY, published_on=date(2026, 7, 10),
            event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CUSTOMERS_SUPPLIERS, materiality="high",
            hypothesis="Is AUM growth being supported by durable client acquisition and retention rather than market appreciation alone?",
        ),
        Evidence(
            entity="ANANDRATHI", kind=EvidenceKind.POSITIVE,
            claim="Q1FY27 adjusted revenue was about INR 336 crore, up 18% YoY, and adjusted PAT was about INR 116 crore, up 24% YoY; management maintained FY27 guidance of INR 1,415 crore revenue and INR 460 crore PAT.",
            # Downgraded from PRIMARY (item 19 / F1): a video platform is
            # not an independently re-checkable document.
            source="https://www.youtube.com/watch?v=EFvyPYEU13I",
            source_tier=SourceTier.SECONDARY, published_on=date(2026, 7, 10),
            event_date=date(2026, 7, 10), retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high",
            hypothesis="Can relationship-manager productivity and client growth support revenue growth without proportionate employee-cost escalation?",
            notes="Derived from the company's Q1FY27 management interview and result disclosures; underlying management source is the official Anand Rathi Wealth YouTube channel.",
        ),
        Evidence(
            entity="ANANDRATHI", kind=EvidenceKind.POSITIVE,
            claim="The company's Q1FY27 management interview states that operating leverage is expected to improve over the next two years and highlights RM capacity utilisation and new RM hiring as growth levers.",
            # Downgraded from PRIMARY (item 19 / F1): a video platform is
            # not an independently re-checkable document.
            source="https://www.youtube.com/watch?v=EFvyPYEU13I",
            source_tier=SourceTier.SECONDARY, published_on=date(2026, 7, 10),
            event_date=date(2026, 7, 10), retrieved_on=RETRIEVED,
            domain=ResearchDomain.MANAGEMENT, materiality="high",
            hypothesis="Can relationship-manager productivity and client growth support revenue growth without proportionate employee-cost escalation?",
        ),
        Evidence(
            entity="ANANDRATHI", kind=EvidenceKind.NEGATIVE,
            claim="Q1FY27 reported EBITDA margin fell to about 34% from 47% a year earlier, with employee costs rising 53% YoY; reporting included a one-time ESOP charge.",
            source="https://www.livemint.com/market/mark-to-market/anand-rathi-wealth-arwl-q1fy27-wealth-management-aum-growth-client-retention-ebitda-margin-11784011282038.html",
            source_tier=SourceTier.SECONDARY, published_on=date(2026, 7, 14),
            event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high",
            hypothesis="Can relationship-manager productivity and client growth support revenue growth without proportionate employee-cost escalation?",
        ),
        Evidence(
            entity="ANANDRATHI", kind=EvidenceKind.POSITIVE,
            claim="The board approved a proposal to apply to SEBI to act as sponsor of a mutual fund under the SEBI Mutual Funds Regulations 2026.",
            source="https://economictimes.indiatimes.com/anand-rathi-wealth-ltd./stocksupdate/companyid-2020300.cms",
            source_tier=SourceTier.SECONDARY, published_on=date(2026, 7, 9),
            event_date=date(2026, 7, 9), retrieved_on=RETRIEVED,
            domain=ResearchDomain.GOVERNMENT_REGULATION, materiality="high",
            hypothesis="Are regulatory and product changes likely to alter the economics of distribution and the proposed AMC expansion?",
        ),
        Evidence(
            entity="ANANDRATHI", kind=EvidenceKind.POSITIVE,
            claim="SEBI's Mutual Funds Regulations 2026 are the current regulatory framework for mutual funds, with the regulation page last amended on 7 July 2026.",
            source="https://www.sebi.gov.in/legal/regulations/jul-2026/securities-and-exchange-board-of-india-mutual-funds-regulations-2026-last-amended-on-july-7-2026-_102780.html",
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 7, 7),
            event_date=date(2026, 7, 7), retrieved_on=RETRIEVED,
            domain=ResearchDomain.GOVERNMENT_REGULATION, materiality="medium",
            hypothesis="Are regulatory and product changes likely to alter the economics of distribution and the proposed AMC expansion?",
        ),
        Evidence(
            entity="ANANDRATHI", kind=EvidenceKind.UNKNOWN,
            claim="The reviewed materials confirm the AMC application but do not establish the eventual approval date, product launch timing, fee structure, distribution economics or incremental profitability of the proposed AMC.",
            source="research-window: Q1FY27 company disclosures and SEBI regulation review",
            source_tier=SourceTier.DERIVED, retrieved_on=RETRIEVED,
            domain=ResearchDomain.GOVERNMENT_REGULATION, materiality="high",
            hypothesis="Are regulatory and product changes likely to alter the economics of distribution and the proposed AMC expansion?",
        ),
        Evidence(
            entity="ANANDRATHI", kind=EvidenceKind.POSITIVE,
            claim="Digital Wealth AUM reached INR 2,526 crore in Q1FY27, up 23% YoY, and the company reported that its UK subsidiary had started operations.",
            source="https://economictimes.indiatimes.com/markets/stocks/earnings/anand-rathi-wealth-q1-results-profit-rises-24-to-rs-116-crore-revenue-grows-18/articleshow/132287729.cms",
            source_tier=SourceTier.SECONDARY, published_on=date(2026, 7, 9),
            event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.TECHNOLOGY_IP, materiality="medium",
            hypothesis="Is the business sufficiently diversified across clients, products and channels to remain resilient during weak capital markets?",
        ),
        Evidence(
            entity="ANANDRATHI", kind=EvidenceKind.POSITIVE,
            claim="FY26 annual reporting shows AUM of INR 93,037 crore, 13,395 active client families and 401 relationship managers at 31 March 2026, with five-year growth across these operating metrics.",
            source="https://www.anandrathiwealth.in/wealthpdf/27april2026/AnnualReport2025-26.pdf",
            source_tier=SourceTier.PRIMARY, published_on=date(2026, 4, 27),
            event_date=date(2026, 3, 31), retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="medium",
            hypothesis="Is the business sufficiently diversified across clients, products and channels to remain resilient during weak capital markets?",
        ),
        Evidence(
            entity="ANANDRATHI", kind=EvidenceKind.NEGATIVE,
            claim="AUM growth contains a market-performance component: management stated that about 14% of Q1FY27 AUM growth came from net inflows, with the remainder supported by portfolio appreciation.",
            # Downgraded from PRIMARY (item 19 / F1): a video platform is
            # not an independently re-checkable document.
            source="https://www.youtube.com/watch?v=EFvyPYEU13I",
            source_tier=SourceTier.SECONDARY, published_on=date(2026, 7, 10),
            event_date=date(2026, 7, 10), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPITAL_MARKETS, materiality="high",
            hypothesis="Is the business sufficiently diversified across clients, products and channels to remain resilient during weak capital markets?",
        ),
        Evidence(
            entity="ANANDRATHI", kind=EvidenceKind.UNKNOWN,
            claim="The reviewed disclosures do not provide a sufficiently detailed stress test of revenue and PAT under a prolonged equity-market drawdown; market sensitivity therefore remains partly unresolved.",
            source="research-window: Q1FY27 results and annual report review",
            source_tier=SourceTier.DERIVED, retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPITAL_MARKETS, materiality="high",
            hypothesis="Is the business sufficiently diversified across clients, products and channels to remain resilient during weak capital markets?",
        ),
        Evidence(
            entity="ANANDRATHI", kind=EvidenceKind.UNKNOWN,
            claim="The reviewed Q1FY27 materials do not establish the future contribution, cost structure or return profile of the UK, digital and proposed AMC initiatives at scale.",
            source="research-window: Q1FY27 company disclosures",
            source_tier=SourceTier.DERIVED, retrieved_on=RETRIEVED,
            domain=ResearchDomain.TECHNOLOGY_IP, materiality="medium",
            hypothesis="Is the business sufficiently diversified across clients, products and channels to remain resilient during weak capital markets?",
        ),
    )


def anandrathi_packet() -> ResearchProviderPacket:
    evidence = anandrathi_evidence()
    refs = {e.claim: evidence_ref(e) for e in evidence}

    def ref(claim: str) -> str:
        try:
            return refs[claim]
        except KeyError as exc:
            raise ValueError(f"unknown evidence claim: {claim}") from exc
    return ResearchProviderPacket(
        plan=anandrathi_plan(),
        evidence=evidence,
        causal_findings=(
            CausalFinding(
                hypothesis=anandrathi_plan().hypotheses[0],
                finding="AUM growth has both flow and market-return components; client families and retention metrics provide direct evidence of platform growth, while the lower YoY net inflow base means market appreciation remains an important contributor.",
                mechanism="Net client inflows add assets directly, while portfolio appreciation raises AUM without equivalent new-client funding; revenue then depends on the monetisation of the resulting asset base.",
                timing="Quarterly and multi-year; the next earnings cycles can separate flow-led from market-led AUM growth.",
                uncertainty="The reviewed materials do not provide a full revenue sensitivity to market levels.",
                evidence_refs=(ref("As of 30 June 2026, AUM was INR 1,06,300+ crore, with 417+ relationship managers and 13,941+ clients according to the company's current website."), ref("Q1FY27 AUM rose 21% YoY to INR 1,06,300 crore and net inflows were INR 2,743 crore; active client families rose 13% YoY to 13,941."), ref("Q1FY27 client attrition measured by AUM lost was 0.09%; management also reported zero regret relationship-manager attrition during the quarter."), ref("Q1FY27 net inflows were INR 2,743 crore versus INR 3,824 crore in Q1FY26, so the inflow contribution was lower year over year even as AUM increased."), ref("FY26 annual reporting shows AUM of INR 93,037 crore, 13,395 active client families and 401 relationship managers at 31 March 2026, with five-year growth across these operating metrics."), ref("AUM growth contains a market-performance component: management stated that about 14% of Q1FY27 AUM growth came from net inflows, with the remainder supported by portfolio appreciation.")),
            ),
            CausalFinding(
                hypothesis=anandrathi_plan().hypotheses[1],
                finding="Client and RM growth create a potential operating-leverage path, but Q1 employee-cost growth shows that productivity must outrun compensation intensity for margins to expand.",
                mechanism="Revenue is linked to assets and client relationships, while a large portion of operating cost is people-driven; RM capacity utilisation and client acquisition therefore matter to incremental margins.",
                timing="Near-to-medium term, with management explicitly discussing two-year operating leverage.",
                # Loop 14 adversarial council: the FY26 growth figure cited
                # below is stated EXCLUDING ESOP expenses (an adjusted basis),
                # while the Q1FY27 margin decline cited below is a REPORTED
                # figure driven partly BY an ESOP charge -- two different
                # accounting bases juxtaposed in one finding without
                # reconciliation. Made explicit rather than left implicit.
                uncertainty="The effect of the one-time ESOP charge versus recurring employee-cost growth requires subsequent quarters to separate. Note also that the FY26 growth figure above is stated on an ex-ESOP adjusted basis while the Q1FY27 margin decline is a reported (non-adjusted) figure driven partly by an ESOP charge -- the two are not on the same accounting basis, and whether FY26 growth would look as strong stated on a reported basis, or whether Q1FY27's ESOP charge is the same or a distinct cost category from what FY26 already excluded, is not established by the reviewed materials.",
                evidence_refs=(ref("FY26 consolidated total income excluding fair-value gains, ESOP expenses and related tax effects was INR 1,198.49 crore, up 22.3% YoY; adjusted PAT was INR 385.73 crore, up 28.4%."), ref("Q1FY27 adjusted revenue was about INR 336 crore, up 18% YoY, and adjusted PAT was about INR 116 crore, up 24% YoY; management maintained FY27 guidance of INR 1,415 crore revenue and INR 460 crore PAT."), ref("The company's Q1FY27 management interview states that operating leverage is expected to improve over the next two years and highlights RM capacity utilisation and new RM hiring as growth levers."), ref("Q1FY27 reported EBITDA margin fell to about 34% from 47% a year earlier, with employee costs rising 53% YoY; reporting included a one-time ESOP charge.")),
            ),
            CausalFinding(
                hypothesis=anandrathi_plan().hypotheses[2],
                finding="The AMC initiative changes the product architecture from distribution/wealth management toward potential fund manufacturing, but economics cannot yet be established.",
                mechanism="Regulatory approval would be required before launch; product mix, fees, distribution arrangements and investment scale would determine incremental economics.",
                timing="Future and conditional; no completed AMC launch is established by the reviewed evidence.",
                uncertainty="Approval, launch timing, fee structure, AUM ramp and profitability remain unknown.",
                evidence_refs=(ref("The board approved a proposal to apply to SEBI to act as sponsor of a mutual fund under the SEBI Mutual Funds Regulations 2026."), ref("SEBI's Mutual Funds Regulations 2026 are the current regulatory framework for mutual funds, with the regulation page last amended on 7 July 2026."), ref("The reviewed materials confirm the AMC application but do not establish the eventual approval date, product launch timing, fee structure, distribution economics or incremental profitability of the proposed AMC.")),
            ),
            CausalFinding(
                hypothesis=anandrathi_plan().hypotheses[3],
                # Loop 14 adversarial council: this finding's own evidence_refs
                # (below) are AUM/inflows/channel items and two absence-of-data
                # DERIVED items -- none of them discuss retention. The actual
                # retention evidence (0.09% AUM attrition, zero regret RM
                # attrition) is real but is cited only under hypotheses[0]'s
                # finding, not here. Removed the unsupported "strong retention"
                # clause rather than let a true fact from elsewhere in the
                # packet be claimed as support for a finding that doesn't cite it.
                finding="The platform has multiple channels (Digital Wealth, UK), but AUM remains partly market-sensitive and the reviewed materials do not quantify earnings under a prolonged market decline.",
                mechanism="Portfolio appreciation affects AUM without new inflows; weak markets can reduce AUM-based revenue even if client relationships remain intact, while digital/UK channels may diversify future growth.",
                timing="Ongoing; stress becomes visible through AUM, flows and revenue across subsequent quarters.",
                uncertainty="No company-specific prolonged-bear-market sensitivity was established.",
                evidence_refs=(ref("Digital Wealth AUM reached INR 2,526 crore in Q1FY27, up 23% YoY, and the company reported that its UK subsidiary had started operations."), ref("AUM growth contains a market-performance component: management stated that about 14% of Q1FY27 AUM growth came from net inflows, with the remainder supported by portfolio appreciation."), ref("The reviewed disclosures do not provide a sufficiently detailed stress test of revenue and PAT under a prolonged equity-market drawdown; market sensitivity therefore remains partly unresolved."), ref("The reviewed Q1FY27 materials do not establish the future contribution, cost structure or return profile of the UK, digital and proposed AMC initiatives at scale.")),
            ),
        ),
        contradictions=(
            ContradictionFinding(
                hypothesis=anandrathi_plan().hypotheses[0],
                original_claim="AUM growth demonstrates durable underlying business growth.",
                counter_evidence="Only about 14% of Q1FY27 AUM growth came from net inflows according to management; the remainder was supported by portfolio appreciation, while Q1 net inflows were lower than the prior-year quarter.",
                resolution="Separate flow-led growth from market-led AUM growth; both contribute to reported AUM but have different durability implications.",
                # original_claim_refs/counter_evidence_refs (item 7): the prior
                # single evidence_refs list cited two AUM-growth items but never
                # the item that actually states the "~14%" figure this
                # counter_evidence quotes -- it was cited elsewhere (causal
                # findings 0 and 3) but not here. Added. Also dropped the
                # stress-test-derived item: it is about future bear-market
                # sensitivity, not the flow-vs-appreciation composition this
                # contradiction is actually about; it stays correctly cited on
                # hypotheses[3]'s contradiction below.
                original_claim_refs=(ref("Q1FY27 AUM rose 21% YoY to INR 1,06,300 crore and net inflows were INR 2,743 crore; active client families rose 13% YoY to 13,941."),),
                counter_evidence_refs=(ref("Q1FY27 net inflows were INR 2,743 crore versus INR 3,824 crore in Q1FY26, so the inflow contribution was lower year over year even as AUM increased."), ref("AUM growth contains a market-performance component: management stated that about 14% of Q1FY27 AUM growth came from net inflows, with the remainder supported by portfolio appreciation.")),
            ),
            ContradictionFinding(
                hypothesis=anandrathi_plan().hypotheses[1],
                original_claim="Strong client/RM growth should produce operating leverage.",
                counter_evidence="Q1 employee costs increased 53% YoY and reported EBITDA margin declined to about 34%, partly because of a one-time ESOP charge.",
                resolution="Treat operating leverage as a management hypothesis to be monitored, not as a completed outcome.",
                # item 7: the AMC board-approval ref was misattached here -- it
                # has nothing to do with RM productivity or operating leverage.
                # It belongs to (and is now cited on) the AMC contradiction below.
                original_claim_refs=(ref("The company's Q1FY27 management interview states that operating leverage is expected to improve over the next two years and highlights RM capacity utilisation and new RM hiring as growth levers."),),
                counter_evidence_refs=(ref("Q1FY27 reported EBITDA margin fell to about 34% from 47% a year earlier, with employee costs rising 53% YoY; reporting included a one-time ESOP charge."),),
            ),
            ContradictionFinding(
                hypothesis=anandrathi_plan().hypotheses[2],
                # Loop 14 adversarial council: the prior original_claim ("The
                # AMC proposal is an additional growth engine") was asserted
                # by no evidence item -- the board-approval item only states
                # that an application was approved, not that it constitutes a
                # growth engine. Rescoped the claim down to what the cited
                # evidence actually supports.
                original_claim="The board's approval to apply for AMC sponsorship signals strategic intent to expand into fund manufacturing, a new product line beyond distribution/wealth management.",
                counter_evidence="The board has only approved an application; approval, launch, fee economics and AUM scale are not established.",
                resolution="Record the AMC as a conditional strategic initiative rather than current earnings contribution.",
                # item 7: the board-approval item is the actual factual basis
                # for "the AMC is a growth engine" and belongs here, not on the
                # operating-leverage contradiction above. Dropped the SEBI
                # regulations item (generic background, not about growth-engine
                # status) and the Digital Wealth item (a different initiative)
                # -- both remain correctly cited on the AMC causal finding above.
                original_claim_refs=(ref("The board approved a proposal to apply to SEBI to act as sponsor of a mutual fund under the SEBI Mutual Funds Regulations 2026."),),
                counter_evidence_refs=(ref("The reviewed materials confirm the AMC application but do not establish the eventual approval date, product launch timing, fee structure, distribution economics or incremental profitability of the proposed AMC."),),
            ),
            ContradictionFinding(
                hypothesis=anandrathi_plan().hypotheses[3],
                original_claim="Diversification makes the platform resilient to market weakness.",
                counter_evidence="Management attributed most Q1 AUM growth to portfolio appreciation rather than net inflows, and no prolonged-market stress sensitivity was disclosed in the reviewed materials.",
                resolution="Diversification is visible in channels and client base, but market sensitivity remains an unresolved economic exposure.",
                # Loop 14 adversarial council: swapped the FY26 annual-report
                # AUM figure (already flagged 144d old against a 100d
                # half-life in this dossier's own Stale-evidence table) for
                # the fresher Q1FY27 figure covering the same channels/
                # client-base claim -- a non-stale, same-metric alternative
                # was available and already used for the identical
                # AUM-durability narrative elsewhere in this same dossier.
                original_claim_refs=(ref("Q1FY27 AUM rose 21% YoY to INR 1,06,300 crore and net inflows were INR 2,743 crore; active client families rose 13% YoY to 13,941."),),
                counter_evidence_refs=(ref("The reviewed disclosures do not provide a sufficiently detailed stress test of revenue and PAT under a prolonged equity-market drawdown; market sensitivity therefore remains partly unresolved."), ref("The reviewed Q1FY27 materials do not establish the future contribution, cost structure or return profile of the UK, digital and proposed AMC initiatives at scale."), ref("AUM growth contains a market-performance component: management stated that about 14% of Q1FY27 AUM growth came from net inflows, with the remainder supported by portfolio appreciation.")),
            ),
        ),
        unresolved_questions=(
            "What portion of future revenue growth can be generated from net inflows versus market appreciation?",
            "What is the recurring employee-cost trajectory after the one-time ESOP impact?",
            "When will the proposed AMC receive regulatory approval and launch, and what economics are expected?",
            "How sensitive are revenue and PAT to a prolonged equity-market drawdown?",
            "What steady-state economics will the UK and digital businesses contribute?",
        ),
        monitoring_questions=(
            "Track quarterly net inflows, AUM growth and the flow-versus-market contribution.",
            "Track AUM per RM, client additions, regret RM attrition and employee cost per incremental AUM.",
            "Track AMC application/approval/launch lifecycle and disclosed fee economics.",
            "Track revenue and PAT through materially different equity-market conditions.",
        ),
    )
