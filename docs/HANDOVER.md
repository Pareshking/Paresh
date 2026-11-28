# Handover: Pareshking/Paresh, coordinating role

The one living handover (S201): edit this file in place at each handover (the
state, queue and dates sections); do not write a dated copy. Earlier dated
handovers are in `docs/archive/HANDOVER_*.md`. Paste the prompt at the end as
the first message of a fresh session.

_Last updated: 26 Nov 2026 ~15:45 IST, coordinating session session_016X4g5Y1bsnhgFzzKddp8Wc (took over 14:00 IST)._

## The owner's standing rules (unchanged)

- **One activity at a time.** Don't wake other sessions unless a task needs it.
  Start no new work from TODO; finish what is listed below, in order.
- **Merging:** you do the merges. Merge only when CI is green on the PR's
  **current head** and it merges cleanly with `main`. Squash-merge with
  `expectedHeadSha`. After a squash merge, restart your branch from `main`.
- **Before taking an S-number,** check open PRs as well as `main`. Next free:
  **S234** (TODO's header lists what is reserved).
- **Verify every claim yourself.** Nothing is deleted without the owner's yes on
  each item; the `ref_*` release files always stay.
- **Tests:** `python scripts/fetch_nse_closes.py` first, then
  `python -m pytest tests -q -n 4 --dist worksteal` (as CI, S138 I8), and `ruff check`.
  The suite's cache is a temporary directory (S138 I7); only the fetched closes are
  copied in from the checkout's `data_cache/`, so in a git worktree run the fetch
  inside the worktree too (6 `test_nse_prices.py` errors otherwise).
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

**Standing instruction (owner, 24 Nov ~09:05 UTC):** "Check what is already done or covered and work on them ... now onwards you will don't wait for my commands to start, start one by one and finish them." Work the TODO queue in order without asking; owner decisions (ranks, frozen record, model book, deletions) still go to the owner one at a time.

## State at handover

**26 Nov ~10:15 UTC.** #705 merged (2c184e2, S172 (b) step 1): the first `app_pack` run (45797631273) published revision 3f6254ca and read all 37 files back matching main; Production QA 45797631376 green, served 2c184e2. Step 2 after a week of green `app_pack` runs. On the branch, no PR yet: S233 (1) the Backtest default page kept as its parts, (2) the daily price history kept on disk (`src/core/disk_memo.py`); after a full cache clear, locally, Dashboard 19.8 -> 5.7 s and Backtest 17.1 -> 4.9 s, pages identical. Not done: the shared price load (~4 s after a pull; `keep_and_fill` records sources as side effects, so a disk copy needs care) and the model book replay (its key lacks membership and the industry map). **26 Nov ~11:10 UTC:** #706 merged (d80e02c; S233 (1) (2) and the membership in both run keys); Production QA 45803161505 green: Backtest 22.3 -> 17.0 s (the first visit after a code change misses the kept page by design), Sectors 4.5 -> 1.7 s. The shared price load and the record's basis frame are deferred until S172 step 2 is measured (TODO S233). No PR open.
**26 Nov ~14:35 UTC:** #707 merged (3881a18): S232's PicklingError fixed (the regime and index-frame caches keep plain values); TODO S203 closed, S227 seen live, the queue above refreshed. Production QA 45839638472 green. No PR open.

**24 Nov ~13:15 UTC.** #674 merged (6a613a5; S203 wrong-today sentences, S189 items 3 and 8, S223, S224 notes, S163 §5-6). On the branch, opened as one PR: S225, all ten pipeline follow-ups. The owner answered (1) "Hold back on Saturday", (2) "Drop schedule only", (8) "Drop 02:00"; built (3) conflict warnings, (4) every green run scanned, (5) push alerts for Production QA and Full Validation, (9) pip cache; (6) and (10) explained. The nightly hold after a Saturday breach is pending approval (above). Next: Production QA on 6a613a5, merge the S225 PR on green, then S203's per-sentence tests, S189 item 6 (a), S163 2 (f).

**24 Nov ~11:30 UTC.** #671 merged (cb0e825); Production QA, parity, R2 gate and lint green on it. On the branch, no PR yet: S203's wrong-today sentences on eight pages; the owner's five S203 answers (all "recommended", one at a time) built; S189 item 3 (the Screener key folds on a phone). Next: run CI's checks locally, open one draft PR, merge on green.

**24 Nov ~08:05 UTC.** #669 merged (91af345) after its run 45350700763 passed the layout audit with the short zone words; main's validation (45352380590), Production QA (45352380424) and parity (45352380450) on 91af345 are running: green there closes S222 and #668. On the branch, no PR yet: the readouts measure again once the web fonts load (e3ee870, S222's second half; local layout audit clean on all ten pages). Owner asked for the waiting decisions one at a time: 1 of 4 (#638) put to the owner 24 Nov; then S138 NEXT 2-7, S166, the readout wording.

**24 Nov ~07:40 UTC.** #667 merged (1fdd88d); Production QA green on 9649964 and 1fdd88d. **Main's validation is red since #666 (S222, issue #668)**: the Dashboard's flows readout crowds its chart at 412 px on the runner only; cause found 07:45: a readout line wraps in the runner's fallback font (DejaVu Sans), not in Inter; fix on #669 (short zone words, test pinned). Open: #669 (S168 benchmarks on NSE closes from 2012, owner OK 24 Nov; S191, S167 (b), S196, S175 recorded). Merge only once its validation is green.

**24 Nov ~06:45 UTC.** #665 and #666 merged; Production QA green on 9649964 (run 45340114559, served 9649964). S210, S136, S214 closed from the live site (S214: the live Backtest holds R2's current long-file revision, `r2:5ae3e494706e…`). Next PR (branch, open when its checks pass): S138 I2/I3 (markers), I6 (page CSS in `src/ui/page.css`), I7 (test cache in a temp dir), ruff B, UP and SIM, NEXT 8 (engine edge cases; a repeated or reversed date no longer crashes or empties the ranking). Left in S138: NEXT 2-7, research for the owner. The four 15-minute check-ins (`trig_01Lc8…`, `trig_01DiPA…`, `trig_01Q8Qj…`, `trig_01DGbs…`) run to 16:45 UTC and are then deleted.

**24 Nov ~05:25 UTC.** #664 merged (d3f5def): the batch below plus the calendar 52-week high in the engine and "a year is the calendar year everywhere" (owner, 24 Nov), and S165 on the Dashboard. Next PR (branch, open when its checks pass): S164's two late figures (12-month tile names its finished months; DII tile adds NSE's provisional days), S173 (c) label fixes, S203 leftovers (pf.view.1 dropped, pf.err.3, "Out"). Work loops every 15 min to 16:45 UTC (`trig_01Lc8VcpwheKPuvE5jGmab9x`, `trig_01DiPAupW1m1NdtAUruteAum`, `trig_01Q8Qjyayj1FBgYRhSTfqDPR`, `trig_01DGbshARRgk12eRUeFTKM5V`; delete after).

**24 Nov ~04:40 UTC (combined batch, one PR).** #663 merged (the catch-up sync, S221). In one PR: S203 (Dashboard and Portfolio sentences from the approved templates), S165 (Market and the header strip read Nifty Total Market; Dashboard and Portfolio still to do), S173 (b)(d) (the label audit and a banned-synonym guard), S154 (a)(b) (figure inventory and a same-label test, 4 strict xfails = findings), S129 (c) (the ICICIPRULI -> ICICILIFE alias; the freeze leaves out renames after its date, hash unchanged). Next: S154's three fixes (Nifty Total Market weekend sessions before 8 Dec first), S173 (c) label fixes, 52W high by calendar date (owner, 24 Nov), S164 when its agent reports.

**24 Nov ~03:10 UTC (overnight, owner away).** S193 E-L and S219 are all merged: #657, #658, #659. Overnight merges:
- #660: the Dashboard no longer crashes on a month's first session; three wording faults fixed; the crawler race fixed.
- #661: Backtest budget 17 → 31 s by rule; S220 opened.
- #662: Backtest's figures, trade table and trade log cached once per run (warm 6 → 1.5 s locally); flows "Tested here" counts 129 months.

Production QA green on af15327. Open:
- S220: live Backtest is about 11 s (server stages ~0.6 s; the rest is outside the page body); parked to 2 Feb 2027 (owner, 24 Nov).
- 24 Nov checks (B10, the all-time-high move, long-vs-Screener, breadth, the S186 note): moved to 26 Nov 11:41 IST (owner, 24 Nov; a reminder is set).
- S186 deploy note not yet seen.
- Reminder set for the 1-5 Dec monthly run (2 Dec 04:41 UTC).

**23 Nov ~17:15 UTC (S193 E-L decided).** The owner decided S193 E-L and S219 one at a time (TODO S193, S219). Three PRs: PR 1 = G + E date rules (open); PR 2 = H, I, J, K, L, E "–" wording, S219 (1)-(3); PR 3 = S219 (4)-(7). Overnight loops :05 :20 :35 :50 IST from 00:05 to 09:00 24 Nov (start `trig_01NW6p8NqsVkvDvVeAzvzUbi`, end `trig_01UabbtWyKHZgvhPhbBK6uwr`). Owner's away rule: CLAUDE.md "Decisions when the owner is away". Reports: `docs/archive/S193_ITEM_{E,H}_2026-11-23.md`, `S193_BENCHMARK_HJ_2026-11-23.md`; the K crawl and the L bench are running or due.

**Pending approvals (decided by benchmark or by rule, owner to confirm):**
- **Confirmed by the owner 27 Nov ("Confirm all"); was decided (S172 (b), 26 Nov):** the 37 page-read job outputs move to R2 as one `app/pack` (zip with a SHA-256 manifest, read once at startup, committed files as the one fallback), not as 37 datasets: one R2 read instead of 37 and one writer step. Reversal: per-file datasets as S172 first said. **Owner, 26 Nov: "Stop commit and save everything in R2"**: the daily data commits stop in step 2, job by job, after a week of the pack matching git. [inventory](archive/S172_INVENTORY_2026-11-26.md)
- **Confirmed by the owner 27 Nov ("Confirm all"); was decided by benchmark (S166, 26 Nov):** the methods review is closed: every one of its 30 rows quotes its source, its fixes are built (S223). The owner's read confirms it; a reversal reopens the row.
- **Answered by evidence (S172, 26 Nov):** the R2 keys are in the live secrets; the owner's Streamlit log shows the app reading R2.
- **Confirmed by the owner 27 Nov ("Confirm all"); was decided by benchmark (S165, 26 Nov):** the Nifty 500 stays where history needs it (Backtest, the Dashboard's signal rows and tests, frozen months, Indices P/E, Guide's reset test), each named with its reason; Nifty Total Market everywhere else. Evidence: GIPS asks that a benchmark change state its date, description and reason (Q&A 5051, quoted in TODO S165). A reversal is wording only.
- **Confirmed by the owner 27 Nov ("Confirm all"); was decided by benchmark (S190, 25 Nov):** Sectors pairs 12 finer NSE indices with the 750's stocks of an NSE industry or basic industry (`data/reference/nse_finer_index_stocks.csv`, a reason per row): the index's own name matched to NSE's own classification. Not checked: each index's eligible basic industries in NSE's methodology (PDFs 503). Sector-wide variants are not paired. A reversal is one file.
- **S212, owner 26 Nov: "Yes, remove".** `page_kit.equity_chart`, `Metric`, `metric_tile` and every `st-key-mrow_` CSS rule removed (shared `.mkt-strip` rules kept). Then (owner: "Remove") `lw_chart.series_points` and its two tests.
- **Confirmed by the owner 27 Nov ("A"); was decided by benchmark (S231, 26 Nov):** Indices' earnings get a switch, All companies (default) / Without financials (NSE's macro sector Financial Services left out). Evidence: NSE's own Corporate Earnings Review reports figures "ex-Financials" (search snippets; the PDF returned 503, retried daily); brokerages report ex-BFSI. Reversal: drop the switch, the all-company figures never changed.
- **Answered (owner, 25 Nov, "It's fraud company, leave it"), S171:** Rajesh Exports left out of every index sum (`screener_earnings.LEFT_OUT`, reason recorded); the page names it neutrally, its own Stock page still shows what it reported. Microcap 250 revenue Q2 FY26 +48.0% → +11.3%.
- **Found and fixed (25 Nov), S171:** 46 companies stopped publishing consolidated accounts and Screener's consolidated table for them ends years ago (TATAELXSI Mar 2015, 3MINDIA Jun 2024); their standalone page is read instead (`stale` in `screener_earnings_measure.py`). Nifty 500 coverage 488 → 497 of 500. All 1,243 pages read, 0 failures; 2 merged past members (IDFC, TV18BRDCST) have no current quarters, 4 new listings show their quarters with growth "–".
- **Built (owner, 25 Nov: "Screener do restatement when companies does, so ensure we are saving updated one"):** each week's page wins for all 13 quarters it shows; a changed quarter keeps its earlier reading in the R2 store with `superseded_on`, the run log lists the restated company-quarters, and every growth figure is recomputed from the current rows. Restatements arrive with results (next quarter, year end), when the job reads that company anyway; any other is caught at the quarterly full read.
- **Fixed (owner, 25 Nov: "It's impossible, check screener website with company names etc first"; "If you are using NSE CSV to build latest universe, this issue would not be there, where are we making mistakes?"):** the mistake was ours: the job took `nse_classification.universe()`, which adds every symbol in TradingView's classification file (2,404, of which 315 are not on NSE's main board: old tickers AKZOINDIA, TV spellings BAJAJ_AUTO, partly-paid lines ATLPP.E1). The universe is now NSE's lists only (750, Nifty 1000, Nano) plus past index members, 1,243 stocks, each read as NSE lists it today (BARBEQUE → UFBL, HIL → BIRLANU); names from NSE's equity list. Found on the way: our Nano list carries SHUKRAPHAR, renamed SHUKRAMED (S227). The quarterly full run is ~1 h, not ~2; no manual option (owner: "Keep it in auto").
- **Built (owner, 25 Nov: "keep our weekly run intelligent"):** `pages_to_read`: new stocks; a stock lacking the due quarter with a results meeting in NSE's calendar since its last read; with no calendar entry, while the filing window is open (45 days, 60 after March, LODR Reg 33); every page once a quarter on the first run after the deadline. Off-season Saturdays read almost nothing; `all=true` by hand reads every page.
- **Built (owner, 25 Nov: "storing in R2 so we can have own history getting build up, use correct R2 format"):** the weekly job starts from and publishes R2 `fundamentals/screener_quarters` (parquet, zstd, ~0.2 MB per 1,000 companies, a fifth of the CSV), one revision a week, every quarter kept; the repo keeps the pages' copy of the last 13 quarters. Retention: full history (not in r2_retention's daily lists).
- **Approved (owner, 25 Nov, "Go ahead"), S171 Stock page results:** section "5 · Results", 8 quarters, sales / operating profit (profit before tax for lenders) / net profit / EPS with YoY; exact crore and EPS to two decimals (PAGE_DESIGN rule 2 exception widened); note "last updated <date>", no source, no schedule (owner: "Show last updated but don't show will get every Saturday update"), applied to the Indices note too. Weekly job reads every listed stock (~2 h of Actions a week).
- **Answered (owner, 25 Nov), S171:** "We will use Screener data only": the Indices Earnings section and chart read our calculation (`data/reference/screener_earnings.csv`), NSE's figures off the page, NSE kept as the weekly job's log check. **Still for the owner:** (a) profit as reported or (b) without other income (built as (b), `earnings_review.PROFIT`; with Tata Motors out, Q2 FY27 Nifty 500 reads 30.3% (b) vs 27.3% (a); the gap is widest in Q4 FY26, 14.1% vs 25.1%, Vodafone Idea); **decided by rule, owner to confirm:** Tata Motors also out of Q2 and Q3 FY27 (their base holds the demerger; TMPV Sep 2025 profit ₹76,248 Cr, 16 points of the Nifty 500 alone), and a quarter shows once 90% of the Nifty 500 has reported. Reversal: one constant, or one set in `scripts/screener_earnings.py`.
- **For the owner (S171 (2), 25 Nov), one question:** our Screener aggregate (933 pages, point-in-time members; [note](archive/S171_SCREENER_EARNINGS_2026-11-25.md)) matches NSE's **revenue** growth on all 8 quarters (within 1.7 points) but not **profit** (8 quarters over 5 points), led by one-off gains Screener counts in Net Profit: Vodafone Idea Mar 2026 ₹51,970 Cr profit on ₹57,595 Cr other income lifts the Nifty 500's Q4 FY26 to 25.1% (NSE 15.3%). Rows checked on Screener's live pages 25 Nov: ITC Mar 2025, IDEA Mar 2026, RELIANCE Jun 2025. **Recommended:** revenue ours now, profit stays NSE's until a one-off rule is tested against NSE. Lead (25 Nov, tested after the results were seen): profit without other income for non-financial companies cuts the flags from 8 to 2 (archive note); first out-of-sample check is Q2 FY27. Other ways: profit as reported with a note; or wait for both. Nothing on the page has changed.
- **Answered (owner, 24 Nov, confirmation round):** S225 (1) nightly hold kept. S203: the stock lede's market cap **exact** ("₹29,944 Cr", reversing the cr() choice; a lakh crore and above keeps "₹1.22 lakh Cr"); Actions in whole rupees kept; Backtest "2026, to Oct" and the majority colour kept; the Screener footnote says **"the Ultra Nano Cap list (> ₹2,000 Cr until January)"** now (the bracket, "until January": approved by the owner, 24 Nov). S189: item 1 **reverted** ("look is also important": "Out" alone again; a too-new stock's 52W ✗ says why on hover), item 2 kept (after an image), items 4, 5, 8 kept, item 7 **changed** (the short-history Max DD shows with a "†", "since listing", and a caption), item 9 dropped. The calendar 52-week high goes into the model book from 30 Nov (approved). S224 (d) deletions: yes.
- **Answered (owner, 25 Nov), S171 (2):** earnings growth from Screener's company-page quarters, point-in-time members, weekly on Saturday; "Use screener over NSE for decision" (Screener primary where they differ; NSE a reported cross-check, a gap over 5 pts flagged). Measure running (agent); the page switch and the Saturday job follow it.
- **Answered (owner, 25 Nov, "Ok"), S171:** Q3 FY26 excludes Tata Motors (NSE's ex-Tata Motors rows: Nifty 50 revenue 12.5%, profit 12.8%; Nifty 500 11.1%, 18.2%), as Q2 FY26 and NSE's summary; the quarterly history chart is built on it. Reversal: empty `EX_TATA_QUARTERS` in `scripts/nse_earnings_review.py` and rebuild.
- **Answered (owner, 25 Nov, "1"), S193 A11:** the Dashboard reads each stock's last close in the week, as Market does (`market_questions.last_close_in_week`). Measured on the cache (today's 750, 271 sessions to 5 Nov 2026): the 6 sessions where the 12M median lead differed by 0.1 pt now agree; the share was never apart as shown. No rank moves.
- **Answered (owner, 25 Nov):** S189 item 10, the Screener's "Market cap, Cr" column stays exact (₹2,97,404), written into glossary 2 as the exception; item 11, the column sets keep their names. No code change.
- **Approved (owner, 24 Nov, "Ok"), S226:** pages name NSE's finer levels "industry" and "basic industry" (and "NSE macro sector"), as NSE Indices' Industry Classification Structure names its four levels (Macro-Economic Sector, Sector, Industry, Basic Industry; nseindia.com/products-services/industry-classification); glossary 2 amended. A stock the file lacks reads "Unclassified" at those levels, never TradingView's label. Reversal: `LEVEL_NAMES` / `_SEARCH_KINDS` and the glossary row. The sector cap is **not** switched: `scripts/s226_measure.py` measures it for the owner (`docs/archive/S226_PLAN_2026-11-25.md`). **Names checked 24 Nov** (search result of NSE Indices' own page, [niftyindices.com/resources/industry-classification](https://niftyindices.com/resources/industry-classification)): a four-tier structure, Macro-Economic Sector, Sector, Industry, Basic Industry; 12 / 22 / 59 / 197 (the 21 Mar 2022 press release said 58 and 200). The PDF itself (nsearchives) answered 503 and niftyindices' PDF timed out, so no stock's placement was checked against NSE.
- **For the owner (S226 (B), 24 Nov):** switching the sector cap to NSE's sector moves the record's cap group for **121 of 411 Nano** stocks (0 on the 750 and the 1000): `python scripts/s226_measure.py --system nano`. Also: on Nano the live plan caps by TradingView's sector and the record by NSE-voted industries, and they differ for 387 of 411. Plan reading, 24 Nov Nano ranking, empty book: the same buys both ways. Backtest (24 months, 98% of priced stocks classified; the 84% trial gave the same): 1 month differs (May 2026, HFCL for GVPIL), 28.1% → 28.5% a year, max DD the same. **Approved (owner, 24 Nov, "Ok"):** the cap switches to NSE's sector with S198's January change (S198 (e)), so the record changes once. Not switched before then.
- **Approved (owner, 24 Nov, "Ok for all"):** the Screener shows NSE's sectors on Nano and Combined only once `data/reference/nse_classification.csv` covers 90% of that system's stocks (`MIN_COVERAGE`), so the column is never half NSE's names and half TradingView's. Below that it stays as today. Reversal: one constant.
- **Approved (owner, 24 Nov, "Ok for all"):** the R2 membership set (`indices/membership/*`, `indices/constituents/*`, `universes/point_in_time`, ~8 MiB) is **kept**, though S224 (d) listed it: point-in-time evidence that can't be downloaded again, and S197/S198 read it in December (`docs/PENDING_DELETIONS.md`).
- **Approved (owner, 24 Nov, "Ok for all"):** S198 (a), fixed before any result: Ultra Nano Cap passes when, at 60 bps a round trip, it compounds faster than Nifty Total Market over the window and its max drawdown is within 5 pts of today's > ₹2,000 Cr system's (`PASS_RULE`, `scripts/s198_measure.py`); before NSE's first Nifty 1000 list (30 Oct 2026) the measurement uses a proxy, the 750 plus the 250 largest others by month-end cap. Reversal: edit `PASS_RULE` and re-dispatch `s198_measure.yml`.
- **Approved (owner, 24 Nov):** month bars on the Dashboard: the step is 0.25% unless a row would pass 65 lines, then 0.5/1/2% (the list showed a 544 px track, over the 520 px rule); PAGE_DESIGN 4.2 updated.
- **Approved (owner, 24 Nov):** amber notes split into warnings and info notes (`kit.note(kind=...)`): now info, the Backtest system note, Actions' "No model book yet", the Nano/Combined Screener footnote; kept as warnings, Backtest's empty window and Config's "every stock at the cap" (borderline).
- **Approved (owner, 24 Nov):** Backtest's Nifty 500 column shows its own volatility, Sharpe and Sortino (were "–"); both sides are price returns, which the page's note already says (^CRSLDX, the price index).
- **Approved (owner, 24 Nov):** Portfolio's lead-by-month chart opens on all months of the book (was the last 12; the same today); look again on a phone when the book passes ~24 months.
- **Approved (owner, 24 Nov), with a reset on ~1 Dec to the week's slowest reading x 1.5:** Production QA's Backtest load budget 31 s (was 17; rule: the slowest live reading x 1.5); back down once S220 is fixed.
- **Approved (owner, 24 Nov), all four as built:** PR 3 (S219 4-7, S193 L), see TODO S219 and S193: Watchlist search labels show the company name (the Screener's show the sector); Backtest's line says "rebalanced monthly, at the month’s last close" for 21; Sectors' 3M and 12M sit after the 1M lead and Broad or narrow keeps 3M and 1M; the Nifty 1000 row follows Nifty Total Market.
- **Approved (owner, 24 Nov), reset ~1 Dec as above:** **S193 L budgets vs live:** the first live readings were over the local budgets on 9 of 10 pages; budgets reset by the same rule on the larger of local and live (Dashboard 8 ... Backtest 17 s, `scripts/production_qa.py`). One live reading is thin: revisit after a week of runs. Backtest raised to 31 s on 24 Nov (live 18-20.5 s on every new reader; Production QA 45271454528 failed on it twice in a row); why it never warms is S220.

- **Built (owner, 25 Nov: "A quarter appears once 90% of Nifty 500 companies have reported - we can show how many companies out of universe reported"):** the latest-quarter table has a "Companies reported" column (Q2 FY27: Nifty 50 49 of 50, Nifty 500 493 of 500), counted against the index's full size. The 90% rule stays. Not yet confirmed by the owner: profit without other income; Tata Motors out of Q2 and Q3 FY27.

- **Built (owner, 25 Nov: "Show partial one"; "show partial also by showing how many companies out of universe reported"):** also the top row "<quarter> so far, N of 500 reported" in both quarterly tables; the quarter still coming in shows as "<quarter> so far" under the latest table from one in ten Nifty 500 companies reported (`PARTIAL_SHARE`) until nine in ten; an index under one in ten of its own companies reads –. Thresholds decided by rule, owner to confirm. First real one: Q3 FY27, mid-January 2027.

**25 Nov ~15:45 UTC (state).** #692 merged (b2253f5, QA 45625108822). Owner back, five decisions one at a time: (1) profit without other income, confirmed; (2) Tata Motors out of Q2 FY27, Q3 FY27 on data (built on the branch, check in Jan-Feb); (3) "so far" from 1 in 10, confirmed; (4) S227 "Fix now", but the premise I gave was wrong (the stock is current, 1st in the Nano list and held in the model book), the fix reverted unshipped; asked again, "Redirect now, rename in Jan": the redirect built (display only), the rename dated to the January rebuild; (5) S228 leave as is.

**25 Nov ~12:40 UTC (state).** #689 merged (06be1d5, QA 45605237656 green): Indices "Companies reported" column and the quarter coming in as "so far". The R2 inventory failed on 25 Nov (45605511334): its freshness list still held `market_caps/nse_history`, retired 24 Nov (S224 (d)); fixed in the next PR with a test. S163 section 3 outside addresses: when each last answered added (§5); licence and terms quoted (§5a), finding S228 for the owner (on the branch, no PR yet). Next: 28 Nov 04:23 UTC first `screener_earnings` run (log: pages chosen, restated, NSE check; first R2 publish).

**25 Nov ~10:40 UTC (state).** #686 (5f5b322, QA 45584701444) and #688 (184ce7d, QA 45595793084) merged, both green and seen live: Indices earnings from our Screener calculation with quarterly tables for six indices; the Stock page "5 · Results". First Saturday run of `screener_earnings.yml` 28 Nov 04:23 UTC: first R2 publish of `fundamentals/screener_quarters`, check its log (pages chosen, restated, NSE check). Waiting on the owner: S227 (Nano list ticker), and the three S171 rules marked owner to confirm. Work loops stay on.

**25 Nov ~04:25 UTC (state).** #683 merged (d81a83d: S193 A11 Dashboard 12M on Market's rule, S154 one tick set, S189 10-11 answers); Production QA 45546189516 running on it. Work loops (:05 :20 :35 :50 UTC) **stay on while anything is pending** (owner, 25 Nov ~09:40 IST: "If anything pending don't off the loops and let's work"); renamed "(while work is pending)". Open: no PR. Dated: S142 after 27 Nov, #638 after the 1 Dec fill (owner's explicit yes), S95/S111 after 2 Dec, S198 (a) after the 1-5 Dec freeze.

**24 Nov ~21:40 UTC (state).** Merged tonight: #680 (ea662a6: confirmation round, NSE classification job, S198 (a) job, S224 (d) retirements, S203 size.4), #681 (66d471e: S226 (A) search and Sectors), #682 (c4e2ca9: S226 (A) Dashboard/Market/Watchlist labels, former members via historical_industries.csv, "Unclassified"); Production QA green after each (45454590758, 45478051877, 45491939468). R2: 399 keys deleted (apply 45455963163, audit passed). Classification sweep 45454637779 (2,385 stocks, 99.6-99.7% agree with NSE's lists). Open: no PR. Next: S198 (a) dispatch after the 1-5 Dec freeze (`s198_measure.yml`); S198 (e) carries the sector-cap switch (owner, 24 Nov); #638 after the 1 Dec fill with the owner's explicit yes; Screener-vs-NSE sector cases CMPDI, SUDEEPPHRM, INA, BUILDPRO (lead: all listed in the last 12 months; not checked on NSE).

**23 Nov ~09:30 UTC.** #647 merged (938121e). Earlier: the owner asked for a fresh session from 14:00 IST; this session stopped new work and finished
what was in progress. Merged on 23 Nov: #628, #630, #634-#637, #639 (S209), #640 (S212 clean-up, ~13,700 lines),
#644 (S214), #645 (numpy 2.5.5; Dependabot #641-#643 carried in and closed), #646 (S205 step 1).

**Open pull requests**
- Merged 23 Nov: #650 (S193 C), #651 (S216), #652 (S217), #653 (since-start market from the fill), #654 (S213), #655 (S218). **S193 B** PR #656 (bugs B1-B9, the Guide, history from daily closes, wording per system; owner approved 23 Nov): merge when CI is green.
- **#638 (S211, one date rule):** draft. Owner, 24 Nov: option 1: after the 1 Dec fill, rebuild on main without its 52-week-high part, re-measure, one yes on the new figures, merge that day. Merge only after the 1 Dec fill **and the owner's explicit yes** (659 of 750
  published ranks move). It conflicts with main again: merge main into it once, just before merging. Reminder
  `trig_01MGhPjDNkLj9QptrreSjzZh` fires 1 Dec 13:30 UTC.
- **#607** is parked by the owner (read-only R2 key).

**S189 confirmed (owner, 24 Nov):** see the confirmation round above.

**Confirmed by the owner (24 Nov, "With your recommendation 1"):** the Dashboard flows readout keeps "heavy buying" / "moderate buying" / "net selling" (S222).

**Waiting on the owner (24 Nov, laptop back):**
- (a) **Done 27 Nov** (owner: "Yes"): `owner_cleanup.yml` run 45956749746, 28 branches deleted (15 kept as `archive/*` tags), 14 heads left. Was: run the branch clean-up in TODO S212: tags for group C, then delete the merged branches. This session could
  not: proxy 403 on tags, branch deletes refused.
- (b) Send the Streamlit log after tonight's nightly run, the first past #636/#644. S210 is done when it reads
  "Precomputed ranking accepted" for all three systems: open each system once after boot. Once the S213 PR is
  deployed, the same log should no longer say "Replacing with pyarrow<25".
- (c) Optional: set the Dependabot secrets (TODO S209). Until then every Dependabot PR fails validate at the R2 step.

**S205 done** (owner, 23 Nov: target 7 min; 6 min 33 s and 6 min 10 s).

**S208 merged** (#648, 8da8793): bench memory equal to main (490 MB warm). Found: Portfolio hashes 17 times per warm rerun.

**Benches:** run `audit_page_bench.py` in a worktree nobody commits to. A commit in the served checkout makes the app
log "New revision pulled ... caches dropped" and the run reads seconds slower (seen 23 Nov).

**S193 item A:** A10, A12, A13, A14 merged (#649). Item C merged (#650). Since-start market: owner chose "2: from the fill" (23 Nov); done. A5 needs a `record_run` on the R2 store first (A11 answered 25 Nov)
(a CI job with R2 secrets). Then items B, C, E-L, one at a time with the owner.

**S213 done** (23 Nov; `docs/archive/S213_PRICE_TRACE_2026-11-23.md`): CCAVENUE fixed by rule with a nightly check. **S218** (owner: "from now on"): a new listing's first sessions chained from NSE; PR open, merge when CI is green. S207 closed 23 Nov (measured: leave both).

**Scheduled tasks** (moved to session_016X4g5Y1bsnhgFzzKddp8Wc on 23 Nov; the old copies are disabled, not deleted):
work loops `trig_01KG5jvzmWy7SdBisDHRCQAK` (:07) and `trig_01T3tgnXxsesBznuVJpMLaZD` (:37); S211 #638 1 Dec 13:30 UTC
`trig_01RRuhPGXZ3Xo6XQ23KqhE78` (asks the owner before merging); dated checks 24 Nov watch `trig_01YMp7cDMoQ7p18hkkUPxMxQ`,
27 Nov S142 `trig_01BMkMc7CRLhjqo2BHmFDXCG`, 29 Nov backtest_reference + r2_retention `trig_01PWh1QomzgnMSfsLn2Yh7Es`,
2 Dec shadow freeze `trig_01JH4bPnsALWMcP1LA6GuDBz`, S175 `trig_01T13UvPhM7bXnjivKoNudi6`, S95/S111/S154
`trig_01NJgbbcXR4NpaYQ3pttbQFk`, 5 Dec S185 `trig_01Ui6ohXqWkJFQgYrdEGXwS8`, 2 Jan shadow first month
`trig_01VkbjLtSj5n5MJknR5MUaiC`. A new session re-creates them (update_trigger cannot re-point a task) and disables these.

**Local state:** the checkout is on `claude/handover-session-setup-7bd5zk`; scratch worktrees in the scratchpad.

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

_Refreshed 26 Nov 2026. Items 0-3 of 23-24 Nov are merged (S188, S193 A-L, S203); S193 A5 and L's live cold start are still open (see 0b)._

0. **Site audit, 28 Nov (S235, S236; `docs/SITE_AUDIT_2026-11-28.md`)**: 19 stocks' figures agree with Screener and BSE; no live fault; 22 findings, 12 fixed in the S236 PR. Open: F8, F9-F10 (glossary, by benchmark), F13, F15-F18, F20-F21; F19 (export format) is the owner's. Then **S237** (pages against tipsheet.markets, copying allowed, CLAUDE.md) once the S236 PR merges.
   Owner's Streamlit log after 2 Dec (S232).
   - **Owner's Streamlit log, 28 Nov (23-28 Nov)**: S152 (d) done (the missing-cap line only for HEGRAPHITE on its listing day, gone after the 27 Nov nightly). S232: 4 import tracebacks on 26 Nov 10:38 UTC, after the fix; cause (the lock was rebuilt on every re-import of code_reload) fixed 28 Nov. Next: ask for one more log after three pulls of that fix.
0b. **Promises audit, 26 Nov** (my replies and reasoning since 23 Nov checked against the docs): the S189 sector check of INA, SUDEEPPHRM, BUILDPRO, CMPDI (blocked here: NSE's quote page answered 503 and BSE 403 to this session, and an NSE API read with session cookies was refused by the permission check; owner, 26 Nov: "One-off GitHub job": run 45895841820 got HTTP 403 from NSE for all four; 27 Nov BSE's scrip list from GitHub also 403 (run 45950146411); the job removed on the owner's yes; the four read Unclassified where the sources disagree until NSE's next list or Screener's re-read agrees); the dead `stPills` CSS (done, below); then in CI with R2 keys after the freeze: S129's before/after backtest and S193 A5. Not measurable while `keep_awake` runs: S193 L's live cold start. Tracked under S233: Portfolio's 17 fingerprints.
0a. **S198 (c) prices from ₹800 Cr: by 15 Dec, with S198 (e)** (checked 26 Nov: no history is lost before then and the December measurement prices the band from NSE's own files; the January switch is the only reader). Its own store, not the one the app loads. See TODO S198.
1. **Dated checks** (each has a scheduled reminder): S142 closed 27 Nov (6,953 min/week; owner: "Public"); 28 Nov the earnings run; 29 Nov `backtest_reference` and `r2_retention` (S188 (c)); 26 Nov-3 Dec a week of green `app_pack` runs, then S172 step 2 job by job; ~1 Dec page budgets reset by rule (S193); 1 Dec budgets and #638 (owner's yes on the figures); 2 Dec freeze checks, `momentum_health` (S177 (c)), S116 (c); 5 Dec S185 replay; 13 Dec S116 (d); 15 Dec S137; Jan S227 rename, S188 (h); 2 Feb S220.
2. **S233 after S172 step 2**: re-measure Production QA; then decide the shared price load and the record's basis frame (TODO S233).
3. **S231**: owner confirmed 27 Nov ("A"). Left: NSE's Q2 FY27 earnings PDF (daily retry), to note NSE's own cut.
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

- **27 Nov, local CI writes `data/`**: `/tmp/claude-0/s203/ci.sh` (its live smoke) refreshes NSE's index lists into `data/indices/` and `indices_sync_meta.json`; a branch behind main then fails `test_the_latest_membership_is_nses_list_name_for_name` on the newest NSE list (27 Nov: HEGRAPHITE, recorded by that night's sync 2b459c4). Restore `data/` with `git checkout -- data/` and merge main before committing. HEGRAPHITE is HEG's demerged business (NSE's DUMMYHEG slot, as ENNATURE was India Glycols'); the 7 Sep demerger day uses NSE's 0% (`PRICE_PIPELINE.md`), and it is ranked once it has 63 sessions.

- **26 Nov, dead pill CSS: resolved** (owner, 26 Nov: "No pill required"): the 7 `stPills` rules and the 3 `stSegmentedControl` rules (both ids gone since Streamlit 1.65) removed from `page.css`, so pills keep Streamlit's look as today; `tests/test_css_test_ids_exist.py` fails on any test id the installed Streamlit no longer emits.
- 25 Nov: Configuration at 1400 px shows three 56 px "empty bands" in the layout audit: they are its section breaks (space, a rule drawn as a border, the next numbered section; screenshot checked), which the audit does not count as drawn. Intended, not fixed; the page is not in CI's layout list. Its missing foot line was fixed in #694.

- **Layout audit, Dashboard at 412 px, 25 Nov:** "segbar frame taller than its drawing 39 px spare" failed #692's validate (run 45621877248, attempt 1) on a docs-only change; the same code passed on #689, #691 and locally, and the one re-run passed. Lead: the frame keeps its fallback-font height past the audit's second reading. If it recurs, wait for `document.fonts.ready` inside the frame before measuring.

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

## Owner decisions of 22 Nov (S174 "1 a")

Recorded 25 Nov in `DASHBOARD_REQUIREMENTS.md` "Data pass decisions" D1-D3. All three are built: D3 the backup-copy foot line, D2
the ledger's nightly R2 copy checked against git, D1 each Backtest test from Mar 2012. Check after the
merge: the first `daily_sync` logs "R2 copy matches git" three times.

## Dates to watch

**Schedule (set 25 Nov ~21:00 UTC, owner: "plan your schedule and work on pending items"; stop at the first usage warning).** Four work loops (:05 :20 :35 :50) carry the work; each dated check below is its own scheduled task, so a stopped session loses none: 26 Nov 06:11 UTC data checks (B10, ATH, S188, S186); 26 Nov on, daily 06:11 UTC, S231 retry of NSE's review PDF (until 15 Dec); 27 Nov 04:53 Actions minutes (S142); 28 Nov 05:31 first weekly earnings run (S171); 29 Nov 05:50 backtest_reference and r2_retention; 1 Dec 05:43 page budgets (S193 L); 1 Dec 13:30 #638 (owner's yes); 2 Dec 03:43, 04:41, 09:30, 12:30 the monthly freeze checks (shadow books, S178/S188 g, S175, S95/S111/S154); 5 Dec S185 bundles; 15 Dec S137 holidays; 2 Jan shadow books; 4 Jan the January items (S227 rename, S226/S198 (e) sector switch, the Tata Q3 check); 2 Feb S220. Work order between them: the open batch PR and its live checks (S173); then S190 (Sectors' finer NSE indices), then S174 "1 a" (Dashboard data pass), each decided by benchmark, owner to confirm; owner questions one at a time (S212 follow-up first).

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
queue in order, starting with item 0.
```
