# Stage 4 — Deep Company Intelligence Specification

Date: 2026-09-19
Status: REQUIRED REFINEMENT BEFORE STAGE-4 GATE

## 1. Purpose

Stage 4 is not a news collector.

Its purpose is to produce a **360-degree contextual Company Intelligence Dossier** that explains the interaction between the company, its peers, industry, sector, government/regulation, macro/geopolitics, inputs, capacity, customers/suppliers, capital structure, technology/IP, FX/trade, and market reaction.

The dossier must reduce UNKNOWNs by reviewing the underlying documents, not by generating more headlines.

## 2. Research hierarchy

For each Top-N candidate:

Quant candidate
→ Company
→ Business segments
→ Peers
→ Industry
→ Sector
→ Government/regulation
→ Macro/geopolitics
→ Inputs/commodities/energy
→ FX/tariffs/trade
→ Capacity/utilisation/capex
→ Customers/suppliers/orders
→ Financial results/guidance
→ Management commentary
→ Capital allocation/funding/shareholding
→ Technology/IP/patents
→ Market reaction
→ Contradictions
→ Unknowns / questions requiring follow-up

No single source is sufficient for the dossier.

## 3. Mandatory research domains

The domains below are a **research library, not a universal checklist**. The agent must first profile the company and select the domains that can materially affect that specific business. Irrelevant domains must be explicitly marked NOT APPLICABLE rather than researched mechanically. Material domains must have evidence or an explicit UNKNOWN explaining why no directional conclusion is established.

1. Company operations and business mix
2. Quarterly results and financial trajectory
3. Management guidance
4. Earnings-call transcript / management commentary
5. Annual report / business model / risks
6. Orders, contracts, backlog and cancellations
7. Capacity, utilisation, commissioning and capex
8. Customers and suppliers
9. Peers and competitive capacity
10. Industry-wide order flow / demand indicators
11. Sector-wide developments
12. Government policy / regulation / tenders / subsidies
13. Macro and geopolitical developments
14. Raw materials / commodities / energy / freight
15. FX exposure
16. Tariffs / duties / trade restrictions / dumping / export controls
17. Technology / patents / product launches / obsolescence
18. Acquisitions / JVs / divestments / funding / debt / rights issues
19. Promoter / institutional ownership / capital-market events
20. Litigation / regulatory / compliance
21. Market reaction and abnormal price/volume context
22. Upcoming catalysts / scheduled events
23. Contradictions between management, filings, media and industry evidence
24. Open questions / evidence needed to resolve them

## 4. Company-specific research profiling

Before collecting evidence, create a **Company Research Profile**. This is the first analytical step and determines what the agent should investigate.

The profile must identify:
- business model and revenue/profit drivers;
- major products/services and segments;
- geography and export/import exposure;
- customer type and concentration;
- supplier/input dependencies;
- capital intensity and capacity constraints;
- regulatory/licensing sensitivity;
- financing/funding model;
- competitive structure;
- technology/IP dependence;
- current quantitative signal and the factual question the research is trying to understand.

Then select **material research domains** for that company and record why each was selected. There is no requirement to research every possible domain.

### Examples of different research profiles

These are illustrative archetypes only. They are not templates that should be blindly applied.

**Bank / NBFC** may require emphasis on:
- loan growth and mix;
- NIM;
- deposit growth/cost of funds;
- CASA or funding structure where relevant;
- asset quality;
- GNPA/NNPA/slippages;
- restructuring/write-offs;
- capital adequacy;
- provisioning;
- unsecured exposure;
- liquidity;
- regulatory changes;
- credit-cycle indicators;
- competitor pricing/deposit behaviour.

A steel-price or plant-utilisation investigation may be irrelevant to a bank unless it affects a material borrower/sector exposure.

**Pharma** may require a completely different lens depending on the company:
- API company: raw-material chemistry, pricing, capacity, regulatory approvals, China exposure, backward integration;
- CDMO: customer pipeline, molecule/program wins, plant qualification, utilisation, customer concentration, development-to-commercial conversion;
- domestic branded pharma: prescription trends, therapeutic mix, price controls, doctor/channel dynamics, launches, field-force/productivity;
- U.S.-focused generic: ANDA pipeline, USFDA observations, product pricing, litigation, competition, launches and supply constraints;
- specialty/new-patent company: patent expiry/approval, exclusivity period, clinical/regulatory milestones, manufacturing scale-up and commercialisation.

These examples demonstrate why the company itself must determine the research lens.

**IT/SaaS**, **auto OEM**, **auto ancillary**, **commodity producer**, **hospital**, **consumer company**, **insurance company**, **asset manager**, **real-estate company**, etc. should each generate their own material-driver map rather than inheriting a generic checklist.

### Adaptive domain rule

For every candidate:

Company profile
→ economic drivers
→ material risks/opportunities
→ relevant research domains
→ hypotheses/questions
→ evidence collection
→ causal analysis
→ contradiction search
→ unresolved questions.

This prevents irrelevant research and reduces headline accumulation.

## 5. Analytical reasoning layer — connect the dots

Evidence collection is only the input. Stage 4 must contain a separate **analysis layer** that connects evidence to company economics.

The agent should construct explicit causal chains where evidence supports them:

**External event → transmission mechanism → company exposure → timing → financial/operational variable → management response → peer comparison → uncertainty.**

For example, instead of:

> "Copper prices increased."

The report should investigate whether:

Copper price
→ company copper intensity
→ procurement/inventory timing
→ contract pricing or pass-through
→ customer pricing
→ gross-margin exposure
→ reporting-quarter timing
→ peer exposure
→ management commentary.

Likewise, instead of:

> "U.S. tariff increased."

investigate:

Tariff
→ product classification
→ country of origin
→ company's manufacturing footprint
→ revenue exposed
→ customer responsibility
→ contract repricing/pass-through
→ competitor exposure
→ order-book exposure
→ timing.

The chain must stop where evidence stops. The missing link becomes UNKNOWN rather than invented.

### Analytical questions for every material finding

1. **What changed?**
2. **Why does it matter to this particular company?**
3. **Through what mechanism could it affect the business?**
4. **Which segment/geography/product is exposed?**
5. **When could the effect appear?**
6. **What offsets or mitigants exist?**
7. **What do peers experience?**
8. **What does management say?**
9. **What evidence contradicts the initial interpretation?**
10. **What remains unknown?**

### Hypothesis-driven research

Do not begin with a pile of searches. Begin with a small set of material questions/hypotheses derived from the company profile and quantitative context.

Example only:
- Is the current order strength company-specific or industry-wide?
- Is capacity the limiting factor rather than demand?
- Does a tariff advantage actually exist after product classification and contract terms?
- Is an apparent margin risk offset by pass-through or hedging?
- Is a new plant an earnings catalyst or simply replacement capacity?

The agent must test these hypotheses with evidence and actively seek disconfirming evidence.

## 6. Materiality and relevance gate

Every discovered item passes through three filters:

**Relevant?** Does it affect a selected company driver/domain?

**Material?** Could it plausibly affect earnings, cash flow, growth, timing, competitive position, balance-sheet risk, regulation or valuation-relevant business conditions?

**Connected?** Can the evidence be connected to a company-specific mechanism, or does it remain generic background?

Generic information can remain in the context layer, but it must not dominate the dossier.

## 7. Peer and industry analysis

Peers must not be a list of names.

For each material peer, research:

- comparable products and end markets;
- domestic vs export exposure;
- geography and manufacturing footprint;
- installed and announced capacity;
- utilisation where disclosed;
- recent orders;
- order-book direction;
- customer concentration;
- raw-material exposure;
- tariff/duty exposure;
- new plants/capacity;
- pricing behaviour;
- margin commentary;
- major wins/losses;
- shutdowns/commissioning;
- strategic announcements.

Then produce **relative context**, without scoring or ranking:

Example:
- Company has U.S. manufacturing capacity while Peer A remains India-only.
- Company has 70% export exposure while Peer B is domestically focused.
- Peer C announced a new plant that may increase competitive supply.
- Industry order flow is increasing, but company-specific order conversion remains the unresolved question.

## 8. Industry-wide order-flow layer

Search beyond the company.

Examples:
- tender awards;
- government procurement;
- project pipelines;
- customer capex;
- infrastructure awards;
- industry order-book commentary;
- import/export statistics;
- capacity additions;
- utilisation trends;
- industry pricing;
- raw-material supply.

The report must distinguish:

**Company order**

from

**industry demand**

from

**government/project pipeline**

from

**derived opportunity**.

## 9. Government and regulatory layer

Track policies that can materially affect economics:

- tariffs;
- import/export duties;
- anti-dumping;
- subsidies;
- environmental rules;
- local-content requirements;
- government funding;
- tender rules;
- tax changes;
- export restrictions;
- sanctions;
- licensing;
- sector-specific regulation.

A policy should be translated into a company-specific exposure map:

Policy
→ affected product
→ affected geography
→ company exposure
→ peer exposure
→ likely timing
→ whether pricing can be passed through
→ evidence still required.

Do not assume the economic effect.

## 10. Capacity and utilisation engine

Capacity must be tracked as a timeline:

Existing capacity
→ utilisation
→ debottlenecking
→ announced expansion
→ construction
→ commissioning
→ commercial production
→ utilisation ramp
→ order coverage.

For every material facility, record:

- location;
- product;
- capacity;
- current utilisation if disclosed;
- commissioning date;
- expansion capacity;
- capex;
- order coverage;
- constraints;
- peer comparable capacity.

This is particularly important where the company has a geographic advantage over peers.

## 11. Input-cost and margin-pressure analysis

The research system must actively search for adverse second-order effects.

Examples:

- crude oil;
- steel;
- aluminium;
- copper;
- chemicals;
- electricity;
- gas;
- freight;
- wages;
- financing costs;
- currency;
- imported components.

For each input:

Input change
→ percentage relevance if disclosed
→ affected segment
→ inventory lag
→ pricing/pass-through mechanism
→ peer exposure
→ likely reporting quarter
→ management commentary
→ unresolved evidence.

Example structure:

**Steel price rises**

→ company uses steel-intensive input

→ order pricing may or may not have escalation clause

→ gross margin exposure depends on procurement timing

→ peers may have different sourcing

→ next-quarter margin risk = UNKNOWN until contract/pricing evidence is established.

Never convert the example into a fact without company-specific evidence.

## 12. FX analysis

For export-heavy companies:

- revenue currency;
- cost currency;
- net exposure;
- hedging;
- natural hedge;
- contract currency;
- translation effects;
- sensitivity disclosed by management.

Then test scenarios qualitatively:

INR appreciation → export revenue translation / competitiveness
INR depreciation → imported input cost / export competitiveness

The report must not assume the direction without understanding the company's natural hedge.

## 13. Tariff and trade-war analysis

This is mandatory for companies with material cross-border exposure.

Track:

- current tariff;
- proposed tariff;
- effective date;
- product classification;
- country of origin;
- manufacturing location;
- exemptions;
- customer responsibility;
- pass-through clauses;
- peer manufacturing footprint.

A critical comparison can therefore be:

**Company manufactures in the U.S.**

vs

**Peer exports from India to the U.S.**

A U.S. tariff can then have asymmetric effects.

Conversely:

**Company has 75% export exposure and the U.S. becomes subject to a 100% tariff**

could materially threaten future order economics even if the order book is large.

The system must quantify only where source data permits and otherwise label the magnitude UNKNOWN.

## 14. Geopolitical analysis

Monitor events such as:

- wars;
- sanctions;
- shipping disruptions;
- Strait/Hormuz disruptions;
- regional instability;
- trade restrictions;
- energy shocks.

Map:

event
→ geography
→ company facility
→ customer geography
→ input exposure
→ logistics route
→ revenue exposure
→ competitor exposure
→ potential positive/negative/unknown channels.

A geopolitical event must never be treated as automatically positive or negative.

## 15. Management consistency analysis

Every earnings cycle should compare current management commentary with prior commentary.

Track changes in:

- guidance;
- demand;
- utilisation;
- margins;
- capex;
- capacity timing;
- order pipeline;
- working capital;
- customer concentration;
- pricing;
- risks.

Flag:

- guidance raised;
- guidance maintained;
- guidance reduced;
- assumption changed;
- previous expectation delayed;
- previous concern resolved;
- previous concern worsened.

This is one of the highest-value parts of Company Intelligence.

## 16. Event lifecycle

Do not treat every announcement as a completed event.

Track:

MOU
→ agreement
→ approval
→ funding
→ construction
→ commissioning
→ commercial production
→ customer order
→ execution
→ revenue.

Likewise:

proposal
→ announced transaction
→ conditional approval
→ completion
→ cancellation.

The current state must be explicit.

## 17. Contradiction engine

For every major thesis, actively search for opposing evidence.

Examples:

- record order book vs capacity constraint;
- high utilisation vs announced expansion;
- strong EBITDA vs input inflation;
- strong exports vs tariff exposure;
- new plant vs weak industry demand;
- management optimism vs lower guidance;
- large order vs customer funding problems;
- peer capacity addition vs company pricing power;
- government project announcement vs actual tender award.

Contradictions are first-class output, not footnotes.

## 18. Research value test

A finding is high-value when it does at least one of:

- changes understanding of future earnings;
- changes timing of expected earnings;
- identifies a second-order risk;
- reveals a competitive advantage/disadvantage;
- explains a market move;
- detects management expectation change;
- links industry data to company exposure;
- resolves a previous UNKNOWN;
- creates a specific question worth monitoring.

Routine announcements should be retained in the evidence log but compressed in the final dossier.

## 19. Final dossier structure

Each company report should contain:

1. Quantitative identity
2. Executive intelligence summary
3. Business and segment map
4. Financial trajectory
5. Orders/backlog
6. Capacity/utilisation/capex
7. Management commentary and guidance
8. Management consistency tracker
9. Peer comparison
10. Industry order-flow and demand
11. Sector context
12. Government/regulatory environment
13. Inputs/commodities/energy
14. FX
15. Tariffs/trade
16. Geopolitics
17. Customers/suppliers
18. Technology/IP
19. Capital allocation/funding/shareholding
20. Litigation/regulatory
21. Market reaction
22. Contradiction map
23. Positive evidence
24. Negative evidence
25. Unknowns and research questions
26. Upcoming events
27. Evidence quality / source coverage
28. Change log versus previous report

## 20. No recommendation

The dossier must not produce:

- buy/sell/hold;
- best/worst;
- qualitative investment score;
- target price;
- probability of success;
- directional ranking.

It provides evidence and context for human interpretation.

## 21. Research coverage metrics

Track:

- primary-source coverage;
- underlying-document review rate;
- evidence count by domain;
- domain coverage;
- unresolved UNKNOWN count;
- UNKNOWNs resolved since previous report;
- contradictions found;
- management statements compared;
- peer coverage;
- industry-source coverage;
- stale evidence;
- duplicate evidence;
- factual corrections.

The objective is not to maximise evidence count. It is to maximise **decision-relevant information density**.

## 22. Stage-4 gate

Stage 4 cannot close until at least one complete company dossier demonstrates the above workflow end-to-end.

WELCORP is the acceptance sample.

The first basic Top-25 report is therefore retained as an intermediate artifact, not the final Stage-4 deliverable.


## 23. Non-news-report acceptance test

A Stage-4 dossier fails the gate if it can be reduced to a chronological list of announcements with little company-specific reasoning.

The minimum analytical chain is:

**evidence → relevance → company exposure → mechanism → timing → offset/mitigant → peer/industry comparison where relevant → contradiction → uncertainty → monitoring question.**

Not every chain will reach a conclusion. A correctly bounded UNKNOWN is preferable to a plausible but unsupported narrative.

The WELCORP document is an **illustration of analytical structure only**, not a universal research template. The acceptance test for another company must be generated from that company's own profile and economic drivers.