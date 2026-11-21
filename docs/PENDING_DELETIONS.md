# Deletions waiting on the owner

Owner, 11 Nov 2026: *"Record items which required delete as I am on mobile and
can't do it, whatever possible please delete it."*

## RRG (removed 21 Nov 2026, S169): nothing waits on the owner

The page and its code were deleted in the repository by #587 (`ab5adc7`), which
needed no owner step: `src/ui/views/rrg_view.py` (with `compute_rrg_data` and
`render_rrg_view`), `render_rrg_chart`, `_build_rrg_html` and `rrg_summary` in
`src/ui/charts.py`, the RRG rules in `src/ui/theme.py`, `_page_rrg` in `app.py`,
and `tests/test_rrg_centre_is_the_benchmark.py` and
`tests/test_rrg_missing_data_integrity.py`. It had **no data of its own**: it read
the ranking's prices and `fetch_benchmark_history`, so there is no R2 prefix,
release asset or `data/` file to remove for it.

Kept on purpose, as the evidence for the removal: `docs/RRG_ANALYSIS_2026-11-21.md`,
`docs/RRG_REQUIREMENTS.md` (marked superseded), `scripts/research/rrg_vs_stockcharts.py`
and `scripts/research/fetch_sector_index_closes.py`.

Left in the code (a tidy-up, not a deletion for the owner; checked 22 Nov): the
`QUADRANT` column badges in `src/ui/theme.py`'s table renderer, which no table
now has; the docstring of `src/ui/charts.py` ("Stock chart and the Relative
Rotation Graph") and the comment on `BENCHMARK_SYMBOL_N50` in `src/core/config.py`
("offered beside it on the RRG").

Not RRG, but next to it: the R2 dataset `indices/prices/research` and its job
`r2_nse_index_prices.yml` (NSE sector and size indices, in practice Screener's
charts) have no reader: the one function that read them,
`src/loaders/index_levels.fetch_index_levels`, was deleted with the old Dashboard
in #601 (S179), and
`scripts/r2_inventory.py` still requires the dataset fresh. Retiring the job is
TODO S168 (c). Its stored revisions sit under `indices/`, which
`scripts/r2_retention.py` protects, so removing them would be an owner decision
and a change to that list, not a clean-up run.

## Done, 15 Nov 2026

Run 43674615797 (`owner_cleanup.yml`, mode delete, on `fc976c8`) ended
**"done: 235 deleted, 0 failed"** after a dry run (43671866353) that listed the
same 235 with 0 skipped: 233 merged branches (321 branches before, 88 after; none
of the listed ones left; `main`, `agent/*`, stage4b, the backup and the three
open-PR branches all still there), the R2 prefix `scratch/bse_bhavcopy_2026-10-03/`
(23 objects, 1,221.8 MiB) and the release asset `tmp_session_2026-10-03.zip`.
Items 1 and 2 below are therefore done; they are kept for the record.

Still the owner's call, one by one: 69 branches holding unmerged work
(`Sandbox`, `redesign-v2*`, `feat/r2-*` and others, listed with their evidence
in the 15 Nov classification), and `history_backtests.zip` (3.3 MB, 7 Oct, named
nowhere in the code or docs).

## Third batch (15 Nov 2026): the branches of two closed PRs

Owner, 15 Nov: "Yes add both branches to the clean-up job", then "Delete them if you can". **Done.** Dry run 43708207307 listed "2 to delete, 0 skipped by a check, 4 already gone". Delete run 43708240986 first backed both branches up into the artifact `unmerged-branches-bundle` (28,280,240 bytes, expires 13 Feb 2027), then ended "done: 2 deleted, 0 failed". The repository has 17 branches.

| Branch | Tip | Why |
|---|---|---|
| `ccr-cd46f9c8-zksr9j` | `58373e2` | PR #511, closed and replaced by #535. Its tip is main's own #535 commit, so it holds nothing unmerged |
| `claude/investment-platform-audit-djf1we` | `d4db9b3` | PR #513 (the Dashboard design audit), closed. Owner: "drop it entirely". The delete run bundles it first, so it can be restored for 90 days |

Each is deleted only if its tip still matches the sha above and no pull request is open on it.

## Second batch (15 Nov 2026): the unmerged branches and `history_backtests.zip`

**Done.** Dry run 43677292481: "70 to delete, 0 skipped by a check, 2 already gone".
Delete run 43677526783: backup first, artifact `unmerged-branches-bundle`
(22,790,482 bytes, expires 13 Feb 2027), then **"done: 70 deleted, 0 failed"**.
The repository now has 19 branches: `main`, the ten `agent/*`, the stage4b
branches, `archive/probe-test`, `audit-backup-20260831`,
`fix/r2-membership-test-live-change` and the three with open pull requests.
Nothing is left on this page for the owner.

Owner, 15 Nov: *"Yes delete it"*. `.github/cleanup/branches.tsv` now lists the 69
branches that hold work never merged (24 with no PR, 45 whose PR was closed
unmerged; each with its tip sha), and `owner_cleanup.py` adds
`history_backtests.zip` (3,311,385 bytes, 3 downloads, 7 Oct 2026, named nowhere).

**Backup first.** A delete run bundles every listed branch into the artifact
`unmerged-branches-bundle` (kept 90 days) before deleting anything: 69 heads,
about 22 MB (built and verified locally on 15 Nov). To restore one:

```sh
# download the artifact from the run page, unzip it, then in a clone:
git fetch /path/to/unmerged-branches.bundle "refs/backup/<branch>:refs/heads/<branch>"
git push origin <branch>
```

## The one-tap way (15 Nov 2026)

Owner, 15 Nov: *"Build the one-tap clean-up job."* GitHub's own runner can do
what the cloud session cannot, so `.github/workflows/owner_cleanup.yml` does items
1 and 2 below plus the 233 merged branches, from a phone:

1. Open **github.com/Pareshking/Paresh/actions/workflows/owner_cleanup.yml**.
2. Tap **Run workflow**, leave *mode* on **dry-run**, tap the green **Run workflow**.
3. Open the run and read the log: one line per item, `delete`, `skip` (a check
   failed, with the reason) or `gone`, and a total. Expect **235 to delete**:
   233 branches, the R2 prefix and the asset.
4. If that is what you expect, run it again with *mode* = **delete**.

`scripts/owner_cleanup.py` re-checks each item when it runs and skips, never
forces, anything that changed: a branch someone pushed to since 15 Nov, or one
with an open pull request; an R2 prefix that is not exactly 23 objects and
about 1,221.8 MiB; an asset that is no longer 10,851,823 bytes with 0
downloads. The branch list is `.github/cleanup/branches.tsv` (each a merged PR
whose branch tip is still the PR's head, or a branch with no commit off main;
checked against all 506 PRs). Not in it: `main`, `agent/*`, stage4b, backups,
the three branches with open PRs, and 69 branches holding unmerged work, which
are the owner's call one by one. A deleted branch can be restored from its PR
page ("Restore branch").

---

Nothing on this page could be deleted from the cloud session. Both items are
outside what it can reach, for two different reasons, both verified on 11 Nov:

- **R2** — no credentials at all. `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
  `R2_ACCOUNT_ID`, `R2_BUCKET` and `R2_ENDPOINT` are all unset in the
  container, so no object can be listed, let alone removed.
- **GitHub release assets** — refused by the platform, not by a missing
  permission we could grant:
  `HTTP 403: Creating, editing, or deleting releases is not permitted for this
  session type.`

Each item below states what it is, why it is safe to remove, **what to check
before removing it**, and the exact command. Check first in every case: a
deletion that turns out to be wrong cannot be undone, and two of the three
candidates originally on this list did not survive their own check.

---

## 1. The BSE scratch prefix on R2 — 1,221.8 MiB, 39% of the bucket

`scratch/bse_bhavcopy_2026-10-03/` — 23 objects: 19 raw tar files, the built
table, the gap CSV, `status.csv` and `MANIFEST.json`.

**Why it is safe.** The alignment work it was created for has shipped: the BSE
fill of NSE-only gaps (S38), the ISIN-first `bse_fill.map_code` the gap audit
now shares with the fill (S52/S53), and `bse_daily.yml` keeping both the
release asset and `archive/bse/daily` current. Nothing under the prefix is a
live source — the table is superseded, the gap CSV is rebuilt on every
long-file build, and the raw tars are re-downloadable with
`scripts/bse_bhavcopy.py --mode download`. It sits outside every dataset
`scripts/r2_retention.py` knows, so nothing prunes it and nothing reads it.

**The one thing that used to block it is already fixed.**
`.github/workflows/bse_daily.yml` seeded from
`scratch/bse_bhavcopy_2026-10-03/bse_daily.parquet` as its third fallback;
since commit `b4f7111` it exits with an instruction to re-run with `full=yes`
instead, so deleting the prefix cannot cause a silent eighteen-year
re-download.

**Removed 15 Nov 2026** (no longer true): `.github/workflows/bse_bhavcopy_r2.yml`
carries this prefix as its *default input*. That is the dispatch-only job which
*wrote* the scratch. It never runs on its own and it writes rather than reads,
so it does not block deletion — but dispatching it would recreate the prefix.

**Check, then delete** (needs the R2 credentials):

```sh
# 1. Confirm what is there: expect 23 objects, 1,221.8 MiB
aws s3 ls --recursive "s3://$R2_BUCKET/scratch/bse_bhavcopy_2026-10-03/" \
  --endpoint-url "$R2_ENDPOINT"

# 2. The same command as a removal, without removing anything
aws s3 rm --recursive "s3://$R2_BUCKET/scratch/bse_bhavcopy_2026-10-03/" \
  --endpoint-url "$R2_ENDPOINT" --dryrun

# 3. For real, once step 2 listed exactly what step 1 did
aws s3 rm --recursive "s3://$R2_BUCKET/scratch/bse_bhavcopy_2026-10-03/" \
  --endpoint-url "$R2_ENDPOINT"
```

---

## 2. One dead release asset — 10.85 MB

`tmp_session_2026-10-03.zip` on the `data-latest` release: **10,851,823 bytes,
0 downloads**, untouched since 2026-10-03. `docs/AUDIT_PLAN.md` mentions it
only as an observation that it is waste; nothing reads it, and no workflow
names it.

```sh
gh release delete-asset data-latest tmp_session_2026-10-03.zip \
  --repo Pareshking/Paresh
```

---

## What came off this list, and why

**`ref_long_price_audit_2026-10-03.zip` is NOT dead — do not delete it.** It
was on this list as the second "dead asset" (330,498 bytes, 0 downloads,
superseded by `long_price_audit_latest.zip`). Reading
`docs/R2_RECOVERY_AND_RETENTION.md` before deleting showed otherwise: it is
named there as part of the deliberately retained 3 October reference set,
beside `ref_nse_action_list_api_2008_2026.zip` and `ref_marketlens_sectors.csv`,
mirrored in the owner's local backup. The `ref_` prefix is the convention for
reference evidence. `long_price_audit_latest.zip` is the rolling current audit,
which does not replace a dated snapshot. Zero downloads is what you expect of
an archive.

So the figure of "two dead release assets, 11.18 MB" was wrong: it is **one
asset, 10.85 MB**.

**`nse_index_rebuild/` stays** (owner, 11 Nov 2026). 12,101 KB of the
repository's 25,689 KB, 1,314 of its files NSE announcement text. It is live —
read by `src/engine/index_universe.py`, two scripts, two workflows and a test —
and it is what makes the membership history defensible. The 20%-less-space
target was dropped rather than paid for out of this.

**Two empty files were deleted** (`nse_index_rebuild/announcements/dl.log` and
`dl_old.log`, 0 bytes each, referenced by nothing; `*.log` now ignored). Across
2,046 tracked files a reachability audit found nothing else worth removing:
0 of 105 `src` modules are unimported, and every script with no caller is
either a documented hand-run tool or named by description in a spec.
