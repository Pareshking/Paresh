# Stage 3 — Market → Sector → Industry → Peer Plan

Date: 2026-09-19
Branch: agent/foundation-v1
Status: PLAN RECORDED — implementation not started

## Objective

Expose Paresh's existing market, sector, industry and peer context to the research-agent layer without creating a second quantitative or taxonomy system.

Required hierarchy:

`canonical quantitative snapshot → market context → sector context → industry context → peer context`

The Stage-3 layer is an orchestration/read-only boundary. Existing Paresh calculations and classifications remain the sources of truth.

## Fresh repository inspection completed before implementation

The following were re-read on `agent/foundation-v1`:

- `agent/AI_AGENT_MASTER_SPEC.md`
- `agent/AI_AGENT_DEVELOPMENT_TRACKER.md`
- `agent/REPO_INTEGRATION_MAP.md`
- `agent/STAGE_1_PDCA.md`
- `agent/STAGE_2_PLAN.md`
- `agent/STAGE_2_PDCA.md`
- `src/core/config.py`
- `src/loaders/price_loader.py`
- `src/loaders/tv_loader.py`
- `src/loaders/indices_loader.py`
- `src/engine/membership.py`
- `src/engine/breadth.py`
- `src/engine/momentum.py`
- `src/ui/views/sector_view.py`
- `src/ui/views/breadth_view.py`
- `src/ui/views/rrg_view.py`
- `app.py`
- `tests/test_navigation_is_visible.py`
- `data/nse_tv_classification.csv`

### Existing owners identified

| Context | Canonical owner | Stage-3 treatment |
|---|---|---|
| Market benchmark | `src/core/config.py::BENCHMARK_SYMBOL` and `src/loaders/price_loader.py::fetch_benchmark_history` | Consume existing benchmark identity/history; do not create another benchmark |
| Market regime | `src/loaders/price_loader.py::get_market_regime` | Reuse existing regime calculation and output |
| Market breadth | `src/engine/breadth.py::compute_ma_breadth` | Reuse existing breadth engine; do not duplicate MA/breadth formulas |
| New highs/lows | `src/engine/breadth.py::compute_hl_timeseries` and `get_recent_hl_events` | Reuse existing calculations |
| Current index universe | `src/loaders/indices_loader.py` + `data/indices/` | Reuse current membership/universe |
| Historical membership | `src/engine/membership.py` + `data/membership_history.json` | Reuse for date-aware historical context |
| Sector/industry taxonomy | `src/loaders/tv_loader.py` + `data/nse_tv_classification.csv` | Reuse exact stored taxonomy |
| NSE industry | Existing `rank_df["Industry"]` from index loader/ranking pipeline | Preserve as an existing classification, not replace it |
| Industry aggregation | `src/engine/momentum.py::MomentumEngine.get_industry_rankings` | Reuse existing aggregation; no second industry ranking |
| Sector/industry UI | `src/ui/views/sector_view.py` | Treat as existing consumer; agent adapter should not copy its arithmetic |
| RRG hierarchy view | `src/ui/views/rrg_view.py` | Existing UI calculation is not to be duplicated into agent logic |
| Quantitative input | Stage-2 `agent/quant_hand_off.py` → `QuantSnapshot` | Use the accepted read-only snapshot as the quantitative boundary |

## Important inspection findings

1. There is no separate `src/engine/sector.py` or `src/engine/industry.py` owner. Industry aggregation is owned by `MomentumEngine.get_industry_rankings`; sector/industry labels come from the existing taxonomy fields.
2. `TV_Sector` and `TV_Industry` are loaded from the committed TradingView classification file and merged into `rank_df` by `app.py`. Missing classification is represented explicitly rather than invented.
3. The existing sector view can switch among NSE Industry, TradingView Industry (119), and TradingView Sector (20). Stage 3 must preserve taxonomy identity in its output so a reader cannot mistake one classification for another.
4. Existing breadth code already handles observed denominators and new-high/new-low time series. Stage 3 must call it rather than reproduce those formulas.
5. Existing market regime is benchmark-vs-200DMA using the canonical `BENCHMARK_SYMBOL` (currently `^CRSLDX`). The agent must preserve that benchmark identity and must not silently substitute `^NSEI`.
6. Existing point-in-time membership explicitly returns `None` when history does not cover a requested date. Stage 3 must propagate that uncertainty instead of falling back to today's membership for historical questions.
7. Existing RRG code contains a documented equal-weighted peer/sector proxy calculation. Stage 3 will not copy that calculation. If RRG context is needed, it must be consumed from the existing owner or remain outside Stage-3 scope.
8. `app.py` currently loads the production price frame through the existing price loader and merges TradingView taxonomy before rendering. The agent layer must not introduce another price source, taxonomy loader, or benchmark rule.

## Stage-3 output boundary

The implementation should expose a small read-only market-hierarchy context object/adapters containing, as applicable:

- snapshot/as-of identity;
- benchmark identity;
- market regime result;
- breadth result(s) from the canonical breadth engine;
- taxonomy name/version/identity;
- sector/industry membership for the snapshot rows;
- industry aggregates from the canonical `get_industry_rankings`;
- peer membership derived from the already-existing industry/taxonomy labels;
- explicit unknown/missing classification state;
- provenance pointing to the existing Paresh owner/function/data file.

The adapter must not calculate a new score or investment ranking.

## Peer definition

For Stage 3, a peer group is a deterministic membership set derived from an already-existing taxonomy column:

- requested taxonomy must be explicit (for example `TV_Industry`, `Industry`, or `TV_Sector`);
- peer members are the symbols sharing the same non-empty taxonomy value;
- no similarity model, market-cap clustering, semantic model, or new peer taxonomy is permitted;
- missing taxonomy means peer group is unknown, not an inferred group.

The output must retain the taxonomy field used so the peer set is reproducible.

## Historical/as-of rule

For a current snapshot, use the current accepted QuantSnapshot rows and current canonical taxonomy.

For a historical question, Stage 3 may use the existing point-in-time membership timeline where membership matters. If the requested date predates membership coverage, return an explicit unknown/insufficient-coverage state. Do not silently substitute today's members.

Taxonomy dates are a separate concern from index membership dates. The Stage-3 adapter must not claim historical taxonomy accuracy unless the repository contains dated taxonomy evidence for that date.

## Data-source boundary

Normal Stage-3 context construction must not introduce a new external downloader.

Allowed:
- existing Paresh functions and already-loaded data supplied by their canonical callers;
- existing benchmark/regime/breadth functions where the stage explicitly needs their existing output;
- existing static taxonomy and membership files;
- Stage-2 QuantSnapshot.

Not allowed:
- new Yahoo/Screener downloader;
- new benchmark calculation;
- copied breadth formulas;
- copied sector/industry ranking formulas;
- second taxonomy;
- external company/news research (Stage 4).

## Failure policy

Fail closed or return explicit unknown state for:

- missing QuantSnapshot;
- missing required taxonomy column;
- empty symbol universe;
- duplicate symbols;
- missing requested classification;
- historical membership outside coverage;
- malformed/corrupt classification data;
- incompatible as-of inputs.

Never infer a peer from an unrelated taxonomy or current membership when historical membership is unknown.

## Planned implementation sequence

1. Record this plan before code. **DONE.**
2. Search existing Stage-3 callers/tests again immediately before implementation.
3. Define the smallest agent-side read-only context contract, reusing Stage-1 contract types where practical.
4. Implement market context adapter around existing regime/breadth outputs.
5. Implement taxonomy/industry context adapter around existing `TV_Sector`, `TV_Industry`, `Industry` fields and `get_industry_rankings`.
6. Implement peer derivation strictly as grouping over the selected existing taxonomy.
7. Add focused tests for identity, missing data, duplicate symbols, taxonomy choice, peer membership, and historical membership uncertainty.
8. Run focused tests and static checks, then full regression/CI when available.
9. Perform Researcher → Prosecution/Challenger → Defence → Reviewer → Jury → Judge.
10. Fix every discovered defect and rerun the relevant tests.
11. Reconcile PDCA, tracker, integration map and master spec only where rules changed.
12. Execute the Stage-3 exit gate. Do not start Stage 4 unless it passes.

## Adversarial review questions

### Researcher
- Which exact existing function/file owns each output?
- Is the selected taxonomy explicitly identified?
- Can a reader reproduce the peer set from the stored fields?

### Prosecution / Challenger
- Did any Stage-3 function recalculate breadth, sector ranking, industry ranking, or benchmark?
- Can a missing taxonomy silently become a fabricated peer?
- Can a historical request accidentally use today's membership?
- Can NSE Industry and TradingView Industry be conflated?
- Does the adapter introduce a second data download path?
- Can duplicate symbols create inflated peer counts?
- Can as-of dates from different sources be presented as if they were identical?

### Defence
- Does every derived field trace to a canonical owner?
- Is peer membership only grouping over an existing taxonomy?
- Are unknown/missing states preserved?
- Is the quantitative snapshot still read-only?

### Reviewer
- Are taxonomy identity and as-of provenance explicit?
- Are historical coverage limitations visible?
- Are failure modes tested?
- Are no-duplication constraints demonstrable by code inspection?

### Jury
- Are any remaining uncertainties factual limitations of repository data rather than hidden assumptions?
- Is the hierarchy sufficient for Stage 4 company research without introducing qualitative scoring?

### Judge
Stage 3 passes only if:
- market context reuses canonical market/breadth owners;
- sector/industry context reuses canonical taxonomy/aggregation;
- peer groups derive only from existing taxonomy;
- no duplicate quantitative/taxonomy engine exists;
- missing/historical uncertainty is explicit;
- focused and regression tests pass;
- documentation and provenance are reconciled;
- real execution evidence is recorded as VERIFIED or NOT VERIFIED.

## Non-goals

- No company research.
- No external news/filing retrieval.
- No new quantitative ranking.
- No new sector/industry formulas.
- No new benchmark.
- No RRG reimplementation.
- No portfolio/backtest changes.
- No automation.
- No production UI redesign.

## Entry condition for implementation

This plan is now recorded. Implementation may begin only after the Stage-3-specific existing callers/tests are searched once more and the smallest integration point is confirmed.

## Verification repair plan — 2026-09-19

The first CI execution found one test defect: the no-duplicate-engine test searched
raw source text for the substring "price_loader", but the adapter intentionally
records the canonical owner string
"src/loaders/price_loader.py::get_market_regime" as provenance. The implementation
does not import price_loader.

Before changing code, the repair decision is:

1. keep the adapter provenance string unchanged;
2. replace the brittle raw-substring assertion with an AST/import-level check that
   verifies the module has no import from price_loader, pipeline, or yfinance;
3. retain the explicit provenance owner assertion separately;
4. rerun the focused Stage-3 tests and full regression;
5. only then continue the adversarial gate.

This is a test-quality repair, not a weakening of the Stage-3 no-duplication rule.

## Adversarial repair plan — date coherence — 2026-09-19

The completed test run will be followed by a deeper reviewer pass on provenance
coherence. The current MarketContext labels its context with the QuantSnapshot
as-of date even when a supplied breadth series could end earlier or accidentally
contain a future row.

Before changing implementation, the repair decision is:

1. retain the canonical breadth values unchanged;
2. record an explicit breadth_as_of derived only from the supplied breadth index;
3. reject a breadth series whose latest dated observation is after snapshot.as_of;
4. permit an older breadth observation but preserve its actual date so downstream
research cannot mistake it for same-session data;
5. add regression tests for future breadth and older-but-explicit breadth;
6. rerun the full regression and continue the adversarial review.

This is provenance hardening, not a new breadth calculation.


## Live-output verification plan — 2026-09-19

The implementation gate was previously based on tests and canonical artifact hand-off, but the actual Stage-3 hierarchy had not yet been executed against the current published ranking artifact. This is a verification gap, not an implementation change.

Before changing code, the repair/verification plan is:

1. Use the existing Stage-2 `load_quant_snapshot()` boundary to load the current published `rankings.parquet` and validate its embedded contract.
2. Use the production `load_tv_classification()` owner and committed taxonomy data; do not create another taxonomy loader.
3. Build the Stage-3 hierarchy from all currently published ranking rows, then inspect the actual Top-25 by canonical Rank.
4. Produce a machine-readable/Markdown live verification artifact containing snapshot as-of, row count, taxonomy, Top-25 hierarchy, peer counts, and peer membership.
5. Assert that the live artifact has the expected 750-row snapshot, 25 Top-25 rows, non-duplicated symbols, and taxonomy-derived peer groups.
6. Upload the verification artifact in CI so the evidence is retained with the workflow run; GitHub Actions artifacts are intended for persisting test/output files after a run. citeturn2search0turn2search1
7. Record the exact verification result in the Stage-3 PDCA/tracker/master documentation. A future Stage-3 gate must not be marked complete without either a live execution artifact or an explicit documented NOT VERIFIED state.
8. Run the full adversarial review again after the live-output implementation and stop before Company Intelligence if this live gate fails.

This verification path is an audit harness around existing owners. It does not calculate a new ranking, download a second price source, or alter the Stage-3 methodology.
