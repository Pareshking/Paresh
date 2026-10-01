# Track Record → Portfolio Canonical Architecture

## Status

Design baseline for the Track Record / Portfolio / Actions alignment work.

This document deliberately separates the research Backtest from the recorded model portfolio.

## 1. Architectural decision

The application has four different questions:

- Backtest: "What would the strategy have done under the selected historical assumptions?"
- Track Record: "What did the recorded strategy post?"
- Portfolio: "What is the current model portfolio represented by the recorded strategy?"
- Actions: "Given the current recorded book, what should happen at the next rebalance?"

The Backtest tab remains independently configurable and is not the canonical portfolio ledger.

The canonical live-model relationship is:

    Track Record
    frozen historical ledger + pinned record replay
                    |
             canonical current book
                /          \
               /            \
          Portfolio        Actions
        current state    next rebalance

## 2. Source-of-truth rules

### Track Record

The Track Record ledger remains authoritative for frozen monthly performance:

- frozen monthly return
- benchmark return
- alpha/difference
- origin (recorded/backfilled)
- point-in-time/current-list provenance
- freeze date
- pricing/data date
- configuration provenance

The live/current model book is produced through the Track Record's pinned configuration and canonical record replay (record_run()), rather than from Backtest-tab settings.

### Portfolio

Portfolio must consume the canonical current book exposed by the Track Record path.

Portfolio must not independently reconstruct a competing model book from the current ranking page.

It may calculate presentation/accounting fields from the canonical positions and current marks:

- capital sizing
- target/current weight
- shares
- invested value
- current value
- realised/unrealised P&L
- holding days
- current market mark

These are accounting views of the same positions, not a second selection engine.

### Actions

Actions remains forward-looking.

It may calculate the next rebalance using the strategy's canonical selection/weighting logic, but its starting holdings must be the same canonical current book used by Portfolio.

Therefore:

- HOLD/SOLD decisions must reconcile against the canonical current holdings.
- BUY candidates must exclude canonical current holdings.
- The resulting post-rebalance book must be testable against the strategy's own selection/weighting implementation.

### Backtest

Backtest remains independent.

Its controls may change:

- historical window
- assumptions
- weighting
- costs
- buffer
- risk settings
- benchmark and other research parameters

Backtest results must not become the source of truth for the live/current Portfolio.

## 3. Canonical current-book contract

The Track Record current-book representation must provide, at minimum:

- System
- Symbol
- Company/label where available
- Entry Date
- Entry Price
- Entry Rank
- Rank at Rebalance
- Target Weight
- Current/marked Price
- Holding Days
- Position state

The representation must have stable symbol identity and deterministic ordering.

The Portfolio layer may enrich this with:

- Capital
- Shares
- Invested Value
- Current Value
- Unrealised P&L
- Unrealised P&L %
- Weight %
- Target Weight %
- Weight Drift %
- Sector/industry
- Current rank where explicitly labelled as a current observation
- 1M/3M/6M/12M returns
- Last rebalance
- action/status

No enrichment may change the underlying membership of the canonical book.

## 4. Actions contract

Actions is not a second portfolio ledger.

At a given current state:

1. Read canonical current holdings.
2. Evaluate the next rebalance against the canonical strategy rules.
3. Produce SELL / BUY / HOLD and next-in-line candidates.
4. Validate that the HOLD set comes from canonical holdings.
5. Validate that BUY candidates are not already held.
6. Validate that the resulting target book follows the canonical selection and weighting functions.

## 5. Exact invariants

At the latest recorded rebalance:

    Track Record canonical current book
            ==
    Portfolio current holdings
            ==
    Actions current holdings
            ==
    record_run().live_book

Comparison is row-by-row, keyed by Symbol.

Required equality/consistency fields:

- Symbol
- Entry Date
- Entry Price
- Target Weight
- Entry Rank
- Rebalance rank / signal rank where applicable
- position membership

Derived market/accounting fields may differ only when their timestamp or capital-sizing purpose differs, and those differences must be explicit.

## 6. Rebalance semantics

A monthly rebalance is signalled on the last session of the closed month and filled on the next available trading session.

The current book means the post-fill book.

Therefore:

- newly bought positions receive the current fill date and fill price;
- retained positions keep their original entry date/entry price;
- sold positions are absent from the current book;
- a retained position is not a new entry.

The current book must never be described as "pending" when its fill has already occurred.

## 7. Track Record versus Backtest

The two systems intentionally answer different questions.

### Track Record

- pinned strategy configuration
- frozen monthly history
- evidence/provenance
- actual recorded months where available
- deterministic record replay for the current model book

### Backtest

- user-selected research configuration
- hypothetical historical reconstruction
- independent performance analysis
- independent tradebook/equity/statistics
- no requirement to match the live Portfolio except where the same assumptions and state are intentionally selected

A change to Backtest reporting windows must therefore not change the Track Record canonical book or Portfolio membership.

## 7A. Performance accounting contract (required)

The current-book contract above is necessary but not sufficient: matching symbols
does not prove that Track Record and Portfolio report the same portfolio
performance.

### One performance series

For a given system and as-of date, the canonical performance series is the
pinned Track Record replay and its append-only monthly ledger. Portfolio must
present that same series, not calculate a second cumulative return from the
current holdings. The ledger is the frozen source for closed months; the
replay's `live_meta` is the source for the not-yet-frozen month. The month
being shown must be identified as live MTD or closed/awaiting freeze.

The frozen monthly series and the live month must use the same:
- strategy configuration and rebalance timing;
- canonical price basis and benchmark basis;
- point-in-time membership and former-member treatment where available;
- corporate-action treatment;
- transaction-cost convention; and
- return units (decimal fractions internally; percent only at presentation).

Never silently force a recomputed month over a frozen ledger value. Report drift
as a diagnostic, with provenance, and preserve the append-only guarantee unless
an explicit, audited rebuild is requested.

### Account value versus current-position P&L

These are different, valid measures and must not be presented as interchangeable:

- **Portfolio value / since-inception return:** the ₹20 lakh starting account
  compounded by the canonical net portfolio-return series, including realized
  results, cash/unallocated capital and modeled trading costs.
- **Current-book unrealized P&L:** the marked value of positions currently held
  minus their entry cost. It excludes gains/losses already realized on sold
  positions and is not the account's cumulative return.
- **Day P&L:** the change in the current held positions between the two marks,
  using unchanged share quantities for that interval.
- **Monthly return:** a net account-level period return from the canonical
  replay, not an average of individual position returns.

Portfolio's headline performance must reconcile to its equity curve and the
Track Record headline for the same system, dates and return convention. The
holdings table's unrealized P&L may differ; label it as such and never use it as
a substitute for total portfolio return.

### Required reconciliation gates

Automated tests must check, on identical price/membership/configuration inputs:

1. Track Record's frozen months equal the corresponding canonical replay months
   when first finalized; existing frozen values remain unchanged on ordinary
   reruns.
2. Track Record and Portfolio use the same live MTD strategy/benchmark values,
   as-of date, price basis and configuration fingerprint.
3. Portfolio equity values equal starting capital compounded by the exact
   monthly series it displays; no percent/fraction 100x scaling.
4. The Portfolio and Track Record headline return, equity endpoint, calendar
   cells and benchmark endpoint reconcile for the same as-of snapshot.
5. Current-book holdings still reconcile row-by-row to
   `record_run().live_book` and Actions; this is a separate invariant from
   performance equality.
6. Unrealized current-book P&L is labelled separately from cumulative account
   performance; cash, transaction costs and realized results are accounted for
   exactly once.
7. A closed month awaiting the scheduled freeze remains visible and is not
   accidentally replaced by the next month's MTD or omitted from CY/FY totals.

## 8. Portfolio presentation target

Portfolio should become a real model-portfolio tracker rather than a second stock-selection screen.

Core summary:

- Portfolio value
- Invested capital
- Cash / unallocated capital
- Exposure
- Holdings
- Day P&L
- MTD P&L
- Total unrealised P&L
- Turnover / last rebalance where available

Current holdings table:

- Symbol
- Company
- Entry Date
- Entry Price
- Current Price
- Shares
- Invested Value
- Current Value
- P&L ₹
- P&L %
- Weight %
- Target Weight %
- Weight Drift %
- Rank at Rebalance
- Entry Rank
- Holding Days
- Sector/Industry
- Status

The table must be generated from the canonical current book plus accounting/market enrichment.

## 9. Test strategy

Tests must protect architecture, not just rendering.

### Canonical-book tests

- Track Record current book contains exactly the post-fill holdings.
- Sold names are absent.
- Newly bought names have the fill date/price.
- Retained names preserve their original entry date/price.
- Current-book symbols are unique.
- Target weights reconcile to the canonical weighting output.

### Cross-view reconciliation tests

For the same input snapshot:

- Track Record book symbols == Portfolio symbols.
- Track Record book symbols == Actions current holdings.
- Track Record book == record_run().live_book on canonical fields.
- Row-level mismatches identify symbol and field.

### Actions tests

- every HOLD is a current holding;
- every BUY is not currently held;
- every SELL is currently held;
- resulting target book follows canonical selection;
- weights use canonical weighting/cap logic.

### Independence tests

Changing Backtest-tab parameters must not alter the Track Record canonical book or Portfolio membership.

### Temporal tests

- current book is post-fill;
- current book excludes the current in-progress month as a rebalance signal;
- current marks may use the latest available close but must not leak into frozen Track Record performance.

## 10. Implementation rule

Do not introduce parallel implementations of:

- ranking
- selection
- weighting
- portfolio membership
- benchmark
- price methodology

Reuse the canonical engine and record configuration.

The main implementation objective is one canonical current-book object and multiple views of it, not a generic portfolio framework.

## 11. Acceptance gate

The work is complete only when:

1. documentation matches the implemented architecture;
2. Track Record current-book path is deterministic;
3. Portfolio consumes that path;
4. Actions reconciles against that path;
5. row-by-row automated tests pass;
6. Backtest remains independently configurable;
7. full test suite is green;
8. lint/type/static checks required by CI are green;
9. the relevant GitHub Actions validation is green;
10. no UI tab contains a competing portfolio-selection implementation.
