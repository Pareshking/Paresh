# PARESH QUANT v2 — MASTER DESIGN SPECIFICATION

**Status:** DESIGN / PRE-IMPLEMENTATION
**Design branch:** `design-spec-v2`
**Implementation branch:** `redesign-v2`
**Production branch:** `main` (untouched)
**Date established:** 2026-09-04

---

## 1. Why this document exists

This document is the anti-drift contract for the PARESH QUANT redesign.

The redesign is intentionally a clean-room product exercise. We are not taking the existing UI and progressively decorating it. We are rethinking the application from first principles while preserving the existing quantitative intelligence as the trusted calculation foundation.

Before implementation, every major page will have a desktop and mobile visual concept. Those concepts will be challenged, revised, and then treated as the visual/information-architecture reference for implementation.

If implementation later becomes inconvenient, we do **not** silently change the product design to fit old code. We first determine whether the limitation is real, whether Streamlit Free supports an equivalent, and whether the design can be implemented with native Streamlit plus controlled CSS/HTML/components. Any material change is recorded here or in the decision log.

---

## 2. Product vision

PARESH QUANT should feel like a professional quantitative equity research terminal that happens to run on Streamlit.

It should not feel like:

- a collection of Streamlit widgets;
- a collection of decorative KPI cards;
- a desktop dashboard squeezed onto a phone;
- a visual rewrite that changes quantitative meaning;
- a UI constrained by legacy component structure.

The experience should make the user answer three questions quickly:

1. **What is the market doing?**
2. **Which stocks currently deserve attention?**
3. **Why does a particular stock deserve attention, and what is its risk state?**

---

## 3. Non-negotiable design principles

### 3.1 Quantitative truth first
Existing production quantitative calculations remain authoritative unless a new value is a transparent derivation from existing data/calculations.

### 3.2 No invented metrics
A label must never imply a calculation that does not exist.

Examples of acceptable derived presentation:
- score percentile derived from the existing score cross-section;
- setup labels derived from existing signals using documented rules;
- counts derived from existing stock-level states;
- market summaries derived from existing breadth/price states.

Examples deliberately excluded:
- Rank Δ1D;
- Rank Δ7D;
- an invented proprietary RS score;
- resurrecting the removed momentum-acceleration system merely to populate a card.

### 3.3 Clean-room UI
The old UI is reference material only. Existing layout, CSS, components, page composition, navigation, and visual patterns do not receive automatic preservation rights.

### 3.4 Light institutional visual language
Default visual direction:
- white/light-gray workspace;
- restrained blue primary accent;
- green/red only for meaningful state;
- high legibility;
- strong numeric hierarchy;
- compact but not cramped data density;
- minimal decorative gradients/shadows;
- UI typography separated from quantitative/numeric typography.

### 3.5 Mobile is a first-class product
Mobile is not a desktop layout with smaller columns.

Desktop optimizes for comparison and information density.
Mobile optimizes for scanning, prioritization, touch interaction, and progressive disclosure.

### 3.6 Streamlit Free is a hard deployment constraint
The design must be implementable on the actual Streamlit Free deployment model.

Preferred hierarchy:
1. native Streamlit primitives;
2. CSS for visual/responsive behavior;
3. `st.html`/controlled HTML where it materially improves the experience;
4. existing compatible chart libraries;
5. custom components only where necessary.

Do not create a design that fundamentally depends on a separate SPA backend, paid infrastructure, persistent websocket architecture outside Streamlit, or native-mobile capabilities that Streamlit cannot provide.

### 3.7 Progressive disclosure
Do not show every available number at once.

Use:
- Summary for discovery;
- Standard for research;
- Full Quant for deep inspection;
- Stock Detail for the complete evidence trail.

### 3.8 Tables remain first-class
The screener and analytical ranking surfaces should use tables where comparison benefits from tables. Cards are for summaries and mobile scanning, not a replacement for every data grid.

---

## 4. Responsive product model

### Desktop
- full application shell;
- market context strip;
- broad filters;
- dense quantitative table;
- optional secondary market/sector rail;
- detailed stock workspace.

### Tablet
- reduced table columns;
- stacked analytical sections;
- collapsible/overlay secondary controls;
- fewer simultaneous visual elements.

### Mobile
- compact top header;
- market summary;
- search;
- filter chips + dedicated filter workspace;
- ranked stock cards;
- focused stock detail;
- touch-friendly actions;
- bottom navigation where appropriate.

Never rely on horizontal scrolling as the primary way to use the mobile product.

---

## 5. Master navigation / page sequence

The design sequence is fixed unless explicitly changed:

1. **Screener**
2. **Stock Detail**
3. **Qualified**
4. **Markets**
5. **Industries**
6. **RRG**
7. **Portfolio**
8. **Delivery**
9. **Backtest**
10. **Watchlist**
11. **Guide / Methodology**
12. **Configuration / Data Status**

Every page gets:
- desktop concept;
- mobile concept;
- information hierarchy review;
- quantitative field mapping;
- interaction review;
- Streamlit feasibility review;
- final design status.

---

## 6. Shared application shell

The shared shell is not yet code-frozen, but the direction is:

### Header
- PARESH QUANT brand;
- concise terminal descriptor;
- primary navigation;
- search/command entry;
- contextual user actions where required.

### Market context
A compact market intelligence layer should make the application feel live and contextual without consuming excessive vertical space.

Possible elements, only when backed by existing calculations/data:
- market regime/state;
- index value/change where already available;
- breadth;
- stocks above 50 EMA;
- 52W high/low counts;
- data freshness.

### Page header
Every major page should explain:
- what this page is for;
- current universe/context;
- relevant as-of date/freshness.

### Content
Use a predictable rhythm:
`Context → Controls → Primary analysis → Secondary evidence → Drill-down`.

---

## 7. Screener — design target

### Desktop
Primary discovery surface.

Expected hierarchy:
1. market context;
2. search;
3. universe/filter presets;
4. screener toolbar;
5. primary ranking table;
6. compact market pulse / secondary intelligence;
7. pagination/data status;
8. stock drill-down.

Potential table information:
- rank;
- stock identity;
- price;
- composite score;
- score percentile;
- Rank Δ1M / Δ3M;
- 1M/3M/6M/9M/12M returns and/or Sharpe depending on density mode;
- 52W high distance;
- 50 EMA distance/state;
- volume signal;
- setup/state derived from existing signals;
- risk levels where useful.

### Mobile
Use ranked cards rather than the desktop table.

A mobile stock card should prioritize:
- rank;
- symbol/name/industry;
- price and daily price change if available;
- score + percentile;
- setup/state;
- 1M/3M/6M/12M momentum summary;
- 52W high distance;
- 50 EMA state;
- one clear drill-down affordance.

### Filters
Filters should become a focused mobile workspace/overlay rather than a huge permanent control wall.

---

## 8. Stock Detail — design target

The stock detail view is the evidence page behind every ranking decision.

Expected hierarchy:

1. identity / price / state;
2. rank and score;
3. price chart;
4. momentum returns and Sharpe;
5. trend and risk;
6. 52W/ATH context;
7. volume/persistence;
8. stop loss / Chandelier / ATR;
9. market/sector/industry metadata;
10. transparent setup interpretation;
11. watchlist/action controls.

Desktop can use multiple analytical columns/rails. Mobile becomes a vertically ordered research brief.

---

## 9. Qualified

Purpose: reduce the universe to stocks meeting the application's qualification criteria.

The page should answer:
- how many qualify;
- what criteria are active;
- which stocks qualify;
- how strong/risky each candidate is;
- what changed in the actionable subset using only supported metrics.

Avoid duplicating the Screener unnecessarily. Qualified should have a stronger decision/action orientation.

---

## 10. Markets

Markets consolidates market-state information that should not be scattered across pages.

Potential sections:
- market regime;
- breadth;
- participation;
- 52W high/low context;
- index/market state;
- market-level trend interpretation.

The page must distinguish observed data from derived interpretation.

---

## 11. Industries

Purpose: understand where momentum is concentrated.

Desktop:
- industry ranking;
- performance distribution;
- breadth/participation;
- top/bottom industries;
- constituent drill-down.

Mobile:
- ranked industry cards;
- compact participation/performance metrics;
- tap-through to constituents.

No new external industry-relative model should be introduced merely to make the page look richer.

---

## 12. RRG

Purpose: visualize relative rotation using the application's existing supported RRG calculations/data.

Desktop should prioritize the visualization and readable quadrant context.
Mobile should prioritize:
- simplified plot;
- quadrant filters/toggles;
- ranked lists of movers/leaders where supported;
- easy constituent drill-down.

Do not manufacture unsupported RS metrics just to imitate a generic RRG product.

---

## 13. Portfolio

Purpose: turn quantitative selection into a portfolio-level view.

Expected hierarchy:
- portfolio summary;
- performance;
- risk;
- holdings;
- weights;
- position-level risk/exit information;
- drill-down to stock detail.

Mobile should put portfolio health and holdings ahead of secondary analytics.

---

## 14. Delivery

Purpose: expose delivery/accumulation information already supported by the project.

The design should connect delivery signals to price, momentum, and stock identity rather than presenting delivery as an isolated spreadsheet.

Avoid adding unsupported delivery-derived metrics during the visual redesign phase.

---

## 15. Backtest

Purpose: research and validate the quantitative process.

Desktop hierarchy:
- configuration;
- headline performance;
- equity curve;
- drawdown;
- key statistics;
- trade/portfolio details;
- walk-forward results where already supported.

Mobile should prioritize headline performance, equity curve, drawdown, and key statistics before detailed tables.

Backtest is research UI, not an execution UI.

---

## 16. Watchlist

Purpose: personal monitoring of selected stocks.

Should be intentionally lighter than the Screener while retaining the same visual language.

Prioritize:
- stock identity;
- current rank/score;
- momentum state;
- trend/risk state;
- actionable changes supported by current data;
- direct stock detail.

---

## 17. Guide / Methodology

This is part of the product, not an afterthought.

It should explain:
- what the momentum engine does;
- the five calendar lookback windows;
- return and Sharpe interpretation;
- winsorization/z-scoring where relevant;
- composite score/rank meaning;
- risk metrics;
- qualification logic;
- data-quality flags;
- terminology/glossary.

The guide should make the terminal auditable to a sophisticated user.

---

## 18. Configuration / Data Status

Purpose: operational transparency.

Potential sections:
- system status;
- data freshness;
- source status;
- coverage;
- configuration;
- universe settings;
- data-quality diagnostics;
- gap/fill information.

Do not bury important data-quality warnings in decorative UI.

---

## 19. Quantitative source of truth

The current production momentum engine is the calculation boundary.

Known supported areas include:
- composite Rank / momentum score;
- 1M / 3M / 6M / 9M / 12M returns;
- 1M / 3M / 6M / 9M / 12M Sharpe;
- maximum drawdown for each window;
- 50 EMA and distance/above-EMA state;
- 52W high, high date, distance from high, near-high state;
- ATH and distance from ATH;
- ATR;
- Stop Loss;
- Chandelier Exit;
- 6M persistence;
- volume ratio/status;
- market-cap/data-quality fields;
- industry/sector/index membership;
- qualification-related signals;
- existing breadth/RRG/portfolio/backtest/delivery calculations where already supported by their respective engines.

The current engine explicitly describes itself as the single production momentum core. Alternative momentum systems that were removed should not be resurrected merely for UI variety.

---

## 20. Explicit exclusions

The following are not redesign requirements:

- Rank Δ1D;
- Rank Δ7D;
- unsupported proprietary RS score;
- a separate momentum acceleration model that is not part of the current production composite;
- external research dependencies purely for visual enrichment;
- fake live values in design mockups presented as production data.

Mockup numbers are illustrative only.

---

## 21. Design review checklist for every page

Before a page is marked frozen:

- [ ] Desktop screenshot created.
- [ ] Mobile screenshot created.
- [ ] Tablet behavior considered.
- [ ] Primary user question identified.
- [ ] Information hierarchy challenged.
- [ ] Every displayed quantitative field mapped to an existing calculation or transparent derivation.
- [ ] Unsupported metrics removed.
- [ ] Interaction model checked against Streamlit Free.
- [ ] Empty/loading/error states designed.
- [ ] Data freshness state designed.
- [ ] Accessibility/readability reviewed.
- [ ] Navigation/drill-down path reviewed.
- [ ] Visual consistency with frozen design system checked.
- [ ] Decision recorded in the design log.

---

## 22. Implementation rule

Only after the visual concepts and page architecture are sufficiently frozen should implementation begin.

Implementation should be a reconstruction of the approved product design, not an exploration disguised as coding.

When implementation exposes a limitation:

1. identify the exact limitation;
2. check whether native Streamlit provides an equivalent;
3. check whether controlled CSS/HTML/component implementation solves it;
4. if the design must change, record the change and reason;
5. never silently substitute a legacy UI pattern just because it already exists.

---

## 23. Current status

**Phase:** Visual product design

**Current page:** Screener

**Completed concept work:**
- desktop screener concept;
- mobile screener/filter/stock-detail concept;
- initial all-pages design portfolio concept.

**Next:**
- challenge and freeze Screener;
- create dedicated Stock Detail desktop/mobile concept;
- continue through the master page sequence.

**No production UI replacement has been merged to `main`.**
