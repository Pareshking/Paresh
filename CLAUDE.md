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

## Working on a change

- Branch, commit and push to the branch you are given; open the pull request as a
  draft. Merge only when the owner says to, and only after CI is green **on the
  PR's current head** (a notification can name an earlier commit).
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
- **One PR per piece of work**, not one per document. A TODO or handover update rides in the PR of
  the work it describes, unless the work is already merged.
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
