"""Acceptance research packet for the consumer D2C-retail-archetype adaptive execution.

Company: LENSKART (Lenskart Solutions Limited, formerly Lenskart Solutions Private
Limited; CIN U33100DL2008PLC178355) -- confirmed via its own SEBI-mandated Q1 FY27
financial-results filing.
Archetype: technology-led, vertically-integrated omnichannel eyewear D2C retailer,
combining owned/JV manufacturing, an India + international store network, and a
digital-to-store customer-acquisition funnel.
Snapshot cutoff: 2026-09-18
Retrieved: 2026-09-19

This packet demonstrates that a consumer D2C retail brand selects a different
research lens from an industrial exporter (SANSERA), a wealth-management platform
(ANANDRATHI), a fintech platform (PAYTM) or a hospital operator (YATHARTH): the
material economic drivers here are store-network expansion and densification,
same-store/same-pincode sales growth, average-selling-price/premiumization mix,
vertically-integrated manufacturing margin under currency pressure, digital-to-
offline conversion, and post-IPO capital allocation -- not loan books, AUM,
order-book conversion, or bed occupancy.

Sources actually fetched and read for this packet (2026-09-19):
- Lenskart's own Q1 FY27 Shareholders' Letter (assets.lenskart.com, dated 12 Aug 2026)
- Lenskart's own SEBI Regulation-33 Q1 FY27 financial-results filing with the
  independent auditor's review report (assets.lenskart.com, dated 12 Aug 2026)
- Motilal Oswal Financial Services' "Lenskart Solutions -- Clear vision, strong
  execution" initiating-coverage report (hosted on bsmedia.business-standard.com;
  PDF creation metadata 19 Feb 2026, independently confirmed as publicly covered by
  news on 20-23 Feb 2026)
- tradebrains.in, "Lenskart Is Having A 'Yuan' Problem Instead Of A 'Dollar'
  Problem" (4 Sep 2026)
- chaiandcharts.substack.com, "In the Hare and Tortoise Battle for the Eyewear
  Market" (28 Feb 2026)
- kotakneo.com, "Lenskart Shares Surge 98% From Listing-Day Low As Stock Hits New
  High" (18 Sep 2026)
- rupeezy.in, "Is Lenskart Solutions IPO Good or Bad -- Detailed Review" (last
  updated 7 Sep 2026)
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

H1 = (
    "Is India store network expansion, particularly Tier 2+ and pin-code "
    "densification, generating incremental same-store and same-pin-code sales "
    "growth rather than cannibalizing existing stores, and is backend "
    "manufacturing/eye-testing capacity keeping pace with that growth?"
)
H2 = (
    "Is Lenskart's vertically-integrated, in-house frame and lens manufacturing "
    "structurally offsetting INR/RMB currency depreciation and China import "
    "dependency, or does product-margin durability remain exposed to further "
    "currency and supply-chain risk?"
)
H3 = (
    "Can premiumization (Owndays, Rodenstock/Tokai, rising ASP) and mass-market "
    "volume expansion (Hustlr Club, sub-Rs.500 pairs) both scale together without "
    "one undermining the other's economics, and can adjacent bets such as B by "
    "Lenskart smart glasses become a genuine incremental profit contributor?"
)
H4 = (
    "Is customer acquisition being achieved efficiently through the digital-to-"
    "store eye-test funnel, Gold membership and organic/word-of-mouth demand "
    "rather than escalating paid-marketing intensity, and is this durable as "
    "store expansion accelerates into Tier 2+ towns?"
)
H5 = (
    "Is the International segment's (Japan/Owndays, Southeast Asia, Middle East) "
    "improving profitability a structural, durable improvement, or does it still "
    "rest on scale/currency tailwinds alongside loss-making overseas "
    "subsidiaries?"
)
H6 = (
    "Does post-IPO capital allocation (net cash deployment into Hyderabad "
    "manufacturing and store capex, and the Dealskart/Lenskart Eyetech merger "
    "scheme) support the growth plan and the market's post-listing re-rating "
    "without unresolved legal/regulatory overhangs such as the pending FEMA "
    "inquiry and franchise litigation?"
)

SHAREHOLDERS_LETTER_Q1FY27 = (
    "https://assets.lenskart.com/documents/2026/08/12/LenskartShareholdersLetterQ1FY27.pdf"
)
FINANCIAL_RESULTS_Q1FY27 = "https://assets.lenskart.com/documents/2026/08/12/FinancialResults.pdf"
MOTILAL_OSWAL_INITIATION = (
    "https://bsmedia.business-standard.com/_media/bs/data/market-reports/"
    "equity-brokertips/2026-02/17715807930.19335400.pdf"
)
TRADEBRAINS_YUAN_PROBLEM = (
    "https://tradebrains.in/indian-markets/"
    "lenskart-is-having-a-yuan-problem-instead-of-a-dollar-problem-12492880"
)
CHAI_AND_CHARTS_TITAN = "https://chaiandcharts.substack.com/p/lenskart-vs-titan-eyecare-who-is"
KOTAK_NEO_SHARE_PRICE = (
    "https://www.kotakneo.com/news/stocks/lenskart-stock-rises-98-percent-from-listing-day-low/"
)
RUPEEZY_IPO_REVIEW = "https://rupeezy.in/blog/is-lenskart-solutions-ipo-good-or-bad"


def lenskart_plan() -> ResearchPlan:
    return ResearchPlan(
        symbol="LENSKART",
        company_archetype=(
            "technology-led, vertically-integrated omnichannel eyewear D2C retailer "
            "combining owned/JV manufacturing (Bhiwadi, Gurugram, an upcoming "
            "Hyderabad facility, and a China frame-manufacturing JV), an India + "
            "international (Japan/Owndays, Southeast Asia, Middle East) store "
            "network, and a digital-to-store eye-test customer-acquisition funnel"
        ),
        economic_drivers=(
            "India store-network expansion and pin-code/Tier 2+ densification",
            "same-store sales growth (SSSG) and same-pincode sales growth (SPSG)",
            "average selling price / premiumization mix versus mass-market volume",
            "vertically-integrated/private-label manufacturing margin under "
            "INR-RMB currency and China-import-dependency pressure",
            "digital-to-offline conversion of the eye-test funnel and loyalty "
            "(Gold membership) retention economics",
            "International segment (Japan/Owndays, Southeast Asia, Middle East) "
            "scale and profitability",
            "post-IPO capital allocation, balance-sheet capacity and ROCE "
            "trajectory",
        ),
        material_domains=(
            ResearchDomain.FINANCIALS,
            ResearchDomain.CUSTOMERS_SUPPLIERS,
            ResearchDomain.CAPACITY,
            ResearchDomain.FX,
            ResearchDomain.PEERS,
            ResearchDomain.INDUSTRY,
            ResearchDomain.CAPITAL_MARKETS,
            ResearchDomain.LEGAL_COMPLIANCE,
            ResearchDomain.MARKET_REACTION,
            ResearchDomain.TECHNOLOGY_IP,
        ),
        hypotheses=(H1, H2, H3, H4, H5, H6),
        exclusions=(
            "bank-style loan-book, NIM, GNPA/NNPA or capital-adequacy analysis, "
            "because Lenskart is a retail/manufacturing D2C company, not a "
            "lending institution",
            "store-level or machine-level unit-economics modelling beyond what "
            "management and independent brokerages have themselves disclosed "
            "(e.g. a full store-by-store P&L or machine-by-machine plant "
            "scheduling), which this research does not attempt to reconstruct",
            "target prices and valuation recommendations -- this research cites "
            "brokerage risk/moat analysis but does not adopt any brokerage's "
            "target-price scenario (INR600/735/395) as its own view",
            "qualitative investment scoring",
            "recalculation of System-1 ranking or momentum",
            "country-by-country regulatory analysis of every international "
            "market Lenskart operates in (Japan, Singapore, Thailand, UAE, Saudi "
            "Arabia, etc.) beyond the two India-linked items that are actually "
            "material and sourced here (the FEMA/ED inquiry and China sourcing "
            "exposure)",
        ),
    )


def lenskart_evidence() -> tuple[Evidence, ...]:
    return (
        # ---------------------------------------------------------------- FINANCIALS
        Evidence(
            entity="LENSKART", kind=EvidenceKind.POSITIVE,
            claim="Q1 FY27 (quarter ended 30 June 2026) reported consolidated revenue from operations was INR 2,714.18 crore, versus INR 1,894.46 crore a year earlier, and consolidated PAT attributable to owners of the company was INR 221.84 crore, versus INR 60.08 crore; on a proforma basis (per the IPO prospectus, adjusting for in-period M&A including Dealskart, GeoIQ and Meller), management stated revenue grew 33.6% YoY, EBITDA (pre-IndAS 116) grew 95.0%, PAT grew 2.8x to INR 228 crore, and consolidated product margin crossed 70% for the first time (70.3% versus 68.7% a year earlier).",
            source=FINANCIAL_RESULTS_Q1FY27, source_tier=SourceTier.PRIMARY,
            published_on=date(2026, 8, 12), event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high", hypothesis=H6,
        ),
        Evidence(
            entity="LENSKART", kind=EvidenceKind.POSITIVE,
            claim="Q1 FY27 segment revenue was INR 1,530.82 crore for India and INR 1,203.29 crore for International (reported basis); on a proforma basis management reported India grew 30.7% YoY and International grew 38.0% YoY, with segment profit-before-tax of INR 183.28 crore for India and INR 103.67 crore for International.",
            source=FINANCIAL_RESULTS_Q1FY27, source_tier=SourceTier.PRIMARY,
            published_on=date(2026, 8, 12), event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high", hypothesis=H5,
        ),
        Evidence(
            entity="LENSKART", kind=EvidenceKind.NEGATIVE,
            claim="A February 2026 brokerage analysis found FY25 net losses at several overseas subsidiaries -- INR 615 million at Lenskart Solutions Pte. Ltd. (Singapore), INR 489 million at Lenskart Arabia Limited (Saudi Arabia), and INR 98 million at Owndays Co., Ltd. (Japan) -- stating these loss-making entities required ongoing funding from the parent and diluted consolidated profitability.",
            source=MOTILAL_OSWAL_INITIATION, source_tier=SourceTier.SECONDARY,
            # Independently confirmed public by 20-23 Feb 2026 news coverage of
            # this same Motilal Oswal report (businesstoday.in/topnews.in), even
            # though the PDF's own creation metadata reads 19 Feb 2026.
            published_on=date(2026, 2, 20), event_date=date(2025, 3, 31), retrieved_on=RETRIEVED,
            domain=ResearchDomain.FINANCIALS, materiality="high", hypothesis=H5,
        ),
        # ------------------------------------------------------ CUSTOMERS_SUPPLIERS
        Evidence(
            entity="LENSKART", kind=EvidenceKind.POSITIVE,
            claim="India delivered same-store sales growth (SSSG) of 18.3% in Q1 FY27 across Metro, Tier 1 and Tier 2+ markets, while same-pincode sales growth (SPSG) reached 24.3% -- run consistently ahead of SSSG -- and in the 1,517 pin codes that already had a Lenskart store nine months earlier, density rose from 1.5 to 1.6 stores per pin code, with Bengaluru (189 stores, 13 net additions in nine months) posting ~20% SSSG over the same window.",
            source=SHAREHOLDERS_LETTER_Q1FY27, source_tier=SourceTier.PRIMARY,
            published_on=date(2026, 8, 12), event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CUSTOMERS_SUPPLIERS, materiality="high", hypothesis=H1,
        ),
        Evidence(
            entity="LENSKART", kind=EvidenceKind.POSITIVE,
            claim="Lenskart added 132 net new stores in Q1 FY27 (versus 83 in Q1 FY26), taking total active stores to 3,459; India added 116 net new stores (83 in Tier 2+ towns) while entering 50 new cities, and International added 16 net new stores (718 to 734).",
            source=SHAREHOLDERS_LETTER_Q1FY27, source_tier=SourceTier.PRIMARY,
            published_on=date(2026, 8, 12), event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CUSTOMERS_SUPPLIERS, materiality="high", hypothesis=H1,
        ),
        Evidence(
            entity="LENSKART", kind=EvidenceKind.POSITIVE,
            claim="0.7 crore eye tests were conducted in Q1 FY27 (+39.8% YoY), India eyewear unit volumes grew 22.8% YoY to 82 lakh units, digitally-influenced sales rose to about 55% of India revenue (up from about 41% a year earlier), and cumulative app downloads crossed 12 crore (from 10 crore a year earlier).",
            source=SHAREHOLDERS_LETTER_Q1FY27, source_tier=SourceTier.PRIMARY,
            published_on=date(2026, 8, 12), event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CUSTOMERS_SUPPLIERS, materiality="high", hypothesis=H4,
        ),
        Evidence(
            entity="LENSKART", kind=EvidenceKind.POSITIVE,
            claim="Lenskart Gold active members reached 93.5 lakh in Q1 FY27 (up from 71.2 lakh a year earlier, +31.3% YoY) with quarterly Gold subscription fees of INR 66 crore (+57.4% YoY); Quarterly Transacting Customer Accounts grew 18.5% YoY to 44 lakh; India NPS was 77.6 (a minor dip from FY26's 79.8); and marketing expense fell to 4.8% of India revenue in Q1 FY27 from 5.7% in Q1 FY26, which management attributed to quality-led word of mouth as the primary acquisition engine.",
            source=SHAREHOLDERS_LETTER_Q1FY27, source_tier=SourceTier.PRIMARY,
            published_on=date(2026, 8, 12), event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CUSTOMERS_SUPPLIERS, materiality="high", hypothesis=H4,
        ),
        Evidence(
            entity="LENSKART", kind=EvidenceKind.POSITIVE,
            claim="India ASP grew 6.4% YoY to INR 1,856 in Q1 FY27 on premiumization of mix; Owndays premium lenses now generate over INR 1,500 crore annually in prescription-eyeglass sales, Rodenstock and Tokai luxury lenses generated about INR 250 crore last year with combined volumes up over 35% YoY, while at the mass end the Hustlr Club's sub-INR-500 frames-and-lenses pair reached its largest-ever customer cohort in the quarter, which management described as now sold profitably after multiple prior attempts.",
            source=SHAREHOLDERS_LETTER_Q1FY27, source_tier=SourceTier.PRIMARY,
            published_on=date(2026, 8, 12), event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CUSTOMERS_SUPPLIERS, materiality="high", hypothesis=H3,
        ),
        # ------------------------------------------------------------------ CAPACITY
        Evidence(
            entity="LENSKART", kind=EvidenceKind.NEGATIVE,
            claim="Manufacturing-facility capacity utilization remained low across FY23-1QFY26 -- Gurugram at 52.3% (FY23), 40.9% (FY25) and 39.2% (1QFY26); Bhiwadi at 20.0% (FY23), 54.3% (FY25) and 68.3% (1QFY26) -- which a February 2026 brokerage report characterized as indicating under-absorption of fixed costs and a historical drag on RoCE.",
            source=MOTILAL_OSWAL_INITIATION, source_tier=SourceTier.SECONDARY,
            published_on=date(2026, 2, 20), event_date=date(2025, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="high", hypothesis=H1,
        ),
        Evidence(
            entity="LENSKART", kind=EvidenceKind.POSITIVE,
            claim="In-house frame production grew from 4.4 million (FY23) to 6.4 million (FY25) to 1.9 million in 1QFY26 alone, and in-house lens production from 2.1 million to 4.1 million to 1.3 million over the same points, which a brokerage estimated cut material costs by 35-40% versus third-party procurement; the upcoming Hyderabad facility is designed as a ~50-million-pair export-oriented manufacturing hub, and Q1 FY27 plant capex of INR 132 crore was directed largely toward it.",
            source=MOTILAL_OSWAL_INITIATION, source_tier=SourceTier.SECONDARY,
            published_on=date(2026, 2, 20), event_date=date(2025, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="high", hypothesis=H2,
        ),
        Evidence(
            entity="LENSKART", kind=EvidenceKind.NEGATIVE,
            claim="Owned manufacturing production remains geographically concentrated in Gurugram (Haryana) and Bhiwadi (Rajasthan) -- 93%/6% of production in FY23 shifting to about 32%/67% by 1QFY26, with Singapore/Dubai contributing only ~1-2% -- creating single-region dependency; the company is building a larger Hyderabad unit specifically to diversify this regional concentration.",
            source=MOTILAL_OSWAL_INITIATION, source_tier=SourceTier.SECONDARY,
            published_on=date(2026, 2, 20), event_date=date(2025, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPACITY, materiality="medium", hypothesis=H1,
        ),
        # ------------------------------------------------------------------------ FX
        Evidence(
            entity="LENSKART", kind=EvidenceKind.NEGATIVE,
            claim="The Rupee depreciated against the Chinese Yuan (RMB), moving from around 11 to 14, pressuring frame-procurement costs since a meaningful share of frames is sourced from China; CEO Peyush Bansal was quoted saying structural margin improvements were being offset by currency movements, and management cautioned that short-term headwinds could remain if currencies worsen further, even though consolidated product margin still reached a record 70.3% in Q1 FY27.",
            source=TRADEBRAINS_YUAN_PROBLEM, source_tier=SourceTier.SECONDARY,
            published_on=date(2026, 9, 4), event_date=date(2026, 9, 4), retrieved_on=RETRIEVED,
            domain=ResearchDomain.FX, materiality="high", hypothesis=H2,
        ),
        Evidence(
            entity="LENSKART", kind=EvidenceKind.NEGATIVE,
            claim="About 42% of FY25 total purchases (INR 10,624 million of INR 25,168 million) were imported from China, produced in part via a China-based frame-manufacturing JV; a February 2026 brokerage report found earnings and net worth showed high sensitivity to forex movements -- including OCI translation swings -- despite the company's partial hedging.",
            source=MOTILAL_OSWAL_INITIATION, source_tier=SourceTier.SECONDARY,
            published_on=date(2026, 2, 20), event_date=date(2025, 3, 31), retrieved_on=RETRIEVED,
            domain=ResearchDomain.FX, materiality="medium", hypothesis=H2,
        ),
        Evidence(
            entity="LENSKART", kind=EvidenceKind.UNKNOWN,
            claim="The reviewed materials do not provide a constant-currency or fully hedged sensitivity of consolidated product margin to further INR depreciation against the RMB beyond qualitative management commentary that short-term headwinds could persist.",
            source="research-window: Q1FY27 shareholders' letter, financial results and brokerage review",
            source_tier=SourceTier.DERIVED, retrieved_on=RETRIEVED,
            domain=ResearchDomain.FX, materiality="medium", hypothesis=H2,
        ),
        # --------------------------------------------------------------------- PEERS
        Evidence(
            entity="LENSKART", kind=EvidenceKind.POSITIVE,
            claim="Lenskart generates roughly 7x the revenue of Titan Eye+ and operates roughly 3x the store count, while eyewear represents under 1.5% of Titan's consolidated revenue (versus 90-92% from jewellery), reflecting a scale and management-attention gap versus its largest organized domestic competitor.",
            source=CHAI_AND_CHARTS_TITAN, source_tier=SourceTier.SECONDARY,
            published_on=date(2026, 2, 28), event_date=date(2025, 3, 31), retrieved_on=RETRIEVED,
            domain=ResearchDomain.PEERS, materiality="medium", hypothesis=H1,
        ),
        # ------------------------------------------------------------------ INDUSTRY
        Evidence(
            entity="LENSKART", kind=EvidenceKind.NEGATIVE,
            claim="Organized retail's share of India's eyewear industry rose only about 200bps to roughly 24% over FY20-25 despite a roughly 15% CAGR in organized-industry size, indicating that the large majority of the industry (about three-quarters) remains fragmented and unorganized.",
            source=MOTILAL_OSWAL_INITIATION, source_tier=SourceTier.SECONDARY,
            published_on=date(2026, 2, 20), event_date=date(2025, 3, 31), retrieved_on=RETRIEVED,
            domain=ResearchDomain.INDUSTRY, materiality="medium", hypothesis=H1,
        ),
        Evidence(
            entity="LENSKART", kind=EvidenceKind.POSITIVE,
            claim="Lenskart's addressable total addressable market across its existing geographies (India, Japan, Southeast Asia, Middle East) was estimated at about INR 2.3 trillion, while the company's own market share stood at only about 5% in India and about 1.8% in international markets, indicating substantial headroom before saturation.",
            source=MOTILAL_OSWAL_INITIATION, source_tier=SourceTier.SECONDARY,
            published_on=date(2026, 2, 20), event_date=date(2025, 3, 31), retrieved_on=RETRIEVED,
            domain=ResearchDomain.INDUSTRY, materiality="medium", hypothesis=H1,
        ),
        # ---------------------------------------------------------- CAPITAL_MARKETS
        Evidence(
            entity="LENSKART", kind=EvidenceKind.POSITIVE,
            claim="Lenskart completed an IPO of 181,058,478 equity shares (53,495,905 fresh issue plus 127,562,573 offer-for-sale) aggregating INR 7,278.02 crore, and was listed on NSE and BSE on 10 November 2025; of the fresh-issue proceeds, INR 363.77 crore had been utilised towards the stated objects of the offer by 30 June 2026, with the remainder temporarily invested in fixed deposits.",
            source=FINANCIAL_RESULTS_Q1FY27, source_tier=SourceTier.PRIMARY,
            published_on=date(2026, 8, 12), event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPITAL_MARKETS, materiality="high", hypothesis=H6,
        ),
        Evidence(
            entity="LENSKART", kind=EvidenceKind.POSITIVE,
            claim="Return on Capital Employed improved to 23.2% in Q1 FY27 from 14.6% for full-year FY26; net cash excluding IPO-related payables stood at INR 4,104 crore at Q1 FY27-end; and Q1 FY27 operating cash flow of INR 297 crore (82% of pre-IndAS 116 EBITDA of INR 361 crore) exceeded total capex of INR 207 crore (INR 75 crore stores, INR 132 crore plant/Hyderabad), leaving positive net cash flow pre-M&A/equity of INR 116 crore.",
            source=SHAREHOLDERS_LETTER_Q1FY27, source_tier=SourceTier.PRIMARY,
            published_on=date(2026, 8, 12), event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPITAL_MARKETS, materiality="high", hypothesis=H6,
        ),
        Evidence(
            entity="LENSKART", kind=EvidenceKind.POSITIVE,
            claim="The Board of Directors, at its meeting on 2 July 2026, approved a scheme merging wholly-owned subsidiaries Dealskart Online Services Private Limited and Lenskart Eyetech Private Limited into Lenskart Solutions Limited, subject to shareholder, creditor and NCLT approval; no effect of the proposed merger had been given in the Q1 FY27 results, and the company was in the process of filing the approved scheme with the NCLT.",
            source=FINANCIAL_RESULTS_Q1FY27, source_tier=SourceTier.PRIMARY,
            published_on=date(2026, 8, 12), event_date=date(2026, 7, 2), retrieved_on=RETRIEVED,
            domain=ResearchDomain.CAPITAL_MARKETS, materiality="medium", hypothesis=H6,
        ),
        # --------------------------------------------------------- LEGAL_COMPLIANCE
        Evidence(
            entity="LENSKART", kind=EvidenceKind.NEGATIVE,
            claim="Lenskart is subject to an ongoing Enforcement Directorate inquiry under FEMA related to procedural delays in import/export filings; a September 2026 independent review states the outcome has included denial of a No-Objection Certificate for Overseas Direct Investment, which it flags as a challenge to further international expansion.",
            source=RUPEEZY_IPO_REVIEW, source_tier=SourceTier.SECONDARY,
            published_on=date(2026, 9, 7), event_date=date(2026, 9, 7), retrieved_on=RETRIEVED,
            domain=ResearchDomain.LEGAL_COMPLIANCE, materiality="high", hypothesis=H6,
        ),
        Evidence(
            entity="LENSKART", kind=EvidenceKind.NEGATIVE,
            claim="Lenskart's franchise (FoFo) stores retain limited store-level operational control, and a February 2026 brokerage report noted that franchisees have in the past filed litigation alleging point-of-sale data manipulation, raising concerns about revenue transparency, inventory discipline and brand consistency, even as the company shifts toward a Company-Owned-Company-Operated model.",
            source=MOTILAL_OSWAL_INITIATION, source_tier=SourceTier.SECONDARY,
            published_on=date(2026, 2, 20), event_date=date(2025, 3, 31), retrieved_on=RETRIEVED,
            domain=ResearchDomain.LEGAL_COMPLIANCE, materiality="medium", hypothesis=H6,
        ),
        Evidence(
            entity="LENSKART", kind=EvidenceKind.UNKNOWN,
            claim="The reviewed materials do not establish the outcome, timeline, or any quantified financial or operational impact of either the pending Enforcement Directorate FEMA inquiry or the franchise point-of-sale-data-manipulation litigation.",
            source="research-window: Q1FY27 disclosures and independent-review search",
            source_tier=SourceTier.DERIVED, retrieved_on=RETRIEVED,
            domain=ResearchDomain.LEGAL_COMPLIANCE, materiality="high", hypothesis=H6,
        ),
        # ----------------------------------------------------------- MARKET_REACTION
        Evidence(
            entity="LENSKART", kind=EvidenceKind.POSITIVE,
            claim="Lenskart shares traded around INR 695.55 on 18 September 2026 -- about 73% above the INR 402 IPO price and about 98% above the INR 355.70 listing-day low -- with brokerages continuing to highlight the company's store-network growth and manufacturing integration.",
            source=KOTAK_NEO_SHARE_PRICE, source_tier=SourceTier.SECONDARY,
            published_on=date(2026, 9, 18), event_date=date(2026, 9, 18), retrieved_on=RETRIEVED,
            domain=ResearchDomain.MARKET_REACTION, materiality="high", hypothesis=H6,
        ),
        # ------------------------------------------------------------- TECHNOLOGY_IP
        Evidence(
            entity="LENSKART", kind=EvidenceKind.POSITIVE,
            claim="B by Lenskart smart glasses (priced at INR 22,000, with photo/video capture and Google Gemini integration) crossed 80,000+ sign-ups in Q1 FY27, more than double the over-30,000 reported the prior quarter, and the company began shipping to customers; a self-eye-test also entered pilot stores this quarter.",
            source=SHAREHOLDERS_LETTER_Q1FY27, source_tier=SourceTier.PRIMARY,
            published_on=date(2026, 8, 12), event_date=date(2026, 6, 30), retrieved_on=RETRIEVED,
            domain=ResearchDomain.TECHNOLOGY_IP, materiality="medium", hypothesis=H3,
        ),
        Evidence(
            entity="LENSKART", kind=EvidenceKind.UNKNOWN,
            claim="The reviewed materials do not establish B by Lenskart's or the self-eye-test pilot's unit economics, revenue contribution, or profitability; both remain early-stage initiatives without disclosed standalone financials.",
            source="research-window: Q1FY27 shareholders' letter review",
            source_tier=SourceTier.DERIVED, retrieved_on=RETRIEVED,
            domain=ResearchDomain.TECHNOLOGY_IP, materiality="medium", hypothesis=H3,
        ),
    )


def lenskart_packet() -> ResearchProviderPacket:
    evidence = lenskart_evidence()
    refs = {e.claim: evidence_ref(e) for e in evidence}

    def ref(claim: str) -> str:
        try:
            return refs[claim]
        except KeyError as exc:
            raise ValueError(f"unknown evidence claim: {claim}") from exc

    return ResearchProviderPacket(
        plan=lenskart_plan(),
        evidence=evidence,
        causal_findings=(
            CausalFinding(
                hypothesis=H1,
                finding="Store-network growth is currently demand-accretive rather than cannibalistic -- SPSG has run consistently above SSSG and existing pin codes kept densifying -- but the network is scaling into a market where organized retail still holds only ~24% share and Lenskart's own manufacturing facilities have historically run at well under full utilization, so backend capacity is not yet the binding constraint even as store count grows.",
                mechanism="GeoIQ-driven site selection identifies whitespace pin codes; new stores add eye-test volume in adjacent catchments without measurably slowing existing stores' growth (SPSG >= SSSG); demand converted at the store level is then fed by centralized, historically under-utilized manufacturing capacity, with Hyderabad added as a second large node.",
                timing="Densification data covers the nine months to Q1 FY27; capacity utilization data covers FY23 through 1QFY26.",
                uncertainty="Whether SPSG will keep leading SSSG as densification continues past 1.6 stores/pin code, and whether capacity utilization has meaningfully changed since 1QFY26, are not established by the reviewed materials.",
                evidence_refs=(
                    ref("India delivered same-store sales growth (SSSG) of 18.3% in Q1 FY27 across Metro, Tier 1 and Tier 2+ markets, while same-pincode sales growth (SPSG) reached 24.3% -- run consistently ahead of SSSG -- and in the 1,517 pin codes that already had a Lenskart store nine months earlier, density rose from 1.5 to 1.6 stores per pin code, with Bengaluru (189 stores, 13 net additions in nine months) posting ~20% SSSG over the same window."),
                    ref("Lenskart added 132 net new stores in Q1 FY27 (versus 83 in Q1 FY26), taking total active stores to 3,459; India added 116 net new stores (83 in Tier 2+ towns) while entering 50 new cities, and International added 16 net new stores (718 to 734)."),
                    ref("Manufacturing-facility capacity utilization remained low across FY23-1QFY26 -- Gurugram at 52.3% (FY23), 40.9% (FY25) and 39.2% (1QFY26); Bhiwadi at 20.0% (FY23), 54.3% (FY25) and 68.3% (1QFY26) -- which a February 2026 brokerage report characterized as indicating under-absorption of fixed costs and a historical drag on RoCE."),
                    ref("Owned manufacturing production remains geographically concentrated in Gurugram (Haryana) and Bhiwadi (Rajasthan) -- 93%/6% of production in FY23 shifting to about 32%/67% by 1QFY26, with Singapore/Dubai contributing only ~1-2% -- creating single-region dependency; the company is building a larger Hyderabad unit specifically to diversify this regional concentration."),
                    ref("Organized retail's share of India's eyewear industry rose only about 200bps to roughly 24% over FY20-25 despite a roughly 15% CAGR in organized-industry size, indicating that the large majority of the industry (about three-quarters) remains fragmented and unorganized."),
                    ref("Lenskart's addressable total addressable market across its existing geographies (India, Japan, Southeast Asia, Middle East) was estimated at about INR 2.3 trillion, while the company's own market share stood at only about 5% in India and about 1.8% in international markets, indicating substantial headroom before saturation."),
                    ref("Lenskart generates roughly 7x the revenue of Titan Eye+ and operates roughly 3x the store count, while eyewear represents under 1.5% of Titan's consolidated revenue (versus 90-92% from jewellery), reflecting a scale and management-attention gap versus its largest organized domestic competitor."),
                ),
            ),
            CausalFinding(
                hypothesis=H2,
                finding="Rising in-house frame and lens production is a genuine, growing structural offset to import-cost and currency pressure, but it has not fully neutralized the INR-RMB move, and China import dependency (~42% of FY25 purchases) keeps a meaningful share of cost base exposed until Hyderabad and further backward integration scale up.",
                mechanism="In-house manufacturing substitutes China-sourced/third-party frames and lenses at 35-40% lower material cost and full control over volumes and mix; as its share of total volume rises (helped by Hyderabad), pass-through of RMB depreciation into product margin should shrink, but the substitution is gradual and the company still imports a large share of frames.",
                timing="Already partly visible in Q1 FY27 (record 70.3% product margin despite currency depreciation); the more complete structural shift is contingent on Hyderabad ramping over the next several years.",
                uncertainty="Management's own caution that short-term headwinds could persist if currencies worsen further, and the absence of a disclosed constant-currency/hedged sensitivity, mean the durability of this offset under a sharper RMB move is not established.",
                evidence_refs=(
                    ref("In-house frame production grew from 4.4 million (FY23) to 6.4 million (FY25) to 1.9 million in 1QFY26 alone, and in-house lens production from 2.1 million to 4.1 million to 1.3 million over the same points, which a brokerage estimated cut material costs by 35-40% versus third-party procurement; the upcoming Hyderabad facility is designed as a ~50-million-pair export-oriented manufacturing hub, and Q1 FY27 plant capex of INR 132 crore was directed largely toward it."),
                    ref("The Rupee depreciated against the Chinese Yuan (RMB), moving from around 11 to 14, pressuring frame-procurement costs since a meaningful share of frames is sourced from China; CEO Peyush Bansal was quoted saying structural margin improvements were being offset by currency movements, and management cautioned that short-term headwinds could remain if currencies worsen further, even though consolidated product margin still reached a record 70.3% in Q1 FY27."),
                    ref("About 42% of FY25 total purchases (INR 10,624 million of INR 25,168 million) were imported from China, produced in part via a China-based frame-manufacturing JV; a February 2026 brokerage report found earnings and net worth showed high sensitivity to forex movements -- including OCI translation swings -- despite the company's partial hedging."),
                    ref("The reviewed materials do not provide a constant-currency or fully hedged sensitivity of consolidated product margin to further INR depreciation against the RMB beyond qualitative management commentary that short-term headwinds could persist."),
                ),
            ),
            CausalFinding(
                hypothesis=H3,
                finding="Premiumization (Owndays/Rodenstock/Tokai lenses, rising ASP) and mass-market volume expansion (Hustlr Club) are currently scaling together rather than trading off, each drawing on a different part of the same customer base created by the eye-test funnel; adjacent bets like B by Lenskart are still too early to judge as profit contributors.",
                mechanism="The eye-test funnel converts first-time customers across income levels; premium lens brands monetise willingness-to-pay at the top of that funnel while Hustlr Club converts price-sensitive first-time buyers at the bottom, and management states it has only recently made the low-end pair profitable rather than loss-leading.",
                timing="Already visible in Q1 FY27 reported figures; B by Lenskart's sign-up growth is a leading indicator, not yet a revenue-scale outcome.",
                uncertainty="No standalone unit economics are disclosed for B by Lenskart or the self-eye-test pilot, and it is not established whether Hustlr Club's low-price segment is margin-accretive at true full cost once store staffing/logistics are allocated.",
                evidence_refs=(
                    ref("India ASP grew 6.4% YoY to INR 1,856 in Q1 FY27 on premiumization of mix; Owndays premium lenses now generate over INR 1,500 crore annually in prescription-eyeglass sales, Rodenstock and Tokai luxury lenses generated about INR 250 crore last year with combined volumes up over 35% YoY, while at the mass end the Hustlr Club's sub-INR-500 frames-and-lenses pair reached its largest-ever customer cohort in the quarter, which management described as now sold profitably after multiple prior attempts."),
                    ref("B by Lenskart smart glasses (priced at INR 22,000, with photo/video capture and Google Gemini integration) crossed 80,000+ sign-ups in Q1 FY27, more than double the over-30,000 reported the prior quarter, and the company began shipping to customers; a self-eye-test also entered pilot stores this quarter."),
                    ref("The reviewed materials do not establish B by Lenskart's or the self-eye-test pilot's unit economics, revenue contribution, or profitability; both remain early-stage initiatives without disclosed standalone financials."),
                ),
            ),
            CausalFinding(
                hypothesis=H4,
                finding="Customer acquisition in Q1 FY27 leaned more on the organic digital/eye-test funnel and loyalty retention than on paid marketing -- marketing fell as a share of India revenue even as digitally-influenced sales and Gold membership both grew -- but new Tier 2+ stores are staffed ahead of their revenue ramp, a cost the current marketing-efficiency trend does not capture.",
                mechanism="Eye tests (increasingly remote/self-service) create first-time customers; digital channels (app, digitally-influenced sales) increasingly originate the journey; Gold membership then converts and retains those customers into recurring purchases, reducing reliance on paid acquisition spend even as the store base expands.",
                timing="Q1 FY27 shows the pattern; durability depends on whether it holds as the incremental store mix shifts further into smaller, less brand-aware Tier 2+ towns.",
                uncertainty="It is not established whether the marketing-efficiency trend can continue once Lenskart is opening stores in towns (per the letter's own examples) where the brand has no prior digital footprint to draw on.",
                evidence_refs=(
                    ref("0.7 crore eye tests were conducted in Q1 FY27 (+39.8% YoY), India eyewear unit volumes grew 22.8% YoY to 82 lakh units, digitally-influenced sales rose to about 55% of India revenue (up from about 41% a year earlier), and cumulative app downloads crossed 12 crore (from 10 crore a year earlier)."),
                    ref("Lenskart Gold active members reached 93.5 lakh in Q1 FY27 (up from 71.2 lakh a year earlier, +31.3% YoY) with quarterly Gold subscription fees of INR 66 crore (+57.4% YoY); Quarterly Transacting Customer Accounts grew 18.5% YoY to 44 lakh; India NPS was 77.6 (a minor dip from FY26's 79.8); and marketing expense fell to 4.8% of India revenue in Q1 FY27 from 5.7% in Q1 FY26, which management attributed to quality-led word of mouth as the primary acquisition engine."),
                ),
            ),
            CausalFinding(
                hypothesis=H5,
                finding="International segment margin improvement is real and driven by both scale and structurally higher product margin from Owndays/Meller integration, but it coexists with several loss-making overseas subsidiaries that still require parent funding, so segment-level profitability is not yet uniform across every geography.",
                mechanism="International ASP runs roughly 3x India's while ACP runs roughly 2x, structurally lifting product margin as revenue scales; fixed employee and marketing costs in more mature markets (Japan, Southeast Asia) get diluted by growth, while newer/smaller entities (Singapore, Saudi Arabia) have not yet crossed into profitability.",
                timing="Segment margin expansion is already visible in Q1 FY27; subsidiary-level losses are FY25 figures and their current trajectory is not established by the reviewed materials.",
                uncertainty="Whether the specific loss-making subsidiaries (Singapore, Saudi Arabia) have narrowed losses since FY25, and how much of the segment-level margin gain is currency-tailwind versus structural, are not established.",
                evidence_refs=(
                    ref("Q1 FY27 segment revenue was INR 1,530.82 crore for India and INR 1,203.29 crore for International (reported basis); on a proforma basis management reported India grew 30.7% YoY and International grew 38.0% YoY, with segment profit-before-tax of INR 183.28 crore for India and INR 103.67 crore for International."),
                    ref("A February 2026 brokerage analysis found FY25 net losses at several overseas subsidiaries -- INR 615 million at Lenskart Solutions Pte. Ltd. (Singapore), INR 489 million at Lenskart Arabia Limited (Saudi Arabia), and INR 98 million at Owndays Co., Ltd. (Japan) -- stating these loss-making entities required ongoing funding from the parent and diluted consolidated profitability."),
                ),
            ),
            CausalFinding(
                hypothesis=H6,
                finding="Post-IPO capital allocation is currently supporting the growth plan -- strong reported revenue/PAT growth and record product margin, rising ROCE, positive net cash flow after capex, a large net-cash balance funded in part by the November 2025 IPO, and a corporate-simplification merger scheme -- and the market has re-rated the stock well above its IPO price, but two unresolved legal/regulatory items (the FEMA/ED inquiry and franchise litigation) sit alongside that re-rating without a quantified resolution.",
                mechanism="IPO proceeds and operating cash flow fund store and plant capex while remaining net-cash positive; the merger scheme simplifies the corporate structure ahead of further scaling; the market's response (share-price re-rating) reflects the combination of reported growth and capital discipline, but that re-rating does not itself resolve pending regulatory/legal matters.",
                timing="Capital-allocation metrics and the merger scheme are current as of Q1 FY27 (quarter ended 30 June 2026, board approvals in July-August 2026); the FEMA inquiry and franchise litigation are open-ended as of the most recent independent review (7 September 2026).",
                uncertainty="Neither the NCLT/shareholder timeline for the merger nor the outcome, timeline, or financial exposure of the FEMA inquiry or franchise litigation is established by the reviewed materials.",
                evidence_refs=(
                    ref("Q1 FY27 (quarter ended 30 June 2026) reported consolidated revenue from operations was INR 2,714.18 crore, versus INR 1,894.46 crore a year earlier, and consolidated PAT attributable to owners of the company was INR 221.84 crore, versus INR 60.08 crore; on a proforma basis (per the IPO prospectus, adjusting for in-period M&A including Dealskart, GeoIQ and Meller), management stated revenue grew 33.6% YoY, EBITDA (pre-IndAS 116) grew 95.0%, PAT grew 2.8x to INR 228 crore, and consolidated product margin crossed 70% for the first time (70.3% versus 68.7% a year earlier)."),
                    ref("Lenskart completed an IPO of 181,058,478 equity shares (53,495,905 fresh issue plus 127,562,573 offer-for-sale) aggregating INR 7,278.02 crore, and was listed on NSE and BSE on 10 November 2025; of the fresh-issue proceeds, INR 363.77 crore had been utilised towards the stated objects of the offer by 30 June 2026, with the remainder temporarily invested in fixed deposits."),
                    ref("Return on Capital Employed improved to 23.2% in Q1 FY27 from 14.6% for full-year FY26; net cash excluding IPO-related payables stood at INR 4,104 crore at Q1 FY27-end; and Q1 FY27 operating cash flow of INR 297 crore (82% of pre-IndAS 116 EBITDA of INR 361 crore) exceeded total capex of INR 207 crore (INR 75 crore stores, INR 132 crore plant/Hyderabad), leaving positive net cash flow pre-M&A/equity of INR 116 crore."),
                    ref("The Board of Directors, at its meeting on 2 July 2026, approved a scheme merging wholly-owned subsidiaries Dealskart Online Services Private Limited and Lenskart Eyetech Private Limited into Lenskart Solutions Limited, subject to shareholder, creditor and NCLT approval; no effect of the proposed merger had been given in the Q1 FY27 results, and the company was in the process of filing the approved scheme with the NCLT."),
                    ref("Lenskart shares traded around INR 695.55 on 18 September 2026 -- about 73% above the INR 402 IPO price and about 98% above the INR 355.70 listing-day low -- with brokerages continuing to highlight the company's store-network growth and manufacturing integration."),
                    ref("Lenskart is subject to an ongoing Enforcement Directorate inquiry under FEMA related to procedural delays in import/export filings; a September 2026 independent review states the outcome has included denial of a No-Objection Certificate for Overseas Direct Investment, which it flags as a challenge to further international expansion."),
                    ref("The reviewed materials do not establish the outcome, timeline, or any quantified financial or operational impact of either the pending Enforcement Directorate FEMA inquiry or the franchise point-of-sale-data-manipulation litigation."),
                ),
            ),
        ),
        contradictions=(
            ContradictionFinding(
                hypothesis=H1,
                original_claim="Store densification and network growth are capital-efficient: SPSG has run ahead of SSSG, stores pay back quickly, and ROCE has expanded sharply through disciplined capital allocation.",
                counter_evidence="An independent brokerage found manufacturing-facility capacity utilization remained low across FY23-1QFY26 (e.g. Gurugram 36.9-52.3%, Bhiwadi 20.0-68.3%), indicating historical under-absorption of fixed costs and a drag on RoCE even as the store network scaled.",
                resolution="Store-level economics and centralized manufacturing utilization are two different capital bases; store growth being demand-accretive (SPSG >= SSSG) does not by itself establish that the manufacturing asset base backing it has been used efficiently -- both should be tracked separately.",
                original_claim_refs=(
                    ref("India delivered same-store sales growth (SSSG) of 18.3% in Q1 FY27 across Metro, Tier 1 and Tier 2+ markets, while same-pincode sales growth (SPSG) reached 24.3% -- run consistently ahead of SSSG -- and in the 1,517 pin codes that already had a Lenskart store nine months earlier, density rose from 1.5 to 1.6 stores per pin code, with Bengaluru (189 stores, 13 net additions in nine months) posting ~20% SSSG over the same window."),
                ),
                counter_evidence_refs=(
                    ref("Manufacturing-facility capacity utilization remained low across FY23-1QFY26 -- Gurugram at 52.3% (FY23), 40.9% (FY25) and 39.2% (1QFY26); Bhiwadi at 20.0% (FY23), 54.3% (FY25) and 68.3% (1QFY26) -- which a February 2026 brokerage report characterized as indicating under-absorption of fixed costs and a historical drag on RoCE."),
                ),
            ),
            ContradictionFinding(
                hypothesis=H2,
                original_claim="In-house frame and lens manufacturing is a structural, long-term offset that is durably reducing Lenskart's exposure to INR/RMB currency depreciation.",
                counter_evidence="Independent reporting found the RMB moved sharply against the Rupee, management itself cautioned that short-term headwinds could remain if currencies worsen further, and a brokerage found earnings/net worth remained highly sensitive to forex movements despite only partial hedging, with ~42% of FY25 purchases still imported from China.",
                resolution="In-house manufacturing is a real and growing offset (rising in-house frame/lens volumes, falling material cost), but it has not yet eliminated currency exposure -- the two facts are not in tension so much as describing a gradual, incomplete transition that should be tracked via product margin under future currency moves.",
                original_claim_refs=(
                    ref("In-house frame production grew from 4.4 million (FY23) to 6.4 million (FY25) to 1.9 million in 1QFY26 alone, and in-house lens production from 2.1 million to 4.1 million to 1.3 million over the same points, which a brokerage estimated cut material costs by 35-40% versus third-party procurement; the upcoming Hyderabad facility is designed as a ~50-million-pair export-oriented manufacturing hub, and Q1 FY27 plant capex of INR 132 crore was directed largely toward it."),
                ),
                counter_evidence_refs=(
                    ref("The Rupee depreciated against the Chinese Yuan (RMB), moving from around 11 to 14, pressuring frame-procurement costs since a meaningful share of frames is sourced from China; CEO Peyush Bansal was quoted saying structural margin improvements were being offset by currency movements, and management cautioned that short-term headwinds could remain if currencies worsen further, even though consolidated product margin still reached a record 70.3% in Q1 FY27."),
                    ref("About 42% of FY25 total purchases (INR 10,624 million of INR 25,168 million) were imported from China, produced in part via a China-based frame-manufacturing JV; a February 2026 brokerage report found earnings and net worth showed high sensitivity to forex movements -- including OCI translation swings -- despite the company's partial hedging."),
                ),
            ),
            ContradictionFinding(
                hypothesis=H5,
                original_claim="International segment profitability is now structurally improving, with EBITDA (pre-IndAS 116) margin nearly tripling year-on-year, driven by scale and product-margin expansion from Owndays/Meller integration.",
                counter_evidence="A February 2026 brokerage analysis found FY25 net losses at several overseas subsidiaries -- Singapore, Saudi Arabia and Japan/Owndays -- that required ongoing funding from the parent and diluted consolidated profitability.",
                resolution="Segment-level aggregation can mask entity-level losses; International's blended margin improvement is consistent with some large, mature entities (e.g. Japan at the group level) improving sharply while smaller or newer entities remain loss-making -- both should be tracked, not netted into a single narrative.",
                original_claim_refs=(
                    ref("Q1 FY27 segment revenue was INR 1,530.82 crore for India and INR 1,203.29 crore for International (reported basis); on a proforma basis management reported India grew 30.7% YoY and International grew 38.0% YoY, with segment profit-before-tax of INR 183.28 crore for India and INR 103.67 crore for International."),
                ),
                counter_evidence_refs=(
                    ref("A February 2026 brokerage analysis found FY25 net losses at several overseas subsidiaries -- INR 615 million at Lenskart Solutions Pte. Ltd. (Singapore), INR 489 million at Lenskart Arabia Limited (Saudi Arabia), and INR 98 million at Owndays Co., Ltd. (Japan) -- stating these loss-making entities required ongoing funding from the parent and diluted consolidated profitability."),
                ),
            ),
            ContradictionFinding(
                hypothesis=H6,
                original_claim="Post-IPO capital allocation and corporate simplification (rising ROCE, a large net-cash balance, the Dealskart/Lenskart Eyetech merger scheme) support a clean growth-funding structure, reflected in the stock trading about 73% above its IPO price by 18 September 2026.",
                counter_evidence="Over the same period, two unresolved legal/regulatory items -- an Enforcement Directorate FEMA inquiry that has already led to denial of an ODI No-Objection Certificate, and franchise litigation alleging POS data manipulation -- sit outside the reported cash/ROCE metrics and are not reflected in them.",
                resolution="The market's re-rating and the reported capital-allocation metrics describe realized financial performance; the FEMA inquiry and franchise litigation describe unresolved regulatory/legal exposure that has not yet been quantified in the financials -- both should be monitored as distinct, unreconciled facts rather than assuming one implies the other is immaterial.",
                original_claim_refs=(
                    ref("Return on Capital Employed improved to 23.2% in Q1 FY27 from 14.6% for full-year FY26; net cash excluding IPO-related payables stood at INR 4,104 crore at Q1 FY27-end; and Q1 FY27 operating cash flow of INR 297 crore (82% of pre-IndAS 116 EBITDA of INR 361 crore) exceeded total capex of INR 207 crore (INR 75 crore stores, INR 132 crore plant/Hyderabad), leaving positive net cash flow pre-M&A/equity of INR 116 crore."),
                    ref("Lenskart shares traded around INR 695.55 on 18 September 2026 -- about 73% above the INR 402 IPO price and about 98% above the INR 355.70 listing-day low -- with brokerages continuing to highlight the company's store-network growth and manufacturing integration."),
                ),
                counter_evidence_refs=(
                    ref("Lenskart is subject to an ongoing Enforcement Directorate inquiry under FEMA related to procedural delays in import/export filings; a September 2026 independent review states the outcome has included denial of a No-Objection Certificate for Overseas Direct Investment, which it flags as a challenge to further international expansion."),
                    ref("Lenskart's franchise (FoFo) stores retain limited store-level operational control, and a February 2026 brokerage report noted that franchisees have in the past filed litigation alleging point-of-sale data manipulation, raising concerns about revenue transparency, inventory discipline and brand consistency, even as the company shifts toward a Company-Owned-Company-Operated model."),
                ),
            ),
        ),
        unresolved_questions=(
            "What is Lenskart's manufacturing-facility capacity utilization since 1QFY26, now that Q1 FY27 plant capex has stepped up toward Hyderabad?",
            "What outcome, timeline and financial/operational impact will the pending Enforcement Directorate FEMA inquiry and the franchise POS-data-manipulation litigation ultimately have?",
            "What incremental revenue and profitability will B by Lenskart smart glasses and the self-eye-test pilot contribute once out of early-stage rollout?",
            "What would International segment EBITDA margin look like on a constant-currency basis, and have the FY25 loss-making overseas subsidiaries (Singapore, Saudi Arabia) narrowed losses since?",
            "Will marketing efficiency (falling as a share of India revenue) hold as store expansion moves further into Tier 2+ towns with less pre-existing brand awareness?",
            "When will the Dealskart/Lenskart Eyetech merger scheme receive NCLT and shareholder/creditor approval, and will it change reported segment or consolidated financials?",
        ),
        monitoring_questions=(
            "Track SSSG versus SPSG each quarter as densification continues past 1.6 stores per pin code.",
            "Track manufacturing capacity utilization by facility, especially the Hyderabad ramp, against store-network and volume growth.",
            "Track China import dependency (% of purchases), INR-RMB movement, and consolidated/India/International product margin.",
            "Track FY25 loss-making overseas subsidiaries' (Singapore, Saudi Arabia, Japan) subsequent-year P&L for narrowing or widening losses.",
            "Track resolution of the FEMA/ED inquiry and franchise litigation, and any quantified financial exposure disclosed.",
            "Track marketing expense as a share of revenue and Gold membership growth as the store mix shifts further into Tier 2+ towns.",
        ),
    )
