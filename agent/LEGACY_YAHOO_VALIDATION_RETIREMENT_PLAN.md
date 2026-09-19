# Legacy Yahoo Full-Validation Retirement Plan

Date: 2026-09-19
Branch: agent/foundation-v1

## Decision

Retire `scripts/full_validation.py` and remove its `Full current-universe quantitative integration` workflow step.

Reason: the production ranking path has switched to the canonical Screener-backed price-source selection and the published `data-latest/rankings.parquet` artifact. `scripts/full_validation.py` independently calls `src.loaders.price_loader.fetch_price_history()`, which is the legacy Yahoo/yfinance historical-price path. Its fixed finite-score/coverage assertions therefore validate a ranking path that is no longer the production ranking path.

## Scope

1. Delete `scripts/full_validation.py`.
2. Remove its workflow invocation from `.github/workflows/v1-full-validation.yml`.
3. Keep the Stage-2 real-artifact hand-off as the quantitative production validation boundary.
4. Keep the Stage-3 live hierarchy execution and durable artifact retention.
5. Keep the remaining application compile, deprecated-HTML guard, and Streamlit smoke-test gates.
6. Rename the final artifact upload from the obsolete `v1-quantitative-validation` label to a generic V1 validation artifact, because it may now contain Stage-3 audit evidence rather than output from the retired Yahoo script.
7. Update documentation to state that Yahoo `full_validation.py` is retired and must not be reintroduced as a production ranking gate.
8. Do not modify the canonical ranking formulas, price-source selection, Screener data path, or the existing Yahoo-related loader code used elsewhere unless a separate task requires it.

## Adversarial checks before/after

### Prosecution
- Confirm `full_validation.py` is not required by application runtime or another workflow.
- Confirm no production ranking code imports it.
- Confirm deleting the workflow step does not remove the canonical ranking-artifact validation.

### Defence
- The production artifact hand-off remains fail-closed and validates the real published 750-row ranking artifact.
- The Stage-3 live verifier runs from that same artifact.
- Compile and Streamlit smoke tests remain.

### Reviewer
- Search repository documentation/workflows for stale references.
- Verify the workflow no longer executes the Yahoo full-validation script.
- Verify the file is actually deleted.

### Judge / exit gate
Retirement is complete only when:
- the script is deleted;
- workflow is green through the remaining intended gates;
- Stage-2 hand-off passes;
- Stage-3 live output passes and is retained;
- no stale `full_validation.py` production-gate references remain.

## Non-goal

This does not mean Yahoo/yfinance must disappear from the repository. It only retires this obsolete ranking-validation script/path as a V1 production gate. Any other Yahoo use must be assessed against its current owner and purpose separately.


## Execution closure — 2026-09-19

Retirement was executed and verified.

- `scripts/full_validation.py`: **deleted**.
- Workflow invocation of that script: **removed**.
- Final artifact label: `v1-validation-artifacts`.
- V1 Full Validation run **#304**: **PASS** through all remaining gates.
- Full regression: **PASS**.
- Compile: **PASS**.
- Stage-2 canonical ranking artifact hand-off: **PASS**.
- Stage-3 live hierarchy: **PASS**.
- Stage-3 artifact retention: **PASS**.
- Deprecated Streamlit HTML guard: **PASS**.
- Headless Streamlit runtime smoke test: **PASS**.
- Final V1 validation artifact upload: **PASS**.

The former 430/750 Yahoo coverage failure no longer blocks V1 because the obsolete Yahoo ranking-validation path has been retired. Production ranking validation remains anchored to the published Screener-backed ranking artifact.

### Status

**RETIREMENT VERIFIED.**
