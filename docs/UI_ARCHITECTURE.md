# UI architecture: the tab problem, and whether to rewrite

**Date:** 2026-09-11
**Status:** recommendation, not yet executed
**Question put by the owner:** *"Shouldn't we re-write the complete code from
blank? Current one doesn't even have real tabs, everything in one container is
a bad thing."*

---

## 1. The observation is correct, and it is now measured

The app does use real `st.tabs` (`app.py:454`, eleven tabs). The problem is not
that the tabs are fake — it is that **`st.tabs` executes every tab body on every
run.** Streamlit builds all eleven, sends them all to the browser, and the
browser shows one. That is Streamlit's documented behaviour, not a defect in
this app, but the consequences here are real and were measured rather than
assumed:

| Measurement | Value | How |
|---|---|---|
| Python per interaction | **~1.0 s** (lower bound) | `AppTest` warm rerun of `app.py`, best of 3, charts stubbed locally — production does the real rendering and will be slower |
| Cold start | ~15.6 s local / **22.0 s** production | local `AppTest`; production QA run 297 |
| Widgets coexisting in one DOM | 8 sliders, 18 buttons, 13 selectboxes (local); **14 sliders** (production) | `AppTest`; production QA run 295 read RRG, Portfolio, Backtest and Configuration sliders in a single frame |

That last row is not a curiosity. It is how the Configuration defect was finally
diagnosed: the Backtest tab's `1M (21D)` slider and the Configuration tab's `1M`
slider were readable in the *same frame*, one correct and one at its minimum,
which is what isolated the cause to the missing explicit `value=`.

**The documented remedy is `st.navigation` + `st.Page`**, where only the active
page's script executes. Available since Streamlit 1.36; this app is pinned to
1.63.0, so it is available today.

---

## 2. What a blank rewrite would actually cost

The instinct is right that the *shell* is wrong. The risk is in the word
*complete*.

```
src/engine    4,338 lines   ← verified; this is where the money is
src/loaders   1,983 lines   ← verified
src/core        732 lines   ← verified
                -----
              7,053 lines of engine, under 794 tests

src/ui       10,351 lines   ← where the architectural problem lives
app.py          530 lines   ← where the architectural problem lives
                ------
             10,881 lines of presentation
```

The engine is not merely "code that works". It carries properties that were
*established by adversarial verification* and that a blank rewrite would have to
re-earn from zero, with real money riding on the interval:

- **Screener/backtester parity.** 0 of 3,000 symbol-horizons differ on the real
  tape — down from 750 of 750 before the engines were unified.
- **Causality.** Scrambling future returns leaves holdings bit-identical, which
  is the test that the engine cannot see forward.
- **Corrected statistics.** Period-scale Sharpe, Lo (2002) standard error
  (checked against a 20,000-trial Monte Carlo after the first attempt understated
  it ~9×), Sortino from target semideviation, one turnover definition.
- **Cap projection.** Headroom redistribution with joint feasibility
  `Σ min(sector_cap, nᵢ·stock_cap)`, and the relaxation reported rather than
  silently applied.
- **Dozens of smaller invariants**: calendar-month anchoring, the 5-session
  anchor staleness limit, breadth denominators over *observed* stocks, DUMMY
  row filtering, point-in-time membership.

Every one of those is a line that looks arbitrary until you know which defect it
answers. A blank rewrite discards the answers and keeps only the questions. The
2026-09-10 audit found and fixed dozens of defects in this engine; a rewrite
starts that clock again.

There is a second, sharper reason. Of the defects repaired during that audit, a
significant number were **introduced by the repairs themselves** — a breadth fix
that crashed its caller, a cap fix that made the weighting selector inert, a
config repair that crashed the tab when all five weights hit zero. Those were
caught only because a large test suite and a production probe already existed.
A blank rewrite means writing that volume of new code *without* the suite that
catches this class of mistake, because the suite is written against the code
being discarded.

---

## 3. Recommendation: rewrite the shell, keep the engine

Do not rewrite from blank. Split the work along the line that already exists:

**Keep, untouched:** `src/engine/`, `src/loaders/`, `src/core/`. These have
nothing to do with the tab problem. Not one line of the eager-rendering issue
lives there.

**Rewrite, in stages:** `app.py` and `src/ui/`.

### Stage 1 — the shell (small, bounded, high value)

Replace `st.tabs` with `st.navigation`/`st.Page`. The change is concentrated:
`app.py:454` plus eleven `with tab_x:` blocks, roughly 80 lines of structure.
Shared data loading stays where it is — with `st.navigation` the main script
runs first, then the selected page — so the pipeline and caching are unaffected.

Expected effect: only the active page's Python executes, so a click costs one
page instead of eleven; and each page's widgets stop sharing a DOM with every
other page's.

Verification already available: the full suite, plus **V1 Production QA**, which
walks all eleven tabs on eight viewports and reads the Configuration panel's
actual values off the live site.

### Stage 2 — one page at a time

With the shell lazy, each view can be rewritten independently and shipped
independently, each one green against the existing tests and the production
probe before the next begins. `src/ui/theme.py` (~2,000 lines of hand-built HTML
table rendering) is the strongest candidate to go first or to be replaced by
`st.dataframe` + `column_config` wherever per-cell colouring is not actually
needed.

### What "from blank" should mean, if it means anything

If the intent is *"stop copying the old UI code"*, that is right and Stage 2 is
exactly that: write each page fresh against the engine's public functions, with
the old view open only as a specification of what the page must show. What
should **not** be rewritten from blank is the engine underneath it.

---

## 4. Why not simply revert the Configuration tab instead

Considered and rejected on evidence. Before `4622d93` (3 Sept) the Configuration
tab was one flat page of `st.divider()` sections, so every widget rendered on
every run and nothing was ever evicted — which is why the sliders worked then.
Reverting would fix the symptom.

It is unnecessary now: production QA run 297 reads the live panel as
`weights={1M: 0.1, 3M: 0.3, 6M: 0.3, 9M: 0.2, 12M: 0.1}` agreeing with its own
pill, with `no failures`. The explicit-value plus mirror-key fix in
`src/ui/widget_state.py` addresses the cause rather than the trigger, and it
protects every other conditionally-rendered widget in the app, not just these
five. The flat-layout revert remains the fallback if this recurs.

Note also that switching the sliders to `st.number_input` would **not** have
helped: `number_input` uses the same session-state mechanism and fails the same
way without an explicit value. The widget type was never the axis that mattered.

---

## 5. Order of work, if approved

1. Stage 1 shell migration to `st.navigation`/`st.Page`, engine untouched.
2. Re-measure per-interaction cost the same way §1 did, and record the result
   here. If it does not improve materially, stop and re-diagnose rather than
   continuing to Stage 2 on faith.
3. Stage 2, page by page, each shipped and verified before the next.

Nothing in Stage 1 or 2 changes a number the app reports. If any stage changes a
reported figure, that is a defect in the migration, and the parity tests should
catch it.
