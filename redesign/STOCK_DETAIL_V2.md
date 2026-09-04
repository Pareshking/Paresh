# Stock Detail v2 — Data-Grounded Design

**Status:** CONCEPT — CORRECTED AFTER REVIEW
**Rule:** This page may only expose information already produced by the current application/quantitative data pipeline or a transparent derivation from it.

## Approved information hierarchy

### 1. Identity / current state
- Symbol
- Company name where already available
- Industry / sector where already available
- Index membership where already available
- CMP/current price
- Current daily price change where directly derivable from available price history
- Data-as-of / freshness

### 2. Rank & momentum
- Rank
- Composite momentum score
- Score percentile (transparent cross-sectional derivation)
- Rank Δ1M
- Rank Δ3M
- 1M / 3M / 6M / 9M / 12M Return
- 1M / 3M / 6M / 9M / 12M Sharpe

### 3. Price / technical chart
Use the existing historical price data to visualize:
- price/candles
- volume where available
- 50 EMA
- 52W high context
- ATH context

The chart is a visualization of existing data, not a new calculation model.

### 4. Trend / position
- Above 50 EMA
- % above/below 50 EMA
- Near 52W High
- % from 52W High
- 52W High Date
- ATH / % from ATH
- 6M persistence

### 5. Risk / exit levels
- ATR / ATR%
- Stop Loss
- Chandelier Exit
- 1M / 3M / 6M / 9M / 12M Max Drawdown

### 6. Volume / participation
- Volume status
- Volume ratio
- Any existing volume fields already returned by the engine

### 7. Company metadata already available
- Market Cap (Cr)
- Industry / sector
- Index membership
- Data-quality fields such as FFill %, Data Gap, Short History

### 8. Qualification / signal interpretation
If a setup label is shown, its rule must be explicitly derived from existing fields. Examples may include:
- Leader
- Strong
- Near High
- Accumulation / Base Building
- Pullback

These are presentation states, not new quantitative systems.

### 9. Actions
- Back to Screener
- Add/remove Watchlist if existing watchlist functionality supports it
- Open the relevant existing analytical view

## Deliberately excluded

Do **not** design or imply these unless a real supported data source/calculation is later introduced:

- Shareholding pattern
- Quarterly financial results
- P/E, P/B, dividend yield, EV, enterprise value
- Fundamental financial statements
- News/events feed
- Peer comparison based on unsupported external data
- Generic RS score
- analyst ratings/targets
- unsupported market weights
- unsupported exchange identifiers

These were mistakenly introduced in an earlier concept and are explicitly rejected from the frozen design.

## Desktop composition

1. Header: identity + price + rank/score/state
2. Main chart workspace
3. Momentum returns/Sharpe panel
4. Trend / 52W / ATH panel
5. Risk / exit panel
6. Volume / persistence panel
7. Data quality / metadata panel
8. Transparent setup interpretation
9. Actions

Avoid filling the page with unrelated financial-data categories.

## Mobile composition

1. Identity + price + setup
2. Rank / score / percentile
3. Chart + timeframe controls
4. Momentum returns
5. Trend / 52W / EMA
6. Risk / exits
7. Volume / persistence
8. Metadata / data quality
9. Setup explanation
10. Watchlist action

Mobile should use progressive disclosure and not attempt to show every desktop metric simultaneously.

## Freeze criterion

This page is not frozen until a visual concept has been reviewed against this document and every visible metric can be traced to an approved source.
