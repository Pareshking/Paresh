# PARESH QUANT v2 — DESIGN DECISION LOG

This file exists specifically to prevent loss of context during the long redesign.

## D-001 — Clean-room redesign
**Decision:** Rebuild the UI conceptually from scratch rather than porting existing page layouts/components.

**Reason:** The goal is a fundamentally better quantitative-terminal experience, not cosmetic modernization.

**Consequence:** Existing UI code is reference material only. Quantitative engines remain the trusted foundation.

---

## D-002 — Separate design and implementation branches
**Decision:** Keep visual/product specification work on `design-spec-v2` and implementation work on `redesign-v2`.

**Reason:** The design reference must remain stable while code evolves.

**Consequence:** Do not use implementation convenience to rewrite the approved design without documenting the change.

---

## D-003 — Main remains protected
**Decision:** `main` remains production until the redesign is fully validated.

**Reason:** The redesign is intentionally high-scope and should not destabilize the working application.

---

## D-004 — Desktop + mobile for every page
**Decision:** Every major page gets both a desktop and mobile visual concept before implementation.

**Reason:** Mobile is a first-class use case and cannot be safely inferred from desktop.

---

## D-005 — Light institutional design
**Decision:** Use a light visual system as the default.

Direction:
- white/light-gray surfaces;
- restrained blue accent;
- green/red state colors only where meaningful;
- strong numeric typography;
- clean borders and spacing;
- minimal visual noise.

---

## D-006 — No Rank Δ1D / Δ7D
**Decision:** Do not add daily or 7-day rank delta requirements.

**Reason:** These require historical rank snapshots and are not necessary for the redesign. Existing Rank Δ1M / Δ3M can be used.

---

## D-007 — No invented RS metric
**Decision:** Do not display a generic `RS 92`-style metric unless a real supported calculation is defined and implemented.

**Reason:** A visually familiar metric must not be presented as quantitative truth when it does not exist in the engine.

---

## D-008 — Do not resurrect removed momentum systems
**Decision:** The removed momentum-acceleration/alternative systems are not part of v2 merely to create more UI content.

**Reason:** The current production momentum engine is intentionally the single composite system.

---

## D-009 — Mobile screener uses cards
**Decision:** Mobile screener is a ranked card/list experience rather than a compressed desktop table.

**Reason:** Touch screens favor prioritization and progressive disclosure. The complete quantitative table remains a desktop-strength surface.

---

## D-010 — Native Streamlit first
**Decision:** Design for Streamlit Free using native primitives wherever possible.

**Reason:** Reliability and deployment compatibility matter more than reproducing every native-app animation.

**Consequence:** CSS/HTML/custom components are permitted when justified, but should not become an accidental second application framework.

---

## D-011 — Mockup values are illustrative
**Decision:** Values shown in design screenshots are visual placeholders unless explicitly marked as production data.

**Reason:** Design work must never be mistaken for live market output.

---

## D-012 — Design before implementation
**Decision:** Complete visual concepts and information hierarchy review before broad implementation.

**Reason:** This is the primary mechanism for preventing design drift.

---

## D-013 — Required states
Every major data surface must eventually define:
- loading;
- empty;
- error;
- stale/data-quality warning;
- normal populated state.

These states are part of the product design, not implementation leftovers.

---

## D-014 — Quantitative provenance
Every important number shown in v2 must be traceable to:
- an existing engine output; or
- an explicit derivation documented in the implementation.

The UI should never create a metric merely because a card has empty space.

---

## D-015 — Page sequence
The design/review order is:

Screener → Stock Detail → Qualified → Markets → Industries → RRG → Portfolio → Delivery → Backtest → Watchlist → Guide → Configuration/Data Status.

This order establishes shared patterns early and reuses them deliberately rather than through legacy coupling.

---

## Context preservation rule

If future work is resumed after a long gap, read:

1. `redesign/DESIGN_MASTER.md`
2. `redesign/DESIGN_DECISIONS.md`
3. `redesign/PAGE_MAP.md`

before making design or architecture decisions.

Then inspect the relevant current branch/files. Never infer forgotten design decisions from the current code alone.
