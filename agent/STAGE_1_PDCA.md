# Stage 1 — Foundation PDCA Record

Date: 2026-09-19
Branch: agent/foundation-v1

## PLAN

### Objective
Create a fail-closed boundary between Paresh's deterministic quantitative engine and a future research-agent orchestration layer.

### Sub-stages
- 1.1 Architecture boundary
- 1.2 Quantitative snapshot identity
- 1.3 Evidence/provenance contract
- 1.4 Research/review/report schema
- 1.5 Runner and package integration
- 1.6 Adversarial validation
- 1.7 Completion gate

### Exit criteria
- No agent contract contains ranking mathematics.
- Quant snapshot identifies benchmark, universe, model, as-of date and configuration fingerprint.
- Evidence records source, dates, entity, kind and confidence.
- Positive, negative and unknown evidence remain structurally distinct.
- A report cannot contain duplicate symbols or reviews for absent symbols.
- Foundation tests are discovered by normal pytest.
- Runner uses the canonical V1 configuration identity.
- No production ranking or portfolio code is modified.

## DO

Implemented on the isolated branch:
- Added `agent/__init__.py`.
- Added immutable contracts in `agent/contracts.py`.
- Added deterministic canonical configuration fingerprinting in `agent/fingerprint.py`.
- Updated `agent/run.py` to use the real V1 fingerprint and package imports.
- Moved foundation tests into `tests/test_agent_foundation.py`.
- Added provenance and report-integrity validation.
- Added this PDCA record and updated the foundation README.

## CHECK

### Structural checks performed
- Reviewed the current Paresh configuration: canonical benchmark is `^CRSLDX`; System-1 horizons and weights are read from `src/core/config.py`.
- Confirmed the foundation runner does not rank securities or mutate portfolio rules.
- Identified and corrected an initial test-discovery/import defect: `agent/test_foundation.py` imported `contracts` as a top-level module. It was moved to `tests/` and imports `agent.contracts`.
- Confirmed the existing full-validation workflow runs the full pytest suite on pull requests and main pushes.

### Adversarial cases covered
- Missing snapshot identity.
- Confidence outside [0, 1].
- Empty evidence fields.
- Publication date after retrieval date.
- Positive/negative/unknown evidence in the wrong report bucket.
- Duplicate research symbols.
- Non-positive ranks.
- Review referencing a symbol absent from the report.
- Deterministic configuration fingerprint stability.

### Execution limitation
The repository was inspected and modified through the connected GitHub interface. A local checkout of the full repository was not available in this run, so this loop does **not** claim that pytest was executed locally. CI is the authoritative execution check once the branch is proposed to `main`.

## ACT

Stage 1 is accepted as **complete at the source-contract level** because the exit criteria are represented in code/tests and the discovered import/discovery defect was corrected.

### Deliberately outside Stage 1
- Web/news research.
- Market/sector/industry/peer adapters.
- Company research.
- LLM/API dependency.
- Qualitative scoring.
- Ranking changes.
- Agent automation.

These belong to later stages and must not be pulled forward for convenience.

## Next PDCA gate

Stage 2 begins with a read-only adapter over the **existing** quantitative engine. Its first check must prove adapter output is identical to engine output for the same as-of/configuration state; otherwise the loop stops before research-agent work proceeds.

## POST-STAGE-1 REPOSITORY RE-AUDIT — 2026-09-19

The initial Stage-1 completion was source-contract focused. Before beginning Stage 2,
the repository was reviewed again with the explicit goal of preventing duplicate systems.

### Repository findings

1. A canonical precomputed ranking already exists.
   - scripts/sync_data.py::_precompute_rankings() uses the canonical src/engine/pipeline.
   - It ranks the same published price snapshot used by production.
   - It writes rankings.parquet with an embedded contract.
   - daily_sync.yml and weekly_full_sync.yml publish that artifact as the rolling data-latest release asset.

2. The Streamlit app already consumes that artifact.
   - app.py fetches the ranking snapshot concurrently.
   - _precomputed_ranking() validates its contract.
   - A valid hit skips the expensive engine build.
   - A miss deliberately falls back to the canonical engine.

3. The ranking contract is already stronger than the original Stage-1 design.
   It carries pipeline version, price fingerprint, symbol fingerprint, weights, universe,
   price source, price-as-of and corporate-action digest.

4. One contract gap was found and corrected.
   ranking_store.matches() previously did not compare price_as_of. A table from the same
   price frame but a different deliberately selected ranking date could therefore have
   been accepted. The contract now compares price_as_of, and tests/test_precomputed_ranking.py
   covers the failure case.

5. The original Stage-1 configuration fingerprint was incomplete.
   It identified several constants but did not explicitly incorporate the canonical
   pipeline version or configured ranking price source. It now includes both.
   The pipeline version already incorporates ranking-changing engine constants.

6. The repository contains existing owners for nearly every planned Stage-2 quantitative
   task. Breadth, sector/industry classification, membership, market caps, ATH, corporate
   actions, backtest, portfolio construction and track record already have production owners and tests.

### Stage-1 contract upgrade

QuantSnapshot now has provenance fields for:
- pipeline version;
- price source;
- price as-of;
- source artifact.

These fields do not implement quantitative logic. They make the hand-off contract capable
of identifying the actual artifact consumed by the agent.

### Revised Stage-2 rule

The first Stage-2 implementation must consume the accepted rankings.parquet artifact.
It must not download prices or recreate ranking mathematics as part of normal operation.

The existing engine may be invoked only as an explicit audit/reference path when testing
the artifact, not as a second production implementation.

### Revised completion gate

Stage 1 remains a foundation stage, but its completion gate is now:
- contract definitions identify the actual quantitative artifact;
- the canonical configuration identity is sufficiently discriminating;
- precomputed ranking provenance is fail-closed;
- repository capabilities are mapped so Stage 2 does not duplicate them;
- the Stage-2 plan is based on actual repository ownership rather than assumptions.

### Execution limitation

This audit was performed through the connected GitHub repository interface.
The current environment still does not provide a local full-repository checkout,
so no local pytest run is claimed. The branch contains the targeted regression test;
GitHub Actions remains the authoritative execution check.

### Decision

**Stage 2 is not started yet.**

The next action is a dedicated Stage-2 plan/implementation only after the repository
integration map and Stage-1 hardening are reviewed. The first Stage-2 deliverable should
be a read-only adapter around the existing ranking artifact and its contract, with no
new ranking/data-download pipeline.

## STAGE-2 HAND-OFF START — 2026-09-19

Stage 2 was authorized only after repository inspection and a written `agent/STAGE_2_PLAN.md` were recorded. The implementation is deliberately limited to `agent/quant_hand_off.py` plus focused tests. The canonical ranking artifact remains the only quantitative source of truth.
