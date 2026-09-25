# R2 Engineering Loop — Phase Tracker

Status: **Current production contract — 2026-09-22**

> **This file contains historical engineering notes as well as the current contract. The current contract below takes precedence over older implementation notes. Do not use older “next gate” lists as operational instructions.**

This tracker is the working checklist for the market-data archive. Do not wait on
the long Screener deep-history acquisition to advance independent engineering
work. The production 10Y run is checked separately when it completes.

## R2 / V1 boundary — HARD ARCHITECTURAL SEPARATION

**R2 implementation and V1/Stage-4B stock research are separate engineering tracks. They must not be mixed.**

R2 is the market-data storage/archive and reader layer. Its responsibilities are limited to historical data acquisition, normalization, immutable publication, manifests, checksums, coverage/integrity audits, and reproducible reads. R2 does **not** own ranking, stock selection, Stage-2/3 hierarchy, Stage-4B research, archetype execution, or Streamlit product validation.

V1 is the application/quantitative-research validation track. Stage-4B live archetypes such as SANSERA, ANANDRATHI, PAYTM, YATHARTH, and LENSKART belong to V1 research validation and are not R2 acceptance criteria.

### CI rule

- R2-only changes must be validated by R2-specific tests/workflows and must **not** trigger the expensive V1 Full Validation suite merely because the repository contains both systems.
- V1 Full Validation remains responsible for application + System-1 regression. Stage-4B live archetype execution is temporarily isolated in its own workflow so R2/V1 progress does not wait on the expensive research loop.
- An R2 gate is green only from R2 evidence; a Stage-4B result is neither a substitute for nor a prerequisite for an R2 storage gate.
- A V1/Stage-4B failure must not block independent R2 engineering unless the changed R2 code is demonstrably on the failing execution path. Stage-4B remains intact and independently executable; this is CI decoupling, not removal or weakening of Stage-4B tests.
- R2 consumer integration is now split by purpose: research/backtest remains explicitly pinned; Streamlit production is a separate daily-current consumer behind its feature flag.

This separation is intentional: the combined V1 suite currently executes multiple real Stage-4B archetypes and Streamlit checks, so attaching it to every R2 storage/documentation change creates unnecessary latency and makes unrelated failures harder to diagnose.

## A. Current production run — Screener 10Y

- [x] Real 10Y acquisition completes — 750 symbols, 1,161 sessions, 2016-09-23 → 2026-09-21.
- [x] Confirm complete universe walk and unresolved-symbol count — 0 unresolved.
- [x] Confirm unsettled sessions are removed.
- [x] Record rows, symbols, min/max dates, and older-session coverage — 750 symbols; 910 sessions older than 370 days.
- [x] Confirm no historical shrinkage versus the pre-run store — 277,600 existing cells preserved; +913 sessions.
- [x] Confirm R2 revision object exists.
- [x] Confirm revision SHA-256 — `df03ed6d6fb9c8ca963c4f3fb3b73386c43e6f106cc9a3307d7b693cf80455dd`.
- [x] Confirm immutable revision manifest exists.
- [x] Confirm immutable revision manifest matches the object via live read-back.
- [x] Confirm `current.json` points to that revision via live read-back.
- [x] Confirm R2 HEAD + byte/hash read-back.
- [x] Confirm release asset contains the exact published artifact by SHA equality.
- [x] Confirm release/R2 SHA-256 equality — `df03ed6d6fb9c8ca963c4f3fb3b73386c43e6f106cc9a3307d7b693cf80455dd`.
- [x] Run an identical retry/idempotency check against the live publication.
- [x] Record final evidence in the run summary.

## Status note — 2026-09-21

The long-running 10Y Screener acquisition has completed independently: 750 symbols, 1,161 sessions, 2016-09-23 through 2026-09-21, 0 unresolved symbols, 910 sessions older than 370 days, and 277,600 existing cells preserved while adding 913 sessions. The resulting artifact SHA-256 is `df03ed6d6fb9c8ca963c4f3fb3b73386c43e6f106cc9a3307d7b693cf80455dd`.

R2 publication hardening is now merged on main (PR #46, V1 Full Validation #524 passed). The independent storage gates are therefore complete at the code/test level: live archive audit, pointer/manifest/object mismatch coverage, schema-version enforcement, and interior-session no-shrinkage checks.

The remaining Section A boxes are **real-data publication verification**: live R2 read-back of the completed Screener revision, exact current-pointer verification, and a real identical retry. These require the production R2 object and are not replaced by CI simulation.

The next engineering loop is Section C historical evidence datasets. It must not redesign System-1 or Stage-4B.


## Production verification gate — 2026-09-21

A dedicated read-only production verification workflow is now present at
`.github/workflows/r2_screener_production_verification.yml`. It is designed to
use the existing `data-latest/screener_prices.parquet` release artifact, verify
the expected production SHA/date, perform the live manifest/current/object/HEAD/SHA
audit, execute an **actual identical immutable retry** through
`scripts/r2_publish.py`, and perform a second live audit.

Current expected production evidence:
- as_of: `2026-09-21`
- SHA-256: `df03ed6d6fb9c8ca963c4f3fb3b73386c43e6f106cc9a3307d7b693cf80455dd`

The workflow was executed against the real R2 object: Run #1 / Run ID 35635710984 passed manifest/current/object/HEAD/SHA read-back, an identical immutable retry, and post-retry verification.

## Section-C coordination

PR #49 (historical evidence bootstrap) is merged and must not be duplicated.
The bootstrap established source-faithful constituent evidence, point-in-time
membership, sparse confirmed-session evidence, the initial NSE market-cap snapshot,
and corporate-action evidence with explicit provenance.

The observed-session and dated-market-cap builders are present on main and both
have completed live R2 publication/read-back verification.

No Yahoo raw-price rebuild is authorized by this tracker; it remains parked.

## B. R2 publication integrity — do now, independent of Screener

- [x] Content-addressed revisions.
- [x] Same-date different-byte revisions are preserved.
- [x] Same-byte retry is idempotent.
- [x] Manifest is immutable.
- [x] Current pointer is explicit.
- [x] Object PUT/HEAD/GET/SHA verification exists.
- [x] Publisher now re-reads and verifies object + manifest + current pointer.
- [x] Standalone archive-audit command for arbitrary dataset/date.
- [x] Negative tests for pointer/manifest/object mismatch.
- [x] Schema validation/version enforcement for archived datasets.
- [x] Archive no-shrinkage/coverage audit tooling, including interior-session continuity.

## C. Historical evidence datasets — after publication hardening

- [x] Index constituent snapshots — bootstrap evidence published through the immutable R2 publisher.
- [x] Point-in-time membership logic — bootstrap intervals published with provenance.
- [x] Confirmed trading-session evidence — kept separate and explicitly sparse/source-confirmed.
- [x] Observed trading-session archive — 1,161 sessions, 2016-09-23 → 2026-09-21; live R2 publication/read-back verified.
- [x] Dated historical market-cap snapshots — 21 explicit snapshots, 2026-08-18 → 2026-09-18, 15,750 rows; live R2 publication/read-back verified.
- [x] Corporate-action evidence archive — published with source/evidence URI/date.
- [x] ~~Raw source snapshots where useful.~~ Closed 2026-09-25 as not needed: every implemented dataset already carries source, evidence date and commit provenance, and no consumer needs the raw vendor payloads.
- [x] Source provenance/evidence dates carried by the implemented historical datasets.

## D. Raw Yahoo reproducibility — PARKED 2026-09-22

The isolated Yahoo raw acquisition work remains preserved as reproducibility evidence,
but **Yahoo is no longer an active R2 acceptance or migration path**.

Verified evidence retained:
- Two independent 10Y Yahoo runs returned 750/750 symbols, 0 missing, 2,475 sessions,
  2016-09-21 → 2026-09-21.
- Run #3 published the raw artifact to R2 and verified immutable publication.
- The exact raw artifact and diagnostic workflows remain available for future research.

Decision:
- Do **not** spend further engineering time on Yahoo-vs-Screener equivalence.
- Do **not** attempt V1 consumer migration to Yahoo.
- Do **not** make Yahoo corporate-action attribution a blocker for R2 acceptance.
- Keep the raw Yahoo artifact immutable as optional provenance/reproducibility evidence.
- The canonical production price path remains the verified Screener publication.

The previously generated Yahoo equivalence/corporate-action diagnostics are historical
evidence only. They do not alter V1, System-1, rankings, or the canonical price path.

## E. R2 consumer layer


- [x] R2 read adapter for analytical datasets — manifest-pinned `R2DatasetReader` resolves current or explicit revisions and verifies manifest identity, HEAD size, object SHA, and byte size.
- [x] Research/backtest reader — separate manifest-pinned consumer adapter; it accepts an explicit dataset/as_of/revision SHA and never falls back to the mutable current pointer. No ranking, price, universe, or Stage-4B logic is moved into R2.
- [x] Research/backtest live R2 acceptance — Final Acceptance Run 35704396591 passed the live immutable research acceptance against the pinned revision.
- [x] Controlled research fallback — explicit opt-in local/release artifact fallback; no silent fallback and no R2 write-back.
- [x] Streamlit reader boundary behind a feature flag — disabled by default; when enabled for production it follows the latest validated `current.json` revision for `prices/screener`.
- [x] Controlled fallback to release/local artifacts — research consumers may use explicit opt-in fallback; the production Streamlit reader does **not** silently fall back.
- [x] Manifest-pinned research runs — immutable pin adapter implemented and live acceptance verified by Final Acceptance Run 35704396591.
- [x] Point-in-time membership consumer contract — isolated under `r2/consumers/`, fail-closed on unknown coverage and duplicate active intervals.
- [x] Live point-in-time universe reconstruction acceptance — Final Acceptance Run 35704396591 passed live PIT membership acceptance.


## CI isolation — VERIFIED 2026-09-22

R2 and V1/Stage-4B are now separate CI tracks.

- R2-only paths run **R2 Focused Validation** rather than the expensive V1 Full Validation suite.
- V1 Full Validation and V1 Production QA ignore R2-only paths.
- R2 Focused Validation remains the canonical gate for R2 changes.
- V1 Full Validation now excludes R2 paths and no longer executes Stage-4B live archetypes.
- Stage-4B live archetypes are retained in `.github/workflows/stage4b-independent-validation.yml` and run only on dedicated Stage-4B branches or manual dispatch.
- This removes Stage-4B latency/failure coupling from the V1/R2 engineering loop without deleting or weakening any Stage-4B executable checks.

This is intentional: R2 acceptance is based on R2 evidence. SANSERA, ANANDRATHI, PAYTM, YATHARTH, and LENSKART are V1/Stage-4B research workloads and are not R2 acceptance tests.

## Current production contract — Streamlit R2 read path

The production Streamlit R2 reader is a **daily-current consumer**, not a manually pinned deployment.

- Feature flag: `R2_STREAMLIT_READER_ENABLED`.
- Dataset: `R2_STREAMLIT_DATASET`, default `prices/screener`.
- When enabled, the reader resolves the latest accepted `current.json` pointer and then reads the referenced immutable revision.
- The immutable revision SHA is still the historical identity of the exact bytes consumed, but it is **not** a Streamlit secret that must be changed every day.
- The daily Screener publication creates/preserves an immutable revision and advances `current.json` after validation.
- Streamlit cache TTL allows the application to pick up the newly published daily revision without editing deployment configuration.
- A read/integrity failure fails closed. The application does not silently switch to Yahoo or another source.
- Research/backtest consumers remain explicitly pinned to dataset/as_of/revision SHA and do **not** use `current.json`.

This distinction is intentional:

```
Production Streamlit:
current.json -> latest validated immutable revision -> live app

Research/reproducibility:
explicit SHA -> exact immutable revision -> reproducible run
```

Deployment configuration therefore requires only the existing five R2 credentials plus:

```toml
R2_STREAMLIT_READER_ENABLED = "1"
R2_STREAMLIT_DATASET = "prices/screener"
```

No daily `R2_STREAMLIT_AS_OF` or `R2_STREAMLIT_REVISION_SHA256` is required.

## F. Operations / governance

- [x] Archive inventory/audit report — read-only inventory tool and scheduled/manual workflow live-verified successfully (Run ID 35642709261).
- [x] Coverage/continuity observability — scheduled observed-session continuity audit added; it reconstructs the canonical release dataset and fails closed on duplicate, unsorted, non-NSE, or non-session rows.
- [x] Failure/recovery tests — current-pointer full read-back recovery audit and unit coverage are implemented; combined final acceptance workflow now executes the live recovery audit.
- [x] Retention policy before any deletion mechanism — documented as retain indefinitely until explicit recovery/reproducibility prerequisites are met.
- [x] R2 request/storage cost observability — read-only manifest inventory reports immutable revision count/bytes and audit-derived LIST/HEAD operations; provider billing remains external.
- [x] Document recovery procedure from R2 alone — `docs/R2_RECOVERY_AND_RETENTION.md`.

## Operating rule

The current Screener 10Y workflow is a long-running acquisition and must not
block Sections B–F. When it finishes, validate its real data as evidence; do
not use its eventual green status as a substitute for object, manifest,
coverage, and read-back verification.


## Section-C publication state

Section-C bootstrap is merged. The observed-session archive and dated market-cap
history are both live-verified R2 datasets. The observed archive contains 1,161
sessions (2016-09-23 → 2026-09-21). The dated market-cap archive contains 21 explicit
snapshots (2026-08-18 → 2026-09-18; 15,750 rows).

The sparse confirmed-session dataset remains separate from observed sessions. It is
source evidence, not a complete exchange calendar. The observed dataset records
sessions actually present in the production price archive and is the appropriate
contract for archive continuity/read-coverage checks.

## Yahoo raw verification status — 2026-09-22

The real Yahoo raw acquisition is now proven reproducible at the acquisition level: two independent 10Y runs returned the full 750-symbol NIFTY TOTAL MARKET universe with zero missing symbols and the same 2,475-session date range. The second run was deliberately non-publishing and produced a separate workflow artifact.

Run #3 published the raw artifact to R2 and the publisher verified the immutable object, manifest, and current pointer. The remaining Yahoo-specific gate is an **exact-byte retry using the already captured Run #3 artifact**, not a fresh Yahoo download. A separate equivalence workflow now compares the exact raw artifact's project-adjusted closes with the canonical V1 archive without modifying either source. This is implemented in `.github/workflows/r2_yahoo_raw_retry.yml` and is intentionally manual so the exact source artifact is explicit.

No V1 consumer has been switched to raw Yahoo prices. Equivalence and migration remain blocked until the exact retry and comparison evidence are complete.

## Immediate next loop

1. **R2 acceptance is complete.** Bootstrap Run 35703827204 and Final Acceptance Run 35704396591 are green.
2. Keep the published Screener, PIT membership, observed-session, market-cap, and corporate-action datasets under routine audit.
3. Use the manifest-pinned R2 reader for research/backtest work where historical reproducibility is required; research remains explicitly SHA-pinned. Streamlit production, when enabled, follows the validated R2 current pointer.
4. Streamlit R2 production consumption is implemented behind its separate feature flag and equivalence gate. When enabled, it follows the validated daily `current.json` revision; when disabled, the canonical existing Screener path remains unchanged.
5. Continue Stage-4B independently.
6. Yahoo remains parked optional evidence.


## Verified production milestones — 2026-09-21

### Screener R2 production gate: VERIFIED

Production verification workflow run **#1 / Run ID 35635710984** completed SUCCESS.

Verified against the real `data-latest/screener_prices.parquet`:
- release SHA-256 = `df03ed6d6fb9c8ca963c4f3fb3b73386c43e6f106cc9a3307d7b693cf80455dd`
- as_of = `2026-09-21`
- live manifest read-back = PASS
- `current.json` pointer identity = PASS
- live object HEAD/byte/SHA verification = PASS
- immutable object SHA = `df03ed6d6fb9c8ca963c4f3fb3b73386c43e6f106cc9a3307d7b693cf80455dd`
- object size = 5,381,737 bytes
- actual identical retry = PASS; existing revision and manifest were re-read and verified
- post-retry live verification = PASS

This closes all four production Screener verification boxes that were previously open.

### Observed trading-session archive: VERIFIED

Workflow run **#1 / Run ID 35637235582** completed SUCCESS using the production Screener release:
- 1,161 observed sessions
- 2016-09-23 → 2026-09-21
- R2 revision SHA = `e6b9f2e02fac818dc8b72a4e090a9c982e616b3df73dbbe6d5965259cdae8923`
- live R2 publication = PASS
- standalone R2 read-back audit = PASS
- object size = 13,270 bytes

### Validation

V1 Full Validation run **#553 / Run ID 35637235543** completed SUCCESS on the same main commit:
- full regression suite = PASS
- compile = PASS
- Stage-2 hand-off = PASS
- Stage-3 hierarchy = PASS
- all five Stage-4B live archetype executions = PASS
- deprecated Streamlit cleanup = PASS
- headless Streamlit smoke test = PASS

The next engineering work is now live PIT consumer acceptance, manifest-pinned research/backtest consumption, and the remaining operational gates; the Screener production gate is no longer a blocker.


## Final acceptance loop — 2026-09-22

PR #72 merged the explicit opt-in research fallback and read-only cost-observability gates. PR #73 merged the combined R2 final acceptance workflow, which exercises focused regression, live PIT membership acceptance, an explicit immutable research revision, the recovery audit, and cost observability.

The r2_cost_audit.main() argparse argv leak and the self-referential Stage-4B marker
scan in r2-focused-validation.yml were resolved in this session (branch
claude/pr-75-4b-interference-8ndpep / PR #76). The r2-focused CI gate is now green.

Contract tests for the r2_final_acceptance.yml step ordering and required arguments are
added in tests/test_r2_final_acceptance_contract.py and run as part of the r2-focused
validation gate.

The live execution result for the two Section E items (PIT membership, research pin)
is intentionally not marked PASS until GitHub Actions provides actual run evidence
with real R2 credentials.

### Membership dataset path fix — 2026-09-22

R2 Final Acceptance run #2 (ID 35676371725) failed at "Live PIT membership acceptance":

```
FileNotFoundError: no current R2 pointer for dataset indices/membership
```

Root cause: `MEMBERSHIP_DATASET = "indices/membership"` in `r2/consumers/r2_historical.py`
but the bootstrap published to `indices/membership/nifty_total_market`. The constant
was updated to `"indices/membership/nifty_total_market"` to match the published path.


## Final R2 acceptance — VERIFIED 2026-09-22

The historical-evidence bootstrap and final acceptance gates are now closed on live R2 data.

### Bootstrap
- Workflow Run **35703827204** — GREEN.
- All substantive bootstrap steps passed: build/tests, constituent snapshots, PIT membership, confirmed sessions, market caps, corporate actions.
- PIT membership is published under `indices/membership/nifty_total_market/2026-09-18`.
- Immutable membership revision: `cd820a04f4d085c8317a269e49187ce22f06004558c30e2f77f22ce7e2eb9058`.

### Final Acceptance
- Workflow Run **35704396591** — GREEN.
- **R2 regression** — PASS.
- **Live PIT membership acceptance** — PASS.
- **Live immutable research acceptance** — PASS.
- **Live recovery audit** — PASS.
- **Live cost observability** — PASS.

Therefore the remaining unchecked Section-E live acceptance items are closed. R2 is now an accepted historical-data/evidence substrate.

### Re-acceptance on current head — 2026-09-25

A real NSE index constituent change (HEGAM added, HEG removed on 2026-09-23) broke a
snapshot assertion in `test_r2_historical_evidence.py`. PR #152 replaced the stale
`changes == []` check with the correct contract (rows covering MEMBERSHIP_AS_OF must
exist). R2 Final Acceptance run #8 (ID 36082580748) then passed on the PR #152 merge
commit `6e381e1c`:

- **R2 regression** — PASS (83 tests, HEGAM change correctly handled).
- **Live PIT membership acceptance** — PASS.
- **Live immutable research acceptance** — PASS.
- **Live recovery audit** — PASS.
- **Live cost observability** — PASS.

### Historical acceptance boundary — superseded by the current production contract
At the time of Final Acceptance Run 35704396591, Streamlit had not yet been switched to R2. The later Streamlit read-path gate is documented below and is now the controlling production contract.


---

## Current R2 consumer-hardening closure — 2026-09-22

The post-acceptance immutable-consumer hardening loop is merged on main.

- PR #92 — PIT membership consumer no longer requires current.json; it resolves the latest immutable revision for the exact evidence date.
- PR #93 — research pin validation and integrity failures were hardened; invalid revision identities fail closed and live validation reports integrity failures cleanly.
- PR #94 — immutable revision resolution now requires an exact ISO YYYY-MM-DD evidence date and timezone-aware created_at metadata; research storage-integrity failures are normalized at the consumer boundary.
- PR #95 — explicit research fallback no longer catches arbitrary programming exceptions; fallback occurs only for known consumer/storage failures.
- PR #96 — research pins now require an exact ISO YYYY-MM-DD evidence date rather than accepting timestamp-like values.

Post-merge R2 Focused, R2 Research Consumer, and PIT membership acceptance gates were green for the completed merges. These changes remain confined to R2 storage/consumer boundaries and do not alter System-1 ranking, the canonical Screener production price path, universe methodology, or Stage-4B research logic.

The remaining R2 work is routine provenance/operational hardening only where it materially improves reproducibility or recovery. Streamlit production consumption is governed by the daily-current read-path contract below.


## Canonical status — 2026-09-22 (supersedes earlier working notes)

**R2 implementation and acceptance are complete.** Bootstrap Run 35703827204 and Final Acceptance Run 35704396591 passed on live R2. PRs #92–#100 subsequently hardened the immutable PIT/research consumers, manifest validation, recovery audit, and publication provenance. These are hardening changes only; they do not open a new R2 implementation phase.

The R2 storage/evidence foundation is accepted. Research consumers remain explicitly pinned. Streamlit production consumption is separately gated and, when enabled, follows the latest validated Screener revision through `current.json`. No System-1 methodology changes are part of this path.


## Production Streamlit read path — daily current revision

The Streamlit R2 production reader now follows the **latest validated `current.json` pointer** for `prices/screener`. It does not require a manually maintained `as_of` or revision SHA.

- `R2_STREAMLIT_READER_ENABLED` defaults OFF.
- When enabled, the app reads the configured dataset through `R2DatasetReader.resolve_current()`.
- Every published revision remains immutable and content-addressed for historical reproducibility.
- The mutable `current.json` pointer is updated by the validated R2 publication workflow after a new daily dataset is accepted.
- An archive read/integrity failure fails closed; the app does not silently switch to Yahoo.
- The Streamlit cache is time-limited, so a daily publication is picked up automatically without editing Streamlit secrets.
- The real-credential production gate compares the live current R2 revision with the canonical Screener release artifact and validates the same `from_screener` transformation.

### Two distinct price feeds in the Streamlit process

The production application intentionally has **two different price-data roles**:

1. **Ranking feed:** when the R2 reader is enabled, the Screener ranking dataframe is read from R2 via `current.json`. This is the price source named by the ranking contract and by `price_source`.
2. **Deep-history feed:** the existing `fetch_price_history()` path still loads the Yahoo-backed local price cache. It supplies longer history needed by backtest/track-record pages and is not evidence that the ranking used Yahoo.

Therefore a cold-start log may legitimately contain a Yahoo/snapshot download even while the front-page ranking is R2-backed. The authoritative provenance line is:

`Ranking price source selected: source=r2 ...`

and the R2 revision is logged separately as:

`Screener ranking store: source=R2 dataset=prices/screener as_of=... revision=...`

When R2 is disabled, the corresponding ranking line is `source=screener` and the store line identifies `published_screener_https`. This removes ambiguity between the deep-history transport and the ranking source.

### Production configuration

Only the R2 credentials and the feature flag/dataset selection are deployment configuration. No daily SHA or date needs to be edited in Streamlit.

```toml
R2_STREAMLIT_READER_ENABLED = "1"
R2_STREAMLIT_DATASET = "prices/screener"
```

The existing five R2 credential secrets remain unchanged.

This migration changes only the source of the existing Screener dataframe. It does not change System-1 formulas, ranking weights, benchmark, universe, corporate-action methodology, or Stage-4B logic.


## Historical Research Data Foundation — active expansion 2026-09-22

This expansion completes the durable R2 inputs needed for future point-in-time backtests, while deliberately excluding historical fundamentals because no suitable source is currently available.

- [x] Screener daily price archive — existing canonical R2 path.
- [x] Yahoo raw deep-history archive — existing independent R2 path.
- [x] Market-cap history — `r2_market_cap_history.yml`, daily; `market_caps/nse_history` live through 2026-09-23.
- [x] **Five-index PIT membership history** — NIFTY 50, NIFTY Next 50, NIFTY Midcap 150, NIFTY Smallcap 250, NIFTY Microcap 250. `indices/membership/*` live (historical evidence bootstrap).
- [x] Combined point-in-time universe archive derived from those five histories — `universes/point_in_time` live.
- [x] Official NSE OHLC history for those five indices — `r2_nse_index_prices.yml`, daily; `indices/prices/research` live through 2026-09-23.
- [x] Historical sector/industry classification from dated repository evidence — `classifications/tv_history` live. The R2 copy is stamped 2026-08-15 by older code; the current builder stamps the latest evidence date and replaces it on the next bootstrap run.
- [x] Observed and confirmed trading-session evidence.
- [x] Corporate-action evidence archive.
- [x] Immutable System-1 ranking-calculation archive — `r2_ranking_archive.yml`, daily; `calculations/rankings` live.
- [x] Final live coverage/read-back acceptance for the expansion — replaced by a standing check: `scripts/r2_inventory.py` fails the daily R2 archive inventory when any daily dataset (`DAILY_DATASETS`) is missing or more than 6 days old, and the scheduled-failure alert opens an issue. R2 Final Acceptance run #8 (2026-09-25) covers membership and market caps.

Status verified 2026-09-25 against the live R2 inventory (run 35971204524) and workflow history.

**Next trigger, not started:** the backtester still reads `data/membership_history.json`. Moving it to the R2 membership archive adds nothing yet, because both are rebuilt from the same committed index snapshots, which start 2026-08-15, and the reported backtest window is the last six completed months. Revisit once the archive covers that window (about February 2027), or earlier if a deeper historical membership source is found.

### Hard rules for this expansion

1. Do not alter System-1 ranking methodology, benchmark, canonical Screener price source, or Stage-4B.
2. Do not hard-code symbol aliases for universe churn. Current NSE membership remains authoritative for current operation; historical membership is reconstructed from dated evidence.
3. Apply the central `is_tradeable_symbol()` predicate to every index-universe archive so DUMMY* rows cannot enter the research universe.
4. Keep source datasets separate. NSE index prices remain NSE-source evidence; Yahoo stock history remains Yahoo-source evidence; Screener remains the canonical V1 stock-price source.
5. Preserve immutable revisions/manifests/current pointers for every published dataset.
6. Derived calculations are reproducible from archived inputs, but canonical ranking outputs are also archived as immutable calculation evidence.
7. Fundamental history is explicitly out of scope until a real point-in-time source is available.
8. The expansion is accepted only after automated tests, live publication, manifest/current/object read-back, coverage validation, and consumer/reconstruction checks are green.
