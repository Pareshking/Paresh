# Duplicated calls and wasted storage

What the scheduled jobs and the app actually fetch, how much of it is the same
bytes again, and what is stored that nothing reads. Owner, 10 Nov 2026: "the
same actions are being done multiple times ... this will reduce code as well as
unnecessary calls for R2 / GitHub / sites."

**The measurements on this page changed no behaviour.** The one code change
made with them is an opt-in R2 operation counter (`src/storage/r2.py`,
`R2_CALL_LOG`, off unless the variable is set,
`tests/test_r2_call_counter.py`).

**What has since been acted on (10 Nov, same day):** items 1, 3 and 4 of the
ranked list below, and the `nse_compare` timeout. Each is a saving, not a
behaviour change; see `docs/TODO.md` C1, C3, C4 and S116 (d) for the measured
effect and the tests. Items 2, 6 and 9 need the owner (an R2 delete, a release
delete, a correctness decision) and are deliberately untouched.

_Measured 10 Nov 2026. Fire counts from the Actions API over 27 Oct – 10 Nov
(14 days). R2 inventory from the `r2_archive_inventory` run of 9 Nov
(run 42598042128, job 129095408876) — this container has no R2 credentials, so
every R2 figure here is that job's own output, not a reading of my own._

## 1. What each scheduled job fires and fetches

"Runs/day" is **measured**, over 14 days, counting every event (schedule,
`workflow_run` chain, push, dispatch) — not the cron's arithmetic. GitHub skips
and delays scheduled runs, and five of these workflows are also chained off
another workflow, so the cron alone is not the number.

| Workflow | Cron (UTC) | Cron says /day | Measured runs/day | External resources it fetches |
|---|---|---|---|---|
| `daily_sync` | `30 17 * * 1-5`, `0 2 * * *`, + after `screener_sync` | 1.71 | **2.57** | niftyindices 6 constituent CSVs (**×17 requests**, below); NSE PR bundle (`--recent 3`) and again in `build_benchmarks --update`; screener.in (`classify_missing`); TradingView scanner; R2 (publish ×2, `nse_collect`); release `rankings*.parquet` upload; release packs **only** when a Nano Cap member is missing (exit 3) |
| `r2-historical-evidence-bootstrap` | `15 20 * * *` + after `daily_sync` + push on `data/indices/**` | 1 | **3.50** | R2 only: **17 `r2_publish.py` invocations per run** |
| `r2_ranking_archive` | `45 20 * * *` + after `daily_sync` + push | 1 | **3.79** | release `rankings.parquet`; R2 publish + audit |
| `r2_market_cap_history` | `00 20 * * *` + after `daily_sync` | 1 | **3.50** | R2 only (publish ×2, audit) |
| `nse_collect` | `41 12`, `41 14`, `11 16` (Mon–Fri), `41 3` daily | 2.14 | **3.57** (2.64 scheduled) | release `screener_prices.parquet` **every run**; NSE PR bundle per day R2 lacks; R2 (full pointer listing ×2–3, publish per table) |
| `v1-production-qa` | `17 */6 * * *` + push | 4 | **4.71** | the live Streamlit site; R2 read path |
| `v1-full-validation` | `23 23 * * *` + push + PR | 1 | **7.14** (0.21 scheduled) | the live site; R2 read path |
| `screener_sync` | `45 18 * * *` | 1 | **0.93** | screener.in (~1,167 stocks); niftyindices ×6; release `screener_prices.parquet` **twice in one run**; release `ss_*`; R2 publish |
| `nse_reference_sync` | `45 2 * * *` | 1 | **0.93** | nseindia symbolchange / namechange / equity_l; `check_index_anchor`: 7 CSVs × 2 hosts (niftyindices, nsearchives) |
| `r2_archive_inventory` | `31 2 * * *` | 1 | **0.93** | R2: full bucket listing |
| `r2_session_continuity_audit` | `17 4 * * *` | 1 | **0.93** | release `screener_prices.parquet`; R2 |
| `ss_sync` | `32 16 * * 1-5` | 0.71 | **0.64** | the SS site (40 stocks a night, ≥3 s apart); release `ss_*` + `screener_prices.parquet`; R2 publish |
| `results_calendar` | `23 16 * * *` | 1 | new (3 runs) | nseindia `api/event-calendar`, `api/corporate-board-meetings` |
| `fii_dii` | `47 14`, `47 17` (Mon–Fri) | 1.43 | new (2 runs) | nseindia FII/DII page, twice a day |
| `nsdl_fpi` | `17 4 * * 1-6`, `17 13 * * 1-5` | 1.57 | new (2 runs) | fpi.nsdl.co.in, twice a day |
| `monthly_track_record` | `0 19 1-5 * *` | 0.16 | **0.36** | niftyindices ×6 (`sync_former_member_prices`); NSE bundles (`sync_nse_prices`); release assets |
| `r2_nse_index_prices` | `30 20 * * *` + push | 1 | **1.07** | niftyindices `Backpage.aspx` historical series; R2 publish + audit |
| `nse_compare` | `40 6 * * 0` | 0.14 | **0.29** | release `screener_prices.parquet`, `rankings*.parquet`; R2 |
| `nse_long_prices` | `30 3 * * 6` | 0.14 | **0.29** | release: `nse_raw_pack` 171.7 MB + `nse_actions_pack` 3.8 MB + `bse_daily` 350.7 MB + `nse_long_close` + `ref_*` ≈ 690 MB a run; R2 (sessions and action days the packs lack) |
| `bse_daily` | `30 20 * * 5` | 0.14 | **0.14** | bseindia bhavcopy per new session; release `bse_daily.parquet`; R2 |
| `r2_retention` | `17 3 * * 0` | 0.14 | **0.14** | R2 only |
| `r2_recovery_audit` | `47 3 * * 1` | 0.14 | **0.14** | R2 only (whole bucket; 31–38 min, TODO A3) |
| `weekly_full_sync` | `30 18 * * 5` | 0.14 | **0.14** | as `daily_sync` step 1–2: niftyindices ×11 |
| `nse_history_import` | `13 21 2 * *` | 0.03 | 0.07 | NSE corporate-action list (one request a year per board); R2 |
| `nse_history_audit` | `37 22 3 * *` | 0.03 | 0.07 | R2 |
| `momentum_health` | `23 6 2-6 * *` | 0.16 | 0 scheduled | release assets |

Two corrections to assumptions that were in the brief:

- **`check_corporate_actions.py` downloads nothing.** It reads the local
  Screener store (`src/engine/corporate_actions.detect` over
  `screener_loader.load_store`). Running it in `daily_sync`, `screener_sync`
  and `weekly_full_sync` on the same day costs nothing outbound. NSE's
  corporate-action file is fetched by `nse_collect` (out of the PR bundle,
  once per session) and by `nse_history_import` (once a year per board).
- The nine scripts invoked by more than one workflow are **reuse, not
  duplication**, and are not listed as findings.

## 2. The same resource fetched more than once a day

Per-day counts are (measured runs/day) × (requests per run, counted in the
code or measured). "Repeats" is what a per-day cache would have saved.

| Resource | Changes | Fetches/day | Of which repeats | Verdict |
|---|---|---|---|---|
| niftyindices.com, 6 constituent CSVs | once a day at most (a rebalance is quarterly) | **59.5** | **52.5** | **waste** — see below |
| release `screener_prices.parquet` (8.79 MB) | once a day (`screener_sync` ~18:45) | 6.2 | 5.2 (**46 MB**) | **waste** |
| release `prices.parquet` (10.88 MB) | **never since 1 Oct 2026** | 7.1 (`canonical_parity`, per push/PR) | 7.1 (**77 MB**) | **waste** |
| release `screener_prices.parquet` + `rankings.parquet` in `canonical_parity` | once a day | 7.1 | 6.1 (**55 MB**) | **waste** (CI-driven, scales with PR traffic) |
| release `rankings.parquet` (233 KB) | once a day | ~11 | ~10 (2 MB) | mostly waste, trivial |
| NSE PR bundle for the newest session (a few MB) | immutable once published | 2 per `daily_sync` run → 5.1 | **2.6** | **waste** (`nse_collect` and `build_benchmarks` fetch the same zip in one run) |
| NSE PR bundles for absent days (`--recent 7`, `--weekends 10`) | — | ~8–10 | ~8–10 | **justified**: this is how a Muhurat or Budget session is caught with no holiday list; one 404 each |
| R2 payload just written, read back inside `r2_publish.py` | — | 2 HEAD + 2 whole-object GET per publish | **1 HEAD + 1 whole GET per publish, ≈162 calls/day** | **waste** (two verify layers, below) |
| R2 writes by `r2-historical-evidence-bootstrap`'s 2nd/3rd run of the day | nothing new (same `as_of`, same bytes) | 3.5 runs × 17 publishes | **~425 R2 calls/day that store nothing** | **waste** (TODO A3 already names the 4-a-day firing) |
| nseindia FII/DII; NSDL FPI | twice a day | 2 each | 0 | **justified**: provisional then final |
| nseindia symbolchange / namechange / equity_l | daily | 1 each | 0 | **justified** |
| Screener per-stock histories | nightly | ~1,167 once | 0 | **justified** |
| SS pages | nightly, 40 stocks | once each | 0 | **justified** (and rate-limited by agreement) |

**Total duplicate outbound fetches: about 70 HTTP requests a day** (52.5
niftyindices + ~15 GitHub release + ~2.6 NSE bundles), carrying **~180 MB a
day**, plus **~590 duplicate R2 operations a day**.

### The index CSVs, measured

`scripts/sync_data.run_daily_sync()` fetches the same five CSVs twice in a row:
step 1 `sync_official_nse_indices(force=True)` downloads five (it skips Total
Market), step 2 `fetch_indices_data(["NIFTY TOTAL MARKET"])` downloads all six
again, seconds later. `sync_official_nse_indices` is not cached and
`fetch_indices_data` is `st.cache_data`-memoised, so the two never share.
Measured on the real code path with the responses served from the committed
CSVs (the agent proxy blocks niftyindices.com) —
`/tmp/claude-0/-home-user-Paresh/5c87a591-847c-5ab0-b1a2-7772c4f645cd/scratchpad/count_sync_data.py`:

```
step 1 sync_official_nse_indices : 5 requests
step 2 fetch_indices_data        : 6 requests
total                            : 11 requests for 6 distinct URLs
same URL fetched again           : 5
```

`scripts/precompute_systems.py`, a separate process in the same `daily_sync`
run, calls `fetch_indices_data` again: **17 requests for 6 files per run**.
And `src/loaders/indices_loader._fetch_indices_impl` treats the committed
`data/indices/ind_*.csv` — which that same job writes and commits — as a
*fallback*, used only after three failed attempts. So the lists are downloaded
to write the files, then downloaded again to read them.

The app does the same on every cold start (6 fetches, ~0.65 s each: the
caller's own cold-start measurement, and `docs/TODO.md` A2 puts "the index
files 4.2 s" inside a 9.1 s `load_all_data`). `fetch_indices_data`'s TTL is
3,600 s, so a warm instance re-downloads all six every hour — up to 144 a day
per instance. Not measured in production: I cannot read the Streamlit Cloud
logs from here.

### The double verify in `r2_publish.py`, measured

One publication costs **9 R2 API calls**, of which the payload is HEADed twice
and downloaded back in full twice — once by `R2Archive.put_file(verify=True)`
and once by `_verify_publication`, which calls `verify_file` on the same key
again. Measured against a stub S3 client, real code path
(`.../scratchpad/count_publish.py`):

```
total R2 API calls for one publish: 9
  GetObject x4   PutObject x3   HeadObject x2
whole-payload GETs of the object just written: 2
```

At ~81 publishes a day (daily_sync 5.1, evidence bootstrap 59.5,
market-cap history 7.0, rankings 3.8, index prices 1.1, screener 0.9, ss 0.6,
nse_collect ~3, bse 0.1) that is **~730 R2 calls a day, ~162 of them the
second read of bytes just verified**. In bytes it is worse than it looks on the
big files: the monthly `bse/daily` publish reads 350.7 MB back **twice**, and
each SS night reads 36.8 MB back twice.

## 3. R2 storage

From the 9 Nov inventory: **26,888 objects, 3,135.8 MiB** (3,288,158,705
bytes). 17,757 of the objects are manifests and 8,649 are current pointers —
two bookkeeping objects per revision, 9.5 MB in all.

| Prefix | Objects | Size | Note |
|---|---|---|---|
| `scratch/bse_bhavcopy_2026-10-03` | 23 | **1,221.8 MiB (39%)** | TODO **S34**: raw tars + table + gap CSV + MANIFEST, "delete the prefix when NSE and BSE are aligned". Outside every dataset `r2_retention.py` knows, so nothing will ever remove it automatically |
| `archive/bse/daily` | 2 | 666.3 MiB | two whole copies of the same 2008–2026 table (S52: owner keeps the newest two) |
| `archive/nse/prices_daily` | 4,753 | 508.7 MiB | the record. Keep |
| `archive/prices/ss` | 7 | 257.6 MiB | 7 nightly copies of one whole-history file, 36.8 MB each (retention: 7 + month-ends) |
| `archive/prices/screener` | 11 | 79.7 MiB | 9 dates, retention applies |
| `archive/nse/market_caps` | 687 | 68.0 MiB | keep |
| `archive/reference/*` | 7 | 156.9 MiB | protected audit references. Keep |
| `snapshots/rankings*` + `archive/calculations/rankings` | 378 | 84.7 MiB | ~3.3 revisions per date (113 revisions / 34 dates), ~1.5 MB/day; `PROTECTED`, never pruned |
| the evidence bootstrap's 17 datasets | 681 | ~8.5 MiB | republished daily under a new `as_of`; see below |
| `archive/nse/corporate_actions` | 1,981 | 30.8 MiB | keep |
| everything else | — | ~40 MiB | manifests, pointers, source checks |

**What is dead or near-dead:**

1. `scratch/bse_bhavcopy_2026-10-03/` — 1,221.8 MiB, 39% of the bucket, already
   decided (S34), waiting only on "NSE and BSE are aligned".
2. The **daily evidence bootstrap**. `r2-historical-evidence-bootstrap` fires
   3.5× a day and publishes 17 datasets each time: 6 `indices/constituents/*`,
   6 `indices/membership/*`, `universes/point_in_time`,
   `classifications/tv_history`, `trading_sessions/confirmed`,
   `market_caps/nse_snapshot`, `corporate_actions/evidence`. The `as_of` is the
   index sync date, so a fresh copy of nearly identical content lands every
   day, and every one of these prefixes is in `PROTECTED_DATASETS` — nothing
   prunes them. Growth is ~0.35 MB/day for ever. **Of the 17, exactly one has a
   named reader**: `indices/membership/nifty_total_market`
   (`r2/consumers/r2_historical.py`, itself only exercised by validation
   workflows). No app code path reads any of them.
3. `archive/nse/source_checks` — 57 objects, 0.3 MB. The catalogue says
   "newest day, overwritten daily"; in fact every day is kept.
4. The ranking snapshots' extra revisions: three a date because three jobs
   chain off `daily_sync`. ~1 MB/day of the 1.5 is the second and third
   ranking of the same day.

Everything here is derived and rebuildable except `nse/prices_daily`,
`nse/corporate_actions*`, `bse/daily`, `prices/*` and `reference/*`.

## 4. GitHub as storage

| Store | Measured | Note |
|---|---|---|
| Release `data-latest` | **52 assets, 881.7 MB** | the biggest: `bse_daily.parquet` 350.7, `nse_raw_pack.parquet` 171.7, `ref_tejhq_adjusted_close` 51.1, `prices_full.parquet` 38.1, `ref_marketlens_close` 26.0, `nse_long_value` 24.1 |
| Actions artifacts | **4,960 unexpired, 1,236.9 MB** | `v1-production-qa` is 1,034 of them and **1,062.2 MB (86%)**: ~1 MB per run, ~7 MB/day, and `v1-production-qa.yml` sets no `retention-days`, so GitHub's 90-day default applies. Next: `nse-long-prices` 130.8 MB (3), `nse-compare` 45.3 MB (7) |
| Repository | **23,053 KB** (API, 10 Nov) | working tree: `nse_index_rebuild` 14,796 KB (12,724 of it `announcements/`), `data` 6,680 KB, `src` 1,868, `tests` 1,816. `nse_index_rebuild/` is the membership evidence trail and an owner decision: **measured, not proposed for deletion** |

Release assets with no live reader, or only a stale one:

- `tmp_session_2026-10-03.zip` — 10.9 MB, 0 downloads, uploaded 3 Oct. Scratch.
- `ref_long_price_audit_2026-10-03.zip` — 0.33 MB, 0 downloads, superseded by
  `long_price_audit_latest.zip`.
- `prices.parquet` (10.9 MB) and `prices_extra.parquet` (7.0 MB) — the retired
  Yahoo-era snapshots, last written 1 Oct 2026, the day before Yahoo was
  dropped. The app does not read them (`PRICE_SNAPSHOT_URL` appears only in
  `scripts/`), but `scripts/canonical_parity_check.py` still downloads
  `prices.parquet` on **every push and pull request** (100 `canonical_parity`
  runs in 14 days) and uses it as a price frame called `yahoo`. That is 77 MB a
  day of a file frozen 40 days ago, and the parity gate is comparing today's
  book against it.
- `prices_full.parquet` (38.1 MB) — read only by `nse_sample_check` (manual /
  PR), and only as a trading-day **calendar**; `data/nse_trading_days.json`
  holds the same fact.

Artifact retention is unset in `canonical_parity`, `decile_research`,
`nse_compare`, `nse_sample_check`, `stage4b-independent-validation`,
`v1-cold-start-probe`, `v1-full-validation` and `v1-production-qa` (90-day
default); it is set in `bse_bhavcopy_r2` (14), `nse_long_prices` (14),
`screener_10y_bootstrap` (7), `ss_sync` (30), `nse_history_audit` (30) and
`nse-index-membership-rebuild` (30).

## 5. Ranked: what to remove or cache

| # | Change | Saves per day | Where |
|---|---|---|---|
| 1 | **Done, 10 Nov.** Every publish in `r2-historical-evidence-bootstrap` passes `--skip-if-published`: the dataset's `as_of` pointer is read (a HEAD and a small GET) and a run whose content hash is already there writes nothing. The triggers are kept — the chain off `daily_sync` is a contract (`tests/test_workflow_sequence.py`) — and a re-run after a data fix still publishes | **~380 of the ~425 R2 operations** (two cheap calls per skipped dataset remain); the 2.5 extra runs still start, so the runner minutes are unchanged | `.github/workflows/r2-historical-evidence-bootstrap.yml`, `scripts/r2_publish.py`, `tests/test_r2_publish_call_budget.py` |
| 2 | Delete `scratch/bse_bhavcopy_2026-10-03/` once NSE and BSE are aligned (S34) | one-off **1,221.8 MiB, 39% of the bucket** | by hand / `r2_retention` |
| 3 | **Done, 10 Nov.** `retention-days: 14` on `v1-production-qa`'s evidence upload | holds ~1,062 MB → ~100 MB after it settles; no daily call change | `.github/workflows/v1-production-qa.yml` |
| 4 | **Done, 10 Nov.** `_verify_publication` checks the manifest and pointer contract only; the payload's read-back is `put_file(verify=True)`'s, which runs *before* a manifest or pointer names the object. One publish: 9 calls → **7** (`PutObject x3 GetObject x3 HeadObject x1`), one whole-payload GET | **~162 R2 calls**, and a second full read-back of every payload (350.7 MB on the monthly BSE publish, 36.8 MB a night on SS) | `scripts/r2_publish.py`, `tests/test_r2_publish_call_budget.py` |
| 5 | Read the index lists from the committed CSVs and fetch only when they are stale: `sync_data` step 2 can take step 1's bytes, and `precompute_systems` can read `data/indices/` | **~48 niftyindices requests** of the ~59.5; ~4 s off every app cold start | `scripts/sync_data.py`, `src/loaders/indices_loader.py` |
| 6 | **Report only, and not just waste** (10 Nov, TODO C6). The frozen frame no longer prices the replay — `record_run_uncached` substitutes `basis_frame`'s Screener-then-NSE blend, so the gate's book is struck on current prices (local run: book as_of 2026-11-05, green) — but it still fixes the **universe**: `prices.parquet` covers 749 of today's 752 names, and `_clean_price_df` intersects, so `ENNATURE`, `ICICILIFE` and `IGLSPIRITS` are dropped from the side `ledger_parity`, `hard_caps` and `actions_plan` are computed on. Removing the download needs a replacement second deep frame, which is a correctness decision, not a saving | **~77 MB and 7 downloads/day**, 17.9 MB of release storage, and one stale price frame out of the parity gate | `scripts/canonical_parity_check.py` |
| 7 | Fetch `screener_prices.parquet` once per job: `screener_sync` downloads it twice in one run; `nse_collect` downloads it on all four daily fires for `--check` | **~5 downloads, 46 MB** | `.github/workflows/screener_sync.yml`, `nse_collect.yml` (**another agent's files**) |
| 8 | Have `build_benchmarks --update` read the session `nse_collect` just fetched (or run it from the same process) | **~2.6 NSE PR bundle downloads**, a few MB, and that much less asking of NSE | `scripts/build_benchmarks.py` / `daily_sync.yml` |
| 9 | Delete `tmp_session_2026-10-03.zip` (10,851,823 B, **0 downloads**, 3 Oct) and `ref_long_price_audit_2026-10-03.zip` (330,498 B, **0 downloads**, superseded by `long_price_audit_latest.zip`) from the release. Confirmed from the API on 10 Nov; **not deleted — a release asset is outward-facing, so the owner deletes**: `gh release delete-asset data-latest <name> --repo Pareshking/Paresh` | one-off 11.18 MB | release |
| 10 | Keep one ranking revision per date (or let the chained jobs publish once) | ~1 MB/day of R2, never pruned today | `r2_ranking_archive.yml`, `r2_retention.py` |

Items 1 and 3 were applied on 10 Nov along with item 4; items 7 and parts of 5
and 8 still touch `.github/workflows/*` files other agents hold, and item 6 is
the parity engine's.

### The `nse_compare` timeout (not a duplicate call, but the same shape)

`nse_compare.yml` times out every other week (TODO S116 (d)). Run 42486769158's
`Compare` step was **44m41s of the 45m14s job** and printed nothing after its
first second: `read_nse()` walked every R2 day from 2023-10-01 one at a time —
a `resolve_current` (pointer GET, manifest GET, object HEAD) and a
`read_parquet` of the whole market per day, ~520 sessions, ~5 s each. Fixed on
10 Nov by reading them in a thread pool (`NSE_COMPARE_WORKERS`, default 8, one
reader and so one boto3 client per thread) with the frames reassembled in date
order, plus a timestamped progress line for every phase so the next timeout
names its own step. `timeout-minutes` is unchanged. The equality of the output
is pinned by `tests/test_nse_compare_reads.py` (concurrent == serial, date
order, the unreadable list, the progress lines); the wall clock could not be
measured here — no R2 credentials — so the saving is still to be confirmed by a
run.

## 6. How big is this actually

Smaller than it looks, and the two biggest numbers are not the duplication the
hypothesis names. The duplicated **calls** come to about 70 outbound HTTP
requests and ~590 R2 operations a day. At Cloudflare's published rates
(Class A $4.50, Class B $0.36 per million) the duplicate R2 traffic is **under
ten cents a month**; the duplicated GitHub release traffic is ~180 MB a day
from a public repository, which costs nothing; and the ~70 repeated requests to
NSE are a politeness and block-risk question, not a bill. What the duplication
really costs is **runner minutes** (2.5 unnecessary bootstrap runs a day, each
installing the full dependency set) and **~4 seconds of every app cold start**
spent re-downloading six CSV files the repository already contains. Meanwhile
the storage is dominated by two single decisions, neither of them a duplicate
call: **1,221.8 MiB of scratch BSE tars (39% of R2)** that S34 already agreed
to delete, and **1,062 MB of QA artifacts** kept for 90 days because one
`retention-days:` line is missing. So the owner's hypothesis is **right about
the pattern and wrong about the scale**: the same actions genuinely are done
several times a day — 11 index-CSV requests where 6 would do, two full
read-backs of every R2 payload, 3.5 runs a day of a job whose output changes
once — and fixing them is worth doing for code clarity, runner time and cold
start, but it will not change the bill. Two-thirds of the reclaimable bytes sit
behind one `rm` and one `retention-days: 14`.

**Not checked:** the production R2 read path's call count (no credentials here;
counted statically from `src/storage/reader.py` — one dataset read is a pointer
listing, two small GETs, a HEAD and the payload GET, with no duplicate within a
read), the real cold-start rate of the deployed app (no access to the Streamlit
Cloud logs), and the NSE PR bundle's size (the agent proxy blocks
`archives.nseindia.com`).
