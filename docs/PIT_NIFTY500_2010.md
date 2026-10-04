# Nifty 500 PIT audit — 2010

**Status:** Open — baseline and monthly trade book not independently verified  
**Audit year:** 2010  
**Canonical history:** [`data/membership_history.json`](../data/membership_history.json), `indices.nifty_500`  
**Audit register:** [`PIT_NIFTY500_YEAR_BY_YEAR.md`](PIT_NIFTY500_YEAR_BY_YEAR.md)

## 1. Starting point

The repository's current Nifty 500 history declares a baseline effective **2010-01-01**. This is the reconstruction's starting state, not by itself proof that all 500 symbols match the official Nifty 500 constituent list effective on that date.

Before using this baseline as a production backtest universe, independently compare its complete 500-symbol set against dated primary evidence for the Nifty 500 (NSE Indices/IISL constituent records, official factsheets or archived index constituent files where available). Retain the original source, effective date, retrieval date, and hash. Do not silently repair mismatches in the JSON during the evidence-gathering phase.

## 2. Questions to resolve for 2010

- [ ] What is the exact official constituent list effective at the first strategy decision/rebalance date in 2010?
- [ ] Does the repository's 2010-01-01 baseline contain exactly 500 unique symbols?
- [ ] Are all symbols valid securities at that date, with no future ticker substituted without a dated identity mapping?
- [ ] What monthly rebalance schedule does the strategy actually use in 2010, and what is each decision date versus execution/entry date?
- [ ] For each decision date, which members have enough point-in-time price history to compute the strategy's existing 12-month ROC and annualized volatility?
- [ ] How are IPOs, suspended names, missing sessions, delistings, and corporate actions represented?
- [ ] Does the historical trade book contain names that were not members on the relevant decision date, and does it omit valid members because the price file is missing?
- [ ] Can every Top 25 candidate be traced from membership eligibility through price eligibility, score, rank, and final selection?

## 3. Historical identity and security continuity

Use the existing reference sources, including:

- [`data/reference/nse/symbolchange.csv`](../data/reference/nse/symbolchange.csv)
- [`data/reference/nse/isin_history.csv`](../data/reference/nse/isin_history.csv)
- [`data/nse_prices/notes.json`](../data/nse_prices/notes.json)
- [`data/corporate_actions_log.json`](../data/corporate_actions_log.json)

These references are evidence inputs, not an automatic substitute for primary verification of a specific historical transition. A later ticker's current identity does not prove that the same ticker was valid in 2010. A corporate action that changes economic exposure must not be treated as a simple symbol rename.

For each relevant security, record the raw symbol at the time, canonical identity, ISIN and validity dates where available, prior/new symbol, last old-symbol trading date, first new-symbol trading date, transition type, source, and confidence/status.

## 4. Rebalance observation template

Create one row per symbol per rebalance date in the working reconciliation artifact. At minimum, include:

| Field | Meaning |
|---|---|
| decision_date | Date on which membership and ranking information is evaluated |
| effective_date | Date the relevant index membership is effective |
| entry_date | Actual portfolio entry date, if selected |
| raw_membership_symbol | Symbol in the reconstructed historical index list |
| trade_book_symbol | Symbol in the trade ledger |
| canonical_identity | Identity used to reconcile continuity, with supporting evidence |
| isin_at_date | ISIN effective on the relevant date, when known |
| membership_status | Verified / reconciled by identity / conflict / unverified |
| price_status | Valid / insufficient lookback / missing / stale / other explicit exclusion |
| roc_12m | Existing strategy's point-in-time 12-month ROC |
| annualized_volatility | Existing strategy's volatility input, with exact window/convention |
| score | Existing strategy score; do not change its formula in this audit |
| rank | Rank within the eligible universe |
| selected | Whether the strategy selected the symbol |
| discrepancy | Short explanation, or blank if none |
| evidence | Source URL/document and file/hash reference |

Do not fill unknown facts with guesses. If the historical trade book, ranking output, or source evidence is not available, mark that input as missing and leave the year open.

## 5. 2010 completion checklist

- [ ] Official baseline evidence retained and the 500 names compared symbol by symbol.
- [ ] All 2010 membership events identified and dated, with evidence.
- [ ] All monthly rebalance dates and actual trade-book rows enumerated.
- [ ] Ticker/security lineage checked for every candidate and holding.
- [ ] Lookback data completeness and point-in-time availability measured.
- [ ] Top 25 reconciled against the eligible universe for every rebalance.
- [ ] Discrepancies classified as membership event, identity event, corporate action, price-data gap, strategy-rule issue, or unresolved.
- [ ] Year-end holdings and return calculations reproduced from the retained inputs.
- [ ] Reviewer sign-off recorded; otherwise status remains open.

## 6. Initial observations and limitations

1. **Baseline exists:** the repository records a 2010-01-01 Nifty 500 baseline. This is a repository fact, not independent validation of its constituent accuracy.
2. **Identity continuity is a known risk:** the canonical membership history has a narrow `aliases` mapping, while other repository reference files contain broader ticker-change evidence. Their behavior in the complete 2010 backtest path must be tested before the year can be certified.
3. **No trade-level result is claimed here:** the full 2010 trade book and per-rebalance Top 25 have not yet been reconciled in this document.
4. **No membership or strategy changes are proposed by this file:** it records the evidence required and the open questions only.

## 7. Evidence log

Append dated observations here. Each entry must state the date range examined, sources actually inspected, outcome, unresolved questions, and reviewer/status.

| Date examined | Scope | Observation | Evidence | Status |
|---|---|---|---|---|
| 2026-10-04 | Repository schema and current reference paths | Dedicated `indices.nifty_500` history and NSE symbol/ISIN reference files exist; the baseline's official 2010 constituents and 2010 trades have not yet been independently compared. | `data/membership_history.json`; `data/reference/nse/symbolchange.csv`; `data/reference/nse/isin_history.csv` | Open |
