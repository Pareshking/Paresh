# Repository audit plan: cost, speed and resources (7 Nov 2026)

Owner's request (7 Nov 2026): audit the whole repository, from data
collection to the website and its menu, for what is slow, time-consuming or
resource-hungry, planned in blocks.

## Ground rules

1. **Start from what is already known.** Three audits exist:
   `ADVERSARIAL_AUDIT_2026-09-10.md`, `CODE_AUDIT_2026-09-25.md`,
   `MEMORY_AUDIT_2026-10-08.md`, and the S-items in `TODO.md`. Each block
   begins by listing what those left open in its area, and does not redo
   what they closed.
2. **Measure before changing.** Every finding carries a measured number
   (minutes, seconds, MB, bytes, runs per month). "Looks slow" is a lead.
3. **Correctness first.** A speed fix must reproduce the Block 0 frozen
   outputs exactly (or within a tolerance written down before the change).
   S80 and S85 show what a stale or rejected precompute costs.
4. **One fix, one PR.** Each PR states the before and after numbers and the
   frozen-output result. Nothing in `data/` is edited by hand.
5. Findings for a block go in a section of this file (or a linked note);
   promised work goes in `TODO.md` as A-numbers (A1, A2, ...).

## Blocks

| # | Block | Scope | What to look for |
|---|---|---|---|
| 0 | Baseline and safety net | TODO items that fell due; measurement only | Actions minutes per workflow (30 days); test runtime; app cold start; per-page time and memory; repo size. Frozen outputs: the 750 ranking, the three track records, one fixed backtest |
| 1 | Data collection | `nse_collect` (4-hourly), NSE and BSE bhavcopy, `screener_sync`/`backfill`, `ss_sync`, `nse_reference_sync`, index and classification sync | Re-downloading unchanged files, overlapping schedules, serial HTTP, retry storms, the same day fetched by two jobs |
| 2 | Price pipeline and corporate actions | `nse_long`, `nse_adjusted`, `corporate_actions`, `notes.json`, `build_nse_long_prices`, `closes.parquet` | Full rebuilds where incremental would do; parquet read/write cost; S81/S82 |
| 3 | R2 and storage | about 20 `r2_*` workflows, 9 scheduled | One-off bootstrap and acceptance jobs still on a schedule; audit frequency against need; storage and egress |
| 4 | Membership and universes | `membership_history`, notices, three systems, `nse_index_rebuild/` (1,314 files, 15 MB in git) | What belongs in git; what the daily sync recomputes |
| 5 | Engine | `momentum`, `calendar_momentum`, `pipeline`, `backtester`, `track_record`, `ranking_store`, `compute_gate` | Repeated rolling-window work, Python loops, precompute rejections (S85) |
| 6 | App shell and caching | `app.py`, `st.cache_*`, imports, S61-S69 | Cold start, cache keys (code audit W3), memory ratchet, S67 telemetry |
| 7 | Website: menu and pages | 10 pages, redirects, stock page; `theme.py` | Per-page time and memory, duplicated rendering, phone width (S83, S84), unused controls |
| 8 | QA and CI | 218 test files, `production_qa` every 6 h, `v1-*` and `stage4b` jobs | Test runtime, live-data tests, QA frequency |
| 9 | Hygiene and dependencies | `agent/`, `research/`, docs, branches, open Dependabot PRs (pandas, numpy, pyarrow, streamlit) | Dead code; dependency bumps go through the Block 0 frozen-output check |

First proposed order: 0, 3, 1, 5, 6, 7, 2, 4, 8, 9. Revised after the
Block 0 measurements, see 0.7. The owner may reorder.

## Block 0 results (7 Nov 2026, main at e6ff3c1)

Measured in a cloud container (4 cores, 16 GB, Python 3.13; the repo pins
3.14 in `.python-version`). Local numbers compare only with local numbers;
Streamlit Cloud is slower and smaller.

### 0.1 Items that fell due

- **October frozen in all three ledgers:** done. `2026-10` is in
  `track_record.json`, `track_record_nano.json` and `track_record_combined.json`,
  committed by `monthly_track_record` on 3 Nov (b9591f8, 9b83d9c).
  Not checked: the "Three systems" view on the live site.
- **Shadow record's first month (Nov):** due 1-5 Dec; not yet due.
- **New data finding, S86:** the Nifty 750 membership reads **752** from
  2026-11-04. The nightly added ENNATURE and IGLSPIRITS (both in NSE's
  `equity_l.csv` from 04-NOV-2026, series BE, and in the Total Market list
  file, 754 rows) with no removal. Same shape as TRIVENIPT (S78): probably
  demerged companies carried above the 750. **Not verified**: the NSE notice
  has not been found. `tests/test_membership_from_notices.py::test_the_list_is_750_names_on_every_date_it_changes`
  fails on main since then, and nothing turned red, because the nightly's data
  commits carry `[skip ci]` (see A6).

### 0.2 GitHub Actions, 8 Oct - 7 Nov (2,680 runs, read through the API)

The repository is **public**, so standard runners are free: these minutes
are not a bill. They cost wall time, queue slots and attention when red.
Run time = `updated_at - run_started_at`; a sample of 10 runs matched job
time to within 2%.

| Workflow | Runs | Failed | Total min | Median min | Note |
|---|---|---|---|---|---|
| `ss_sync` | 22 | 2 | 6,059 | 278 | 61% of all minutes. Deliberately slow (SS site owner's request): 35 rounds x 40 stocks, 4 s apart, 5 min rest between rounds (8 Nov: 3 s apart, no rests, A4), and each stock fetches a 1,000-session page to learn one new day |
| `screener_sync` | 31 | 7 | 1,151 | 38 | 23% failure rate |
| `v1-production-qa` | 140 | 25 | 576 | 3.4 | every 6 h + every push |
| `v1-full-validation` | 134 | 16 | 437 | 3.5 | PRs and pushes |
| `r2-historical-evidence-bootstrap` | 115 | 0 | 213 | 1.9 | a "bootstrap" running daily and after other jobs |
| `canonical_parity` | 224 | 62 | 196 | 0.9 | 28% failure rate; cause not checked (S12/S60 drift is a candidate) |
| `daily_sync` | 84 | 0 | 168 | 1.7 | |
| `nse_compare` | 5 | 0 | 158 | 42 | weekly |
| `nse_collect` | 104 | 0 | 152 | 1.1 | cron every 4 h implies ~180 runs; 104 ran |
| `r2_recovery_audit` | 4 | 0 | 141 | 35 | weekly |
| `r2_final_acceptance` | 4 | 0 (4 cancelled) | 82 | 20.4 | **times out at its 20-minute limit every week**: 0 results |
| `r2_cost_observability` | 4 | **4** | 2.5 | 0.6 | **fails every run** |
| all 34 workflows | 2,680 | 121 | **9,940** | | |

Raw runs and the aggregation are not committed (re-run the API read for a
new period).

### 0.3 Tests

`python -m pytest tests -q`: **2,364 passed, 1 failed (S86) in 164 s**, peak
memory 478 MB. Slowest: `test_s56_rights_actions` 18 s, one
`test_screener_restatement` case 12 s, the parametrised restatement cases
2-5 s each. Not a bottleneck.

### 0.4 Frozen outputs (the correctness gate for every later fix)

`scripts/audit_baseline.py capture` pins the published `screener_prices.parquet`
and `rankings.parquet` (sha256 in the manifest), recomputes the 750 ranking
with the nightly's own `sync_data._precompute_rankings`, and runs a fixed
12-month backtest on the same frame. `check` recomputes from the same pinned
inputs and compares exactly.

- Recomputed 750 ranking against the nightly's published one: **identical**
  (750 rows, same columns, max difference 0.0). This shows the run is
  reproducible; it is the same code, so it is not evidence the ranking is right.
- A second run (`check`): ranking and backtest **identical** (deterministic).
- Cost on this machine: ranking 2.9 s, 12-month backtest 3.1 s, peak 478 MB.

The pinned folder lives outside the repo (inputs are 9 MB); recapture when
a block starts if the old one is gone, and run `check` before and after each
fix on the same capture.

### 0.5 The website, one reader (`scripts/audit_page_bench.py`)

Local `streamlit run app.py`, empty cache, each page opened in turn in
headless Chromium; time until the script has run and stayed idle 1.5 s;
server memory sampled every 100 ms.

| Page | Cold s | Warm s | Peak MB (cold / warm) |
|---|---|---|---|
| Screener (home) | 7.2 | 1.4 | 397 / 656 |
| **Portfolio** | **17.7** | **8.2** | 676 / 686 |
| Actions | 3.0 | 3.1 | 676 / 706 |
| Sectors | 1.6 | 1.4 | 577 / 636 |
| RRG | 1.4 | 1.5 | 622 / 655 |
| Watchlist | 1.2 | 1.2 | 603 / 677 |
| Breadth | 2.3 | 2.3 | 681 / 717 |
| **Backtest** | **6.0** | **4.6** | 644 / 745 |
| Configuration | 1.3 | 1.2 | 581 / 682 |
| Guide | 1.3 | 1.2 | 598 / 682 |
| Stock page (RELIANCE) | 1.2 | 1.2 | 615 / 695 |

- Cold Screener: the precomputed ranking was accepted ("engine skipped").
- **Portfolio is the slow page, and stays slow when warm** (8 s): something
  on it is recomputed on every visit.
- **Memory only grows**: 330 MB after the first page, 695 MB after 22 visits
  by one reader, never released (the S69 pattern). On a ~1 GB container that
  leaves little for a second reader.

### 0.6 Leads seen in passing (for their blocks)

- `prices.parquet` on the release was last updated 1 Oct (Yahoo era) but has
  593 downloads; `canonical_parity_check.py` still reads it as its "deep"
  frame (Block 1 / 8).
- `audit_short_history.yml` ran 3 times in the window but no longer exists
  on main (a branch workflow).
- Release `data-latest` carries 52 assets; `bse_daily.parquet` 351 MB and
  `nse_raw_pack.parquet` 171 MB with 0 downloads, a 10.9 MB
  `tmp_session_2026-10-03.zip` (Block 3).

### 0.7 Order, revised from the measurements

Actions minutes are free, so the order now follows what readers and data
feel: **7 + 6 (Portfolio, memory growth) → 5 (engine behind Portfolio and
Backtest) → 3 (the two R2 jobs that never succeed, bootstrap on a daily
schedule) → 1 (ss_sync's 1,000-session page per stock) → 8 → 2 → 4 → 9.**
S86 is data, so it goes first in `TODO.md`, outside this audit.
