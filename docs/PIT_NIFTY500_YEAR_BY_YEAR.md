# Nifty 500 point-in-time backtest audit — year-by-year register

**Status:** In progress; not production-certified  
**Scope:** Historical constituent eligibility, ticker continuity, price availability, monthly rebalance selections, and resulting trade/return effects.  
**Rule:** Documentation-only work until an implementation change is separately approved.

## Purpose

Establish, year by year and rebalance date by rebalance date, whether the momentum backtest used the Nifty 500 constituents that were actually effective at the decision date. The audit must distinguish an incorrect membership event from a correct membership event represented under a different ticker.

The canonical membership source remains [`data/membership_history.json`](../data/membership_history.json), especially `indices.nifty_500`. Existing identity evidence remains in [`data/reference/nse/symbolchange.csv`](../data/reference/nse/symbolchange.csv), [`data/reference/nse/isin_history.csv`](../data/reference/nse/isin_history.csv), and [`data/nse_prices/notes.json`](../data/nse_prices/notes.json). This audit does not introduce a second membership engine.

## Required record for every rebalance

For each scheduled rebalance, preserve:

1. Decision date, intended effective date, actual entry date, and price observation date.
2. Membership-history revision/hash and the exact Nifty 500 membership set returned for the decision date.
3. Raw symbol, canonical company/security identity, historical ticker, ISIN where available, and the evidence supporting each identity link.
4. Price availability as of the decision date, including the oldest usable observation and any missing-data exclusions.
5. The complete eligible candidate count before ranking and after each explicit filter.
6. The strategy's existing score inputs and score, without changing the locked strategy formula.
7. Selected Top 25 (or the configured portfolio size for that run), ranks, weights, and reasons for exclusions.
8. Membership disagreements, identity mismatches, corporate actions, relistings, suspensions, and unresolved evidence gaps.
9. Comparison with the stored trade book: entries, exits, holdings, turnover, and return impact.
10. Source URLs/document identifiers, publication/effective dates, retrieval date, and file hashes where available.

A symbol-string mismatch is not, by itself, proof that a company was outside the index. A matching company name is not, by itself, proof that two securities are equivalent. ISIN changes, demergers, mergers, and relistings must be reviewed as security-identity events, not automatically flattened into ticker aliases.

## Status vocabulary

- **Verified:** primary or otherwise authoritative dated evidence was inspected and the reconstruction agrees.
- **Reconciled by identity:** the apparent mismatch is explained by a documented continuity link; the link and effective dates are recorded.
- **Conflict:** available dated evidence disagrees with the reconstructed membership.
- **Unverified:** the available evidence is insufficient or has not yet been inspected.
- **Not applicable:** no candidate/trade or event exists for that check.

Do not convert an inferred event to verified without retaining the evidence that supports it.

## Chronological work plan

| Year | Document | Status | Primary focus |
|---|---|---|---|
| 2010 | [PIT_NIFTY500_2010.md](PIT_NIFTY500_2010.md) | In progress — 2008+ price coverage verified; price/identity exceptions, independent baseline and exact strategy provenance/ranking replay remain open | Baseline constituents, trade-linked price audit, identity transitions, exact generating strategy, monthly Top 25 and trade/return reconciliation |
| 2011 | PIT_NIFTY500_2011.md | Not started | Annual changes and first full-year trade reconciliation |
| 2012 | PIT_NIFTY500_2012.md | Not started | Additions/removals, relistings, corporate actions, trade-book differences |
| 2013 | PIT_NIFTY500_2013.md | Not started | Membership and symbol continuity |
| 2014 | PIT_NIFTY500_2014.md | Not started | Membership and symbol continuity |
| 2015 | PIT_NIFTY500_2015.md | Not started | Membership and symbol continuity |
| 2016 | PIT_NIFTY500_2016.md | Not started | Membership and price coverage |
| 2017 | PIT_NIFTY500_2017.md | Not started | Membership, ticker transitions, trade effects |
| 2018 | PIT_NIFTY500_2018.md | Not started | Membership, ticker transitions, trade effects |
| 2019 | PIT_NIFTY500_2019.md | Not started | Membership, corporate actions, price continuity |
| 2020 | PIT_NIFTY500_2020.md | Not started | Membership during market disruption, data completeness |
| 2021 | PIT_NIFTY500_2021.md | Not started | Membership, relistings, price coverage |
| 2022 | PIT_NIFTY500_2022.md | Not started | Membership and trade reconciliation |
| 2023 | PIT_NIFTY500_2023.md | Not started | Membership and symbol continuity |
| 2024 | PIT_NIFTY500_2024.md | Not started | Membership, ticker changes, corporate actions |
| 2025 | PIT_NIFTY500_2025.md | Not started | Membership and current-history boundary checks |
| 2026 | PIT_NIFTY500_2026.md | Not started | Validate latest history through the audit cutoff |

Year files should be added as each year is actually investigated. The table is a work register, not a claim that any year is verified.

## Gate before any year is called complete

- [ ] Every rebalance date for the year is enumerated from the strategy schedule.
- [ ] Membership is reconstructed for the decision date using the existing canonical history.
- [ ] Membership events affecting that year have dated evidence and correct effective-date semantics.
- [ ] Historical ticker/security identity is resolved without conflating a rename with a corporate action.
- [ ] Candidate prices and lookback windows are point-in-time valid; missing data is explicit.
- [ ] The complete ranking universe and selected portfolio are reconciled to the trade book.
- [ ] All discrepancies are classified and independently evidenced or left explicitly unresolved.
- [ ] Portfolio and benchmark results are recomputed only after the universe reconciliation is ready.
- [ ] Tests and source-code changes, if later approved, are recorded separately from this evidence audit.
- [ ] A reviewer can reproduce the year from retained inputs, sources, and outputs.

## Current known risks

1. The history contains a dedicated `indices.nifty_500` timeline, but the existence of that timeline alone does not certify each historical selection.
2. The membership history's `aliases` field and the broader `symbol_changes`/NSE reference data are not yet demonstrated to resolve the same historical identity set in the backtest path.
3. The price archive may file a renamed company's earlier prices under its newer ticker. Eligibility must be evaluated on the historical identity, while returns must preserve correct security and corporate-action economics.
4. A monthly entry date can differ from the membership decision/effective date. Both dates must be recorded; do not silently substitute one for the other.
5. No year is production-certified until its rebalance-level ledger and the aggregate portfolio impact are reconciled.

## Change control

This branch contains documentation only. Do not edit the membership JSON, price files, ranking logic, trade-book generation, or backtest code as part of this audit without explicit approval. Any future implementation proposal must identify the exact files, expected behavior, tests, and historical impact before it is applied.
