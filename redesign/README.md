# PARESH QUANT — UI Redesign Workspace

This directory is the clean-room design and implementation workspace for the next version of PARESH QUANT.

## Core rule

We are **not** carrying the existing UI forward. The redesign may replace the application shell, navigation, page composition, components, styling, responsive behavior, and interaction model.

The existing quantitative calculation layer is the source of truth unless a metric can be derived directly from those existing calculations/data without introducing a new external research dependency.

## Branch

`redesign-v2`

`main` remains untouched while the redesign is designed, implemented, validated, and compared against production behavior.

## Design principles

1. **Quant first** — the interface exists to expose useful quantitative information, not decorative dashboard widgets.
2. **Light institutional visual language** — white/light-gray surfaces, restrained blue accent, clear positive/negative states, strong numeric typography.
3. **Desktop and mobile are intentional layouts** — mobile is not a squeezed desktop table.
4. **Progressive disclosure** — summary first, detailed quantitative evidence one level deeper.
5. **No invented metrics** — every displayed metric must be sourced from the current engine or be a transparent derivation from it.
6. **Streamlit Free compatible** — design around the actual Streamlit execution/layout model; avoid infrastructure that requires a different hosting platform.
7. **Native first** — use Streamlit primitives wherever they provide the required behavior; custom CSS/HTML/components are used deliberately, not as a replacement for everything.
8. **No legacy visual baggage** — existing CSS, cards, page layouts, navigation, and component patterns are references only and are not assumed to survive.
9. **Validate before replacing main** — the redesign branch is the working product until visual, functional, quantitative, responsive, and deployment checks pass.

## Quantitative boundary

The existing production momentum engine remains authoritative. It currently provides, among other fields:

- composite Rank / momentum score
- 1M / 3M / 6M / 9M / 12M returns
- 1M / 3M / 6M / 9M / 12M Sharpe
- period maximum drawdown
- 50 EMA and distance/above-EMA state
- 52-week high, high date, distance from high, near-high state
- ATH and distance from ATH
- ATR, Stop Loss, Chandelier Exit
- volume ratio/status
- 6M persistence
- market-cap and data-quality fields
- industry/sector/index membership and qualification-related signals

We will **not** add Rank Δ 1D or Rank Δ 7D merely for UI symmetry. Existing Rank Δ 1M / 3M can be exposed where useful.

A visual label such as `LEADER`, `NEAR HIGH`, `STRONG`, or `BASE BUILDING` is acceptable only when its rule is explicitly derived from existing signals. It must not imply a new proprietary calculation that does not exist.

## Design workflow

1. Freeze the product information architecture.
2. Design every page in desktop and mobile form.
3. Freeze the shared design system and responsive rules.
4. Build the new shell/components.
5. Rebuild each page from the information architecture rather than porting the old UI.
6. Wire pages to the existing quantitative/data pipeline.
7. Validate calculations and displayed values against the engine.
8. Test Streamlit Free deployment and responsive behavior.
9. Remove obsolete UI code only after the new application is validated.
10. Merge the completed redesign into `main` only after final acceptance.
