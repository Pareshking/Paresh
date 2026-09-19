# Stage 2 — Quantitative Hand-off Plan

Date: 2026-09-19
Branch: agent/foundation-v1
Status: PLAN RECORDED — implementation authorized

## Objective

Expose the existing published `rankings.parquet` artifact to the research-agent layer as a validated, read-only `QuantSnapshot`.

Normal path:

`published rankings.parquet → artifact/contract validation → QuantSnapshot → downstream research`

The adapter must preserve the canonical System-1 output exactly. It is an integration boundary, not a ranking implementation.

## Repository evidence inspected before implementation

The following existing owners/callers were inspected:

- `src/loaders/ranking_store.py` — published ranking artifact acquisition, embedded contract, contract matching, safe reads.
- `scripts/sync_data.py::_precompute_rankings()` — canonical artifact producer; calls `src.engine.pipeline`.
- `app.py::_fetch_ranking_snapshot()` and `_precomputed_ranking()` — existing production consumer and contract-validation path.
- `src/core/config.py` — canonical benchmark, universe-related configuration, ranking price source, rolling release URL.
- `src/engine/pipeline.py` — canonical ranking owner, pipeline version, ranking as-of rule and fingerprints.
- `tests/test_precomputed_ranking.py` — artifact contract/regression coverage.
- `agent/contracts.py`, `agent/fingerprint.py`, `agent/run.py` — Stage-1 agent boundary and provenance contracts.

## Existing capability ownership

No Stage-2 replacement is permitted for:

- ranking mathematics;
- price acquisition;
- corporate-action adjustment;
- universe construction;
- membership;
- sector/industry taxonomy;
- breadth;
- portfolio construction;
- backtesting;
- track record.

The adapter may call the existing `ranking_store` read path and inspect the returned artifact/contract.

## Validation design

The adapter will validate, without recomputation:

1. artifact exists and can be read;
2. embedded contract exists;
3. contract fields required for provenance are present;
4. pipeline version matches the current canonical pipeline identity;
5. configured ranking price source matches the artifact;
6. artifact `price_as_of` is a valid ISO date;
7. artifact `price_as_of` is not after the snapshot date;
8. benchmark/universe/model identity is attached from the canonical agent configuration;
9. artifact rows have the minimum identity columns required for downstream research;
10. symbols are non-empty and unique;
11. rank values are positive when present;
12. rows are copied/read-only at the adapter boundary and never recalculated;
13. source artifact URL/path is retained in provenance.

## Deliberate limitation

The adapter must not manufacture a new expected price fingerprint from a newly downloaded price frame. The artifact's embedded fingerprint remains provenance for the data used by the producer.

If an independent price-frame audit is needed later, that is an explicit audit path and must be separately labelled.

## Output

The adapter returns a `QuantSnapshot` containing:

- artifact rows exactly as published;
- artifact `price_as_of`;
- current canonical benchmark/universe/model identity;
- current configuration fingerprint;
- artifact pipeline version;
- artifact price source;
- source artifact URL.

The adapter does not select a different ranking or alter rank/score/factor values.

## Failure policy

Fail closed with a specific exception when:

- artifact is missing/unreadable;
- contract is missing;
- required contract identity is missing;
- pipeline version differs;
- price source differs;
- price-as-of is missing/invalid;
- rows are empty;
- required row identity columns are absent;
- duplicate/empty symbols exist;
- invalid rank values exist.

No fallback to live ranking calculation is allowed inside the agent hand-off.

## Testing plan

Unit tests will cover:

- valid artifact → snapshot;
- missing artifact;
- missing contract;
- pipeline-version mismatch;
- price-source mismatch;
- missing/invalid/as-future price-as-of;
- empty rows;
- missing Symbol;
- duplicate Symbol;
- invalid Rank;
- preservation of Score/factor columns and values;
- no call to `pipeline.build_engine` or `rank_with_weights`;
- source artifact provenance;
- deterministic Top-25 helper if implemented.

## PDCA / adversarial checks

### Prosecution

- What existing function already does this?
- Does the adapter download prices?
- Does it call the ranking engine?
- Can a malformed artifact pass?
- Can a future/as-of-incoherent artifact pass?
- Can duplicate symbols pass?
- Can the adapter silently substitute another artifact?

### Defence

- Does the adapter use the canonical artifact reader?
- Are canonical pipeline/source identities preserved?
- Is the artifact row data untouched?

### Reviewer

- Can every snapshot field be traced to artifact or canonical config?
- Are errors explicit?
- Are tests checking failure modes rather than only happy paths?

### Jury

Record unresolved limitations, especially the distinction between artifact provenance and independent quantitative audit.

### Judge / exit gate

Stage 2 may complete only if:

- the adapter is the only new quantitative hand-off owner;
- no ranking/data-download duplicate exists;
- artifact rows equal adapter rows;
- all mandatory failure tests are covered;
- provenance is complete;
- documentation is updated;
- actual execution/CI status is recorded honestly.

## Implementation sequence

1. Record this plan before code.
2. Add the smallest adapter.
3. Add focused Stage-2 tests.
4. Run available checks.
5. Re-audit against production artifact ownership and Stage-1 contracts.
6. Update Master Spec only if implementation exposes a rule gap.
7. Update Development Tracker with PLAN/DO/CHECK/ACT and exact verification status.
8. Update Stage-2/Stage-1 documentation.
9. Report discrepancies/blockers without marking them passed.

## Non-goals

- No company research.
- No external news/filing research.
- No market/sector/industry analysis.
- No LLM/API integration.
- No ranking changes.
- No portfolio changes.
- No automation.


## Adversarial refinement — canonical price-source fallback

Repository review of `src/loaders/price_source.py` after implementation exposed an important nuance: the canonical producer prefers Screener when configured, but deliberately falls back to Yahoo when the Screener store is unavailable or too short. The adapter was therefore hardened to accept `screener` or the documented `yahoo` fallback when Screener is preferred, while rejecting non-canonical source identifiers. A regression test covers both the fallback acceptance and unknown-source rejection.


## Stage-2 gate reopening — 2026-09-19

The current-head GitHub Actions run exposed two regression failures after the implementation was pushed. Stage 2 is therefore **REOPENED** before any Stage-3 work.

### Observed failures

1. `tests/test_agent_quant_hand_off.py::test_contract_mismatch_fails_closed[change1-price_source]` expected every Yahoo artifact to be rejected. That conflicts with the inspected canonical producer: when Screener is preferred, Yahoo is a documented fallback. The test is stale, not the adapter contract.
2. `tests/test_precomputed_ranking.py::test_moving_a_weight_slider_misses_rather_than_serving_the_wrong_table` still exercises a contract without `price_as_of`. Because `matches()` now correctly checks `price_as_of`, the failure reason becomes `price_as_of differs` before reaching the intentionally changed weights. The regression test fixture must include a coherent `price_as_of` so it isolates the weight invariant.

### Repair plan — before code changes

- Inspect the exact failing assertions and current canonical price-source semantics.
- Update the Stage-2 hand-off test to distinguish a legitimate Yahoo fallback from a non-canonical source mismatch.
- Update the precomputed-ranking regression fixture so the weight test isolates weights rather than an unrelated missing as-of field.
- Preserve the production contract semantics; do not weaken validation merely to satisfy the old tests.
- Run the full GitHub regression workflow on the repaired head.
- If failures remain, repeat the adversarial loop before considering the gate.
- Do not begin Stage 3 until the repaired head has successful runtime evidence and the live artifact/parity checks are addressed.

### Gate rule

The observed CI failure is evidence that Stage 2 is **not complete**. No green-by-assumption status is permitted. The gate remains open until the repaired implementation is actually executed and verified.
