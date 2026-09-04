# PARESH QUANT v2 — DESIGN DECISION LOG

This file exists specifically to prevent loss of context during the long redesign.

## D-001 — Clean-room redesign
**Decision:** Rebuild the UI conceptually from scratch rather than porting existing page layouts/components.
**Reason:** The goal is a fundamentally better quantitative-terminal experience, not cosmetic modernization.
**Consequence:** Existing UI code is reference material only. Quantitative engines remain the trusted foundation.

## D-002 — Separate design and implementation branches
**Decision:** Keep visual/product specification work on `design-spec-v2` and implementation work on `redesign-v2`.
**Reason:** The design reference must remain stable while code evolves.

## D-003 — Main remains protected
**Decision:** `main` remains production until the redesign is fully validated.

## D-004 — Desktop + mobile for every page
**Decision:** Every major page gets both a desktop and mobile visual concept before implementation.

## D-005 — Light institutional design
**Decision:** Use a light visual system: white/light-gray surfaces, restrained blue accent, meaningful green/red states, strong numeric typography, clean borders/spacing, minimal noise.

## D-006 — No Rank Δ1D / Δ7D
**Decision:** Do not add daily or 7-day rank delta requirements. Existing Rank Δ1M / Δ3M can be used.

## D-007 — No invented RS metric
**Decision:** Do not display a generic `RS 92`-style metric unless a real supported calculation exists.

## D-008 — Do not resurrect removed momentum systems
**Decision:** Removed momentum-acceleration/alternative systems are not part of v2 merely to create more UI content. The current production momentum engine remains the composite foundation.

## D-009 — Mobile screener uses cards
**Decision:** Mobile screener is a ranked card/list experience rather than a compressed desktop table.

## D-010 — Native Streamlit first
**Decision:** Design for Streamlit Free using native primitives wherever possible. CSS/HTML/custom components are permitted when justified, but should not become an accidental second application framework.

## D-011 — Mockup values are illustrative
**Decision:** Values shown in design screenshots are visual placeholders unless explicitly marked as production data.

## D-012 — Design before implementation
**Decision:** Complete visual concepts and information hierarchy review before broad implementation.

## D-013 — Required states
Every major data surface must eventually define loading, empty, error, stale/data-quality warning, and normal populated states.

## D-014 — Quantitative provenance
Every important number shown in v2 must be traceable to an existing engine output or an explicit derivation documented in implementation. The UI must never create a metric merely because a card has empty space.

## D-015 — Page sequence
The design/review order is:
Screener → Stock Detail → Qualified → Markets → Industries → RRG → Portfolio → Delivery → Backtest → Watchlist → Guide → Configuration/Data Status.

## D-016 — Stock Detail evidence hierarchy
**Decision:** Stock Detail is the evidence trail behind a ranking decision.

Order:
1. identity / price / state;
2. rank / score / percentile;
3. price chart;
4. momentum returns + Sharpe;
5. trend + risk;
6. 52W high + ATH context;
7. volume + persistence;
8. ATR / Stop Loss / Chandelier Exit;
9. market / sector / industry metadata;
10. transparent setup interpretation;
11. watchlist/action controls.

Desktop may use multiple analytical columns. Mobile uses a vertically ordered research brief with progressive disclosure.

## D-017 — Stock Detail optional sections
**Decision:** Fundamentals, news, results, shareholding or peer analysis may appear in visual concepts as future/conditional sections, but are NOT approved quantitative requirements unless the current repository supplies the necessary data. They must not be fabricated during implementation.

## D-018 — No visual filler
**Decision:** Unsupported metrics are omitted rather than invented to fill UI space.

## Context preservation rule
If future work is resumed after a long gap, read:
1. `redesign/DESIGN_MASTER.md`
2. `redesign/DESIGN_DECISIONS.md`
3. `redesign/PAGE_MAP.md`

Then inspect the relevant current branch/files. Never infer forgotten design decisions from current code alone.
