# Resources and data whereabouts, after the 20-22 Nov changes (S195)

> Drafted 22 Nov 2026 at `main` 8ee4b95; reviewed and brought up to `main` e385c13 (after
> #615-#619, the Nifty 1000 and the Watchlist) the same evening by the coordinating session.
> Each "nothing reads it" grep was run again at e385c13; the memory bench was run again.

Owner, 22 Nov 2026: *"memory usage after all these changes and overall GitHub
resources usage and Data whereabouts, which data is where, location, storage
and requirements to store or not store in R2 and old data cleaning from R2 if
any, removing anything stored and not in use from GitHub"*.

Measured on 22 Nov 2026, read-only: at `main` 8ee4b95 (after #609), then re-checked at e385c13.

**Nothing has been deleted.** Every clean-up candidate is in section 4, each with
a yes/no line for the owner.

## Summary

- **Memory is flat now.** One reader opened 22 pages and the server stayed at
  487-491 MB (this machine; 517-524 MB at 8ee4b95 on the same machine). On 7 Nov it grew
  from 330 to 695 MB over the same 22 visits.
  - Portfolio warm: 2.4 s, down from 8.2 s on 7 Nov.
  - The highest peak is the Backtest page's first, cold open: 838 MB.
  - Nothing comes near the ~2.7 GB container.
  - The Nifty 1000 and the Watchlist build (#610-#619) changed neither.
- **GitHub Actions** ran about 2,000 minutes in 38 hours (21-22 Nov), roughly
  8,760 a week. That is a floor, and 3.8 times the 10-16 Nov week.
  - 76% comes from pull requests and pushes, not from the data jobs.
  - `v1-full-validation` alone is 52%.
- **Storage is small and no longer growing fast.**
  - R2: 1.56 GiB, 16% of its free 10 GB.
  - The release: 855 MB.
  - Artifacts: about 235 MB, down from 1,237 MB on 10 Nov.
  - The repository: 30.7 MiB packed. `data/` grew 11.5 MB in 31 days, but 6.1 MB
    of that is now out of git (S178). Ongoing growth is about 1-2 MB a month.
- **Clean-up: no large win is left.** What remains (section 4) totals about
  250 MB, most of it in R2 copies that no code reads.
  - 25 MiB is `calculations/rankings`, retired on 16 Nov but still stored.
  - About 185 MiB is `prices/ss`. Its R2 copy has no reader.
  - The rest is small.
  - Most items sit under protected R2 prefixes, so each needs the owner's yes
    and a change to `PROTECTED_DATASETS`.

## 1. Memory (a)

`scripts/audit_page_bench.py --rounds 2`, run again on 22 Nov evening at `main` e385c13 (after the Nifty 1000
and the Watchlist build):
- A local `streamlit run app.py`, with an empty cache for round 1.
- Each page opened in headless Chromium.
- The server's resident memory sampled every 100 ms.
- 0 Streamlit errors on all 22 loads.
- This container has no R2 keys, so the app read the release files. That is
  its own fallback, and the same frames it reads from R2.

| Page | Cold s | Warm s | Peak MB cold / warm | Resident after, warm |
|---|---|---|---|---|
| Dashboard (`/`) | 9.3 | 2.1 | 567 / 534 | 488 |
| Portfolio | 5.0 | 2.4 | 608 / 522 | 488 |
| Actions | 1.7 | 1.6 | 506 / 537 | 488 |
| Sectors | 3.1 | 1.1 | 506 / 489 | 488 |
| Watchlist (new page, empty list) | 2.3 | 1.2 | 495 / 498 | 487 |
| Market | 3.0 | 2.2 | 512 / 543 | 488 |
| Indices | 1.4 | 1.6 | 476 / 509 | 488 |
| Backtest | **23.3** | 5.2 | **838** / 573 | 491 |
| Configuration | 1.1 | 1.0 | 493 / 493 | 490 |
| Guide | 1.1 | 1.1 | 493 / 506 | 489 |
| Stock page (RELIANCE) | 1.5 | 1.5 | 502 / 504 | 487 |

**The same bench at 8ee4b95 on the same machine and data** (where the draft was measured): resident 517-524 MB
warm, Backtest 23.9 s cold / 4.6 s warm, peak 844 MB. So #610-#619 (the Nifty 1000, the formatter, the Watchlist)
did not raise memory or slow a page; the absolute figures differ from the draft's 431-437 MB because the machine
differs, which is why the comparison is made on one machine.

**One run did not repeat.** The first run at e385c13 had Backtest warm at 22.0 s and resident memory falling by
74 MB mid-run, as if the caches had been dropped. Not reproduced in a second full run or in five two-page runs
(Backtest, then Guide, Watchlist or Configuration, then Backtest; at 8ee4b95, #614, #615, #616, #617 and e385c13,
4.6-5.1 s each). Cause not found; a mid-run refresh of the release files is possible and was not checked.

Against the 7 Nov run (`docs/AUDIT_PLAN.md` 0.5, same script, same kind of
machine):

- **A1's open item is answered.**
  - Memory is flat across the second round: 487-491 MB, against "330 -> 695 MB,
    never released" on 7 Nov.
  - Portfolio warm is 2.4 s, against 8.2 s. S115 had already measured 991 ms on
    a second view.
- **The Backtest cold open is slower than on 7 Nov (23.3 s against 6.0 s).**
  This run fetched the long price file over this container's proxy on first
  use, so the figure includes a download that a warm production process
  doesn't repeat. The warm open is 5.2 s (4.6 s on 7 Nov). Treat 23 s as not
  comparable until it is measured where the file is cached.
- **S61's limits:**
  - The container is about 2.7 GB (Streamlit's documentation, as quoted in
    `docs/archive/MEMORY_AUDIT_2026-10-08.md`). `docs/AUDIT_PLAN.md` says
    "~1 GB container"; the two disagree, and neither was measured.
  - Against either figure, one reader peaks at 838 MB and settles at about
    490 MB.
  - S68 (a separate app for Backtest) stays deferred. Its trigger, `Memory peak
    ... at page:backtest` lines near the limit in the production log, has not
    been reported.
- **Production: not measured.** The owner's Streamlit Cloud log is the only
  source (`Memory peak` lines, S67), and none from after the redesigns was
  available to this session.
- **Not measured:** two readers at once (`docs/archive/MEMORY_AUDIT_2026-10-08.md`
  has the method), and `/screener`, which the bench does not open since the home
  page became the Dashboard.

## 2. GitHub (b)

### Actions minutes

The S142 measurement (session_016X4g5X82JyEPnDNd8HbWgW), received 22 Nov.

**Window:** 2026-11-20 18:30 UTC to 2026-11-22 08:56 UTC (38.4 h).

**Method:**
- The same as the 10-16 Nov baseline of 2,299 min a week.
- Per run: `max(1, ceil(wall minutes))`.
- That is wall time, not the API's billable field. It undercounts jobs that run
  in parallel, so read every figure as a floor.
- 3 unfinished runs counted as 0.

**Extrapolation:** the 30-day figure below is scaled up from 38 hours, and
labelled as an extrapolation. The full 21-27 Nov week is measured on Fri 27 Nov.

| | |
|---|---|
| Runs | 785 (150 skipped) |
| Minutes in 38.4 h | 2,003 |
| Per week (extrapolated) | about 8,760 |
| Per 30 days (extrapolated) | about 37,500 |
| Against 10-16 Nov | 3.8x |
| By event | pull_request 1,096; push 431; schedule 262; workflow_dispatch 186; workflow_run 28 |

| Workflow | Minutes | Runs | Note |
|---|---|---|---|
| v1-full-validation | 1,034 | 159 | 52% of the total. Every PR and push runs the whole suite and the app checks, about 6.5 min each |
| canonical_parity | 165 | 162 | Every PR and push |
| lint | 157 | 157 | Every PR and push |
| nse_indices | 152 | 5 | **Mostly one-off**: the 2012-to-date backfill on 21 Nov (S168). Nightly runs not yet measured |
| v1-production-qa | 128 | 34 | Every push to main and every 6 h |
| ss_sync | 87 | 1 | Weekly, Fridays |
| screener_sync | 81 | 2 | Nightly |
| r2-streamlit-production-gate | 42 | 42 | |
| nse_sample_check | 32 | 3 | Dispatch / PR on its own files |
| r2-focused-validation | 22 | 22 | |
| nse_long_prices | 21 | 2 | Nightly since #597 (cheap build, about 4 min); Saturdays 16-19 min |
| daily_sync | 18 | 5 | |
| scheduled_failure_alert | 10 | 150 | Fires on every completed run, mostly skipped |
| 20 others | 54 | | 1-8 min each |

**Reading:**
- The data jobs are not what grew. PR and push traffic is, from many sessions
  merging on 21-22 Nov.
- A private repository on Free (2,000 min a month) or Pro (3,000) is out of
  reach at this rate.
- The lever is `v1-full-validation`: run it on merge rather than on every PR
  push, or batch changes into fewer PRs. That is untested, and a decision for
  the owner (S141 / S142), not part of this report.

### Artifacts

GitHub's tools here list artifacts one run at a time, so these figures are
**estimated** from one recent run of each workflow, times its runs within its
retention.

| Workflow | Per run | Retention | Standing (estimate) |
|---|---|---|---|
| v1-production-qa | 0.94 MB (run 45004898225) | 14 days | ~11 runs a day (100 runs, 13-22 Nov), about 145 MB |
| nse_long_prices | 43.8 MB (run 44899735933) | 14 days | Saturdays only (the nightly build uploads none), about 88 MB |
| v1-full-validation | 6 KB (two artifacts) | 14 days | under 1 MB |
| canonical_parity | 1 KB | 14 days | negligible |
| ss_sync | 15 KB | 30 days | negligible |
| **Total** | | | **about 235 MB** |

On 10 Nov `docs/CALL_AND_STORAGE_AUDIT.md` measured 4,960 artifacts and
1,236.9 MB, of which v1-production-qa was 1,062 MB with no `retention-days`.
That retention is now 14 days in every frequent workflow. Artifacts uploaded
before the change keep their 90-day expiry, so the old total drains by early
February. That audit's sentence "v1-production-qa.yml sets no retention-days"
is now stale (S192).

### Release assets (`data-latest`)

50 assets, 854.6 MB (22 Nov).

**Biggest:** `bse_daily.parquet` 351.8 MB, `nse_raw_pack.parquet` 172.5 MB,
`ref_tejhq_adjusted_close` 51.1 MB, `prices_full.parquet` 38.1 MB,
`ref_marketlens_close` 26.0 MB, `nse_long_value` 24.1 MB, `ref_yahoo_close`
23.7 MB, `ref_tijori_close_raw` 21.9 MB.

**Download counts are not evidence of use.** An asset re-uploaded with
`--clobber` restarts at 0. `nse_long_value.parquet` shows 0 downloads and is
read by the Backtest page.

### Repository

- **Size:** 30.7 MiB packed, 1,818 commits since 15 Aug 2026.
- **Working tree:** 64 MB. `nse_index_rebuild/` 15 MB (the membership evidence
  trail, kept by owner decision), `tests/` 9.2 MB, `data/` 7.9 MB, `src/` 4.9 MB.
- **History of `data/`:** 16.6 MB packed, all versions.

**Last 31 days:** +16.6 MB in all, of which `data/` 11.5 MB:

| File | Versions | Added | Now |
|---|---|---|---|
| `data/nse_prices/closes.parquet` | 5 | 6.1 MB | **out of git since #602 (S178)**: no further growth |
| `data/nse_indices_history.parquet` | 1 | 2.2 MB | one-off history file (S170); rewritten only by a manual `--freeze` |
| `data/reference/weekly_fill_nano.parquet` | 2 | 1.5 MB | rebuilt when a member outside the 750 is missing; with `--with-nifty-1000` (#615) the 23 Nov run adds the Nifty 1000's 30 |
| `data/former_member_prices.parquet` | 6 | 0.4 MB | rebuilt when the index loses a name |
| everything else | | about 1.3 MB | daily CSV and JSON rewrites, which delta-compress well |

**Growth from here** is about 1-2 MB a month, far from GitHub's 1 GB guidance.

**Next risk:** `data/benchmark_indices.csv` (884 KB, rewritten daily since
20 Nov; 193 KB packed so far). Parquet files do not delta-compress, so each
rewrite of the three parquets above adds about their full size. They are the
ones worth moving if S172 moves files to R2.

## 3. Data whereabouts (c)

**Locations:**
- **git (`data/`):** what the app and jobs read from the checkout.
- **Release (`data-latest`):** the large files, and the app's fallback.
- **R2:** the archive, and the app's first choice for the ranking, the
  Screener store, the long file and the NSE closes.
- **Local cache:** `data_cache/`, or `/tmp/data_cache` on Streamlit Cloud.
  Fetched copies only, rebuilt on demand.

`docs/DATA_CATALOGUE.md` is the per-dataset table (writer, readers, frequency,
retention). This report brought it up to date (section 5). This section adds
location, size and what S172 says.

### Where each kind of data lives

| Data | git | Release | R2 | Cache | Size | Must be on R2 (S172)? |
|---|---|---|---|---|---|---|
| NSE bhavcopy, actions, caps, closed days (`nse/*`) | | | yes (source of record) | | 511 + 31 + 69 + 1 MiB | already |
| NSE two-year closes | no (since #602) | `nse_closes.parquet` | `nse/closes_2y` | yes | 3.1 MB: 521 sessions × 1,250 columns, all 1,000 Nifty 1000 members (revision f0a6b0cc…, after the 22 Nov backfill and fill; 2.4 MB before) | done (S178) |
| Screener store | | `screener_prices.parquet` 8.9 MB | `prices/screener` 122 MiB (14 dates) | yes | | already (app reads R2 first) |
| Rankings, four systems | | `rankings*.parquet` | `snapshots/rankings`, `_nano`, `_combined`, `_1000` 30 MiB (before `_1000`) | yes | | already; the inventory names all four since #615 |
| Long NSE file (2008 on) | | 3 files, 42 MB | `prices/nse_long_*` 40 MiB (newest 2) | yes | | already |
| Long-file inputs (BSE table, packs) | | 352 + 172 + 4 MB | `bse/daily` 334 MiB | | | job inputs, not page data |
| SS store | | `ss_*` 47 MB | `prices/ss` 185 MiB (newest 3) | | | **R2 copy unread** (4.2) |
| Audit references (`ref_*`, `screener_max_history`) | | 186 MB | `reference/*`, `prices/screener/max_history` 175 MiB | | | protected, kept (owner, 3 Oct and 21 Nov) |
| All NSE indices from 2012 | `nse_indices_history.parquet` 2.35 MB + `nse_indices_recent.csv` | | `indices/nse_close_all` | | | S172 (b): pages read the git copy |
| Page tables: benchmarks, breadth, flows, results calendar, momentum health, track records, membership, market caps, index lists ... | 45 files, about 5 MB | | no (except copies in the evidence set) | | | **S172 (b)**: about 30 files the pages read |
| Job state: `screener_company_ids.json`, `former_member_prices.json`, `reference/nse/MANIFEST.json`, `namechange.csv`, `tejhq_actions.csv`, `nse_index_aliases/corrections/missing_sessions.csv` | yes | | | | about 0.4 MB | no page reads them. Code-like reference tables stay in git (S172 (c)) |
| Historical-evidence set (15 datasets) | | | about 8 MiB | | | **no reader** (4.5) |
| Track Record ledgers | `track_record*.json` | | no | | 9 KB | S172 / S185 (each frozen month's book on R2) |
| Nifty 1000 list and history | `indices/ind_nifty1000_list.csv` 66 KB; `membership_history.json` → `indices.nifty_1000` | | no | | | page data in git, as the other index lists (S172 (b)) |
| Nifty 1000 notices ledger | `reference/nse/nifty1000_notices.json` 3 KB (#617, S196) | | no | | | a record with each notice's SHA-256; stays in git |
| Weekly fill for stocks outside the 750 | `reference/weekly_fill_nano.parquet` 1.1 MB | | no | | | grows once by the Nifty 1000's 30 missing members (`--with-nifty-1000`, first nightly run 23 Nov); a parquet, so each rebuild adds its full size to git's history |

The Nifty 1000 is not in the historical-evidence set (4.5): the set's builder lists six indices by hand
(`scripts/r2_historical_evidence_bootstrap.py:23-29`). Nothing reads the set, so this is noted, not proposed.

`data/track_record_1000.json` is not in git yet. That is expected:
`systems.py:46` names it, and `load_ledger` returns an empty ledger until the
first Nifty 1000 freeze on 1-5 Dec (S175 / S194).

### Corrections the catalogue needed (made in this PR)

1. **`nse/source_checks`** is written by `nse_collect` (`scripts/nse_collect.py:53,376`),
   not by `nse_compare` and `nse_sample_check`. No code reads the tables;
   `nse_sample_check.py:351` (dispatch only) reads only manifest sizes.
2. **`indices/membership/nifty_total_market`** has no app reader. The catalogue
   said "Backtester (`former_members`), Track Record". Both read
   `data/membership_history.json`. Its only readers are the hand-run
   validations (`r2_membership_consumer_acceptance`, `r2_final_acceptance`).
   Its writer is `r2-historical-evidence-bootstrap`, not `daily_sync`.
3. **`prices/ss`**: the R2 copy has no reader. The three-source check and
   `ss_sync` restore from the release's `ss_*` files.
4. **Missing rows, now added:**
   - the six R2 datasets of the historical-evidence set;
   - `data/backtest_reference.json`, `indices_sync_meta.json`,
     `screener_pending_history.json`, `reference/nse_sector_index_map.csv`
     and `reference/tejhq_actions.csv`.
5. **`reference/nse/*`**: `CHANGES.json` and `anchor_checks.jsonl` have no code
   reader. They are records for people (the anchor check's agreement on
   separate days). `MANIFEST.json` and `namechange.csv` are read only by their
   own writer, as the previous run's state.

## 4. Clean-up candidates (d)

**Rules.**
- Every candidate was checked by grepping `src`, `app.py`, `scripts`, `r2`,
  `agent` and `.github` at 8ee4b95 (excluding `__pycache__`). The greps are
  quoted where the claim is "nothing reads it".
- I checked against `docs/PENDING_DELETIONS.md` and
  `docs/R2_RECOVERY_AND_RETENTION.md`.
- The `ref_*` set, `screener_max_history` and the protected datasets stay. So
  do `ref_long_price_audit_2026-10-03.zip` and `ref_marketlens_sectors.csv`:
  no code reads them, but they are named in the retained 3 Oct reference set
  (`R2_RECOVERY_AND_RETENTION.md`; `PENDING_DELETIONS.md` "is NOT dead").
- **A deletion needs a route.** The cloud session cannot delete release assets
  (HTTP 403) or reach R2. The route is `owner_cleanup.yml` (one tap,
  dry-run first) or the weekly `r2_retention` run once a list changes.
  Protected prefixes also need `PROTECTED_DATASETS` changed, by its own PR.

### 4.1 `calculations/rankings` on R2: 25.1 MiB, 114 revisions (21 Sep - 13 Nov)

- **Status:** retired on 16 Nov (S141). Its writer `r2_ranking_archive.yml`
  is gone, and `scripts/r2_inventory.py:175` says so.
- **Evidence:** `grep -rn "calculations/rankings"` finds only
  `scripts/r2_inventory.py:175` (a comment) and `r2_retention.py`'s protected
  list.
- **Is it a copy?** The catalogue says it is a byte copy of
  `snapshots/rankings`, which keeps every date.
- **Blocks:** `calculations/` is in `PROTECTED_DATASETS`.

> **Owner: delete `calculations/rankings` (25 MiB, a retired byte copy of `snapshots/rankings`)? yes / no**

### 4.2 `prices/ss` on R2: 184.8 MiB, newest 3 copies kept

- **Status:** one whole-history file a week, written by `ss_sync.yml:145`.
- **Evidence:** no reader. `grep -rn "prices/ss"` finds only the writer and
  `r2_retention.py:68,78-88`, whose own comment (81-83) says "nothing reads it
  from R2 -- ss_sync restores from the release's ss_* files". The release
  holds the same data (`ss_*`, 47 MB).
- **Options:**
  - (a) Keep 1 copy instead of 3: saves about 120 MiB.
  - (b) Stop publishing to R2 and delete the prefix: saves 185 MiB. It also
    removes the rollback the owner chose on 15 Nov ("three dailies").
- **Overlap:** if SS becomes the app's primary source, as the catalogue
  plans, the R2 copy would gain a reader. Decide together with that plan.

> **Owner: `prices/ss` on R2, (a) keep 1 copy, (b) stop publishing and delete, or keep as is?**

### 4.3 `prices_full.parquet` on the release: 38.1 MB, Yahoo era, last written 1 Oct

- **Status:** no writer; last written 1 Oct.
- **Evidence:** `grep -rn "prices_full"` finds only
  `.github/workflows/nse_sample_check.yml:46,60` and
  `scripts/nse_sample_check.py:24`, which use it as a trading-day calendar
  (`--calendar`, dispatch or a PR on its own files).
  `data/nse_trading_days.json` holds the same fact (CALL_AND_STORAGE_AUDIT, 10 Nov).
- **Order:** point `nse_sample_check` at `data/nse_trading_days.json` first (a
  small PR), then delete the asset.

> **Owner: switch `nse_sample_check` to the trading-days file, then delete `prices_full.parquet` (38 MB)? yes / no**

### 4.4 `reconcile_*` on the release: six files, about 50 KB

- **Status:** re-uploaded every Friday by `ss_sync.yml:171`
  (`gh release upload data-latest reconcile_*`).
- **Evidence:** no download pattern or script reads them.
  `grep -rn "reconcile" .github/workflows` shows only the upload; the
  `reconcile_*` names appear elsewhere only in `scripts/reconcile_report.py`
  (the writer) and a test.
- **Already kept elsewhere:** the same report goes to the `reconcile-report`
  workflow artifact (30 days).
- **Saving:** not space. It is one upload step and six assets of clutter on
  the release.

> **Owner: stop uploading `reconcile_*` to the release and delete the six assets (the artifact keeps the report)? yes / no**

### 4.5 The historical-evidence set on R2: 17 datasets, about 8 MiB, published nightly

The datasets:
- `indices/constituents/*` (six: the files in `INDEX_FILES`) and `indices/membership/*`
  (`nifty_total_market` and the five `RESEARCH_INDEXES`);
- `universes/point_in_time`, `classifications/tv_history`,
  `trading_sessions/confirmed`, `market_caps/nse_snapshot` and
  `corporate_actions/evidence`.

- **Writer:** `r2-historical-evidence-bootstrap.yml`, after every daily sync.
  `--skip-if-published` keeps the writes cheap (CALL_AND_STORAGE_AUDIT, 10 Nov).
- **Evidence:** no reader. Each name grepped on its own. The hits are the
  writer, `r2_retention.py` and `r2_inventory.py`'s freshness list (which
  names only `universes/point_in_time` and
  `indices/membership/nifty_total_market`). No name is built at runtime
  (`grep -rnE "f[\"']indices/|f[\"'](classifications|trading_sessions|universes|market_caps|corporate_actions)/"`
  finds nothing).
- **Is it a copy?** Everything in it is also in git's history.
- **Blocks:** every prefix is protected.
- **Saving:** small (8 MiB, about 0.35 MB a day before skip-if-published).
  The job now runs once a night (only after the daily sync's night run), so the win is that run and the clutter.
- **Overlap:** S172 (b) moves page data to R2. If the Dashboard pass reads
  membership or caps from R2, some of these gain a reader. Decide after that
  pass.

> **Owner: stop publishing the 16 evidence datasets nothing reads (keep `indices/membership/nifty_total_market`), and keep what is stored? yes / no**

### 4.6 `indices/prices/research` on R2: 7.0 MiB, 68 revisions

- **Status:** already on `PENDING_DELETIONS.md` as the owner's decision. Its
  job and reader were retired on 22 Nov (S168 (c), #604).
- **Blocks:** `indices/` is protected, and `indices/nse_close_all` replaces it.
- Repeated here so the batch is complete.

> **Owner: delete `indices/prices/research` (7 MiB, retired 22 Nov)? yes / no**

### 4.7 Downloaded and never read: `ref_tijori_close_raw.parquet` (21.9 MB)

- **Status:** the Saturday audit downloads it with the pattern
  `'ref_*_close*.parquet'` (`nse_long_prices.yml:220`), but no `--ref` passes
  it to a script. The seven passed are eod2, marketlens, screener, ss,
  tejhq, tijori (the verified file) and yahoo.
- **Evidence:** `grep -rn "tijori_close_raw"` returns 0 code hits.
- **Not a deletion:** it is protected reference evidence (217 matches to the
  wrong company, kept on purpose).
- **The change:** narrow the download pattern. That saves 22 MB of download
  per Saturday run, and nothing else.

> **Owner: narrow the Saturday audit's download so it stops fetching `ref_tijori_close_raw` (the file itself stays)? yes / no**

### 4.8 Small git files nothing reads (kept unless the owner says otherwise)

| File | Size | Why it stays by default |
|---|---|---|
| `data/reference/nse/anchor_checks.jsonl` | small, 50 commits | Record of the index-anchor check (gate G4) for people |
| `data/reference/nse/CHANGES.json` | 3.4 KB, 52 commits, 85 KB packed history | Daily change summary for people. The log's `::warning::` lines are the alerts |
| `data/membership_notices.json` | 14 KB | Read only by the manual `scripts/extend_membership_from_notices.py` and a test. The notices' evidence (`docs/MEMBERSHIP_FROM_NOTICES.md`) |

> **Owner: keep these three as records (default), or remove? keep / remove**

### Considered and kept

| Item | Why it is not a candidate |
|---|---|
| `bse/daily` (R2, 334 MiB) | Protected, newest copy only. `bse_daily.yml:63-85` restores from it when the release asset is missing |
| `prices/screener/max_history`, `reference/*` (R2, 175 MiB) | Protected audit references. The audit reads the release copies; R2 is their backup (owner, 3 Oct; reconfirmed 21 Nov) |
| `ref_long_price_audit_2026-10-03.zip`, `ref_marketlens_sectors.csv` | No code reader, but part of the retained 3 Oct reference set |
| `long_price_audit_latest.zip` | No code reader. It is the Saturday audit's output for people |
| `market_caps/nse_history` (R2, 2.9 MiB) | Read by the hand-run `r2_final_acceptance`. Protected, newest 2 |
| `nse/source_checks` (R2, 0.4 MiB) | Diagnostic, tiny. The catalogue row is corrected instead |
| `prices/screener/bootstrap` (R2, 2.5 MiB) | `r2_screener_history.py:28` surveys it. "Never touched" by design |
| `nse_raw_pack`, `nse_actions_pack` (release, 176 MB) | Read by every nightly long-file build |
| The 69 unmerged branches, `history_backtests.zip` | Already handled 15 Nov (PENDING_DELETIONS) |

**If every yes above is given:**
- R2: about 220 MiB (25 + 185 + 7 + about 1). The bucket goes from 1.56 GiB
  to about 1.34 GiB. It is free either way (16% of 10 GB).
- Release: 38 MB.
- The real gains are fewer nightly writes and a clearer archive, not cost.

## 5. Overlaps with open work

- **S172** (every page dataset from R2): this report's section 3 is the
  inventory its part (a) asks for. The moves themselves, and the Dashboard pass
  that makes them, are S172 (b). 4.2 and 4.5 should be decided with it.
- **S185** (each frozen month's book and price basis on R2): the Track Record
  ledgers row in section 3. Nothing here touches the freeze.
- **S194** (Nifty 1000 audit):
  - `snapshots/rankings_1000` and `track_record_1000.json` postdate the 21 Nov
    inventory. The first R2 copy is from 21 Nov evening; the ledger is
    expected at the 1-5 Dec freeze.
  - `r2_inventory.py` names `snapshots/rankings_1000`, `_nano` and `_combined` since #615 (S194 L5);
    the first inventory run after it is a 23 Nov check (TODO S188).
- **S173** (formatter): no overlap.
- **S141 / S142** (minutes): the minutes table is S142's partial week. Its full
  week closes on 27 Nov.

## Not checked

- Production memory (no post-redesign log), and two readers at once.
- Billable Actions minutes (the figures are wall time, a floor), and the
  repository-wide artifact total (estimated per workflow).
- R2 sizes are from the 21 Nov 10:02 UTC inventory (run 44892337416). They
  predate `nse/closes_2y`, `indices/nse_close_all` and
  `snapshots/rankings_1000`, each a few MB.
- No object was opened to confirm its content; sizes and names only.
