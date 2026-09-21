# R2 Engineering Loop — Phase Tracker

Status: active

This tracker is the working checklist for the market-data archive. Do not wait on
the long Screener deep-history acquisition to advance independent engineering
work. The production 10Y run is checked separately when it completes.

## A. Current production run — Screener 10Y

- [x] Real 10Y acquisition completes — 750 symbols, 1,161 sessions, 2016-09-23 → 2026-09-21.
- [x] Confirm complete universe walk and unresolved-symbol count — 0 unresolved.
- [x] Confirm unsettled sessions are removed.
- [x] Record rows, symbols, min/max dates, and older-session coverage — 750 symbols; 910 sessions older than 370 days.
- [x] Confirm no historical shrinkage versus the pre-run store — 277,600 existing cells preserved; +913 sessions.
- [x] Confirm R2 revision object exists.
- [x] Confirm revision SHA-256 — `df03ed6d6fb9c8ca963c4f3fb3b73386c43e6f106cc9a3307d7b693cf80455dd`.
- [x] Confirm immutable revision manifest exists.
- [ ] Confirm immutable revision manifest matches the object via live read-back.
- [ ] Confirm `current.json` points to that revision via live read-back.
- [ ] Confirm R2 HEAD + byte/hash read-back.
- [x] Confirm release asset contains the exact published artifact by SHA equality.
- [x] Confirm release/R2 SHA-256 equality — `df03ed6d6fb9c8ca963c4f3fb3b73386c43e6f106cc9a3307d7b693cf80455dd`.
- [ ] Run an identical retry/idempotency check against the live publication.
- [ ] Record final evidence in the run summary.

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

The workflow has been committed and its contract is covered by
`tests/test_r2_production_verification.py`, but its execution result is not yet verified in
this engineering session because the available GitHub action interface does not
expose manual workflow dispatch/list-all-runs. Therefore the Section-A live
verification boxes remain **OPEN** until a real Actions run proves them.

## Section-C coordination

PR #49 (`R2 historical evidence bootstrap pipeline`) is the active Section-C
implementation and must not be duplicated. Review identified four blockers that
must be resolved before merge:
1. membership interval evidence-date bug — fixed with deterministic latest-history evidence date;
2. confirmed-session dataset is intentionally sparse and explicitly typed as
   confirmed evidence, not a universal historical calendar;
3. the current market-cap dataset is explicitly published as an initial
   snapshot, not misrepresented as a historical series;
4. corporate-action evidence now carries source, evidence URI, and evidence date;
5. dedicated executable Section-C tests replaced the zero-match selector.

V1 #546 passed with 1,217+ tests and all existing Stage-2/3/4B and Streamlit gates.

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

- [ ] Index constituent snapshots — existing `build_membership_history.py` + `membership_history.json` provide the local baseline; R2 publication remains.
- [x] Point-in-time membership logic exists locally; R2 publication/manifest remains.
- [x] Trading-session archive builder implemented from observed production sessions; live R2 publication remains.
- [ ] Historical market-cap snapshots.
- [ ] Corporate-action evidence archive.
- [ ] Raw source snapshots where useful.
- [ ] Preserve source provenance and evidence dates in manifests for each historical dataset publication.

## D. Raw Yahoo reproducibility

Source design is documented in `docs/RAW_PRICE_REBUILD.md`.

- [ ] Download/store raw unadjusted Yahoo OHLCV.
- [ ] Preserve immutable raw revisions in R2.
- [ ] Apply project corporate-action adjustments at read time.
- [ ] Keep existing adjusted-price path as migration fallback.
- [ ] Prove track-record/research equivalence before switching consumers.
- [ ] Add migration and reproducibility tests.

## E. R2 consumer layer

- [ ] R2 read adapter for analytical datasets.
- [ ] Research/backtest reader.
- [ ] Streamlit reader behind a feature flag.
- [ ] Controlled fallback to release/local artifacts.
- [ ] Manifest-pinned research runs.
- [ ] Point-in-time universe reconstruction from archived membership.

## F. Operations / governance

- [ ] Archive inventory/audit report.
- [ ] Coverage/continuity observability.
- [ ] Failure/recovery tests.
- [ ] Retention policy before any deletion mechanism.
- [ ] R2 request/storage cost monitoring.
- [ ] Document recovery procedure from R2 alone.

## Operating rule

The current Screener 10Y workflow is a long-running acquisition and must not
block Sections B–F. When it finishes, validate its real data as evidence; do
not use its eventual green status as a substitute for object, manifest,
coverage, and read-back verification.


## Section-C publication state

Section-C historical evidence bootstrap is merged. It publishes repository-maintained
index constituent snapshots, point-in-time membership, confirmed-session evidence,
an explicitly named NSE market-cap snapshot, and corporate-action evidence through
the existing immutable R2 publisher.

This is a **bootstrap evidence layer**, not a claim that all historical evidence
domains are complete. In particular, confirmed trading sessions remain sparse until
the broader observed-session archive is published from production price history, and
market caps remain a snapshot until dated historical snapshots are accumulated.

## Immediate next loop

1. Execute the production Screener verification workflow against the real R2 bucket:
   manifest/current/object/HEAD/SHA read-back, then an identical immutable retry, then
   post-retry read-back.
2. Publish the broader observed trading-session archive from the production price
   history and retain the confirmed-session dataset as separate source evidence.
3. Build/accumulate dated historical market-cap snapshots rather than treating the
   2026-09-18 snapshot as a time series.
4. Then implement R2 readers/consumer integration without introducing another
   historical-data or ranking engine.


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

The next engineering work is now the remaining historical-evidence completeness and R2 consumer layers; the Screener production gate is no longer a blocker.
