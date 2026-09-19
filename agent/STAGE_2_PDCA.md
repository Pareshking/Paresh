# Stage 2 — Quantitative Hand-off PDCA Record

Date: 2026-09-19
Branch: agent/foundation-v1
Status: IMPLEMENTED — VERIFICATION OPEN

## PLAN

The goal was to expose the existing published rankings.parquet as a read-only QuantSnapshot without recreating any quantitative pipeline.

The repository was inspected first. The written plan was recorded in agent/STAGE_2_PLAN.md before implementation.

## DO

Implemented:

- agent/quant_hand_off.py
- tests/test_agent_quant_hand_off.py

The adapter:

1. calls the existing ranking_store.fetch_snapshot();
2. requires the embedded contract;
3. validates pipeline version against pipeline.PIPELINE_VERSION;
4. validates price source against config.RANKING_PRICE_SOURCE;
5. validates canonical default lookback weights;
6. validates ISO price_as_of;
7. validates contract universe;
8. validates Symbol, Rank and Score columns;
9. validates non-empty and unique symbols;
10. validates that row symbols belong to the contract universe;
11. validates positive numeric ranks;
12. preserves the artifact source and as-of in QuantSnapshot;
13. never invokes build_engine or rank_with_weights;
14. does not download prices or create a fallback ranking path.

## CHECK

### Prosecution

The first question was whether Stage 2 had accidentally rebuilt functionality already present in Paresh. It did not. Artifact acquisition remains owned by ranking_store, while ranking mathematics remains owned by pipeline.

The main failure cases are explicitly rejected rather than silently substituted.

An additional adversarial check found that validating the contract universe alone was insufficient: a row could theoretically name a symbol outside that universe. The adapter was hardened to reject this, and a regression test was added.

### Defence

The adapter is deliberately small and read-only. Quantitative values come from the artifact returned by the canonical reader. No independent score, rank, momentum, volatility, breadth or price calculation exists in the adapter.

### Reviewer

Traceability:

- pipeline_version → embedded artifact contract and canonical pipeline;
- price_source → embedded artifact contract and canonical config;
- weights → embedded artifact contract and canonical config;
- price_as_of → embedded artifact contract;
- quantitative rows → published artifact;
- benchmark/model/universe label → current canonical agent/repository identity;
- source_artifact → configured or explicitly supplied ranking artifact location.

### Jury

The structural design satisfies the intended hand-off boundary.

Two verification questions remain unresolved because executable infrastructure was not available:

- Does the test file execute successfully in the repository runtime?
- Does the live published rankings.parquet currently pass the adapter and produce the expected rows/provenance?

These are recorded as NOT VERIFIED, not assumed.

### Judge

Stage 2 cannot be declared complete yet.

## ACT

The implementation is retained, documentation has been reconciled, and Stage 2 remains open pending:

1. actual pytest/CI execution;
2. live artifact end-to-end execution;
3. quantitative parity comparison between artifact rows and QuantSnapshot rows;
4. final Stage-2 gate review.

No Stage 3 work should begin before these conditions are satisfied.

## Files changed

- agent/STAGE_2_PLAN.md
- agent/quant_hand_off.py
- tests/test_agent_quant_hand_off.py
- agent/AI_AGENT_MASTER_SPEC.md
- agent/AI_AGENT_DEVELOPMENT_TRACKER.md
- agent/STAGE_1_PDCA.md
- agent/REPO_REVIEW_2026-09-19.md
- agent/README.md

## Verification limitation

The connected GitHub interface reported no workflow runs for the current head. There is no local full repository checkout in this environment, so no local pytest execution is claimed.

## Exit gate

NOT PASSED — runtime/CI/live-artifact evidence is still required.


## Adversarial refinement after initial implementation

A second prosecution pass inspected `src/loaders/price_source.py` rather than assuming the configured preference was always the actual artifact source. The producer can legitimately stamp `price_source=yahoo` when Screener is preferred but unavailable/too short. The adapter initially required an exact preference match; that would have rejected a valid canonical fallback artifact. This was corrected to mirror the producer's documented source-selection semantics without downloading or reconstructing prices. Focused tests now cover the fallback and non-canonical source cases.


## Gate reopening and final verification — 2026-09-19

### PLAN / REOPEN

GitHub Actions exposed two test defects after the initial implementation. Stage 2 was explicitly reopened before repair. The plan was updated before code changes.

### DO

- Corrected the source-mismatch test so it rejects a non-canonical source rather than the documented Yahoo fallback when Screener is preferred.
- Corrected the precomputed-ranking weight regression fixture to carry a coherent `price_as_of`, isolating the weight invariant.
- Added an existing-CI verification step that executes `load_quant_snapshot()` against the real published `rankings.parquet` before the broader quantitative integration check.

### CHECK — execution evidence

The repaired GitHub Actions run `V1 Full Validation #258` executed against the PR merge ref containing the repaired head.

**VERIFIED:**

- Full regression suite: **1099 passed** in 78.95s.
- Compile application/source: **PASS**.
- Real published Stage-2 hand-off: **PASS**.
- Live artifact as-of: **2026-09-18**.
- Live artifact rows accepted: **750**.
- Pipeline version: **v4_calendar_periods_cbab8da9**.
- Actual artifact price source: **screener**.
- Source artifact: the canonical `data-latest/rankings.parquet` release asset.
- Adapter executed through the real `ranking_store.fetch_snapshot()` path; no ranking engine or price download was introduced by the adapter.

### Prosecution

The repaired hand-off now has both unit/regression evidence and real-artifact execution evidence. The remaining red workflow step is not a Stage-2 hand-off failure: `scripts/full_validation.py` fails later on its existing hard floor of 700 finite ranked scores while the current price session had only 430/750 priceable symbols. The run therefore stops before Streamlit smoke testing. This is recorded as a separate canonical quantitative-validation issue, not hidden or reclassified as a Stage-2 pass.

The live hand-off itself passed before that failure, so the red full-validation result does not invalidate the observed Stage-2 artifact acceptance.

### Defence

The adapter was not weakened to accommodate the failing full-universe check. The source fallback rule was preserved from the canonical producer, and the live artifact was accepted only after contract, source, weight, as-of, universe and row validation.

### Reviewer

The evidence chain is now:

`data-latest/rankings.parquet → ranking_store.fetch_snapshot() → contract validation → row validation → QuantSnapshot`

No independent ranking calculation exists in the Stage-2 adapter. The live artifact reports 750 rows and the adapter preserves the artifact rows into the snapshot; focused tests cover value preservation and engine non-invocation.

### Jury

**Stage-2-specific evidence is sufficient.** The broader V1 validation workflow remains red for an unrelated/current-universe data-coverage assertion and must remain visible as a repository risk.

### Judge

**STAGE 2 GATE: PASSED.**

The Stage-2 acceptance criteria are satisfied: canonical artifact acquisition, contract validation, provenance, row integrity, no duplicate quantitative owner, focused regression coverage, full-suite execution, and real published-artifact execution are all evidenced.

The repository is **not globally green**. The unrelated full-universe validation failure is carried forward explicitly and is not treated as resolved.

### ACT

- Stage 2 is closed.
- Stage 3 may be planned, but must begin with repository inspection and a written Stage-3 plan as required by the master trigger.
- The existing full-universe validation failure remains a separate canonical-system QA issue; do not patch it inside the agent layer or silently lower its threshold.
