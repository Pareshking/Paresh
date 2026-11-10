# Launch test plan — 10 Nov 2026

Owner, 10 Nov 2026: "we are going to launch website tomorrow. Plan all types of
test in next 5 hours and make half hourly schedule to continue working in it."

The site already has 2,607 unit and engine tests, and they pass. What a launch
needs on top of that is the kinds of failure a unit test cannot see: a page that
throws only with real data, a number that two pages report differently, a
control nobody can tap, a job that dies quietly, a secret in a log.

Each slot below says **what it proves** and **how we will know it passed**, so a
slot that finds nothing is still a result and a slot that finds something leaves
evidence. Findings go to `docs/TODO.md` the same day, as CLAUDE.md requires.

## Standing rule for every slot

- A failure is written down with the measurement that found it, not a
  description. "Portfolio drags sideways" is not a finding; "main 1307px in a
  390px viewport" is.
- Nothing merges to `main` without the full suite green and the pages rendered.
- **Launch day is the wrong day for a refactor.** Anything that changes a number
  the site reports stops and waits for the owner, however obviously right it
  looks.

## The schedule (UTC)

| Slot | Time | What |
|---|---|---|
| 1 ✅ | 02:35 | **This plan, and the pre-launch gate.** One command that answers "is the site fit to launch right now": every page renders, no page wider than its viewport, data freshness inside tolerance, no secret in the repo. |
| 2 ✅ | 03:05 | **Functional sweep, desktop.** All 12 pages at 1400px: every control exercised once (filters, pickers, tabs, expanders, downloads, popovers), deep links (`?stock=`, `?owner=`), and the nav. Proves: nothing throws when touched, not merely when loaded. |
| 3 ✅ | 03:35 | **Functional sweep, phone.** The same at 390px, plus tap-target measurement and the menu. Proves: the phone is a first-class reader, not a resized desktop. |
| 4 | 04:05 | **Cross-reading consistency.** Take every figure that appears on more than one page (the EMA distance, the qualified count, returns, drawdown, the book's value) and assert the pages agree. Proves: no second EMA bug. |
| 5 | 04:35 | **Resilience.** Run the app against a missing price file, a stale one, an empty ranking, no R2 credentials, and a benchmark with a gap. Proves: it degrades with a sentence, not a traceback. |
| 6 | 05:05 | **Accessibility.** Contrast on every text colour actually used, heading order, alt text, keyboard-only navigation, focus visibility, screen-reader labels on icon buttons. Target: WCAG 2.1 AA. |
| 7 | 05:35 | **Performance and weight.** Cold start, time to content per page, page bytes, memory at the heaviest page, test-suite runtime. Records the numbers the owner's 10%/20%/20% targets are measured against. |
| 8 | 06:05 | **Security and privacy.** Secret scan over the repo and the built page, the owner-gated controls, query-parameter injection through `?stock=`, what the published page exposes, and what the logs print. |
| 9 | 06:35 | **The jobs.** Every scheduled workflow's last run, the failure alert itself, and a dry run of the two that matter tomorrow (the daily sync and the monthly freeze). Proves: a silent job failure is impossible. |
| 10 | 07:05 | **Content.** No placeholder text, no "TODO" or "lorem", every external link resolves, every date on the page is the date it claims, the Guide matches what the model does. |
| 11 | 07:35 | **Launch report.** One page: what was tested, what was found, what is fixed, what is known and accepted, and the single sentence on whether it is fit to launch. |

## What this plan does NOT cover, and why

- **Real iOS Safari and Android Chrome.** Owner, 10 Nov 2026: "Safari not
  required to be tested." Phone-width Chromium is therefore the standard, and
  slot 3 holds it.
- **Load.** Streamlit Cloud serves one container; a load test would mostly
  measure their queue, and running one against production the night before
  launch risks the thing it is meant to protect. Out of scope deliberately.
- **The strategy's returns against an independent source.** None exists
  (`docs/AUDIT_2026-11-08.md`, "What was not checked").


## Slot results

### Slot 1 — the gate (02:35 UTC, done)

`scripts/launch_gate.py` answers the question in one command, and
`scripts/_launch_pages.js` draws every page for it. First run, 4/4:

| Gate | Result |
|---|---|
| No secret in the repository | 2,022 tracked files scanned, none |
| The committed fallback prices are usable | last session 5 Nov, 4 trading days behind |
| Pages at 1400px | 11 drawn, none throws, none over its viewport |
| Pages at 390px | 11 drawn, none throws, none over its viewport |

One thing the first version of this gate got wrong, worth recording because it
is the kind of mistake a launch gate must not make: it failed the price check at
"4 trading days behind" as though the site were serving stale prices. It is not.
`data/nse_prices/closes.parquet` is the **fallback**
(`src/loaders/nse_prices.py:8`); the app reads the R2 pin or the release copy
first, and the live footer said 8 Nov. A gate that cries wolf about the wrong
file would have been worse than no gate, so it now names the source it read and
fails only if the fallback is old enough to mislead on a day R2 is unreachable.
What a reader actually sees is the footer, which the page sweep reads.

### Slot 2 — every control touched, desktop (03:05 UTC, done)

`scripts/_launch_controls.js` clicks each pill, tab, expander and ordinary
button once at 1400px and waits for the rerun. Loading a page proves little:
most Streamlit failures happen on the rerun a control triggers.

| Page | Controls clicked | Failures |
|---|---|---|
| Dashboard | 0 (it has links, no controls) | — |
| Screener | 7 | none |
| Portfolio | 9 | none |
| Actions | 4 (5 skipped as destructive) | none |
| Sectors | 11 | none |
| Breadth | 6 | none |
| Backtest | 6 | none |
| Watchlist | 1 | none |
| Configuration | 6 | none |
| Guide | 0 | — |
| Sectors rotation (RRG) | 10 | none |

**60 controls, nothing thrown.** Destructive controls are never clicked: a
label matching sync, clear, delete, reset, remove, download or export acts
site-wide or writes a file.

One failure was reported and then withdrawn, which is worth recording. The
first run said a Configuration control could not be clicked (an 8s timeout).
It was the harness: an earlier click had opened a dialog, and the modal covered
everything after it. With dialogs dismissed between clicks, Configuration
passes 6/6. A test that blames the app for its own mess is worse than no test.

**Two 404s on every page, explained and left alone**: Streamlit's own client
asks for `_stcore/health` and `_stcore/host-config` relative to the page path
(`/screener/_stcore/health`) before falling back to the root. It is Streamlit's
behaviour, not ours, the app works, and it accounts for the "console errors: 15"
that production QA reports. Recorded so nobody chases it as a symptom later.

**The owner gate holds.** With no `OWNER_KEY` set, `?owner=`, `?owner=guess`,
`?owner=1`, `?owner=true` and `?owner=admin` all leave the two site-wide
controls hidden ("Sync from niftyindices.com", "Clear cached files"). A visitor
cannot guess their way to a button that clears everyone's caches.

### Slot 3 — the phone (03:35 UTC, done)

**Controls at 390px: 61 clicked across 11 pages, nothing thrown.** The same
sweep as slot 2, at phone width; Backtest exposes one more control there.

**Tap targets, measured with touch emulation so the coarse-pointer rules are in
force.** Before and after, counting only targets a finger actually aims at (an
element clipped to a sliver — the focus-only skip link, a checkbox hidden
behind its own label — is not one, and counting them made the number
meaningless):

| Page | Under 44px before | After |
|---|---|---|
| Dashboard | 24 | **0** |
| Screener | 21 | **0** |
| Actions | 30 | **0** |
| Portfolio, Sectors, Breadth, Guide, Watchlist | 1–4 each | **0** |
| Sector rotation | 2 | 1 |
| Configuration | 13 | 12 |

Three causes, each a real bug rather than a near miss:

1. **Padding cannot make a 16px line box 44px tall.** `.db-sym a` came out
   38.2px and `.mq-more` 42.8px with 11px of padding top and bottom. They set
   `min-height: 44px` with the text centred now, and `.t50-chip` (32px on
   Actions) joins them.
2. **The menu button's phone rule never won.** Its base rule is
   `min-height: 40px !important`; the phone override was not `!important`, so
   the computed height stayed 40px while the CSS claimed 44.
3. **The download button's rule sits *after* the coarse-pointer block.** Equal
   specificity, later wins — so the touch override had to move below it, not
   above. The header brand link needed its height set rather than padded.

**What is left, and why it stays.** Configuration's twelve are Streamlit's own
widget internals on the one page made of sliders: the slider track (16px, seven
of them), a multiselect's "×" (7px), "Clear all" (24px), a help icon (22px).
Their labels and thumbs are what a finger uses, and giving a slider track a
44px box changes what the control looks like. It is a settings page, not the
reader's path. The one on Sector rotation is a 32px Streamlit button in a
narrow container. Both are recorded rather than bodged the night before a
launch.
