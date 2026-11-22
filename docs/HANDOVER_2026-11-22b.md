# Handover, 22 Nov 2026 (evening): Pareshking/Paresh, coordinating role

This replaces `docs/HANDOVER_2026-11-22.md` (PR #613, never merged: close it).
Paste the prompt at the end as the first message of a fresh session.

## The owner's standing rules (unchanged)

- **One activity at a time.** Don't wake other sessions unless a task needs it.
  Start no new work from TODO; finish what is listed below, in order.
- **Merging:** you do the merges. Merge only when CI is green on the PR's
  **current head** and it merges cleanly with `main`. Squash-merge with
  `expectedHeadSha`. After a squash merge, restart your branch from `main`.
- **Before taking an S-number,** check open PRs as well as `main`. Next free:
  **S197**.
- **Verify every claim yourself.** Nothing is deleted without the owner's yes on
  each item; the `ref_*` release files always stay.
- **Tests:** `python scripts/fetch_nse_closes.py` first, then
  `python -m pytest tests -q` (serial; no `-n`), and `ruff check`.
- **Never `git checkout` in a checkout another agent is using;** use
  `git worktree`.
- **Bring the owner** only decisions that are theirs, a few at a time, each with
  a recommendation and a bold reply line.
- **Auto-compaction at 50%:** `.claude/settings.json` sets
  `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50` (owner, 22 Nov).

## State at handover

`main` = `bcfc880` (the backfill's actions commit) plus the squash of this handover's PR. Merged on 22 Nov after the morning handover: #611 (S185),
#614 (S194), #615 (Nifty 1000 priced like the 750), #616 (S173 formatter),
#617 (S196), and this handover's PR.

Open PRs: **#607** parked by the owner (read-only R2 key, the owner makes the
token later). **#613** is the superseded morning handover: close it.

No work is in progress in any session.

### What was done (where to read it)

| Item | Result | Read |
|---|---|---|
| S194 Nifty 1000 pre-freeze fixes | F1–F7 + L1 merged (#614) | TODO S194 |
| Nifty 1000 priced like the 750 | Screener nightly, SS weekly, former members, NSE two-year file, inventory and smoke checks all cover the 1000 (#615) | TODO S175, `PRICE_PIPELINE.md`, `THREE_SYSTEMS.md` |
| S173 formatter + 8-rule style sheet | merged (#616); lakh forms ₹1.22 lakh Cr / ₹34.1 lakh restored at the owner's word (#617) | `PAGE_DESIGN.md` §3a, `scripts/number_format_audit.mjs` |
| S196 Nifty 1000 constituent history | notice ledger, anchor check, size warning, ENNATURE/IGLSPIRITS removed with NSE notice evidence; 1,000 on every date (#617) | `MEMBERSHIP_FROM_NOTICES.md` (S196 section), TODO S196 |
| Industry labels | the 1000's NSE labels matched to the 750's by a spelling-proof key; unknown labels logged (#617) | `src/loaders/extra_universe_loader.py` |
| S175 short NSE columns | filled: run 45038280304 green, parity passed before publish, `nse/closes_2y` revision f0a6b0cc…; columns starting 5 Oct 237 → 0, 115,652 sessions added, 0 stored closes changed | TODO S175 |

## Queue: one at a time, in this order

1. **23 Nov morning checks** (first runs after #615/#617; record each in TODO
   S188 with its run ID):
   - `screener_sync` (~22:00 UTC 22 Nov): the 58 Nifty 1000 members without a
     30 Oct close are fetched; any left are named in
     `data/screener_pending_history.json` and on the banner.
   - `daily_sync`: the weekly fill with `--with-nifty-1000` adds its next batch.
   - former-member prices for ENNATURE and IGLSPIRITS.
   - `nse_reference_sync`: the first `nifty_1000` anchor check and the first
     daily notices check (`scripts/nifty1000_notices.py`).
   - `nse_long_prices`: the run with the 104 new series.
   - `r2_inventory`: lists `snapshots/rankings_1000`, `_nano`, `_combined`.
   - When the weekly fill has held for a run, make `--with-nifty-1000` the
     default in `scripts/build_weekly_fill_extra.py` and tighten its
     committed-file test.
2. **Watchlist build**, branch `claude/friendly-hawking-0fp25l` (`1ff94f8`),
   untested. The owner approved the full mock-up. Build it on the S173
   formatter (`src/ui/formats.py`), then pass the requirements check, the layout
   audit and `number_format_audit.mjs`.
3. **S195 resources report, due 25 Nov.** Branch `claude/laughing-cray-ynqt45`
   (`c44e055`): draft `docs/RESOURCES_2026-11-25.md` plus catalogue fixes.
   It predates #615–#617: add the Nifty 1000 datasets (R2
   `snapshots/rankings_1000`, `nse/closes_2y` now 1,000 wide, the notices
   ledger). Bring the yes/no clean-up list to the owner. **Delete nothing.**
4. **Later, not now:** stock page mock-up v2 (keep the price chart with its RS
   pane; hover readout fixed height, reuse #589's fix with a test; volume pane
   "Volume"; remove stop loss and chandelier exit), then S193 (consistency
   audit), then the Nifty 1000 leads L3/L4 in TODO S194.

## Owner decisions of 22 Nov still to record

In the first PR that touches `DASHBOARD_REQUIREMENTS.md` (S174):
- Keep the Nifty 500 before 2012, labelled "unchecked (Kaggle)", and also show
  each test from 2012.
- The track-record ledger stays in git, with a nightly R2 copy and a check that
  the two match.
- When R2 is unreachable, fall back to the repo copy, with a footer note and
  the date in **red** when it is more than one trading day old.

Recorded today: the NSE two-year file stays monthly (owner: "Keep it monthly");
`theme.FORMAT_MAP` kept; lakh forms for large amounts.

## Dates to watch

- 23 Nov: the checks in queue item 1; breadth after Monday's sync.
- 25 Nov: S195 due.
- 27 Nov: Actions-minutes week ends; S142 (private repo) decided after.
- 29 Nov (Sun) 05:17 UTC: first scheduled `backtest_reference` run.
- 1–5 Dec: monthly freeze. First run without `closes.parquet` in git, the
  Nifty 1000 November freeze, the skip-5 shadow, and the first S185 evidence
  bundles: check with `python scripts/replay_frozen_month.py --system 750
  --month 2026-11` and that a bundle exists for every system frozen.
- 2 Dec: rebalance checks S95, S111, S154; the owner decides S95 and S111 after.

## Prompt for the new session

```
You are taking over coordination of Pareshking/Paresh (NSE Momentum
Terminal). Read CLAUDE.md, then docs/HANDOVER_2026-11-22b.md, then the open
rows of docs/TODO.md (S175, S188, S194, S195, S196). Follow the standing rules
in the handover exactly: one activity at a time, you do the merges (green CI
on the current head, squash, expectedHeadSha), check open PRs before taking an
S-number (next free S197), verify every claim, delete nothing without the
owner's yes. Close PR #613 (superseded). Then work the queue in order,
starting with the 23 Nov first-run checks.
```
