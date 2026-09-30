# Production Status — 2026-09-30

## 2026-09-30 — Streamlit reload race and track-record ledger semantics

Production log investigation found two transient import failures during Streamlit code reload:

- `KeyError: 'src.core.startup_metrics'`
- `KeyError: 'src.ui'`

Root cause: the custom hot-reloader removed application modules from `sys.modules` and released its lock before `app.py` completed re-importing them. Concurrent Streamlit script threads could therefore enter the import window while the application module cache was being rebuilt. The ranking path itself remained healthy and continued accepting the canonical 750-row precomputed artifact.

**Fixed in PR #263, merge commit `3529e834352156fafbd8f8f8b359ac8fb13219fc`:**

- added a process-wide re-entrant application import guard;
- held the guard across reload detection, application imports and `mark_loaded()`;
- added a concurrent-thread regression test.

Validation was green: Lint #237, R2 Streamlit read-path gate #283 and V1 Full Validation #1061.

The same investigation confirmed that missing `data/track_record_nano.json` and `data/track_record_combined.json` on 30 Sep are **expected**, because both ledgers begin with October 2026. The first books are signalled by the 30-Sep close and filled on 1 Oct. The old generic loader message was misleading because it logged a warning for a ledger whose inception had not yet arrived.

**Fixed in PR #263:** a missing ledger before its declared inception is now informational; a missing ledger at or after inception remains a warning. Existing corrupt-ledger protection is unchanged.

# Production Status — 2026-09-27
## 2026-09-27 — three systems

Live from main, production QA green on every merge (#240, #242–#246):

- **Three systems** — Nifty 750 (default), Nano Cap, Combined — chosen in
  Configuration; every page follows; the choice survives a stock link
  (`?sys=`). See `docs/THREE_SYSTEMS.md`.
- **Data from R2 first**, release files as fallback (#223); QA prints the source.
- **Precomputed rankings for all three** (#244). First Nano Cap / Combined
  publish 2026-09-27 (396 / 1,146 rows, release + R2); production's
  acceptance check replayed on the published files: all three accepted.
- **Per-system track records** from Oct 2026, comparison panel (#242);
  backtest for Nano Cap and Combined from Sep 2026 (#246).
- **Liquidity floor** option, off by default (#245).
- **Fixed**: under Combined, a stock that left the 750 for Nano Cap (HEG) was
  priced from the stale 750 copy (#244).
- **R2 retention**: the weekly apply ran as approved (10 superseded
  revisions, 32 MB); its audit now covers only the datasets it deletes from,
  after the whole-bucket audit ran out of time (#243).


## Current state

**Production is green and running from main.** The 2026-09-23 Streamlit deployment pulled the main branch, started successfully, loaded the reconciled NIFTY TOTAL MARKET universe, read both R2 datasets, and accepted the canonical 750-row ranking.

## Canonical production path

1. NSE index constituent data is reconciled into the tradable NIFTY TOTAL MARKET universe.
2. DUMMY* placeholders are discarded; no ticker alias is invented to compensate for them.
3. Screener prices are the canonical System-1 ranking source.
4. The Screener price store is published to R2 as an immutable revision with manifest/current-pointer integrity checks.
5. The ranking store publishes/serves the canonical precomputed ranking artifact.
6. Streamlit validates the published ranking contract against the current expected contract.
7. If accepted, the application uses that artifact and logs engine skipped; the runtime ranking engine is intentionally not rerun.
8. Yahoo-origin deep history is loaded separately from prices/yahoo/raw for deep-history/archive/healing use.

## 750-row completeness contract

The production ranking must contain every current-universe symbol. The previous 90% session-coverage floor allowed a session with one missing current symbol to be treated as complete; the downstream score calculation then dropped that symbol and produced 749 rows.

The coverage floor is now **1.00**. Symbol reconciliation also reports missing, extra and duplicate symbols when a precomputed ranking is rejected. The pipeline settings digest fingerprints this policy change.

**Stragglers (owner decision 2B, 2026-09-25).** The floor is still 1.00, but
up to `MAX_CARRIED_SYMBOLS` (5) symbols missing from the newest session can be
ranked on their last print, if each of them printed within the previous
`CARRY_MAX_AGE` (5) sessions. They count toward coverage and are flagged ⏸ in
the table. It is all or nothing: one missing symbol with no recent print
disqualifies the carry. A session the vendor is still publishing, with hundreds
missing, walks back exactly as before. The ranking still has 750 rows.
(`src/engine/pipeline.py`: `carried_symbols`, `last_ranked_session`.)

## Streamlit rerun optimization

Equivalent rerun work is memoized:

- ranking-contract validation → full contract JSON key;
- Screener frame shaping → immutable R2 revision SHA key;
- repeated identical source-selection/acceptance messages → process-global change detection.

A new R2 revision or changed ranking contract still invalidates the relevant cache, so the optimization does not weaken freshness or integrity checks.

## Verification

- V1 final validation after the 750-row fix: **green**, including full regression, compile, canonical ranking handoff, hierarchy validation and Streamlit smoke.
- Streamlit rerun optimization validation: **green** in V1 full validation.
- R2 Streamlit read-path gate: **green**.
- Live deployment on 2026-09-23: **750-row precomputed ranking accepted**.

## Precompute freshness (2026-09-25)

Production logs showed the precomputed ranking **rejected** (`price_fingerprint
differs`) between each night's Screener publish (~22:00 UTC) and the next
02:00 daily-sync slot (~07:00 UTC). During that window the app ran the engine
live. `daily_sync.yml` now also runs on completion of the Screener sync, so the
published ranking follows the new store within minutes. Confirm with the log
line `Precomputed ranking accepted` after the next overnight run.

## Code audit (2026-09-25)

The whole V1 codebase was read line by line (`docs/CODE_AUDIT_2026-09-25.md`).
Three owner decisions shipped:

- **1B.** Ranking windows count back from the last price date, not the wall clock.
- **2B.** A few stragglers no longer hold the ranking back (see above).
- **3B.** `price_fingerprint` hashes the whole price history, not just the last row.

Runtime dependencies are pinned to the versions CI tests (`requirements.txt`).
V1 Production QA failed twice after #169 (runs 567 and 568). Run 567 caught
the app mid-redeploy. Run 568 was an exact-SHA check that failed because
production was already serving the newer daily-sync build. #171 made the
check accept a newer build that contains the triggering commit. Every run
since (569 onward) has been green.

## Non-blocking observations

NSE PR/market-cap retrieval has previously encountered HTTP 429 rate limiting; the application has a fallback and can still load the market-cap data. This is not a blocker for the canonical ranking path and should not be coupled to the ranking-source architecture.

## Rules to preserve

- Do not use Yahoo downloads as the canonical ranking engine/source.
- Do not invent HEGAM → HEG or other ticker aliases.
- Do not allow DUMMY* symbols into the tradable universe.
- Do not lower the complete-session coverage requirement below 100%, or widen the straggler carry (5 symbols, 5 sessions), without a deliberate methodology change and new validation.
- Do not create a second ranking engine in the AI/research layer.
- Keep R2 production workflows isolated from Stage-4B research workflows.
