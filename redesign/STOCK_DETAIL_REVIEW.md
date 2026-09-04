# Stock Detail v2 — Design Review

**Status:** Concept approved for continued iteration; implementation not started.

## Primary job

Explain **why this stock deserves attention** and expose the quantitative evidence and risk state behind that conclusion.

## Desktop hierarchy

1. Back to Screener / navigation context
2. Stock identity + price + daily state
3. Rank / Score / Percentile / Setup / key state metrics
4. Timeframe selector
5. Dominant price + volume chart
6. Key statistics and setup analysis
7. Returns + momentum
8. Moving-average / trend state
9. Volume analysis
10. Drawdown / risk
11. 52W / ATH position
12. Relative performance only where existing supported data permits it
13. Peer/industry context only where supported by existing data
14. Secondary optional sections only if actual data sources exist
15. Quick actions / Watchlist

## Mobile hierarchy

1. Back + compact header
2. Identity / price / setup state
3. Timeframe selector
4. Compact price chart
5. Key metrics
6. Returns
7. Setup analysis
8. Risk & levels
9. Volume/trend
10. Secondary research sections
11. Watchlist/action bar
12. Bottom navigation

## Quantitative fields approved

Use existing/derivable values including:
- Rank
- Score
- score percentile
- Rank Δ1M / Rank Δ3M
- 1M/3M/6M/9M/12M return
- 1M/3M/6M/9M/12M Sharpe
- period max drawdown
- 50 EMA and distance/above state
- 52W high, date and distance
- ATH and distance
- ATR
- Stop Loss
- Chandelier Exit
- volume ratio/status
- 6M persistence
- market cap/data quality
- sector/industry/index membership

## Conditional / not yet approved

The visual concept may depict fundamentals, news, results, shareholding, peer tables, enterprise value, P/E, dividend yield, free float and similar information as optional product areas. These are **not approved data requirements** unless the current repository already provides them or they are separately authorized later.

Implementation must not fabricate these fields to match the screenshot.

## Interaction rules

- Timeframe changes affect chart/analysis where supported.
- Primary action is Watchlist / return to Screener.
- Mobile must not require horizontal scrolling.
- Secondary information should progressively disclose rather than overwhelm the first viewport.
- Loading/error/stale states must be designed before implementation.

## Screenshot record

A dedicated Stock Detail desktop + mobile concept was generated during the 2026-09-04 design session. It is a visual reference only; generated values are illustrative.

## Review conclusion

The Stock Detail direction is strong: it feels like an evidence page rather than a decorative profile. Continue to the next page while preserving this hierarchy. Any later change must be recorded in `DESIGN_DECISIONS.md`.
