# Full data audit: the checklist (TODO S163)

Owner, 21 Nov 2026: "check source of each and everything on each pages, check are we storing them or not in our
R2, what is yet to be in R2 which must be there ... a full audit page by page, elements by elements. Check those
pipelines are clean and run fast and efficiently, saving data where required. This is required careful audit
without missing anything." Then: "Add them in to do so we don't miss anything."

**When:** starts the day the last page redesign (S151) is merged.
**Done when:** `docs/DATA_AUDIT_<date>.md` exists with every element of every page, every box below is ticked
with its finding, every gap has a fix merged or its own TODO row, and the owner has read it.

## 1. The inventory: one table per page, one row per element

Pages (the menu in `app.py` on 22 Nov 2026): Dashboard, Actions, Screener, Portfolio, Market (`/market`; it was
Breadth at `/breadth`, which now redirects), Indices (new 21 Nov), Sectors, Watchlist, Backtest (the Track Record
is part of Portfolio; `/track-record` redirects there), Configuration, Guide, the stock page, and the header strip
shown on every page (on a desktop the prices date sits at the end of the market line, and on the Dashboard in a row
of its own). RRG: **removed 21 Nov 2026** (S169), nothing to inventory; see the struck boxes in section 4.

Each page is audited under each of the **four systems** (Nifty 750, Nifty 1000, > ₹2,000 Cr, Combined;
`src/engine/systems.py`): a figure that reads a system's own ranking, record or membership is a row per system.

An element is every figure, chart series, table column and number in a label or sentence. For each row:

- [ ] the file or dataset it reads, and the function that makes it
- [ ] the original source: NSE, BSE, NSDL, Screener, AMFI, or computed by us (and from what)
- [ ] whether that source is kept in R2 (dataset prefix, revision, history length), only in the repo's `data/`, or nowhere
- [ ] the job that writes it: workflow, schedule, last success, run time, minutes a month
- [ ] the session the figure ends on, against the page's data date

## 2. Across all rows

- [ ] **(a) Missing from R2.** Everything we could not download again, with a plan to add it, how long to keep it, and a restore test. At least:
  - [ ] NSE's provisional FII/DII report (`data/fii_dii_flows.csv`): NSE keeps no history
  - [ ] NSE's category-wise turnover and its DII history (`data/nse_dii.csv`, added 21 Nov)
  - [ ] Nifty Total Market daily from NSE (`data/nse_total_market.csv`, added 21 Nov)
  - [ ] NSDL FPI daily (`data/nsdl_fpi_daily.csv`)
  - [ ] the track-record ledger and frozen months, `data/book_exposure.csv`, `data/breadth_history.csv`, `data/signal_tests.json`, `data/momentum_health.csv`, the results calendar, the membership history
  - [ ] promoter pledges, if S156 is taken up (history starts only when collection starts)
  - [ ] NSE's Nifty 1000 list (`data/indices/ind_nifty1000_list.csv`) and `indices.nifty_1000` in `data/membership_history.json` (S175): point in time from the first nightly list, so a missed night is lost
- [ ] **(b) Stored twice or never read.** R2 datasets and `data/` files nothing reads; repo data that belongs in R2. Remove or move each, with the reader checked first.
  - [x] the R2 index-level file Breadth stopped reading on 21 Nov (`indices/prices/research`, written by `r2_nse_index_prices.yml`). Lead, 22 Nov: it has no reader: `fetch_index_levels`, its one reader, went with the old Dashboard in #601 (S179); but `scripts/r2_inventory.py` still lists it in `DAILY_DATASETS`, so the daily inventory fails if the job stops before that line goes. The job has been on its Screener fallback while reporting success (S168). Retiring it is S168 (c). **Done 22 Nov 2026**: job, script and test deleted; the dataset is out of `DAILY_DATASETS` and the alert's watch list; its stored revisions stay on R2 (protected `indices/`)
  - [ ] the index store twice: R2 `indices/nse_close_all` and the app's copy in git (`data/nse_indices_history.parquet`, `data/nse_indices_recent.csv`); S172 decides whether the page reads R2
  - [ ] RRG leftovers (S169): no data of its own (it read the ranking's prices and the benchmark), so nothing to remove from R2 or the release; see `docs/PENDING_DELETIONS.md`
- [ ] **(c) Pipelines.** For every workflow:
  - [ ] run time and failures over the last 30 days
  - [ ] what it downloads again that it already has; what could be incremental, cached or merged; minutes saved
  - [ ] it refuses to write bad data (a guard like S91's or S153's reconciliation) and keeps the committed file
  - [ ] a failure raises an alert (the scheduled-failure issue), not a silent skip
  - [ ] it writes only what changed (no daily commit of an unchanged file)
- [ ] **(d) Dates (S164).** `breadth_history.csv` ends 16 Nov while prices end 20 Nov (found 21 Nov). On the live site, every figure ends on its page's session or says that it does not (the S148 rule).
- [ ] **(e) One source per figure** on every page (S154), not only Dashboard, Portfolio, Actions and Market (then Breadth); a test for each shared label. Indices and the Dashboard's "Valuation and styles" card read one copy (`src/ui/indices_data.py`); Large is the Nifty 100 on both (21 Nov).
- [ ] **(f) Costs** against the private-repo budget (S142): GitHub Actions minutes, R2 storage and operations, Streamlit memory.

## 3. Added by Claude (owner: "add your thoughts and improvements")

- [ ] **Restore drill:** rebuild one page from R2 alone on a clean machine, timed; every missing input is a finding.
- [ ] **Every outside address** the jobs and the app call, with the date each last answered and what breaks if it stops.
- [ ] **The date test in CI on every page** (the S154 (c) test, which now covers four pages).
- [ ] **Licence and terms** for each third-party source (Screener, NSE's terms for its archives, any feed like IndiaDataHub).
- [ ] **Reachability:** which figures depend on a source that only GitHub's runners, or only the app, can reach (BSE's FII/DII pages refused this container; R2 was not reachable locally).
- [ ] **First runs of the jobs added on 21 Nov:** the NSE DII step in `fii_dii.yml` and the Total Market collector, checked on GitHub;
  `nse_indices.yml` dispatched once with `backfill` (S168 (a)), then a scheduled night that adds one session and commits
  `data/nse_indices_recent.csv` (header only on 22 Nov); the first `daily_sync` after #591 writes
  `data/indices/ind_nifty1000_list.csv` and `indices.nifty_1000` from 30 Oct (neither in the repository on 22 Nov), and
  publishes `rankings_1000`; the 1-5 Dec `monthly_track_record` freezes November into `data/track_record_1000.json` or names the unpriced members.
- [ ] **Data dictionary:** each file's columns, units, start date and writer, kept beside `docs/DATA_CATALOGUE.md`.
- [ ] **One benchmark (S165)** and **industry practice (S166)** run beside this audit; their own rows in `docs/TODO.md`.

## 4. Pages and datasets added or removed since the list was written (21-22 Nov 2026)

Each box is also a row of the section 1 inventory; these are the parts most likely to be missed.

- [ ] **Indices page** (`/indices`, S170; `src/engine/indices_page.py`, `src/ui/views/indices_view.py`,
      `docs/INDICES_REQUIREMENTS.md`): every figure in Valuation, Styles, How long a style can lag, Calendar years,
      Size year by year and Every index (112 indices at 1M-1Y) traced to the store's rows; the P/E percentile from
      31 Mar 2021 and the old basis drawn apart; the "derived" sessions shown as such; the last session against the
      page's data date (S164).
- [ ] **The every-NSE-index store** (S168): `.github/workflows/nse_indices.yml` (14:10 UTC daily) →
      `scripts/collect_nse_indices.py` / `src/loaders/nse_indices.py` → R2 `indices/nse_close_all` (protected under
      `indices/` in `r2_retention.py`) → `scripts/export_nse_indices_compact.py` → `data/nse_indices_recent.csv`, beside
      the frozen `data/nse_indices_history.parquet`. Check: the guard (no index twice in a session, no stored close
      changed) refuses and keeps the file; the reference tables (`data/reference/nse_index_aliases.csv`,
      `nse_index_corrections.csv`, `nse_index_groups.csv`, `nse_index_missing_sessions.csv`) each carry their evidence
      (`docs/DATA_CORRECTNESS.md` section 5); `indices/nse_close_all` added to `r2_inventory.DAILY_DATASETS` once
      published (S168 (b)); the alert job lists it (`scheduled_failure_alert.yml`: it does); a restore test.
- [ ] **Nifty 1000, the fourth system** (S175): membership (`indices.nifty_1000`, reconstructed from 30 Oct until NSE's
      first list of 16 Nov, and the page says so), the 250 outside the 750 in the Screener store
      (`scripts/sync_screener.py` extras) and later the long file (PR 2b), caps from the daily snapshot, ranking
      (`scripts/precompute_systems.py` → release and R2 `snapshots/rankings_1000`), record (`data/track_record_1000.json`
      from Nov 2026). Every page loaded under it, as under the other three; the members whose prices are still being
      collected (58 on 21 Nov) named in the Screener's footnote (`ranking_view.system_note`).
- [ ] **"> ₹2,000 Cr"** (key `nano`, was shown as "Nano Cap"): the label is the same on every page and in CSVs; old
      `?sys=nano` links still open it; its ISINs from NSE's equity list (410 of 411 on 21 Nov).
- [ ] **Market page at `/market`**: the redirect from `/breadth` keeps `?system=`; the audit scripts and CI open `/market`.
- [x] ~~RRG page: its figures, sources and the benchmark it centred on~~ Removed 21 Nov 2026 (S169, #587): no page
      to audit. Old `/rrg` links are not redirected (owner: "not required").
- [x] ~~RRG's quadrant and rotation line on the Dashboard's section 6, and section 7 "Where leadership is moving"~~
      Removed 21 Nov 2026; section 6 now reads Sectors' measures only (`dashboard_home_view`).
