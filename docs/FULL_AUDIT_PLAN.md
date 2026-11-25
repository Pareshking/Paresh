# Full audit: plan, check, do, act (TODO S227)

Owner, 25 Nov 2026: "full audit ... plan what an audit requires first. Make a to do ... items in to do which are
time bound so kept open ... let audit catch them if any ... Plan, do, check, act."

_Status: plan only, 25 Nov 2026. Nothing below has been run. Phasing (section 3) is **proposed, owner to confirm**._

## 0. What exists, so it is not done twice

| Already done or planned | Where | State on 25 Nov |
|---|---|---|
| Data audit part 1: inventory of every page element, R2 gaps, outside addresses, pipelines, costs | `DATA_AUDIT_2026-11-24.md` (S163's checklist, `archive/DATA_AUDIT_PLAN.md`, is folded into section 4a below and archived) | (c) pipelines, (d) dates, (e) one source per figure done; (a) R2 copies and (f) R2 operations open |
| Cost, speed, resources in blocks 0-9 | `AUDIT_PLAN.md` (A-numbers) | A1, A3 open |
| Methods against industry practice | `METHODS_REVIEW_2026-11-24.md` (S166, S223) | closed |
| Findings already explained | `DATA_CORRECTNESS.md` section 5 | **not re-investigated**; an audit line that matches a row there is cited, not reopened |

This plan adds three things the others lack: one loop that every area runs (section 1), a way to catch dated items
(section 2), and an order that respects the 30 Nov - 5 Dec window (section 3). It repeats none of their inventories.

## 1. The loop, per area (not once over everything)

- **Plan.** The question, the scope, and the **pass rule written before any result is read** (as S198's `PASS_RULE`).
- **Do.** Run the existing script or workflow. Where none exists, say so: that is a finding, not a gap to improvise around.
- **Check.** Against a source we did not derive: BSE or NSE files, NSE notices, Wayback copies of NSE lists, Screener
  for adjusted levels. A check that reproduces our own number, or text pasted from another tool, is a lead, not
  evidence (`DATA_CORRECTNESS.md` section 1). Each area ends with "not checked".
- **Act.** Every finding gets one of four routes: **fix by rule** (never a hand-edited price; a `notes.json` correction
  needs its evidence), **its own TODO row**, **explained** (a new section 5 row), or **owner decision**. Anything that
  moves published ranks, the frozen record or the model book is the owner's, not taken alone.

Limit of this container: no R2 keys. Every R2 check runs as a GitHub Actions job (the `s198_measure.yml` pattern) or
is handed to the owner; the report says which.

## 2. Catching the time-bound items

An audit on day X cannot close an item due after X: it would either raise a false alarm or pass it by default. So the
sweep sorts every open or parked TODO row (52 on 25 Nov; 24 mention a date from 26 Nov on, 28 carry none):

| Status | Meaning | Audit result |
|---|---|---|
| Overdue | its date has passed and the row is still open | finding |
| Due in the window | falls inside the pass being run | checked now, evidence quoted |
| Future-dated | a date or event ahead, written in the row | listed with date and owner of the check; **not** a failure |
| Undated | open, parked or deferred with no date or event (28 rows) | finding: give it a date or event, or close it |
| Done, box open | the status text already holds the evidence | finding: tick it and move it to `TODO_DONE.md` |
| Reminder only | the date lives only in a scheduled task, not in the row | finding: write it in the row |

### Dated items known on 25 Nov (from TODO and HANDOVER; the sweep rebuilds this table from the rows)

| Date | Item | What the audit looks at |
|---|---|---|
| 26 Nov 11:41 IST | the 24 Nov checks (B10, the all-time-high move, long vs Screener, breadth, S186 note) | HANDOVER; reminder set |
| 27 Nov | S142 Actions-minutes measurement, 21-27 Nov | owner decides after it; `ss_sync` first |
| 28 Nov (Sat) | first live test of the Saturday hold in `nse_long_prices` (S225 (1)) | file kept or replaced; `nse_long_hold.json` |
| 29 Nov (Sun) | `backtest_reference.yml` 05:17 UTC; R2 retention (S188 c) | run green; reference file moved only as expected |
| 30 Nov | signal: calendar 52-week high, members-only scoring, EMA 30 prints (forward-dated) | parity gate, fingerprints `4cc739e503d7` / `2c706f297680` |
| 1 Dec | the fill; #638 (owner's yes first); S193 budget reset; A3 first monthly recovery audit < 30 min | S111 drift rule, ranks that move |
| 1-5 Dec | `monthly_track_record`: November frozen for four systems, shadow record, skip-5, S178 closes, S185 bundles | S175, row 9, S160, S178, S185, S188 g, S194 PR 2b |
| 2 Dec | `momentum_health` ends Nov 2026; S95 / S111 rebalance checks 12:30 UTC; S116 (c) | S177 c, S188 f |
| 5 Dec | S185 live-bundle log read | first real R2 read of a bundle |
| 13 Dec | fifth weekly `nse_compare` (S116 d); #382 after the December freeze | |
| mid-Dec | NSE's 2027 holidays land in the file by themselves (S137) | |
| 31 Dec | S198 merged before the signal; first rebalance under S211 | |
| Jan 2027 | three systems; S226 sector cap switches with S198 (e); Combined retired | frozen ledger read-only |
| Mar 2027 | six-monthly reset to 5% (S111); S196 review | |
| 2 Feb 2027 | S220 (live Backtest load) | |
| Dec 2027 | S144, S160 reviews | |

## 3. Order (proposed)

1. **Phase 0, 25 Nov.** Freeze this plan and the pass rules; capture the baseline (`scripts/audit_baseline.py
   capture`); record the commit under audit. No fix that touches the record from now to 5 Dec except a live fault.
2. **Pass 1, 26-29 Nov.** Areas B, C, D (the parts not tied to the 30 Nov rule change), F, G, H, I, J and the
   sweep. Dated items that fall due in these days are checked as they fall.
3. **Hold, 30 Nov - 5 Dec.** Watch only: the signal, the fill, #638, the freeze. Findings queue; they are not fixed
   in the window.
4. **Pass 2, about 6-8 Dec.** Re-run the sweep, the parity gate and the audits for B and D on the state after the
   freeze; area E again on the new rule. Write `docs/FULL_AUDIT_<date>.md`. Future-dated rows stay open and listed.

## 4. The areas

**A. Open items.** *Plan:* every open or parked row has a date or an event, or is closed; every owner approval in
HANDOVER "Pending approvals" matches a TODO row marked "decided by benchmark, owner to confirm" and the reverse.
*Do:* the sweep in section 2 (by hand on the first pass). *Check:* the row's own evidence line, then the run or commit
it names. *Act:* tick, date, close, or put to the owner.

**B. Prices and corporate actions.** *Plan:* the long file's level, big moves, gaps and actions are right to the
standard of `DATA_CORRECTNESS.md` sections 2a-7. *Do:* `audit_long_prices.py`, `audit_against_screener.py`,
`audit_raw_bars.py`, `audit_gaps_against_bse.py`, `verify_bse_fill.py`, `check_long_against_screener.py`,
`check_corporate_actions.py`, `check_symbol_changes.py`; the nightly `nse_history_audit` / `nse_sample_check` /
`nse_compare` results. *Check:* NSE raw rows and BSE bhavcopy (raw against raw, never against the adjusted file). A
sample of recent actions read from the exchange's own notice. *Not checked going in:* moves between 2 and 21% (the
audit's own cut), BSE for the 2008-2010 sessions it lacks.

**C. Membership, classification, market caps, indices.** *Do:* `check_nifty500_against_wayback.py`,
`check_index_anchor.py`, `check_observed_sessions.py`, `r2_membership_live_validation.py`,
`nse_classification.py --validate`, the S168 index-store guard and the S167 (b) comparison. *Check:* NSE's published
lists and notices; Wayback copies. Each count (750, 751-752, 1,000, 411) is explained against section 5. *Not
checked going in:* indices outside the nine against a second source (niftyindices.com refuses this machine).

**D. Engine and outputs.** *Do:* `canonical_parity_check.py`, `audit_baseline.py check`, `check_ranking_frames.py`,
`check_screener_outvotes.py`; the parity gate and each frozen month's fingerprint; one fixed backtest. *Check:* a
ranking recomputed from Screener's own store reproduces the published table (reproducibility, not correctness); for
correctness, the top names' prices against NSE/BSE closes on the day and the gates against NSE's raw bars. The
28 Nov, 30 Nov and 1-5 Dec events land here. *Not taken alone:* anything that moves ranks, frozen months or the book.

**E. Pages by system.** *Plan:* S163's inventory exists; this pass checks it is still true after four weeks of change.
*Do:* `number_format_audit.mjs`, `glossary_audit.mjs`, `check_dashboard_requirements.mjs`, `layout_audit.mjs`,
`page_dates_audit.mjs`, `link_crawl.mjs`, `headless_smoke.py`, `production_qa.py`; `FIGURE_INVENTORY.md` against the
pages. *Check:* each figure on a sample of pages (largest and smallest element per page, every system) traced to its
source file and rechecked against the exchange. *Not checked going in:* a phone browser; Streamlit Cloud memory.

**F. Storage.** *Do:* `r2_inventory.py`, `r2_audit.py`, `s224_r2_copies.py`, `r2_recovery_audit.py`,
`r2_session_continuity_audit.py`; S224 (a)-(c) (track record, membership timelines, FII/DII and results calendar have
no R2 copy). The restore drill: rebuild one page from R2 alone, timed. Licence and terms for each source; which
figures depend on a host only the runners can reach. *Check:* a restore that works, not a listing that looks complete.
*Act:* nothing deleted without the owner's yes per item.

**G. Pipelines and CI.** *Do:* last 30 days of every workflow (failures, minutes, skipped slots), the S221 catch-up
night, the S225 alerts, `schedule_watchdog.yml`, first runs listed in S188. *Check:* the scheduled-failure issue
matches the failed runs found by reading the runs, not the issue. *Not checked going in:* billed minutes (owner's
billing page).

**H. Code, tests, dependencies, security.** *Do:* `python -m pytest tests -q`, `ruff check`, dependency state after
S209, S212's leftovers, and a security review of the pending state of `main` (the repository is public: secrets in
workflows and history, what `pull_request` runs can read, Dependabot secrets). *Check:* `gh`/Actions settings read
from GitHub, not remembered.

**I. Docs.** *Do:* each doc's date against its content, TODO against HANDOVER against CHANGELOG, S-number collisions,
rows quoting a run ID that no longer matches. Already seen while planning: `DATA_CORRECTNESS.md` says "Last updated
2026-10-07" but holds 24 Nov decisions; `TODO.md` says "Last updated 2026-11-23" with rows from 24-25 Nov; HANDOVER's
"Local state" names a checkout that is not this one. *Act:* fix by editing, rides in the audit's PR.

**J. Production against the repository.** *Do:* the site's hidden metrics (`ranking_precompute`,
`nse_long_close_revision`) and Production QA's output on the audited commit. *Check:* every page's date against its
session; the deployed SHA equals `main`'s. *Not checked going in:* what a reader sees on a slow connection.

## 4a. Carried over from S163's checklist (`archive/DATA_AUDIT_PLAN.md`, archived 25 Nov 2026)

Only what was still open on 25 Nov. Everything else in that checklist was ticked with its finding in
`DATA_AUDIT_2026-11-24.md`.

- [ ] **R2 copies (area F, S224 a-c):** track record and frozen months, `book_exposure.csv`, `breadth_history.csv`,
      `signal_tests.json`, `momentum_health*.csv`, the membership timelines other than Total Market and Nifty 1000's list,
      `fii_dii_flows.csv`, `nse_dii.csv`, `results_calendar.csv`, `nsdl_fpi_daily.csv`, `nse_total_market.csv`,
      `ind_nifty1000_list.csv` and `indices.nifty_1000` (point in time: a missed night is lost). Each with a keep-for
      period and a restore test; needs R2 keys, so by the `s224_r2_copies.py` job
- [ ] **Stored twice (S172):** the index store in R2 `indices/nse_close_all` and in git (`nse_indices_history.parquet`,
      `nse_indices_recent.csv`): decide which the page reads
- [ ] **Costs (S142):** R2 operations, Streamlit memory, billed minutes from the owner's billing page
- [ ] **Licence and terms** for Screener, NSE's archives and any feed; **reachability** (which figures depend on a host
      only the runners, or only the app, can reach)
- [ ] **Data dictionary:** each file's columns, units, start date and writer, beside `DATA_CATALOGUE.md`
- [ ] **First runs of the 21 Nov jobs:** the 1-5 Dec freeze of `data/track_record_1000.json` is the one left (by date)
- [ ] **Pages added 21-22 Nov, area E:** Indices (every figure traced to the store; P/E basis break at 31 Mar 2021; "derived"
      sessions shown as such), the S168 store's guard and reference tables, Nifty 1000 under every page, "> ₹2,000 Cr"
      label and `?sys=nano` links, Market's `/breadth` redirect keeping `?system=`

## 4b. Documents to merge or archive next (proposed 25 Nov; owner's yes per group, nothing deleted)

Round 1 (done 25 Nov, S227): six files moved to `archive/` (list in `archive/README.md`); links checked. Judged from
headings, dates and who reads each file, **not** from reading every page for overlap. Per-page `*_REQUIREMENTS.md`,
`PAGE_DESIGN`, `GLOSSARY`, `FIGURE_INVENTORY`, `DATA_CORRECTNESS`, `PRICE_PIPELINE`, `DATA_CATALOGUE`, `TODO`, `HANDOVER`
stay: CI, tests or the rules name them.

| Group | Files | Proposal | Touches |
|---|---|---|---|
| Site and UI | `UI_ARCHITECTURE` (637 lines, Sept history, section 11 current), `THEME` (96) beside `PAGE_DESIGN` section 2a | keep section 11 and the theme's rules in `PAGE_DESIGN`; archive the rest | README cites UI_ARCHITECTURE twice |
| Root `README.md` | ~380 lines, status text of 23-30 Sep, points at archived files | cut to what the site is, how to run, where the docs are | links only |
| Price basis | `NSE_PRICE_BASIS` (75), `PRICE_SOURCES_AUDIT_2026-11-21` (70; S167 open) | first into `PRICE_PIPELINE`; second into `DATA_CORRECTNESS` section 2 when S167 closes | none |
| Track record | `track_record_portfolio_architecture` (390, Sept design), `MONTHS_THAT_DIFFER` | keep `TRACK_RECORD` and `THREE_SYSTEMS`; archive both after a pointer paragraph | README line 197 |
| Cost and storage | `AUDIT_PLAN` (Block 0 numbers), `CALL_AND_STORAGE_AUDIT`, `RESOURCES` (S195), `DATA_AUDIT_2026-11-24` section 7 | one living `RESOURCES`; dated measurements archived | 8 code comments cite the call audit; 2 script docstrings cite `AUDIT_PLAN` |
| R2 specs | `MARKET_DATA_ARCHIVE_R2_SPEC` (1,568 lines), `R2_ENGINEERING_LOOP`, `R2_HISTORICAL_EVIDENCE_SPEC` (all Sept), `PENDING_DELETIONS` (246) | keep `R2_RECOVERY_AND_RETENTION` and `DATA_CATALOGUE`; archive the three specs with a one-page current contract; trim `PENDING_DELETIONS` | **CI**: four workflows filter on the spec's path and `r2-focused-validation.yml` reads the loop file, so a full run |
| Research notes | `MOMENTUM_ABC`, `RISK_OVERLAYS`, `MOMENTUM_HEALTH`, `INDICES_RESEARCH_DATA`, `SECTORS_INDEX_MAP_PROPOSAL` | a `docs/research/` folder, or archive; each is cited by code or a requirements doc | 6 code comments |

Order: site and README, price basis, track record first (no code or CI); cost and R2 last.

## 5. To do

**Phase 0 (25 Nov)**
- [x] Round 1 of the document clean-up (section 4b): six files archived, links and tests checked
- [ ] Owner's yes or no per group in section 4b; then round 2 in one PR
- [ ] Owner confirms or changes the phasing (section 3) and the two suggestions below
- [ ] Capture `scripts/audit_baseline.py` baseline; write the commit under audit and the pass rules into the report's header
- [ ] Build the sweep table (section 2) from the rows; list the 28 undated rows

**Pass 1 (26-29 Nov)**
- [ ] A: the six statuses assigned to all 52 rows; owner list for undated ones
- [ ] B: price audits run, each finding routed
- [ ] C: membership, classification and index checks run
- [ ] D: parity and baseline checks run before 30 Nov (so the signal change is measured against a known state)
- [ ] F: R2 inventory and copies through an Actions job; restore drill timed; licences listed
- [ ] G: 30-day run table; first-run checks of the jobs added 20-24 Nov
- [ ] H: tests, lint, dependencies, security review
- [ ] I: doc dates and cross-references fixed
- [ ] J: live metrics read on the audited SHA
- [ ] Dated items falling due 26-29 Nov checked and quoted (section 2)

**Hold (30 Nov - 5 Dec)**
- [ ] Watch the 30 Nov signal, the 1 Dec fill, #638's decision and the 1-5 Dec freeze; queue findings, fix none

**Pass 2 (6-8 Dec)**
- [ ] Sweep re-run: every dated item in the table is either checked with evidence or still future-dated
- [ ] D and B re-run after the freeze; E re-run on the new rule
- [ ] `docs/FULL_AUDIT_<date>.md` written: findings table (ID, area, evidence, route), what was not checked
- [ ] Every finding has a fix merged, a TODO row, a section 5 row or an owner question; owner has read it

**Done when** the report exists, every box above is ticked or carries the reason it is not, and every future-dated
row is listed with its date and who checks it.

## 6. Suggestions (owner to choose; recommendation marked)

1. **Dates machine-readable in the rows, swept by a script** (recommended). Give each dated TODO row a
   `Due: YYYY-MM-DD` and have `scripts/todo_due_check.py` print the six statuses of section 2. *Cost:* about 25 rows
   edited and one small script, run by hand at each pass first; attaching it to an existing watchdog later only if
   someone reads the output (S195 section 4). *Gives up:* the free-text freedom of a row. *Why:* today the dates for
   the 1-5 Dec window live in session-bound scheduled tasks that "a new session re-creates"; a row cannot be lost
   that way.
2. **Two passes, not one** (recommended, section 3). *Cost:* the report lands about 8 Dec, not this week.
   *Gives up:* one clean date. *Why:* on 25 Nov the 30 Nov rule change, the fill and the freeze are all ahead, so a
   single audit now would describe a state that changes in days, and a fix made before the freeze risks moving frozen
   outputs.
