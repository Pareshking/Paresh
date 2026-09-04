# PARESH QUANT v2 — DESIGN FREEZE

## Purpose

This branch is the visual and product-design source of truth for the complete redesign. No production UI implementation should begin from memory or from the old application structure.

## Required deliverables before implementation

For every page and major state we will produce:

1. Desktop full-page visual mockup.
2. Mobile full-page visual mockup.
3. Page information hierarchy.
4. Component inventory.
5. Interaction/state notes.
6. Data-source mapping to existing quantitative calculations.
7. Streamlit Free feasibility check.
8. Explicit list of anything intentionally excluded.

## Design sequence

1. Screener
2. Stock Detail
3. Qualified
4. Markets / Breadth
5. Industries
6. RRG
7. Portfolio
8. Delivery
9. Backtest
10. Watchlist
11. Guide / Methodology
12. Configuration / Data Status

## Freeze rule

A page is not considered frozen until its desktop and mobile designs have been reviewed and accepted. Once frozen, implementation must follow the frozen design unless a deliberate design revision is recorded.

## Quantitative rule

Existing quantitative calculations are authoritative. UI work may reorganize, summarize, or derive transparent presentation states from them. The UI must never fabricate a metric merely because it looks useful in a mockup.

Rank Δ1D and Rank Δ7D are explicitly out of scope. Rank Δ1M and Rank Δ3M may be displayed because they already exist.

## Responsive rule

Mobile is a first-class composition, not a shrunken desktop. Desktop tables can become ranked cards on mobile; secondary information can move behind progressive disclosure.

## Visual direction

- Light institutional interface
- White/light-gray surfaces
- Restrained blue primary accent
- Clear green/red semantic states
- Strong numeric typography
- Minimal decorative chrome
- High information density without visual clutter
- Tables as first-class quantitative surfaces on desktop
- Cards as discovery surfaces on mobile

## Implementation rule

Do not copy the existing CSS/theme/component architecture merely because it exists. Build the new UI system from the frozen design and the actual capabilities of the current Streamlit platform.
