# Full data audit: the checklist (TODO S163)

Owner, 21 Nov 2026: "check source of each and everything on each pages, check are we storing them or not in our
R2, what is yet to be in R2 which must be there ... a full audit page by page, elements by elements. Check those
pipelines are clean and run fast and efficiently, saving data where required. This is required careful audit
without missing anything." Then: "Add them in to do so we don't miss anything."

**When:** starts the day the last page redesign (S151) is merged.
**Done when:** `docs/DATA_AUDIT_<date>.md` exists with every element of every page, every box below is ticked
with its finding, every gap has a fix merged or its own TODO row, and the owner has read it.

## 1. The inventory: one table per page, one row per element

Pages: Dashboard, Portfolio, Actions, Breadth, Sectors, RRG, Backtest / Track record, the stock page, Screener,
Watchlist, Configuration, Guide, and the header strip shown on every page.

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
- [ ] **(b) Stored twice or never read.** R2 datasets and `data/` files nothing reads; repo data that belongs in R2. Remove or move each, with the reader checked first.
  - [ ] the R2 index-level file Breadth stopped reading on 21 Nov: confirm nothing else reads it before removing it
- [ ] **(c) Pipelines.** For every workflow:
  - [ ] run time and failures over the last 30 days
  - [ ] what it downloads again that it already has; what could be incremental, cached or merged; minutes saved
  - [ ] it refuses to write bad data (a guard like S91's or S153's reconciliation) and keeps the committed file
  - [ ] a failure raises an alert (the scheduled-failure issue), not a silent skip
  - [ ] it writes only what changed (no daily commit of an unchanged file)
- [ ] **(d) Dates.** On the live site, every figure ends on its page's session or says that it does not (the S148 rule).
- [ ] **(e) One source per figure** on every page (S154), not only Dashboard, Portfolio, Actions and Breadth; a test for each shared label.
- [ ] **(f) Costs** against the private-repo budget (S142): GitHub Actions minutes, R2 storage and operations, Streamlit memory.

## 3. Added by Claude (owner: "add your thoughts and improvements")

- [ ] **Restore drill:** rebuild one page from R2 alone on a clean machine, timed; every missing input is a finding.
- [ ] **Every outside address** the jobs and the app call, with the date each last answered and what breaks if it stops.
- [ ] **The date test in CI on every page** (the S154 (c) test, which now covers four pages).
- [ ] **Licence and terms** for each third-party source (Screener, NSE's terms for its archives, any feed like IndiaDataHub).
- [ ] **Reachability:** which figures depend on a source that only GitHub's runners, or only the app, can reach (BSE's FII/DII pages refused this container; R2 was not reachable locally).
- [ ] **First runs of the jobs added on 21 Nov:** the NSE DII step in `fii_dii.yml` and the Total Market collector, checked on GitHub.
- [ ] **Data dictionary:** each file's columns, units, start date and writer, kept beside `docs/DATA_CATALOGUE.md`.
