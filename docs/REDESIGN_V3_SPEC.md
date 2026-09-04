# PARESH QUANT — V3 UI Redesign Specification

Status: design reset after runtime/mobile review
Scope: Screener + Stock Detail only
Branch: `redesign-v3`

## Source of truth

This redesign preserves the documented quantitative system and changes presentation only. The README defines System-1 as the only ranking system, using five calendar horizons (1M/3M/6M/9M/12M) and configured 10/30/30/20/10 weights. Removed systems must not return to the UI. External fundamentals, news, analyst data and undocumented RS scores are out of scope.

The existing documentation also records that the main screener historically used a custom table renderer because it supports per-cell conditional coloring, while `st.dataframe` is appropriate for tables that do not require that treatment. This remains an implementation constraint to respect, not a visual design to copy.

## Product principle

The app is a quantitative decision terminal, not an Excel viewer.

Every screen must answer one question quickly:

- **Screener:** Which stocks deserve attention first?
- **Stock Detail:** Why is this stock ranked here, and what is its quantitative risk/technical state?

## Information hierarchy

### Screener

1. Page identity and current data context
2. Search + universe/filter controls
3. Ranking list/table
4. Key quantitative columns only
5. One-tap transition to Stock Detail

The complete engine output is not displayed simultaneously. A screening surface should optimize comparison; Stock Detail is where depth lives.

### Stock Detail

1. Identity: symbol, rank, CMP, industry/index context
2. Score/rank position
3. Price structure and 50 EMA / 52W high / ATH
4. Five momentum windows: Return, Sharpe, Max Drawdown
5. Risk/technical fields: ATR, ATR%, Stop Loss, Chandelier Exit, persistence, volume
6. Data quality / metadata

No fundamentals, news, shareholding, analyst estimates, peer model, or new research metric.

## Responsive design contract

### Desktop ≥ 1100px

- Screener is table-first.
- Table occupies the main content width.
- Use curated columns: Rank, Symbol, Industry, CMP, 1D, 1M, 3M, 6M, 12M, selected Sharpe, % High, % 50 EMA, State.
- Additional quantitative fields remain available through Stock Detail.
- No giant fixed-height table that creates a secondary scroll surface unnecessarily.

### Tablet 768–1099px

- Condense the table.
- Keep Rank, Symbol, CMP, 1M, 3M, 12M, Sharpe, 52W/EMA state.
- Allow normal horizontal overflow only as a fallback; do not make it the primary interaction model.

### Mobile < 768px

- **Never render the desktop dataframe as the primary screener.**
- Use a purpose-built vertical ranking list/card.
- Each item must show Rank, Symbol, Industry, CMP, 1D, Score/percentile, 1M/3M/6M/12M, 3M Sharpe, 52W/EMA state.
- Entire item is an obvious navigation target.
- Do not require horizontal scrolling to understand the stock's primary ranking information.
- Do not make the user discover a hidden Table/Cards toggle to obtain the usable mobile view.

Streamlit documentation confirms that columns and containers can adapt/wrap, and warns that large scrolling surfaces should be used sparingly on mobile. The redesign therefore uses responsive containers and intentionally different content hierarchy rather than squeezing the desktop table.

## Screener controls

Top control area:

- Search symbol / industry
- Universe preset: All Stocks, Top 50, Qualified (only if engine supplies it), Above 50 EMA, Near 52W High, High Volume
- Sort: Rank, Score, 3M Return, 12M Return, 3M Sharpe, % High
- Row count on desktop/tablet

Mobile controls should collapse into compact controls where needed; filters must not dominate the screen.

No Rank Δ1D or Rank Δ7D.

## Screener states

Badges may use only engine-derived states:

- Above 50 EMA
- Near 52W High
- At ATH
- High Volume

No “New in Top 50”, “Exited Top 50”, momentum accelerator, live index quote, or other field requiring unsupported history/source data.

## Visual language

- Light institutional terminal.
- Background: very light neutral.
- Surfaces: white.
- Ink: near-black blue-gray.
- Muted text: slate gray.
- Borders: subtle neutral gray.
- One restrained indigo/blue accent.
- Positive/negative colors reserved for quantitative direction.
- Numeric data uses a monospaced face where useful.
- Avoid decorative gradients, oversized cards, excessive rounded containers, and dashboard-gadget density.

## Interaction rules

- Stock selection is the central interaction.
- Desktop table row selection can open Stock Detail.
- Mobile card/list tap opens Stock Detail.
- Stock Detail has a clear Back action.
- Search/filter state should survive the navigation round trip where practical.

## Technical implementation rules

- Reuse existing loaders and `MomentumEngine`.
- Do not modify quantitative formulas to support UI.
- Do not cache the engine through `st.cache_data`; stateful engine objects belong in `st.cache_resource` or should remain uncached while serializable outputs are cached.
- Prefer native Streamlit primitives where they provide the needed behavior. Use custom HTML/CSS only for presentation that native components cannot provide.
- The existing documentation says the main screener custom table exists specifically for per-cell conditional coloring; if a custom table is used in V3, preserve that capability intentionally rather than replacing it with a plain dataframe by accident.

## Acceptance test

A V3 build is not considered visually accepted until all are checked from the deployed app:

1. Desktop Screener: comparison is readable without awkward clipping.
2. Tablet Screener: hierarchy remains usable.
3. Mobile Screener: no desktop dataframe is the primary view.
4. Mobile stock selection: one tap opens the correct Stock Detail.
5. Stock Detail: chart and quantitative sections are readable on phone and desktop.
6. No unsupported metric appears.
7. Quantitative values agree with the existing engine.
8. Cold start and refresh complete without cache/hash errors.

## Design gate

`Documentation → field inventory → information hierarchy → responsive wireframe → implementation → deployed screenshot → screenshot audit → correction → freeze.`
