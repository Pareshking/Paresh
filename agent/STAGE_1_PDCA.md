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
