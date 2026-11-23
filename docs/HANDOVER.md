# Handover: Pareshking/Paresh, coordinating role

The one living handover (S201): edit this file in place at each handover (the
state, queue and dates sections); do not write a dated copy. Earlier dated
handovers are in `docs/archive/HANDOVER_*.md`. Paste the prompt at the end as
the first message of a fresh session.

_Last updated: 23 Nov 2026 ~14:00 IST (08:30 UTC), coordinating session of 22-23 Nov (session_016X4g5aV4BforqdG6bYB6KH)._

## The owner's standing rules (unchanged)

- **One activity at a time.** Don't wake other sessions unless a task needs it.
  Start no new work from TODO; finish what is listed below, in order.
- **Merging:** you do the merges. Merge only when CI is green on the PR's
  **current head** and it merges cleanly with `main`. Squash-merge with
  `expectedHeadSha`. After a squash merge, restart your branch from `main`.
- **Before taking an S-number,** check open PRs as well as `main`. Next free:
  **S204** (S203 page sentence templates; S197, S198 by #621/#623; S199-S202 reserved for queue items 6-9).
- **Verify every claim yourself.** Nothing is deleted without the owner's yes on
  each item; the `ref_*` release files always stay.
- **Tests:** `python scripts/fetch_nse_closes.py` first, then
  `python -m pytest tests -q` (serial; no `-n`), and `ruff check`. In a git
  worktree run the fetch inside the worktree too (6 `test_nse_prices.py` errors
  otherwise).
- **Never `git checkout` in a checkout another agent is using;** use
  `git worktree`.
- **Bring the owner** only decisions that are theirs, a few at a time, each with
  a recommendation and a bold reply line.
- **Auto-compaction at 50%** (`.claude/settings.json`).
- **Owner, 22 Nov night:** whatever a session starts (PR, CI, merge, workflow
  run) it finishes before it hands over.
- **Saving resources, for all new changes (owner, 22 Nov night):** the rules are
  in CLAUDE.md, "Saving resources". In short: finish locally and push once;
  batch follow-ups; one PR per piece of work (TODO and handover edits ride in
  it); lean TODO rows; no polling; nothing written that nothing reads. Today's
  handover PR ran the full validation six times for text edits: that is the
  pattern to stop.

## State at handover

**23 Nov ~08:30 UTC.** The owner asked for a fresh session from 14:00 IST; this session stopped new work and finished
what was in progress. Merged on 23 Nov: #628, #630, #634-#637, #639 (S209), #640 (S212 clean-up, ~13,700 lines),
#644 (S214), #645 (numpy 2.5.5; Dependabot #641-#643 carried in and closed), #646 (S205 step 1).

**Open pull requests**
- **#647, S213 batch PR** (branch `ccr-b633a7d9-s213`, draft). Merge when CI is green on its
  current head. It carries:
  - S215 explained: the 34 stocks missing from the > ₹2,000 Cr ranking are new listings under 63 sessions (NSE
    `EQUITY_L.csv`; DATA_CORRECTNESS §5). The reconciliation log now prints `new_listings=N` apart from `missing=`
    (owner, 23 Nov: "Let log shows"; `momentum.too_new_to_rank`, counted from the first price).
  - S205 step 2: the number-format audit saves each page's text (`--save`), and the glossary audit reuses it
    (`--cache`) for the nine pages both read. Shared reader: `scripts/_page_text.mjs`. A planted glossary fault in
    saved text is still reported.
  - pyarrow back to 24.0.0, and Dependabot ignores 25+. The owner's 23 Nov 07:58 boot log showed Streamlit Cloud
    replacing #645's 26.0.1 ("known segfault, apache/arrow#50471"), as on 7 Nov.
  - The S205 CI figure after #646: the layout step went from 15 min 37 s to 7 min 40 s.
- **#638 (S211, one date rule):** draft. Merge only after the 1 Dec fill **and the owner's explicit yes** (659 of 750
  published ranks move). It conflicts with main again: merge main into it once, just before merging. Reminder
  `trig_01MGhPjDNkLj9QptrreSjzZh` fires 1 Dec 13:30 UTC.
- **#607** is parked by the owner (read-only R2 key).

**Waiting on the owner (24 Nov, laptop back):**
- (a) Run the branch clean-up in TODO S212: tags for group C, then delete the merged branches. This session could
  not: proxy 403 on tags, branch deletes refused.
- (b) Send the Streamlit log after tonight's nightly run, the first past #636/#644. S210 is done when it reads
  "Precomputed ranking accepted" for all three systems: open each system once after boot. Once the S213 PR is
  deployed, the same log should no longer say "Replacing with pyarrow<25".
- (c) Optional: set the Dependabot secrets (TODO S209). Until then every Dependabot PR fails validate at the R2 step.

**After the S213 PR merges:** read the layout step's time on its CI run. If it is 6 min or less, S205 is done after
2-3 clean runs (record the run IDs). If not, the parallel runner (`run_page_audits.sh`; the patch is in the old
session's scratchpad, so rebuild it) is the next and last step.

**Not started, in the queue:** S213 beyond S215 (price pipeline end to end); S208 (price_fingerprint once per frame;
the Backtest long file in `st.cache_resource`); S207 (b, c). These were taken over from the speed session.

**Local state:** nothing uncommitted. The worktree `.claude/worktrees/agent-aa31e63eff604b062` (branch s205, merged)
and the s213 worktree are scratch; the main checkout is on `ccr-b633a7d9-f1fqfl` (#638's branch).

From the **January 2027** book: three systems, **Nifty 750 · Nifty 1000 · Ultra Nano Cap** (replaces "> ₹2,000 Cr", key
`nano` kept: ₹1,000 Cr or more outside the Nifty 1000; tracked down to ₹500 Cr, prices from ₹800 Cr, a holding below
₹1,000 Cr sold at the rebalance); **Combined retired**, its ledger read-only as frozen to Dec 2026. Read TODO S198 before
any work on the systems; the 1-5 Dec freeze runs on today's four systems.

### What was done 22 Nov evening (where to read it)

| Item | Result | Read |
|---|---|---|
| Watchlist (S182) | built on the S173 formatter; foot date printed once (was twice); requirements 29/29, layout clean 412/1400, number audit clean; plan agrees with Actions in all four systems; live on e385c13 (Production QA 45045534145) | TODO S182, CHANGELOG |
| S195 resources report | `docs/RESOURCES.md`, due 25 Nov, **done**: Nifty 1000 datasets added, evidence set is 17 datasets (16 unread), memory flat (487-491 MB; no change from #610-#619, bisected); owner answered every clean-up item | the report §1, §4 |
| S195 clean-up | owner: "go with your recommendations", "delete both branches". 4.1/4.6 R2 retirements, 4.4 `reconcile_*`, 4.7 narrower download, two merged branches; 4.3 changed to keep (premise wrong) | TODO S195, `PENDING_DELETIONS.md` |
| Deletions carried out | `owner_cleanup.yml` run 45051454256 (dry run 45051299136 first): the six `reconcile_*` release files and the two branches, 8 deleted, 0 failed. R2: dry run 45051288448 planned 514 keys / 195 MB (446 for the two retired datasets, 68 routine weekly pruning under the existing rules); applied by dispatch 45051716173: `RETENTION_APPLIED deleted=514`, then the recovery audit PASS (143 current pointers, 151 immutable revisions read back) | TODO S195 |
| #611 (S185) | was already merged 12:54 UTC (a relayed message said otherwise) | TODO S185 |

## Queue: one at a time, in this order

0. **Finish what is open**: merge #647 on green; the owner's 24 Nov items (a)-(c) above; then S205's
   CI figure and, only if needed, the runner. Then S213, S208, S207, and the S193 items (one at a time with the owner).

1. **23 Nov first-run checks** (record each in TODO S188 with its run ID). The
   Screener sync is scheduled 17:07 UTC but GitHub starts it 5-7 h late (22:09,
   23:02, 23:31 UTC on recent nights; ~40 min a run). `daily_sync` 02:00 UTC,
   `r2_archive_inventory` 02:31, `nse_reference_sync` 02:45 (all usually hours
   late); `nse_long_prices` runs after `daily_sync` completes.
   - Done 23 Nov night (TODO S194): `screener_sync` 45077658093 (31/31 have a 30 Oct close, 0 pending,
     extra 219/219) and `daily_sync` 45081696293 (weekly fill holds the Nifty 1000's 30; now the default).
     ENNATURE/IGLSPIRITS need no former-member price (no book held them; S196).
   - `nse_reference_sync`: first `nifty_1000` line in `anchor_checks.jsonl`, the
     notices ledger committed (S196).
   - `nse_long_prices`: green with the 104 new series.
   - `r2_archive_inventory`: lists `snapshots/rankings_1000`, `_nano`, `_combined`.
2. **S193, one item at a time with the owner** (examples, recommendation, opposite view). Stock page v2
   live (#628). D (glossary, `docs/GLOSSARY.md`) and K's /stock redirect merged (#631). Next: prepare
   A-C and E-L for the owner; do not apply without their decision. S203 templates: draft only.
3. (merged into 2)
4. **After the 1-5 Dec freeze: S197**, membership from NSE's daily CSVs for
   all seven indices (the Nifty 1000 joins `build_membership_history.py`; a
   missed day is reported, not bridged), and NSE's notices read on the **25th
   of each month** for all seven as a forward warning and cross-check (the
   daily `nifty1000_notices.py` step leaves `nse_reference_sync.yml`; the
   reader is generalised, not deleted). Must be merged **before S198's
   switch**: Ultra Nano Cap's exclusion is the Nifty 1000 on each month-end
   date.
5. **S198, three systems from the January 2027 book** (all decided by the
   owner, 22 Nov; read the TODO row): Nifty 750 · Nifty 1000 · Ultra Nano Cap
   (₹1,000 Cr or more outside the Nifty 1000; key `nano` kept). Combined
   retired, its ledger kept read-only. Below ₹1,000 Cr tracked, not buyable,
   until below ₹500 Cr; prices collected from ₹800 Cr; a holding below
   ₹1,000 Cr sold at the rebalance. First, in early December, the
   measurement and backtest in S198 (a); this needs R2 (a CI job with R2
   secrets, or #607's read-only key once the owner makes the token). Then
   the build, **merged before the 31 Dec signal**.

(Items 4 and 5 come from the S197/S198 session, PR #623.)
Done 23 Nov and gone from the queue: S185 replay step (#625), S199, S201 (#625), S200 (#626),
S194 L3/L4 and S202 (#627).

## Found, not fixed (recorded so it is not rediscovered)

- **Fixed 23 Nov: `test_zeroed_weight_session_recovers.py` failed only in a full run.** Cause: past
  1,800 MB resident (`memory.GUARD_MB`), `app.py` drops every `src.*` module, so the test read a stale
  `startup_metrics`. Reproduced with `UMIYA_MEMORY_GUARD_MB=1` (fails), fixed by reading the live module.
- **Production QA races a data-only commit that lands right after a merge**:
  run 45038274440 tested #617's merge (8f11650) while Streamlit already served
  the next commit, `bcfc880` (chore(data)), and failed "Unexpected served
  revision". S186 handles the opposite case (the live app still on the build
  before). Harmless; the next push's QA passed.
- **Portfolio QA "Equity card MTD summary / Calendar live-month evidence is incomplete"**: the
  desktop read came before the page finished streaming (desktop ~1,000-2,300 characters, phone
  ~3,100). Last seen 20 Nov (run 44744994558); #580's `MONTH_TILE` wait fixed it: 0 in the 42 runs
  from 21 Nov 04:28 to 22 Nov 19:48. Reopen only if it recurs after #580.
- **A module rename shows `ModuleNotFoundError` for a few minutes during the redeploy**: run
  44945662766 (21 Nov 20:19) hit it 3 min after #599 renamed `breadth_view.py` to `market_view.py`;
  the next run, 10 min later, passed. Readers see it too, so time a rename away from busy hours.
- **One memory-bench run did not repeat**: Backtest warm 22 s with a 74 MB drop
  mid-run; six more runs gave 4.6-5.2 s. Recorded in the report §1.
- `audit_page_bench.py` needs the Python `playwright` package: install
  `playwright==1.63.0` (the version of the Node package here), which finds the
  pre-installed browser; do not run `playwright install`.

## Approved in advance (owner, 23 Nov ~03:45 IST, before sleeping)

Each only with CI green on the PR's current head, squash merge, nothing deleted, no price edited by hand:
1. Merge the S193 item D PR (glossary applied to every page + its check) after review, full suite, audits.
2. Merge tonight's job fixes: 23 Nov first-run results in TODO S188/S194; `--with-nifty-1000` default once
   the weekly fill holds; the keep-awake schedule if it has not run by 00:41 UTC; a first-run job that fails
   because of our code.
3. Fix `/stock?stock=X` "Page not found" (S193 item K) with a test.
4. Revert one of these merges at once if Production QA fails because of it; root-cause on a branch.
5. "Continue other pending works also": anything in the queue that needs no new owner decision. S193 items
   other than D still need the owner one at a time; prepare them (examples, recommendation, opposite view)
   but do not apply. S203 templates: draft, do not apply. Not S197/S198 (after the 1-5 Dec freeze).

## Owner decisions of 22 Nov still to record

In the first PR that touches `DASHBOARD_REQUIREMENTS.md` (S174):
- Keep the Nifty 500 before 2012, labelled "unchecked (Kaggle)", and also show
  each test from 2012.
- The track-record ledger stays in git, with a nightly R2 copy and a check that
  the two match.
- When R2 is unreachable, fall back to the repo copy, with a footer note and
  the date in **red** when it is more than one trading day old.

## Dates to watch

- 24 Nov: the owner's branch clean-up and Streamlit log (S210 "accepted" for all three systems; no pyarrow "Replacing").
- 27 Nov: Actions-minutes week ends; S142 (private repo) decided after. Also
  Friday's `ss_sync`: the first without the `reconcile_*` upload (should pass).
- 29 Nov (Sun) 03:17 UTC: the scheduled `r2_retention` run (the retired
  datasets should already be gone; it should plan 0 for them). 05:17 UTC: first
  scheduled `backtest_reference` run.
- 28 Nov (Sat): the first Saturday audit downloading its seven files by name.
- 1–5 Dec: monthly freeze. First run without `closes.parquet` in git, the
  Nifty 1000 November freeze, the skip-5 shadow, and the first S185 evidence
  bundles (queue item 2 makes the replay check possible).
- 2 Dec: rebalance checks S95, S111, S154; the owner decides S95 and S111 after.
- 25 Dec: first monthly notices check (S197), if merged by then.
- 31 Dec: signal for the January 2027 book: S197 and S198 merged before it;
  the first three-system freeze is 1-5 Jan 2027.

## Prompt for the new session

```
You are taking over coordination of Pareshking/Paresh (NSE Momentum
Terminal). Read CLAUDE.md, then docs/HANDOVER.md, then the open
rows of docs/TODO.md (S205, S209, S210, S211, S212, S213, S185, S188, S197, S198). Follow the standing rules
in the handover exactly: one activity at a time, you do the merges (green CI
on the current head, squash, expectedHeadSha), check open PRs before taking an
S-number (next free S216), verify every claim, delete nothing without the
owner's yes, finish whatever you start before handing over, and follow
CLAUDE.md's "Saving resources" (finish locally, push once, batch follow-ups). Then work the
queue in order, starting with item 0 (merge #647 when green).
```
