# R2 Engineering Loop — Phase Tracker

Status: active — documentation synchronized 2026-09-21

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
- R2 consumer integration is a controlled later step. Until then, R2 remains an independent archive/read layer and V1 continues using its canonical existing data path.

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
- [ ] Raw source snapshots where useful.
- [x] Source provenance/evidence dates carried by the implemented historical datasets.

## D. Raw Yahoo reproducibility

Source design is documented in `docs/RAW_PRICE_REBUILD.md`.

- [ ] Download/store raw unadjusted Yahoo OHLCV.
- [ ] Preserve immutable raw revisions in R2.
- [ ] Apply project corporate-action adjustments at read time.
- [ ] Keep existing adjusted-price path as migration fallback.
- [ ] Prove track-record/research equivalence before switching consumers.
- [ ] Add migration and reproducibility tests.

## E. R2 consumer layer

- [x] R2 read adapter for analytical datasets — manifest-pinned `R2DatasetReader` resolves current or explicit revisions and verifies manifest identity, HEAD size, object SHA, and byte size.
- [x] Research/backtest reader — separate manifest-pinned consumer adapter; it accepts an explicit dataset/as_of/revision SHA and never falls back to the mutable current pointer. No ranking, price, universe, or Stage-4B logic is moved into R2.
- [ ] Research/backtest live R2 acceptance — requires a real R2 dataset/revision pin and read-back execution.
- [ ] Streamlit reader behind a feature flag.
- [ ] Controlled fallback to release/local artifacts.
- [ ] Manifest-pinned research runs.
- [x] Point-in-time membership consumer contract — isolated under `r2/consumers/`, fail-closed on unknown coverage and duplicate active intervals.
- [ ] Live point-in-time universe reconstruction acceptance — dedicated workflow merged; real R2 execution remains the acceptance gate.


## CI isolation — VERIFIED 2026-09-22

R2 and V1/Stage-4B are now separate CI tracks.

- R2-only paths run **R2 Focused Validation** rather than the expensive V1 Full Validation suite.
- V1 Full Validation and V1 Production QA ignore R2-only paths.
- R2 Focused Validation remains the canonical gate for R2 changes.
- V1 Full Validation now excludes R2 paths and no longer executes Stage-4B live archetypes.
- Stage-4B live archetypes are retained in `.github/workflows/stage4b-independent-validation.yml` and run only on dedicated Stage-4B branches or manual dispatch.
- This removes Stage-4B latency/failure coupling from the V1/R2 engineering loop without deleting or weakening any Stage-4B executable checks.

This is intentional: R2 acceptance is based on R2 evidence. SANSERA, ANANDRATHI, PAYTM, YATHARTH, and LENSKART are V1/Stage-4B research workloads and are not R2 acceptance tests.

## F. Operations / governance

- [x] Archive inventory/audit report — read-only inventory tool and scheduled/manual workflow live-verified successfully (Run ID 35642709261).
- [x] Coverage/continuity observability — scheduled observed-session continuity audit added; it reconstructs the canonical release dataset and fails closed on duplicate, unsorted, non-NSE, or non-session rows.
- [x] Failure/recovery tests — current-pointer full read-back recovery audit and unit coverage are implemented; live scheduled recovery execution remains to be evidenced.
- [x] Retention policy before any deletion mechanism — documented as retain indefinitely until explicit recovery/reproducibility prerequisites are met.
- [ ] R2 request/storage cost monitoring.
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

## Immediate next loop

1. Keep the verified Screener, observed-session, and dated-market-cap publications
   under routine audit; do not rerun the long 10Y acquisition for engineering work.
2. Complete live PIT membership acceptance through the dedicated R2 consumer workflow.
3. Continue R2 consumer work: live PIT acceptance, manifest-pinned research/backtest execution, controlled fallback, and reproducibility gates.
4. Keep Stage-4B on its independent validation track; reattach it to V1 only after its research gate is deliberately ready.
5. Finish live recovery and cost monitoring gates.
6. Keep the Yahoo raw-price rebuild parked until the R2 consumer layer is stable.


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
