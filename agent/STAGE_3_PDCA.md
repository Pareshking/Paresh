# Stage 3 — Market Hierarchy PDCA Record

Date: 2026-09-19
Branch: agent/foundation-v1
Status: COMPLETE — GATE PASSED

## PLAN

Objective: expose existing Paresh market → sector → industry → peer context to the research-agent layer without creating a second quantitative or taxonomy system.

A fresh repository inspection was completed first and the written plan was recorded in agent/STAGE_3_PLAN.md before implementation.

Canonical owners inspected:
- market benchmark/regime: src/core/config.py, src/loaders/price_loader.py
- market breadth/new highs/lows: src/engine/breadth.py
- current universe: src/loaders/indices_loader.py
- point-in-time membership: src/engine/membership.py
- taxonomy: src/loaders/tv_loader.py and data/nse_tv_classification.csv
- industry aggregation: src/engine/momentum.py::MomentumEngine.get_industry_rankings
- quantitative hand-off: agent/quant_hand_off.py

## DO

Added:
- agent/market_hierarchy.py
- tests/test_agent_market_hierarchy.py

The adapter:
1. wraps an already-computed canonical RegimeData;
2. preserves an already-computed canonical breadth result;
3. records benchmark/as-of identity from QuantSnapshot;
4. accepts only the three taxonomy choices already exposed by the production sector view;
5. validates snapshot/ranking symbol integrity;
6. derives peers only by grouping an existing taxonomy column;
7. builds peer groups from the full supplied ranking frame;
8. preserves missing classification as unknown rather than inferring a peer;
9. preserves supplied industry aggregation rather than recalculating it;
10. delegates historical membership to src.engine.membership.members_on and preserves None outside coverage;
11. contains no price downloader, ranking engine, benchmark formula, breadth formula, or alternate taxonomy.

A provenance hardening change also records breadth_as_of and rejects future breadth observations while permitting older observations explicitly.

## CHECK

### Execution evidence

CI run 279 executed the full repository regression after the Stage-3 repairs.

VERIFIED:
- Full regression suite: 1114 passed in 91.57s.
- Compile application/source: PASS.
- Stage-2 canonical ranking artifact hand-off: PASS.
- Real published artifact: 750 rows, as-of 2026-09-18, pipeline v4_calendar_periods_cbab8da9, actual price source screener.
- Stage-3 focused tests passed as part of the 1114-test suite.

The full current-universe quantitative integration remains a separate repository QA failure in scripts/full_validation.py: its independent Yahoo-backed validation path sees 430/750 closes for 2026-09-17 and hits its existing 700-score floor. This is not a Stage-3 failure and was not weakened or bypassed.

### Researcher
Mapped each Stage-3 output to an existing Paresh owner before implementation. No new quantitative or taxonomy source was introduced.

### Prosecution / Challenger
Found and corrected:
- a test guard that confused provenance text with an import;
- peer groups initially limited to the snapshot instead of the full supplied canonical universe;
- a provenance gap where breadth could be older/newer than the snapshot without an explicit breadth date.

Also challenged taxonomy conflation and historical membership fallback. The final implementation keeps these identities explicit.

### Defence
Canonical calculations remain outside the agent layer. Market regime and breadth are supplied as existing outputs; taxonomy is supplied by existing fields; industry aggregation is preserved as an existing output; peers are only deterministic grouping.

### Reviewer
Confirmed:
- benchmark identity is preserved;
- taxonomy choice is explicit;
- breadth date is explicit;
- input rank data is copied rather than mutated;
- duplicate/missing symbols fail closed;
- missing taxonomy remains unknown;
- historical membership outside coverage remains unknown;
- the module has no imports of yfinance, pipeline, or price_loader.

### Jury
The remaining uncertainty is limited to source data coverage outside Stage 3: the existing full-universe Yahoo validation path is still red. It does not invalidate the Stage-3 adapter tests or canonical taxonomy ownership.

### Judge
**STAGE 3 GATE: PASSED.**

The Stage-3 exit criteria are satisfied:
- canonical market/breadth owners reused;
- canonical taxonomy reused;
- canonical industry aggregation accepted rather than recreated;
- peer groups derived only from existing taxonomy;
- missing/historical uncertainty explicit;
- no duplicate quantitative/taxonomy engine;
- focused tests and full regression pass;
- documentation reconciled;
- unrelated full-validation issue remains visible and separate.

## ACT

Stage 3 is closed. Stage 4 is now eligible only after its own repository inspection and written plan. No company research or external evidence collection was started in Stage 3.

## Files added/changed

Added:
- agent/STAGE_3_PLAN.md
- agent/STAGE_3_PDCA.md
- agent/market_hierarchy.py
- tests/test_agent_market_hierarchy.py

Updated:
- agent/AI_AGENT_DEVELOPMENT_TRACKER.md
- agent/AI_AGENT_MASTER_SPEC.md
- agent/REPO_INTEGRATION_MAP.md
- agent/README.md

No production quantitative formula or portfolio rule was changed by Stage 3.
