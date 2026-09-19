# Stage 3 — Market Hierarchy PDCA Record

Date: 2026-09-19
Branch: agent/foundation-v1
Status: IMPLEMENTATION / VERIFICATION IN PROGRESS

## PLAN

Objective: expose existing Paresh market → sector → industry → peer context to the research-agent layer without creating a second quantitative or taxonomy system.

The written implementation plan is recorded in agent/STAGE_3_PLAN.md before implementation.

Canonical owners:
- market benchmark/regime: src/core/config.py, src/loaders/price_loader.py
- market breadth/new highs/lows: src/engine/breadth.py
- current universe: src/loaders/indices_loader.py
- point-in-time membership: src/engine/membership.py
- taxonomy: src/loaders/tv_loader.py and data/nse_tv_classification.csv
- industry aggregation: src/engine/momentum.py::MomentumEngine.get_industry_rankings
- quantitative hand-off: agent/quant_hand_off.py

## DO

Implemented the smallest agent-side adapter:
- agent/market_hierarchy.py
- tests/test_agent_market_hierarchy.py

The adapter:
1. wraps an already-computed canonical RegimeData;
2. preserves an already-computed canonical breadth DataFrame;
3. preserves benchmark/as-of identity from QuantSnapshot;
4. accepts only the three existing taxonomy choices used by the production sector view;
5. validates snapshot and ranking symbol integrity;
6. derives peers only by grouping the selected existing taxonomy field;
7. derives peers from the full supplied canonical ranking frame so a candidate can see all same-taxonomy peers already present in the supplied universe;
8. preserves missing taxonomy as explicit unknown with an empty peer group;
9. preserves supplied industry aggregation rather than recalculating it;
10. wraps the canonical point-in-time membership query and preserves None outside historical coverage;
11. contains no price downloader, ranking engine, benchmark calculation, breadth formula, or alternate taxonomy.

## CHECK — pending execution evidence

Focused Stage-3 tests were added for:
- canonical market output wrapping;
- canonical regime type enforcement;
- TV industry taxonomy;
- NSE industry taxonomy separation;
- TV sector peer grouping;
- full-universe peer membership;
- missing taxonomy → unknown;
- duplicate snapshot symbols;
- duplicate ranking rows;
- missing snapshot symbols;
- unsupported taxonomy;
- market/as-of identity mismatch;
- preserved industry aggregation;
- input-frame immutability;
- no price/ranking-engine imports;
- point-in-time membership coverage and out-of-coverage behavior.

Repository CI is still executing for the current head. No test pass is claimed until the run completes.

## Adversarial loop

### Researcher
Initial implementation traced each Stage-3 output to an existing owner and avoided new quantitative formulas.

### Prosecution / Challenger
Key attack points:
- a peer group limited to Top-N rows would hide valid peers in the supplied universe;
- NSE Industry and TradingView Industry can differ and must not be conflated;
- missing taxonomy must not create an inferred peer;
- historical membership must not silently fall back to current membership;
- market context must not introduce a second benchmark/regime implementation;
- Stage-3 code must not import price acquisition or ranking orchestration.

The peer implementation was corrected to group over the full supplied ranking frame before verification.

### Defence
The adapter contains no ranking/price/breadth mathematics. Canonical outputs are passed through and their identity is preserved.

### Reviewer
Review will verify code ownership, taxonomy identity, date consistency, immutability, failure behavior, and regression evidence.

### Jury
Pending test/CI evidence. No gate decision yet.

### Judge
Stage 3 remains OPEN until focused tests, regression/CI evidence, adversarial review, documentation reconciliation, and the final exit criteria are satisfied.

## ACT

Not yet closed. The next action is to inspect the completed CI/test result, repair any defects under a written correction plan, rerun checks, then make the Stage-3 gate decision.

## Exit gate

NOT PASSED YET.

Required before closure:
- canonical market/breadth owners reused;
- canonical taxonomy reused;
- industry aggregation reused;
- peer derivation is taxonomy-only;
- historical uncertainty explicit;
- no duplicate quantitative/taxonomy engine;
- focused tests pass;
- full regression/CI status recorded;
- adversarial review complete;
- documentation reconciled;
- exact VERIFIED / NOT VERIFIED status recorded.

## Verification repair — 2026-09-19

CI run 275 produced 1114 passing tests and one failing Stage-3 test. The failure
was in the test's raw-text import guard: the implementation intentionally records
the canonical price-loader owner as provenance, so the substring was not evidence
of an import. The written repair plan in STAGE_3_PLAN.md replaced that check with
an AST import check while retaining the provenance assertion.

A subsequent adversarial review identified a second provenance risk: a supplied
breadth series could be older than the quantitative snapshot while MarketContext
still presented only the snapshot date. A written date-coherence repair plan was
recorded before implementation. The adapter now records breadth_as_of and rejects
future breadth observations while permitting older observations explicitly.

The next CI run must verify both repairs before the Stage-3 gate can be considered.
