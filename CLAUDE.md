# Working in this repository

This is the NSE Momentum Terminal: ranking, backtests and a track record on
Indian equities, fed by NSE, Screener and other price sources. The prices are
the product, so **data correctness comes before features**.

## Before any work on data

Read, in this order:

1. `docs/DATA_CORRECTNESS.md` - how data is checked, which sources are trusted
   for what, the decisions already taken, and the findings already explained
   (so they are not investigated twice).
2. `docs/TODO.md` - what is open, what was promised, S-numbers.
3. `docs/PRICE_PIPELINE.md` for prices and corporate actions,
   `docs/DATA_CATALOGUE.md` for where each dataset lives,
   `docs/MEMBERSHIP_FROM_NOTICES.md` for index membership,
   `docs/THREE_SYSTEMS.md` for the three universes.

Before redesigning a page, read `docs/PAGE_DESIGN.md`: the content, table,
chart and data-check rules the Dashboard redesign settled, with their sources.

## Rules that have been decided

- Judge a fix by independent evidence (a different source, dated, quoted). A
  check that reproduces our own numbers, or text pasted from another tool, is a
  lead, not evidence. Say what was not checked.
- Do not change a price by hand. Fix the rule, or add a `data/nse_prices/notes.json`
  correction with its evidence, then rebuild the long file and run the audits.
- NSE's files do not list a security on days NSE did not deal in it; BSE's
  bhavcopy (`scripts/bse_bhavcopy.py`) says whether it traded. Check both
  before calling a gap a halt or a download fault.
- Anything promised in a conversation goes in `docs/TODO.md` the same day, with
  how we will know it is done.

## Suggesting (owner, 23 Nov 2026)

When the owner plans something or asks a question, look for a better way to reach the goal, not
only an answer to the question as asked. Offer one or two alternatives that change the approach
(example: the owner asked about Gemini writing page text; the better way was templates drafted
offline, approved once, filled by code, S203). Mark each as a suggestion, give its cost and what it
gives up, and say which you recommend. Skip it when nothing better exists; never pad with options.
Improve wording on pages and in docs whenever you touch them.

## tipsheet.markets may be copied (owner, 28 Nov 2026)

"We can copy, it is by my friend only who works at Zerodha. We worked together and I have his go ahead."

- Layout, chart forms, table design and wording may be taken from tipsheet.markets as they stand (S237), with the
  page or pattern it came from noted in the TODO row or the PR.
- Still not taken: its name, logo or anything that would make a reader think our pages are Tipsheet's or Zerodha's.
- The permission is the owner's word, recorded here; a written note from its author, if the owner gets one,
  goes in `docs/archive/`.

## Decisions when the owner is away (owner, 23 Nov 2026)

"Don't stop work ... If you want to continue working and make things ready, and I am not available, you can always benchmark with
good websites and move ahead, in most cases I will support you. There might be few where some decisions may get reverse but I am ok
with it. You can take other agents support for your decisions if needed."

- A choice that would wait for the owner (a wording, a rule, a number, a layout) is taken by benchmark instead: what established sites
  and design systems do, dated, linked and quoted (as `docs/archive/S193_BENCHMARK_HJ_2026-11-23.md`). A second agent may review the
  choice when it is close. Where the benchmark goes against a decision the owner already took, keep the owner's decision.
- Record each such choice in `docs/TODO.md` as "decided by benchmark, owner to confirm" and list it in `docs/HANDOVER.md`'s
  pending-approvals list with the evidence, so a reversal is cheap. Then build it and move to the next item; do not stop.
- Still not taken alone: anything that moves published ranks, the frozen track record, or money in the model book (for example #638).

## Working on a change

- Branch, commit and push to the branch you are given; open the pull request as a
  draft. **Merge without asking once CI is green on the PR's current head** (owner,
  23 Nov 2026: "Do not take permission if CI is green henceforth and merge it"). Check
  the head yourself (a notification can name an earlier commit), squash-merge with
  `expectedHeadSha`, and read Production QA after. Owner decisions on what a change
  does (a page's wording, a rule, a number) are still the owner's: this is about the merge.
- After a squash merge, restart the branch from `main`; push with
  `--force-with-lease`.
- Tests: `python -m pytest tests -q`. Lint: `ruff check`. A data file the
  nightly sync writes (`data/`) is not edited by hand.
- Update `CHANGELOG.md` for a user-visible change and `docs/TODO.md` for the
  state of the work.

## Saving resources (owner, 22 Nov 2026: batch and saving measures for all new changes)

Every push to a pull request reruns the full validation (~14 min; `v1-full-validation` is about half of
all Actions minutes), and every session reads the docs above, so text and pushes cost real resources.

- **Batch.** Finish a change locally (code, tests, docs, TODO, CHANGELOG), run the checks, then push
  once. Do not push small follow-ups one at a time; collect them and push together. Before pushing a
  docs-only fix to an open PR, ask whether it can wait for the next push.
- **Open the PR last** (owner, 23 Nov 2026). CI runs only on a pull request and on main, so commit
  and push to the working branch as you go and open the PR once the batch is finished. Every push to
  an open PR is a full run, and every merge is another on main.
- **One PR per decision round, not per item or document.** Items that are ready together go in one
  PR (S213 and S218 would have been one; item B one, opened when done). A TODO or handover update
  rides in the PR of the work it describes. Keep apart only a live fault on the site (it goes out
  alone, at once) and an item still waiting for the owner. Cap a batch at about a day's decided
  work, so a Production QA failure after the merge has few places to look.
- **Run CI's checks locally before opening the PR:** `pytest`, `ruff`, `headless_smoke.py`, and
  for page changes the number, glossary and requirement audits (`scripts/number_format_audit.mjs`,
  `glossary_audit.mjs`, `check_dashboard_requirements.mjs`), so the PR's one run passes.
- **Keep the docs lean.** A TODO row holds the requirement, how we know it is done, and a one- or
  two-line status with run IDs; the narrative goes in the PR or `docs/archive/`. Do not paste logs or
  long evidence into TODO rows.
- **One living handover** (`docs/HANDOVER.md`, S201): update its state section in place
  instead of writing a new dated file.
- **Do not wait by polling.** Use the PR's events; re-read CI only when an event says it finished.
- **Before adding a job, a schedule, a dataset or an R2 copy,** name who reads it. Nothing is written
  that nothing reads (S195 §4).
- Open items: S199 (docs-only PRs skip the full validation), S200 (TODO trimmed), S201 (one living
  handover), S202 (Production QA cadence).
