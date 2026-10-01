# Canonical account reconciliation, hard caps and parity gate — 2026-10-02

Record of the end-to-end reconciliation requested in the engineering handover of
2026-10-01, the defects it found, the owner decisions it raised, the changes made,
and how agreement is enforced from now on.

Labels used throughout: **Verified** (executed against the published data or the
code, output retained), **Claimed** (stated by a source not re-checked here),
**Not verified** (could not be checked from the environment the work ran in).

---

## 1. Verified baseline

| Item | Value |
|---|---|
| Code baseline | `main` at `1336894` (#304), which already included #313–#316 |
| Published price snapshot (`data-latest/prices.parquet`) | 2024-09-30 → **2026-09-30**, 750 symbols |
| Ranking artifact (`rankings.parquet`) | price fingerprint `2026-09-30_1790x750_23eb9f9caf7d`, pipeline `v4_calendar_periods_87d04bdc`, price source `screener` |
| Committed NSE closes (`data/nse_prices`) | through **2026-10-01**, so the canonical replay's as-of is 2026-10-01 |
| 2026-10-02 | NSE holiday (Gandhi Jayanti); no session |
| Canonical inception | **2026-01** (`systems.inception(SYSTEM_750)`); ledger 2026-01 → 2026-09 |

The handover's reference pipeline `cbab8da9` was historical; the live artifact is
`87d04bdc`.

## 2. Parity scorecard (before any change)

| Comparison | Result | Evidence |
|---|---|---|
| Portfolio book vs Actions/Backtest book | **Exact match** | Portfolio passes the Screener ranking frame, Actions/Backtest the deep Yahoo frame; both reduce to a byte-identical basis frame (fingerprint `…efb9b7bea626`, 0 differing cells), so 20 names, entries, prices and 5.00% weights agree — not a cache artefact |
| Actions planner vs executed 1-Oct rebalance | **Exact match** | `plan_rebalance` on the Sep-30 artifact reproduced 6/6 sells, 6/6 buys |
| Frozen ledger vs live recomputation | **Exact match** | 9/9 months within ±0.05 pp; max drift 0.00005 pp (rounding) |
| Research backtest vs account | **Legitimately different** | Up to 2.36 pp/month drift and September missing; decomposed into price basis (Yahoo vs Screener-primary, ≤ ~1.1 pp), the 30% sector cap the account did not apply, and the month window counted from the Yahoo frame end (30 Sep) |
| "Backtest starts in 2022" | **Resolved in current code** | Research reporting starts at `BACKTEST_START[SYSTEM_750] = 2026-01`; earlier data is warm-up only |

The ledger matching proves **reproducibility, not live provenance**: every month is
`origin: backfill`, rebuilt three times on 2026-10-01 under successive methods
(previous values differed by up to 2.86 pp/month). There are no original fills.

## 3. Root-cause register

| # | Defect | Evidence | Fix | Regression test |
|---|---|---|---|---|
| D1 | `record_run` cache ignored the benchmark (`_benchmark_close` is unhashed and the key string omitted it). One failed benchmark download cached a **0% benchmark** that every page then served for up to the 1-hour TTL, so alpha read as the strategy return. | Reproduced: a healthy call after an empty one returned September benchmark 0.0%; after the fix −5.43%. | `_benchmark_key()` adds a fingerprint of the benchmark slice that can reach the record (inception − 40 days onward), so 2y and 5y downloads still share one replay. | `tests/test_record_run_benchmark_cache_key.py` |
| D2 | The account had **no effective industry cap**: `record_run` passed no `sector_map`, so `run_backtest`'s default never bound, while Actions and the research backtest applied 30%. Actions' code comment claimed it used "the caps the model book's own run uses". | Canonical books held 40–60% in one industry in 7 of 10 months. | Owner decision O1/O2 below. | `tests/test_account_sector_cap.py`, `tests/test_hard_caps.py` |
| D3 | `former_members.industry_for` relabels **current** members from TradingView; used naively it disagreed with the NSE index file for 3 of the 20 October names (CPPLUS, SIGMAADV, STLTECH). | Caught during the first rebuild; that rebuild was discarded and redone from the original ledger. | `record_sector_map()` uses the NSE index label first and `industry_for` only for names the file lacks — the same labels the ranking, Actions and research read. | `test_current_members_keep_their_nse_index_industry` |
| D4 | Cap relaxation was silent: nothing in the UI read `caps_relaxed`. | Code search. | Superseded by O2 (no relaxation); the research page now reports any cash the caps leave. | `test_projection_never_exceeds_stated_caps_on_random_shapes` |
| D5 | Stale docstrings: `systems.backtest_months` says "None for the 750" (code returns a month count); `record_run` says the record is struck on NSE closes (it is Screener-primary). | Code reading. | Not changed; recorded here. | — |

## 4. Owner decisions

| # | Decision | Date |
|---|---|---|
| O1 | The account carries an industry cap. | 2026-10-02 |
| O2 | The cap is **40%**, applied **everywhere**, and **every limit is hard** — 5% per stock, 40% per NSE industry, never relaxed. | 2026-10-02 |

## 5. What "hard" means in the code

- **Selection** (`backtester._select_holdings`, shared by the backtest, the live
  replay, the ledger updater and Actions): no industry gets more than
  `sector_slots(top_n, stock_cap, sector_cap) = floor(sector_cap / min(1/top_n, stock_cap))`
  names — **8** for 20 names at 5% / 40%. Incumbents are retained best-rank-first,
  so an over-full industry keeps its strongest names and sells the rest; the top-up
  skips a full industry for the next-ranked name. Unlabelled names share "Other".
- **Weights** (`portfolio.apply_caps`, now `hard=True` by default): caps are never
  raised and weights are never scaled up; weight the caps cannot place is cash at
  0% (`attrs["cash"]`). The previous relax-to-feasible path remains behind
  `hard=False`; nothing in the app passes it, and its original tests still cover it.
- **Pinned config** (`TRACK_RECORD_CONFIG`): `stock_cap 0.05`, `sector_cap 0.40`,
  `caps "hard_at_rebalance"`, `sector_labels "nse_index_industry_tv_fallback"`.
  Fingerprint **`4cc739e503d7`**.
- **Defaults**: `DEFAULT_SECTOR_CAP = 0.40` (Configuration), and 0.40 in
  `run_backtest`, `plan_rebalance` and `apply_caps`.
- **Actions** reads its caps from the pinned config; its "next in line" list skips
  industries that are full.
- **Research page** shows a note when the chosen settings leave cash.

### Consequences (verified or by construction)

1. **Between rebalances** the book is held, so prices can carry an industry past
   40%. Worst observed: **40.9%** (Financial Services, 2026-02-20). It is trimmed at
   the next rebalance.
2. If fewer than 20 names qualify, or qualifiers sit in ≤ 2 industries, the account
   holds the shortfall **in cash** instead of overweighting. Not yet observed.
3. Research with fewer holdings at the default 5% stock cap holds cash
   (10 holdings → 50%, 15 → 25%) until the stock-cap slider (max 15%) is raised.
4. Industry labels are **today's**, applied to past months; no point-in-time
   classification history is committed.

## 6. Ledger rebuild

Run through the updater's own logged path:

```
python scripts/update_track_record.py --force --note "<owner decision 2026-10-02 …>"
```

with the published `prices.parquet` supplied as the Yahoo frame (the frame only
serves as `basis_frame`'s fallback; the basis was shown identical either way).
Rebuilt from the original ledger, so the log records **one** entry for this
decision (4 in total). The entry's `on` field is UTC (`2026-10-01`); the decision
was taken on 2026-10-02 IST.

| Month | Before | After | Δ pp | Benchmark |
|---|---|---|---|---|
| 2026-01 | +0.17% | −0.21% | −0.38 | −3.32% |
| 2026-02 | +2.46% | +0.70% | −1.77 | +0.38% |
| 2026-03 | −11.85% | −9.89% | +1.96 | −11.39% |
| 2026-04 | +19.84% | +18.78% | −1.06 | +10.50% |
| 2026-05 | +11.53% | +11.77% | +0.24 | −0.12% |
| 2026-06 | +7.25% | +6.76% | −0.49 | +1.49% |
| 2026-07 | −2.20% | −2.14% | +0.06 | +2.02% |
| 2026-08 | +14.43% | +14.79% | +0.36 | −0.04% |
| 2026-09 | +0.99% | +0.17% | −0.82 | −5.88% |
| **Cumulative** | **+46.57%** | **+44.40%** | | **−7.54%** (unchanged) |

Today's book changed by one name versus the uncapped record (AKUMS out, EMIL in),
because earlier months took a different path. The 1-Oct rebalance under hard caps:
buys E2E, EMIL, SHREEJISPG, SIGMAADV, SKYGOLD, SYRMA, WELSPUNLIV; sells ANANDRATHI,
ATHERENERG, HONASA, QUESS, RRKABEL, RUBICON, UTLSOLAR.

## 7. Verification after the change

| Check | Result |
|---|---|
| Every rebalance Jan–Oct: max stock / max industry / invested | 5.00% / ≤ 40.0% / 100% — no cash |
| Live replay vs rebuilt ledger | 9/9, max drift 0.00003 pp |
| Portfolio-input vs Actions-input book | identical |
| Actions planner vs 1-Oct trades and weights | identical; 0.0 pp weight difference |
| Research engine at defaults on canonical prices vs ledger | 9/9 |
| Regression suite / lint | 1936 passed / clean |

## 8. Keeping it matched: the canonical parity gate

`scripts/canonical_parity_check.py` runs the real code on the published release
assets (no secrets) and **exits non-zero** on any failure. Workflow
`.github/workflows/canonical_parity.yml` runs it on every push and PR to `main`,
after every successful **Daily NSE Momentum Data Sync** and **Monthly Track Record
Freeze**, and on demand. Failed post-sync runs open an issue through
`scheduled_failure_alert.yml`. The JSON report is kept as a workflow artifact.

| Check | Fails when |
|---|---|
| `book_parity` | the Screener frame and the Yahoo frame yield different current books |
| `ledger_parity` | any frozen month differs from the replay by more than 0.05 pp |
| `ledger_config` | a frozen month was struck under a config other than today's |
| `hard_caps` | any rebalance exceeds 5% per stock, 40% per industry, or 100% |
| `actions_plan` | Actions' planner does not reproduce the latest executed trades/weights (skipped, not failed, when the artifact is not the latest signal session) |
| `research_default` | the research backtest's defaults no longer reproduce the account |

Negative tests (verified): changing the Configuration default to 30% failed
`research_default`; changing the account's cap without a rebuild failed
`ledger_parity` and `ledger_config`.

What the gate does not cover: a vendor restatement of an old close makes
`ledger_parity` fail by design — accepting or rebuilding is an owner decision; it
checks the published snapshot, which can lag the app by a session; and it compares
engine outputs, not rendered pages (that is V1 Production QA).

## 9. Remaining limitations

- No immutable archive of historical holdings, fills or per-fill costs exists; the
  whole ledger is a backfilled reconstruction under the current method.
- Industry labels are not point-in-time.
- The research backtest still prices on Yahoo; its returns differ from the account
  for that reason alone (legitimately different, labelled on the page).

## 10. Go-live runbook

1. `git am` the three patches on `main` (benchmark cache key; hard caps + ledger
   rebuild; parity gate and this document) and push.
2. Confirm green: Lint, V1 Full Validation (incl. headless smoke), R2 gates,
   **Canonical parity gate**.
3. Streamlit Cloud redeploys from `main`; confirm the deployed commit and run V1
   Production QA at desktop and mobile widths.
4. **Rollback:** revert the hard-cap commit; it restores the previous ledger
   (config `7632b1dd09ca`) and behaviour in one step. The benchmark cache-key fix
   is independent and should stay.

Shipping: the four commits were rebased onto `main` at `510d627` (#317, UI charts;
no engine or ledger changes). On that tree: lint clean, **1951 tests passed**, parity
gate **6/6 PASS**. Pushed and merged via pull request; CI outcomes are recorded on
the PR. The Streamlit Cloud deployment commit is confirmed by V1 Production QA, not
by this document.
