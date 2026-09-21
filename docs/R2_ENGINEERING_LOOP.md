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

## B. R2 publication integrity — do now, independent of Screener

- [x] Content-addressed revisions.
- [x] Same-date different-byte revisions are preserved.
- [x] Same-byte retry is idempotent.
- [x] Manifest is immutable.
- [x] Current pointer is explicit.
- [x] Object PUT/HEAD/GET/SHA verification exists.
- [x] Publisher now re-reads and verifies object + manifest + current pointer.
- [ ] Add a standalone archive-audit command for arbitrary dataset/date.
- [ ] Add negative tests for pointer/manifest/object mismatch.
- [ ] Add schema validation/version enforcement for archived datasets.
- [x] Add archive no-shrinkage/coverage audit tooling.

## C. Historical evidence datasets — after publication hardening

- [ ] Index constituent snapshots.
- [ ] Point-in-time index membership history.
- [ ] Trading-day/session archive.
- [ ] Historical market-cap snapshots.
- [ ] Corporate-action evidence archive.
- [ ] Raw source snapshots where useful.
- [ ] Preserve source provenance and evidence dates in manifests.

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
