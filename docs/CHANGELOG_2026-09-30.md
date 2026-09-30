# Engineering Change Log — 2026-09-30

This document records the material production, data, ranking, UI, reliability and universe-definition changes completed during the September 2026 engineering loop.

## 1. NSE membership history — PR #258

**Merge:** `73b095a49b52ab1a4a968e21e364610e94ed02a5`

- Replaced the old single-index membership-history shape with dynamic multi-index history.
- Covered NIFTY TOTAL MARKET, NIFTY 50, NIFTY NEXT 50, MIDCAP 150, SMALLCAP 250 and MICROCAP 250.
- Excluded `DUMMY*` placeholders from recorded tradable membership.
- Daily sync now derives membership changes from synchronized NSE index files.
- Preserved legacy Total Market compatibility fields during migration.
- R2 historical bootstrap/publication was completed and validated.
- The September 2026 `HEG → HEGAM` event is recorded as a constituent change between two different symbols; it is not a duplicate-company mapping.

## 2. Stock-page price ladder — PR #260 and PR #269

**PR #260 merge:** `26197fbf1b26d17998c7a64e0cb3bc9588a8645d`

**PR #269 merge:** `4eb7898e4e9f555de50424ef11fb387f8e4e8f27`

- Standardized ladder labels to:
  - `52W Low`
  - `-20% 52W High`
  - `50D EMA`
  - `52W High`
- Kept the underlying `52W High × 0.8` threshold unchanged.
- Preserved exact marker positions based on calculated price coordinates.
- Decoupled labels from crowded marker positions using equal-width layout.
- Added matching coloured dots/text so labels remain visually associated with their markers.
- Mobile typography was tightened to avoid overlap.
- Default stock chart remains **Lightweight Charts**; Plotly is fallback only.

## 3. Momentum rank history — PRs #270–#272

**Fingerprint correction merge:** `dd2578b65d3058a0b7e01b5c57c79de2ef2df29e`

The canonical historical rank path is now:

**6M → 3M → 2M → 1M → Now**

- `RANK_HISTORY_MONTHS = (6, 3, 2, 1)` is canonical configuration.
- Historical ranks are calendar snapshots of the same canonical composite ranking, not additional momentum factors.
- The rank-history configuration is included in the pipeline settings fingerprint.
- Stale artifacts produced without the current rank-history configuration are rejected rather than silently reused.
- The stock-page UI always renders all five positions.
- If a historical rank is genuinely unavailable, the UI shows `—` rather than collapsing the sequence.
- Corresponding historical rank deltas use the paired-name rule so comparisons remain meaningful.

## 4. Streamlit hot-reload reliability — PR #263

**Merge:** `3529e834352156fafbd8f8f8b359ac8fb13219fc`

Production logs exposed transient import failures during concurrent Streamlit reloads, including:

- `KeyError: 'src.core.startup_metrics'`
- `KeyError: 'src.ui'`

The custom reload mechanism was removing application modules from `sys.modules` and releasing its lock before application imports completed. The fix:

- added a process-wide re-entrant application import guard;
- held the guard across reload detection, application imports and `mark_loaded()`;
- added a concurrent-thread regression test;
- retained the canonical ranking path unchanged.

The same change clarified track-record ledger semantics: Nano Cap and Combined ledgers are intentionally absent before their October 2026 inception and are informational before inception, while missing ledgers at/after inception remain warnings.

## 5. Nano Cap / Nifty 750 universe correction — PR #273

**Merge:** `811c3f5a6eb89074d39618fd47e2629f9d254834`

The persisted Nano list is a month-end candidate/history source. The effective current Nano universe is now:

**qualifying Nano candidates − current Nifty 750**

with the hard invariant:

`intersection(NIFTY_750, NANO) == ∅`

Details:

- Existing ₹2,000 Cr cutoff and eligibility rules are unchanged.
- Nifty 750 has priority.
- A stock entering the 750 is removed from effective Nano immediately.
- A stock leaving the 750 can enter effective Nano immediately if it remains a qualifying candidate.
- Historical Nano membership records are not rewritten.
- Production and nightly precompute use exactly the same effective-universe definition.
- Nano precompute now loads the current 750 before subtracting it.
- Combined is built from the current 750 plus effective Nano, avoiding duplicate symbols.
- Regression tests cover both current-750 overlap and stock-leaving-750 cases.

## 6. Validation record for PR #273

The final corrected Nano implementation passed:

- **Lint #285 — SUCCESS**
- **V1 Full Validation #1109 — SUCCESS**
- **R2 Streamlit read-path gate #306 — SUCCESS**

Only after all three gates were green was PR #273 merged.

## 7. Production-data verification status

The code change is merged to `main`. Post-merge data-plane verification remains distinct from CI validation. The following must be verified against the published live artifacts after the relevant daily/precompute publication:

1. effective Nano contains no current Nifty 750 symbol;
2. `SIGMAADV` is excluded from Nano while it remains in the current 750;
3. qualifying stocks that leave the 750 can appear in effective Nano without waiting for a monthly Nano-list rebuild;
4. Combined contains the 750 plus effective Nano with no duplicate symbols;
5. published Nano and Combined ranking artifacts use the effective universe rather than the raw persisted Nano candidate list.

No claim of browser-level Streamlit verification is made here; the available verification path is repository/CI/R2/data-artifact based.

## 8. Canonical engineering rules preserved

- System-1 remains the single canonical ranking engine.
- No duplicate ranking, price, benchmark or taxonomy engine was introduced.
- Screener remains the canonical System-1 ranking price source where specified by the production contract.
- Yahoo deep history remains separate from the canonical ranking source.
- R2 storage/archive remains separated from Stage-4B research validation.
- DUMMY symbols are not promoted into the tradable universe.
- Nifty 750 remains the default/base universe and receives priority over Nano.
