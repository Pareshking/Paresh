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
