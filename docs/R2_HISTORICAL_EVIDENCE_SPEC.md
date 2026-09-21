# R2 Historical Evidence Dataset Contracts

**Status:** Engineering design — Section C of the R2 Engineering Loop  
**Last updated:** 2026-09-21 (observed-session archive implemented/verified; dated market-cap publication pending live verification)  
**Scope:** Historical evidence required for point-in-time research and survivorship-bias-aware analysis.

This document converts the original R2 architecture requirements into implementation boundaries. It does not start the parked Yahoo raw-price rebuild.

## R2 / stock-research boundary

Historical evidence stored in R2 is an infrastructure/data contract. It is **not** the Stage-4B research layer.

R2 owns the preservation and reproducibility of source evidence: immutable revisions, manifests, provenance, evidence dates, checksums, coverage, and read-back. Stock research owns interpretation, ranking, hierarchy, agent reasoning, causal findings, contradictions, and Stage-4B archetype execution.

Stage-4B examples such as SANSERA, ANANDRATHI, PAYTM, YATHARTH, and LENSKART must remain outside the R2 dataset and acceptance model. They may become consumers of R2 later, but only through the dedicated reader/consumer contracts in Section E of the R2 engineering loop.

**Do not use V1 Full Validation as the R2 acceptance test.** R2 changes need R2-specific tests and live archive gates. V1/Stage-4B validation remains a separate regression track.

## 1. Non-negotiable principles

1. Historical evidence is append-only where the source permits it.
2. A current universe must never be used as a historical universe.
3. Departed symbols remain in historical price data.
4. Source datasets remain separate; no silent source splicing.
5. Every normalized dataset carries source, evidence date, schema version, and checksum metadata.
6. When a source revises history, preserve the revision rather than silently replacing prior evidence.
7. Derived point-in-time membership must remain reproducible from archived constituent evidence.

## 2. Dataset order

Implement in this order:

### C1 — Index constituent snapshots
Archive the source-faithful constituent snapshot for each tracked index and evidence date.

Logical namespace:
`indices/constituents/<index>/<evidence_date>/`

Minimum normalized fields:
- `index`
- `symbol`
- `evidence_date`
- `source`
- `collected_at`

The snapshot represents what the source published on the evidence date. It is not yet an interval membership table.

### C2 — Point-in-time membership
Derive intervals from snapshots without destroying the source snapshots.

Logical namespace:
`indices/membership/`

Minimum fields:
- `index`
- `symbol`
- `effective_from`
- `effective_to`
- `source`
- `evidence_date`

Rules:
- membership is derived from dated evidence;
- never infer a membership change without an evidence snapshot;
- open-ended current membership uses a null/open `effective_to`;
- a later correction creates a new revision and is traceable to its evidence.

### C3 — Trading sessions
Separate **observed sessions** from **exchange-confirmed sessions**. The project must not manufacture a historical calendar from weekday assumptions, and a sparse confirmed-source file must not be published as if it were complete historical coverage.

Logical namespaces:
- `trading_days/observed/` — sessions actually observed in the production price archive;
- `trading_days/confirmed/` — sessions explicitly confirmed by an exchange/source feed.

Minimum fields:
- `date`
- `market`
- `is_session`
- `source`
- `evidence_date`

The observed dataset is suitable for continuity/read-coverage audits. The confirmed dataset is source evidence and may be sparse unless full historical coverage has been established. Research consumers must declare which contract they require rather than silently treating either one as a universal calendar.

The research layer must use an archived session contract for expected-session checks rather than assuming 252 identical sessions every year.

### C4 — Historical market-cap snapshots
Archive point-in-time market-cap evidence used by universe construction or research.

Logical namespace:
`market_caps/<source>/`

Minimum fields:
- `date`
- `symbol`
- `market_cap`
- `currency`
- `source`
- `evidence_date`

Do not backfill a historical market cap using today's value.

### C5 — Corporate-action evidence
Archive evidence supporting splits, bonuses, demergers, and other events.

Logical namespace:
`corporate_actions/`

Minimum fields:
- `symbol`
- `event_date`
- `event_type`
- `effective_date`
- `ratio` or explicit adjustment terms when applicable
- `source`
- `evidence_date`
- `evidence_uri`

The existing corporate-action adjustment logic remains the consumer-side implementation. This archive is the evidence layer.

### C6 — Raw source evidence
Where useful and legally/operationally appropriate, preserve source-faithful snapshots.

Logical namespace:
`raw/<source>/`

Raw retention is a separate policy decision. Do not create a large raw-data pipeline merely to satisfy the namespace; first identify which sources provide material reproducibility value.

## 3. Manifest contract

Every published dataset/snapshot must have a manifest containing at least:

```json
{
  "dataset": "...",
  "as_of": "YYYY-MM-DD",
  "created_at": "...",
  "source": "...",
  "schema_version": 1,
  "row_count": 0,
  "symbol_count": 0,
  "min_date": "YYYY-MM-DD",
  "max_date": "YYYY-MM-DD",
  "sha256": "...",
  "pipeline_version": "..."
}
```

For source evidence, also record `evidence_date` and the source-specific provenance identifier where available.

## 4. Revision policy

Use the existing content-addressed R2 revision model.

Same date + same bytes:
- idempotent;
- no duplicate revision.

Same date + different bytes:
- preserve a new immutable revision;
- update the current pointer only after validation;
- never overwrite the old evidence.

This applies to constituent snapshots and other revisable source datasets as well as price data.

## 5. Point-in-time reconstruction contract

A research consumer must be able to request:

`membership(index, as_of)`

and obtain only symbols whose membership interval contains `as_of`.

The result must be reproducible from archived evidence and must not depend on today's constituent list.

Required future tests:
- historical member remains present after leaving the current index;
- a newly added constituent is absent before its effective date;
- correction/revision does not silently mutate an already-pinned research artifact;
- unknown/unproven membership intervals fail closed.

## 6. Agent hand-off

Completed and already implemented — do not duplicate:
- R2 storage adapter;
- content-addressed price revisions;
- immutable manifests/current pointers;
- publication read-back;
- standalone archive audit;
- mismatch tests;
- schema-version checks;
- no-shrinkage/coverage audit tooling;
- Section-C bootstrap publication path and provenance contracts.

Section-C implementation state on main:
- C1 constituent snapshots — normalized and published through the immutable R2 publisher.
- C2 point-in-time membership — normalized intervals published with evidence provenance.
- C3 confirmed trading-session evidence — published separately as sparse/source-confirmed evidence.
- C3 observed sessions — implemented from the production Screener price archive and live-verified in R2: 1,161 sessions from 2016-09-23 through 2026-09-21.
- C4 market-cap history — dated snapshot builder is implemented from Git evidence and the R2 publication workflow is on main; live R2 publication/read-back remains an open gate.
- C5 corporate-action evidence — published with source/evidence URI/date.

Do not duplicate the observed-session or market-cap builders/workflows. The next
independent work is the live market-cap verification gate, followed by consumer
integration and point-in-time reconstruction tests.

Still pending Section-C completeness:
- live verification of `market_caps/nse_history`;
- C6 raw source evidence where it provides material reproducibility value;
- full consumer acceptance tests for each dataset;
- point-in-time universe reconstruction against archived evidence.

Parked:
- Yahoo raw-price rebuild in `docs/RAW_PRICE_REBUILD.md`.

## 7. Current acceptance status

The Section-C datasets are intentionally at different maturity levels:

| Dataset | Implementation | Live R2 evidence | Consumer acceptance |
|---|---|---|---|
| Constituent snapshots | complete | bootstrap publication completed | pending |
| PIT membership | complete | bootstrap publication completed | pending |
| Confirmed sessions | complete | bootstrap publication completed | pending |
| Observed sessions | complete | **verified** — 1,161 sessions, 2016-09-23 → 2026-09-21 | pending |
| Dated market caps | complete | **open** — workflow is implemented; live publication/read-back not yet recorded | pending |
| Corporate actions | complete | bootstrap publication completed | pending |
| Raw source evidence | not started | — | — |

## 8. Acceptance gate

No historical evidence dataset is considered complete merely because an object exists in R2. Each dataset must pass:

1. source completeness check;
2. schema validation;
3. coverage/continuity validation;
4. no-shrinkage check where cumulative;
5. immutable publication;
6. manifest/current-pointer verification;
7. object read-back and checksum verification;
8. reproducible consumer test.
