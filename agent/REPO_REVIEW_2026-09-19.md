# Repository Review Before Stage 2 — 2026-09-19

## Decision
**Do not start Stage 2 yet.**
The repository review changed the Stage-2 design materially. Paresh already has a production data/ranking pipeline and a published ranking artifact. Building another download → clean → calculate → rank path in the agent would be duplication and would create a second source of truth.
Stage 1 was therefore re-opened for a repository-integration review and hardened before Stage 2.

## Review scope
Reviewed the branch tree and traced ownership/data flow across root README; agent contracts/runner/fingerprint; core configuration; ranking pipeline; calendar momentum; momentum engine; price loaders/source selection/snapshot recovery; ranking storage; corporate actions; universe/membership; market caps/ATH; sector/industry classification; breadth; backtester; portfolio; track record; daily/weekly sync workflows; QA/full-validation workflows; relevant snapshot tests; and Stage-1 documentation/tests.

## Existing architecture discovered

### Canonical quantitative pipeline
`src/engine/pipeline.py` is the single ranking orchestration owner. The sync job and Streamlit application both call `pipeline.build_engine()` and `pipeline.rank_with_weights()`. This is already tested in `tests/test_precomputed_ranking.py`.

### Precomputed ranking
`scripts/sync_data.py::_precompute_rankings()` reads the production price snapshot, selects the canonical price source, applies the same corporate-action path, calls the canonical pipeline, stamps the ranking with a contract, and writes `rankings.parquet`. Daily and weekly workflows publish it as the rolling `data-latest` release asset.

### Production consumption
`app.py` fetches the ranking artifact and passes it through `_precomputed_ranking()`. A contract hit skips the expensive engine build. A contract miss falls back to the same canonical engine.

### Existing persisted data
The repository already persists or publishes price snapshot, deep price archive, precomputed ranking, NSE index constituents, point-in-time membership history, market-cap snapshot, all-time-high snapshot, TradingView sector/industry classification, corporate-action log, and frozen monthly track record. These are inputs to reuse, not systems to recreate.

## Findings

### Finding 1 — Major architectural duplication risk
**Severity: Critical if ignored**
The planned Stage-2 adapter could have downloaded price data and recalculated System-1. That would have duplicated the exact pipeline that already exists.
**Action:** Stage 2 is now explicitly artifact-first. Normal path: `rankings.parquet → validate → QuantSnapshot → research`. Recalculation is permitted only for explicit audit/reference tests.

### Finding 2 — Ranking contract had an as-of identity gap
**Severity: High**
The ranking contract stored `price_as_of`, but `ranking_store.matches()` did not compare it. The engine can deliberately stop at an earlier completed session while the newest row is still settling, so the same frame can describe different ranking dates.
**Action taken:** `price_as_of` is now part of the contract match fields. Regression test added: `test_a_different_price_as_of_is_rejected`.

### Finding 3 — Stage-1 fingerprint was too narrow
**Severity: High**
The initial agent fingerprint did not explicitly include the canonical `pipeline.PIPELINE_VERSION` or configured ranking price source.
**Action taken:** both are now included in the agent's canonical quantitative identity.

### Finding 4 — Stage-1 QuantSnapshot provenance was insufficient
**Severity: Medium**
The original contract identified benchmark/universe/model/config fingerprint but did not explicitly identify the ranking artifact's pipeline version, price source, price-as-of or source artifact.
**Action taken:** those provenance fields were added without adding quantitative logic.

### Finding 5 — Existing quantitative owners are extensive
**Severity: Informational but important**
There is already a production owner for almost every quantitative capability planned for the agent. The agent must therefore be orchestration/research/audit, not a replacement quant engine.

## Stage-2 ownership map
### Reuse
- Ranking: `src/engine/pipeline.py`
- Ranking artifact: `src/loaders/ranking_store.py`
- Price snapshot: `src/loaders/price_store.py`
- Price-source selection: `src/loaders/price_source.py`
- Corporate actions: `src/engine/corporate_actions.py`
- Universe: `src/loaders/indices_loader.py`
- Membership: `src/engine/membership.py`
- Market caps: `src/loaders/mcap_loader.py`
- ATH: `src/loaders/ath_loader.py`
- Sector/industry: `src/loaders/tv_loader.py`
- Breadth: `src/engine/breadth.py`
- Backtest: `src/engine/backtester.py`
- Portfolio: `src/engine/portfolio.py`
- Track record: `src/engine/track_record.py`

### New agent work
- quantitative hand-off;
- research orchestration;
- external evidence collection;
- evidence classification;
- adversarial challenge;
- review/judge process;
- weekly report generation;
- research-process audit.

## Important distinction
The agent may read a quantitative value, explain it, and audit it against the canonical engine. It must not silently recalculate and replace the quantitative value in normal agent operation.

## Documentation changes
Added `agent/REPO_INTEGRATION_MAP.md` and `agent/REPO_REVIEW_2026-09-19.md`.
Updated `agent/README.md`, `agent/STAGE_1_PDCA.md`, and the root `README.md`.

## Stage-1 status after review
Stage 1 is not discarded. It is upgraded from a generic foundation contract to a foundation contract explicitly anchored to Paresh's real production artifacts and quantitative ownership. The foundation still contains no ranking mathematics.

## Stage-2 entry gate
Before company/market research code is added, Stage 2 must prove:
1. the published ranking artifact can be obtained;
2. its embedded contract is valid;
3. its as-of date is coherent;
4. its pipeline/config identity is preserved;
5. its universe is internally consistent;
6. its rows can be converted to QuantSnapshot without recomputation;
7. no new price/ranking pipeline is created;
8. failure is fail-closed rather than silently substituting data.

## Post-Stage-2 review
When Stage 2 is complete, reopen both Stage 1 and Stage 2 and review source, tests, contracts, actual ranking artifact, actual agent output, provenance, stale-data behaviour, fallback paths, adversarial cases, and documentation.
The review will include prosecution, defence, jury and judge passes. A later stage may reopen an earlier stage if new evidence exposes a flaw.

## Execution limitation
This review used the connected GitHub repository interface. No local pytest run is claimed in this environment. The targeted contract regression test has been added; GitHub Actions remains the authoritative execution check.

## Conclusion
**No Stage-2 duplicate system will be built.** The repository already does the expensive quantitative work. The agent's job is to understand, challenge and enrich those outputs with evidence while preserving the quantitative system as the single source of truth.

## STAGE-2 IMPLEMENTATION REVIEW — 2026-09-19

The planned artifact-first hand-off was implemented after the repository inspection. `agent/quant_hand_off.py` calls the existing `ranking_store.fetch_snapshot()` and performs no price download or ranking-engine call. Focused tests cover malformed contracts, date/source/version/weight mismatches, row integrity, universe consistency, provenance and an explicit guard against engine recalculation.

The Stage-2 adapter does not independently reconstruct the price fingerprint. That remains producer/artifact provenance; an independent quantitative audit is a separate future audit path.

Verification status: focused tests were added but local execution is unavailable in this environment. GitHub Actions for the current head returned no workflow runs, so CI and live published-artifact end-to-end execution remain **NOT VERIFIED**. Stage 2 therefore remains open pending executable verification and final gate review.
