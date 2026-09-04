# Screener v2 — Design Review Record

## Status

**Concept status:** Approved direction / implementation not started

## Frozen principles

- Screener is the primary discovery surface.
- Desktop uses a quantitative comparison table as the hero element.
- Mobile uses ranked stock cards, not a compressed desktop table.
- Search, presets, filters, sort and density controls remain prominent but compact.
- Market context is visible without dominating the page.
- Secondary market intelligence is subordinate to the ranking surface.
- Stock detail is one tap/click away.
- Rank Δ1M and Rank Δ3M may be shown; Rank Δ1D and Rank Δ7D are excluded.
- Score percentile may be derived from the existing cross-sectional score.
- Setup labels may be used only where their rules are explicitly derived from existing signals.
- Mockup values are illustrative, never production data.

## Desktop structure

1. Application header/navigation
2. Page title + purpose + as-of state
3. Market context strip
4. Universe presets
5. Search + contextual filters
6. Screener toolbar / density / sort / columns
7. Primary ranking table
8. Market pulse / secondary insight rail
9. Pagination + data status
10. Stock drill-down

## Mobile structure

1. Compact header
2. Market summary
3. Search
4. Horizontal preset chips
5. Ranked stock cards
6. Dedicated filter workspace
7. Bottom navigation
8. Focused stock detail

## Quantitative field policy

The primary screener may expose existing/derivable fields such as Rank, Score, score percentile, Rank Δ1M/Δ3M, returns, Sharpe, 52W high distance, 50 EMA distance/state, volume signal, drawdown, Stop Loss and Chandelier Exit according to density mode.

Do not add fields solely because a competing terminal commonly displays them.

## Feasibility

The design is intended for Streamlit Free using native layout/data primitives first, CSS for responsive presentation, controlled HTML/components where necessary, and existing chart libraries for visualizations.

## Freeze gate

The Screener is considered visually frozen for implementation once the dedicated desktop/mobile concepts and this document agree on hierarchy, interaction, and supported data. Changes after that point require a design decision-log entry.
