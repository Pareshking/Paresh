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
