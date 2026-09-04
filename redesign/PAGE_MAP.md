# PARESH QUANT — Page Architecture v2

This is the initial information-architecture map. It intentionally does not mirror the old page structure one-for-one.

## Primary navigation

### 1. Screener
The primary discovery surface.

- Universe overview
- Search / command entry
- Filter workspace
- Ranked stock list
- Compact market pulse
- Stock quick view
- Full stock analysis

### 2. Qualified
The actionable subset of the universe.

- Qualification summary
- Qualified ranking
- Signal/setup breakdown
- Risk/quality checks
- Stock detail

### 3. Markets
A consolidated market-state area rather than scattering market context across pages.

- Market regime
- Breadth
- Sector / industry strength
- 52W high/low context
- Market participation

### 4. Industries
Relative sector/industry exploration.

- Industry ranking
- Momentum distribution
- Breadth/participation
- Constituents
- Drill-down to stocks

### 5. RRG
Relative Rotation Graph and supporting relative-strength views.

- RRG visualization
- Quadrant interpretation
- Industry/stock drill-down where supported by existing data

### 6. Portfolio
Portfolio construction and monitoring.

- Current model portfolio
- Position weights
- Risk / stop information
- Portfolio-level performance
- Constituents and drill-down

### 7. Delivery
Delivery/accumulation research surface using the data already available to the application.

- Delivery candidates
- Accumulation signals
- Supporting price/volume context
- Stock drill-down

### 8. Backtest
Research and validation.

- Backtest controls
- Performance
- Drawdown
- Trade/portfolio statistics
- Walk-forward results where already supported

### 9. Watchlist
Personal monitoring surface.

- Watchlist stocks
- Current rank/score
- Momentum changes available from current data
- Technical/risk state
- Stock detail

### 10. Guide / Methodology
A transparent explanation of what the terminal calculates and how to interpret it.

- Momentum methodology
- Lookback windows
- Sharpe and return interpretation
- Risk metrics
- Qualification logic
- Data-quality flags
- Glossary

### 11. Configuration / Data Status
Operational controls and transparency.

- Configuration
- Data freshness
- Data coverage
- Missing/gap diagnostics
- System status

## Shared surfaces

Every major page should have a consistent:

- application header
- navigation
- market context strip
- page title + one-sentence purpose
- contextual search where useful
- filter/sort controls
- primary data surface
- drill-down path
- data-as-of / freshness indicator

## Responsive information hierarchy

### Desktop
Use available width for comparison. Tables are first-class surfaces. Secondary context may live in a right rail.

### Tablet
Reduce simultaneous columns and convert secondary context to collapsible/stacked sections.

### Mobile
Use ranked cards and focused detail screens. Do not force the desktop table into a narrow viewport. Filters become a dedicated overlay/workspace. Stock detail becomes a vertically ordered research brief.

## Page design sequence

We will design and freeze each page in this order:

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

The first two establish the shared component and responsive language used by the remaining pages.
