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


## 8. 2010 trade-book inventory — first pass (2026-10-04)

The Library artifact `PIT_Trade_Reconciliation.xlsx` (derived from `ExitTrades-Sharpe.csv`) was inspected as an existing audit input. It reports 1,552 valid trade rows over 2010-01-04 through 2026-09-01; this section records its 2010 subset only. The workbook is a reconciliation artifact, not a primary exchange source, and its prior membership labels have not been independently re-performed here.

| Entry date | Trade rows opened | Evidence status |
|---|---:|---|
| 2010-01-04 | 20 | Ledger inventory only; ranking and official baseline not yet checked |
| 2010-02-01 | 4 | Same |
| 2010-03-02 | 7 | Same |
| 2010-04-01 | 8 | Same |
| 2010-05-03 | 6 | Same |
| 2010-06-01 | 9 | Same |
| 2010-07-01 | 14 | Same |
| 2010-08-02 | 9 | Same |
| 2010-09-01 | 9 | Same |
| 2010-10-01 | 11 | Same |
| 2010-11-01 | 12 | Same |
| 2010-12-01 | 7 | Same |
| **Total** | **116** | **Not a verified trade/selection count** |

The workbook's 2010 subset contains 116 trade rows and 105 distinct raw symbols. Three rows are marked by the workbook as identity-lineage reconciliations: `HEUBACHIND` → `CLNINDIA` (entry 2010-06-01), `MIRCELECTR` → `ONIDA` (2010-07-01), and `SUNDROP` → `ATFL` (2010-07-01). Treat these as leads only until dated identity/ISIN evidence and the engine's price-series handling are independently verified. The other rows' workbook label `LITERAL_MEMBERSHIP_MATCH` is inherited from the prior audit and is not a fresh independent check.

### What is still missing for a 2010 sign-off

- **Primary baseline:** no dated official/archived constituent snapshot has yet been retained and compared symbol-by-symbol with the repository's 2010-01-01 baseline. A current constituents download is not acceptable evidence for 2010.
- **Full monthly selection replay:** the workbook contains executed trade rows but not each decision-date eligible universe, complete score/rank table, or the Top 25 before execution. Therefore it cannot establish whether every selected name was in the eligible Top 25 or whether excluded names were improperly filtered.
- **Prices and score reproducibility:** no retained 2010 run artifact was found in this pass that independently establishes point-in-time adjusted/raw price basis, exact 12-month ROC and annualized-volatility windows, and ranks at every decision date.
- **Trade mechanics and returns:** this inventory does not recompute corporate actions, entry/exit prices, dividends, costs, cash, weights, or portfolio-level returns. Do not interpret the ledger's P&L as an independently verified strategy result.

### Evidence log update

| Date examined | Scope | Observation | Evidence | Status |
|---|---|---|---|---|
| 2026-10-04 | Trade ledger inventory for 2010 | 116 rows across 12 entry dates (2010-01-04 through 2010-12-01), 105 distinct raw symbols; 3 historical-identity rows are flagged for follow-up. No ranking output or primary official baseline snapshot was present in this workbook. | Library artifact `PIT_Trade_Reconciliation.xlsx`, sheets `Summary` and `All Trades`; source filename recorded inside workbook as `ExitTrades-Sharpe.csv` | Inventory complete; PIT selection unverified |


## 9. Repository membership timeline: structural and event cross-check (2026-10-04)

A read-only parse of `data/membership_history.json` on `main` establishes the following **internal consistency** facts:

- The dedicated `indices.nifty_500` baseline is dated `2010-01-01` and has **500 symbols / 500 unique symbols / 0 duplicate symbols**.
- The reconstructed 2010 event ledger has 12 effective dates:

| Effective date | Added | Removed | Notice key recorded in history |
|---|---|---|---|
| 2010-02-24 | PENINLAND | ASIANHOTNR | ind_prs19022010.pdf |
| 2010-03-09 | BRIGADE | KIRLOSBROS | ind_prs04032010.pdf |
| 2010-04-06 | NHPC | MICRO | ind_prs05042010.pdf |
| 2010-04-08 | BANCOINDIA, BINANICEM, GAMMNINFRA, JSWHL, KGL | CONSOFINVT, DONEAR, MUKTAARTS, SIRPAPER, SMARTLINK | ind_prs24022010.pdf |
| 2010-04-15 | ADANIPOWER, OIL | KIRLOSOIL, ZEENEWS | ind_prs12042010.pdf |
| 2010-05-26 | JSWENERGY | GRASIM | ind_prs20052010.pdf |
| 2010-07-08 | TINPLATE | HINVDIR | ind_prs07072010.pdf |
| 2010-08-31 | GRASIM | HARRMALAYA | ind_prs27082010.pdf |
| 2010-09-17 | JPINFRATEC | FEL | ind_prs16092010.pdf |
| 2010-09-24 | DBREALTY | DALMIASUG | ind_prs22092010.pdf |
| 2010-10-07 | JPPOWER, JUBLFOOD | RNRL, ZEEL | ind_prs01102010.pdf |
| 2010-11-25 | SUNTECK | JUBLPHARMA | ind_prs22112010.pdf |

The repository's independent cross-check against `nse_index_rebuild/reference/IndexInclExcl.xls` records **31 matching event rows, 2 match-renamed rows, and 3 rows classified `only_nse`** for Nifty 500 in 2010. The three `only_nse` entries are explicitly accounted for in `nse_index_rebuild/rules/inclexcl_known_differences.csv` as company-name differences for the same events: JSW Holdings / Jindal SouthWest Hold (2010-04-08), Zee Media Corporation / Zee News (2010-04-15), and Future Retail / Pantaloon Retail (2010-09-17). The two renamed rows are also recorded in that known-differences register. This is evidence that the **2010 event chain agrees with NSE's own inclusion/exclusion workbook after the repository's documented name/rename reconciliation**; it is not an independent check of the starting 500-name baseline.

### Remaining membership evidence gap

The baseline count and event chain now pass the repository's structural checks, but I have not obtained a dated official/archived constituent snapshot for the 2010-01-01 starting list to compare all 500 names individually. The current NSE constituent download is a present-day list and cannot prove 2010 composition. The official event workbook verifies changes, but cannot alone prove the entire initial snapshot because routine market-cap-based reconstitutions may not all be itemized as simple notice events.

Sources inspected in this pass:

- Repository membership: `data/membership_history.json` (`indices.nifty_500`).
- NSE's own inclusion/exclusion workbook retained in repo: `nse_index_rebuild/reference/IndexInclExcl.xls`.
- Cross-check output: `nse_index_rebuild/reference/inclexcl_crosscheck.csv`.
- Documented exceptions: `nse_index_rebuild/rules/inclexcl_known_differences.csv`.
- NSE's current Nifty 500 page (current list only, not historical proof): https://www.nseindia.com/static/products-services/indices-nifty500-index.


## 10. Historical price and audit findings (verified 2026-10-04)

The prior note about an absent 2009 warm-up is **resolved** by inspecting the successful long-history build's GitHub Actions logs and downloading its retained `nse-long-prices` artifact. The artifact was generated by workflow run [37113597811](https://github.com/Pareshking/Paresh/actions/runs/37113597811) on 2026-10-03.

### Coverage facts

- R2 raw pack: **8,475,657 rows, 4,718 sessions** over the reported range 2008-01-01 to 2026-10-02.
- Built adjusted long file: **1,419 symbols, 4,645 sessions**, from 2008-01-01 through 2026-10-01.
- Builder report: 1,419 symbols wanted and 1,419 priced; **zero symbols classified unpriced**.
- The built file dropped 73 copied sessions and reports **16 rename joins refused** because of large price discontinuities or long gaps. Those 16 refusals must not be ignored for PIT identity review.
- The 2009 warm-up is present in the built file's date coverage. This resolves the specific concern that January 2010 necessarily lacks a 12-month lookback, but does **not** prove each member has 252 valid observations or that every price/adjustment is correct.

### Price audit is not a clean bill of health

The same artifact's independent-reference audit reports:

- Across the complete file, 97.8% of 887,093 weekly/interval comparisons with Screener were within 2%; it still contains **19,478 point mismatches** and **539 level shifts** across 1,344 compared symbols.
- The 2010 slice of `screener_level_shifts.csv` contains **21 level shifts**. Examples requiring evidence-led classification include `ANDHRAPAP` (2010-02-19 to 2010-02-26), `BRITANNIA` (2010-03-05 to 2010-03-12), `DALMIASUG` (2010-09-17 to 2010-09-24), `STER` (2010-06-18 to 2010-06-25), `TULIP` (2010-07-02 to 2010-07-09), and `ZEEMEDIA` (2010-04-09 to 2010-04-16). These are **audit leads**, not confirmed errors: Screener can itself contain restated or differently adjusted history.
- The 2010 slice of `screener_point_mismatches.csv` contains **536 rows** with start dates in 2010. The audit must classify these against NSE raw bars, corporate-action records, and identity evidence; a high overall match percentage cannot waive them.
- The report's `isin_lineage.csv` contains **12 transitions dated in 2010 with no ISIN history for the old symbol**, including `JPHYDRO → JPPOWER`, `ILFSTRANS → IL&FSTRANS`, `ANSALINFRA → ANSALAPI`, and `WELGUJ → WELCORP`. These require dated primary symbol-change/listing evidence where they intersect membership or trades.
- The build reports 16 rename joins refused across all history. A refusal means the raw histories were not joined by the price builder; it must be checked against the strategy's historical symbol resolution rather than patched by a guessed alias.

### Strategy provenance gate — must be resolved before ranking replay

A source inspection found a potentially material methodology mismatch that must be resolved before calculating ranks:

- The user's previously specified research strategy is a **single 12-month lookback score = 12-month ROC / annualized volatility**, 20 holdings, equal weight, monthly rebalance.
- The current repository's `src/engine/backtester.py` and `src/engine/rank_history.py` instead call `_composite_z_score` across configured `MOMENTUM_WINDOWS`, using period Sharpe inputs, winsorisation and cross-sectional z-scores; the historical backtest view also applies price/EMA/high and membership gates and uses the engine's own selection rules.
- The workbook identifies its source as `ExitTrades-Sharpe.csv`, but does not prove that this file was generated by the current repository engine or by the single-window formula. Its methodology tab explicitly says it is a reconciliation audit, not a rerun.

**Do not use the current composite engine to regenerate the existing trade book until its provenance is confirmed.** The replay must use the exact code/config that generated `ExitTrades-Sharpe.csv`, including the 12-month score, volatility annualisation convention, universe filters, tie-breaking, rebalance signal date, next-session execution, costs, corporate-action treatment and equal-weight sizing. If the original strategy implementation is not retained, that is a reproducibility gap to resolve explicitly—not permission to replace it with a different scoring method.

This mismatch is now a separate hard gate alongside membership, price and identity evidence. It may explain why a naive replay would produce different Top 25 names even with perfect prices and membership.

### Trade-linked price/identity exceptions (cross-reference completed 2026-10-04)

The 2010 trade rows were cross-referenced against the long-price artifact's existing audit CSVs. This is a targeted prioritization step; it is not a complete ranking or execution replay.

| Artifact finding | 2010 trade-book overlap | Disposition |
|---|---|---|
| 21 Screener level-shift rows dated in 2010 | `PATNI`, `TRENT` | Both require event-by-event classification before any score/return replay can be certified. |
| Unconfirmed large-move rows dated in 2010 | `SKUMARSYNF`, `TATACOFFEE` | Verify against NSE raw bars and corporate actions; don't assume the adjusted factor is correct just because a reference is missing. |
| 2010 point-mismatch rows in Screener audit | `ASTRAZEN`, `AUTOAXLES`, `BEPL`, `CANFINHOME`, `INDORAMA`, `NILKAMAL`, `PATNI`, `PGHH`, `TRENT`, `UNICHEMLAB` | Targeted follow-up list; compare NSE close/action evidence, not only vendor-adjusted returns. |
| Price builder refused rename join | `HEXAWARE` | The 2010 ledger has HEXAWARE opened 2010-01-04 and exited 2010-02-01. Builder refusal says the old/new series are 1,573 days apart. Keep the old historical series distinct unless primary listing/ISIN evidence proves how the post-gap security should be treated; do not silently stitch the gap. |

The trade-linked rows above make the next investigation concrete. They do not imply every row is wrong: a mismatch can be explained by an action, a source's restatement, or an identity boundary. Each requires a documented verdict and primary evidence or must remain unresolved.

### 2010 close-out gates now separated

| Gate | Status | Reason |
|---|---|---|
| 2009 warm-up availability | **Verified at file-coverage level** | Built artifact begins 2008-01-01; symbol-level valid-observation counts still need testing. |
| Nifty 500 baseline shape | **Verified** | 500 unique baseline symbols. |
| Full baseline accuracy against independent 2010 snapshot | **Open** | No dated independent snapshot found and retained. |
| 2010 price integrity / corporate actions | **Open** | 21 Screener level shifts and 536 point mismatches require per-item classification; Screener is a comparator, not final authority. |
| 2010 identity lineage | **Open** | Historical ISIN gaps and refused joins require primary evidence and per-trade relevance checks. |
| Monthly eligible universe, score, Top 25 | **Open** | No independently reproduced decision-date rank tables retained yet. |
| Trade ledger and return replay | **Open** | No recomputed 2010 portfolio ledger/return series produced yet. |

### Next exact steps

1. Join the 12 2010 ledger entry dates to the actual decision dates used by the backtest engine; do not assume entry date equals signal date.
2. For each decision date, reconstruct the Nifty 500 membership as known then, apply dated identity evidence, and measure each candidate's valid trailing observations from the long close file.
3. Recompute the **existing** score and rank with the repository's canonical backtester implementation, retaining all eligible-universe rows and the Top 25—not a new ranking formula.
4. Investigate the 21 2010 level-shift leads against NSE raw rows and dated corporate actions. Accept Screener only as a secondary cross-check; record why each mismatch is raw-source error, corporate action, symbol lineage, source restatement, or unresolved.
5. Reconcile each executed holding, exit, corporate action, price, and return to the original trade ledger. Report both row-level differences and portfolio-level effect.
6. Close the independent baseline evidence gap or explicitly classify the reconstructed baseline as not independently anchored. Do not promote the year to verified without a second-source checkpoint.

**Status:** the 2009 warm-up concern is resolved at coverage level. 2010 is still **not signed off** because price adjustments, identity, baseline independence, ranking replay and return reconciliation remain open. No application code, canonical data, or published price artifacts were changed by this audit.

Evidence inspected:

- [Successful long-price workflow run #37113597811](https://github.com/Pareshking/Paresh/actions/runs/37113597811), including build logs and retained `nse-long-prices` artifact.
- `nse_long_report.json`: date coverage, priced-symbol counts, dropped sessions, and rename refusals.
- `audit/screener_summary.json`, `audit/screener_level_shifts.csv`, `audit/screener_point_mismatches.csv`, `audit/isin_lineage.csv`, `audit/summary.json`, and `audit/raw_summary.json`.
- `data/membership_history.json` and `nse_index_rebuild/reference/inclexcl_crosscheck.csv`.
