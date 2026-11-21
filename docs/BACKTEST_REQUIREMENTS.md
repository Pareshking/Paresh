# Backtest requirements

**Status: approved and built, 21 Nov 2026.** The owner approved mock-up v1 and decided items
A-G as recommended (section "Owner's decisions" below). Built on the branch of S174: 32 of 32
rows and the section order met on the running app (`check_dashboard_requirements.mjs`), layout
audit clean at 412, 1024 and 1400 px with the expanders open; the page joins CI's step.

**Built, what differs from the mock-up and why:**
- The page's own industry map (today's list, then TradingView, then
  `data/reference/historical_industries.csv`, each leaver its own group) is the one the page always
  used; the mock-up's figures used the record's map, which leaves leavers in a shared "Other" the
  cap squeezes. On the page's map the default run makes **18.75%** a year (mock-up 18.56%), ₹100
  became ₹1,801 (₹1,751), the lead is 8.7 pts (8.5). The weekly reference
  (`scripts/build_backtest_reference.py`) uses the same map (`backtest_page.industry_map`), so
  "As tested" in section 4 is the page's own run.
- After tax on the long file of 16 Nov: the rule 15.23% a year, the Nifty 500 9.35% (mock-up, 7 Nov
  file and record map: 15.14%); tax costs the lead 2.8 pts (2.7). Replay before tax 18.75%, equal to
  the backtest's (gap 0.00 pts).
- The month in progress is a sentence under the year table (to the long file's last session), not a
  partial row.
- The lead column of the year rows is in pts without the unit in each cell ("Lead, pts"), so it fits
  at 412 px.
- Section 6 adds the profit factor weighted by each trade's size ("Gains over losses", audit A8).
- The rebalance log keeps Portfolio's words Buy / Sell / Hold (one word across pages); the engine's
  reasons read "Rank 12, new" and "Rank 31, kept".

Started 21 Nov 2026 for S174 (the next page makeovers), from:
- the page as it stands (`src/ui/views/backtest_view.py`, `src/engine/backtester.py`);
- the owner's decisions of 21 Nov: one market benchmark, Nifty Total Market, except where
  long history needs the Nifty 500, which the Backtest keeps, named with its reason (S165);
  one name and one unit per idea (S173); every dataset a page reads listed by where it lives
  (S172); price or total return said on every figure;
- the rules of `docs/PAGE_DESIGN.md` and `docs/DATA_CORRECTNESS.md`;
- a real run of the page's default settings, below.

Mock-up: `docs/mockups/backtest_v1.html` (static, real figures). Checked with:

    node scripts/check_dashboard_requirements.mjs docs/mockups/backtest_v1.html docs/BACKTEST_REQUIREMENTS.md

Each row's **Marker** is text that must appear on the rendered page (`+` joins texts that
must all appear, `|` separates alternatives). A row is changed or dropped only with the
owner's word. The `Order:` line is a proposal until the owner approves it.

## Where the figures come from

    PYTHONPATH=. python scripts/research/backtest_mockup_numbers.py \
        --long data_cache/nse_long_close.parquet --out bt.json

The NSE long file built to **16 Nov 2026** (1,429 symbols, all priced), `data/benchmarks.csv`
(Nifty 500 to 20 Nov), `data/nse_indices_history.parquet` (S168 store: Total Market, Nifty200
Momentum 30, the Nifty 500's dividend yield), `data/membership_history.json`. The run is the
page's History default: Nifty 500 point in time, Jan 2010 to Oct 2026, 20 holdings, keep in
the top 40, 50D EMA, within 20% of the 52W high, Sharpe score, weights .10/.30/.30/.20/.10,
5% stock and 40% industry caps, 30 bps a round trip, the six-monthly reset applied from 2010
(as the page does). Industry labels from `model_record.record_sector_map` (the record's; the
page builds its own map, which can differ for a few former members). The mock-up's HTML is
formatted from that JSON; the after-tax rows are copied from the 11 Nov audit (S124,
`scripts/research/cost_and_index_tax.py`, long file of 7 Nov), not re-run.

Reproducibility check: the run's calendar-time figure, **18.56% a year** over 4 Jan 2010 to
30 Oct 2026, equals the 11 Nov audit's 18.56% for the same rules on the 7 Nov file. That
confirms the set-up, not the result: both are our own engine.

## What a reader comes with

The owner runs a monthly momentum book. He opens this page to ask:

1. Over a long, honest history, has this rule beaten the market, after costs, and by how
   much **a year**?
2. How bad does it get: how far below a peak, for how long, and where is it now?
3. How steady is the lead: by year, by month, in both halves of the history?
4. What does the result depend on: costs, tax, the rebalance rule, the universe, and is it
   better than an NSE momentum index he could buy?
5. Can the figure be trusted: survivorship, look-ahead, stale prices, settings chosen after
   looking, and what was not checked?
6. What if I change a rule (and give me every trade)?

## The page

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 1 | Kicker "Backtest"; a title answering question 1 with the two figures a year, the benchmark named and "before tax" | PAGE_DESIGN §2a; S173 | Top | Backtest + a year to the Nifty 500 |
| 2 | One lede: what was replayed (the record's rules, the index as it stood each month), the window, the price source, the cost, and that both sides are **price returns** | Owner 21 Nov (price vs total return) | Top | Price returns on both sides |
| 3 | A visible "What was tested" line listing every setting of the run shown, in words (no "ATH", "D EMA" abbreviations without the word) | Current `bt-sum` line, kept and reworded | Top | What was tested |
| 4 | The settings form stays (nothing runs until Apply), folded under "Change the test"; universe, months, holdings, keep rank, EMA, 52-week high, all-time high, rebalance rule, costs, score, weights, traded-value floor, weighting | Owner 9 Oct 2026 (form) | Top | Change the test |
| 5 | Beside any run whose settings differ from the record's, one line: a setting chosen after seeing its result on this same history flatters the result. The in-sample "Recommendation: 30 holdings…" caption is removed (decision F) | Audit A10 | Top | flatters the result |
| 6 | **Section 1.** Four tiles: a year, compounded (with the Nifty 500 beside); lead over the Nifty 500 in **pts a year**; what ₹100 became (both); months ahead of the Nifty 500 out of all months, and months up | PAGE_DESIGN §2a; S173 | §1 | A year, compounded + Lead over the Nifty 500 |
| 7 | The lead is a difference of the two yearly figures, in pts a year. The cumulative "Ahead of the index +1,249 pts" is removed | Audit A3 | §1 | points a year |
| 8 | A two-pane chart, one crosshair: growth of ₹100 on a **log scale** (both lines) and below its peak (both); values under the pointer in a readout above the chart, latest values at rest, arrow keys, `touch-action: pan-y` | PAGE_DESIGN §4.1, §4.3 | §1 | Growth of ₹100 + Below its peak + arrow keys |
| 9 | "A year" is compounded over **calendar time** (365.25-day years), not 252 sessions; the page and the Guide quote the same figure (decision D) | Audit A2 | §1 note | calendar time |
| 10 | The dividend gap stated: the rule keeps only dividends of 10% or more, the Nifty 500 is a price index; NSE's file puts the index's yield at 1.25% a year on average since Feb 2012 against about 0.5% for the book (S125), so against the index with dividends the lead is about 0.8 pts a year smaller (decision E) | Owner 21 Nov; S125; S168 store | §1 note | dividend yield |
| 11 | Why the Nifty 500 and not Nifty Total Market, in one sentence (Total Market starts 14 Oct 2021); Total Market beside it wherever its history allows (decision A) | S165, owner 21 Nov | §1 note | Why the Nifty 500 and not Nifty Total Market |
| 12 | The lead in each half of the history, and the median month | PAGE_DESIGN §5.6 (both halves) | §1 note | The two halves |
| 13 | "Show the table" under the chart: total return, a year, before costs, volatility, Sharpe with its ± (over the 6.5% risk-free rate, named), Sortino, turnover one way a month | Current tiles, moved | §1 | Show the table |
| 14 | **Section 2.** Tiles: below its peak now (with the Nifty 500), largest fall from a peak, days below its peak, recovered or "not yet" with the rise needed | PAGE_DESIGN §6a terms; S173 | §2 | Below its peak now + Largest fall from a peak + Days below its peak |
| 15 | A table of the three largest falls of the rule and the two largest of the Nifty 500: fall, peak date, low date, back at the peak, days below. Every figure from `metrics.drawdown` on daily closes | `src/engine/metrics.py`; PAGE_DESIGN §6a | §2 | Back at the peak |
| 16 | **Section 3.** One row per calendar year: the rule, the Nifty 500, Nifty Total Market (from 2022), and the lead over the Nifty 500 as a two-colour line bar (2.5 pts a line, dark zero line, negatives leftward) with the exact figure after it. A part year names its months | PAGE_DESIGN §4.2; S165 | §3 | Lead over the Nifty 500 + Total Market + Jan–Oct |
| 17 | The line-bar key says its step | PAGE_DESIGN §4.2 | §3 | Each line is 2.5 pts |
| 18 | The month-by-month grid (Portfolio's layout) under "Show the table", lead in pts | Current calendar grid, folded | §3 | Month by month |
| 19 | **Section 4.** The same window re-run with: the monthly reset, 60 and 100 bps a round trip; the Nifty 500 itself; as line bars on one 0–20% scale (0.5% a line), the Nifty 500 marked | Owner's question 4; S123 | §4 | Costs 60 bps + Monthly reset |
| 20 | After-tax estimates for the default run only, dated and sourced (S124: the rule 15.1%, the Nifty 500 held and sold at the end 9.4%), never for a custom run (decision C) | S111, S124 | §4 | After tax |
| 21 | Against what the owner could buy: since NSE's Nifty200 Momentum 30 went live (31 Aug 2020), the rule, that index and the Nifty 500, a year and largest fall; since Total Market went live (29 Oct 2021), the rule on the Nifty 500 and on Total Market against Total Market and the Nifty 500 | S168 store; owner's question 4 | §4 | Nifty200 Momentum 30 + This rule, Nifty Total Market |
| 22 | **Section 5.** A checklist with a status per line (Checked / Soft spot / Not checked): survivorship (rebalances on the index as it stood, of all), look-ahead (signal close, next-close fill, list effective dates), stocks that stopped trading (sales on a price five or more sessions old, counted), cash months, costs, tax, rules chosen after looking, industry labels, the benchmark before Feb 2012, a second source | PAGE_DESIGN §5, §5.8; DATA_CORRECTNESS §1 | §5 | Survivorship + Look-ahead + Not checked |
| 23 | The rules-chosen-after-looking line names the 12 Oct sweep and the shadow records that test it forward | Audit A10 | §5 | Rules chosen after looking |
| 24 | Cash held because too few stocks passed the rules is said as that (April 2020: 10 names, half the book in cash), not as "the caps left cash" | Audit A6 | §5 | April 2020 |
| 25 | **Section 6.** Tiles: trades closed (and still held), share won, median holding in days, median trade | Current "Every trade" tiles, reworded | §6 | Trades closed + Median trade |
| 26 | One download: the rules and every trade, a ZIP of two CSV files (as now); every trade and the rebalance log under "Show the table", filters kept | Owner 8 Oct 2026 | §6 | Download the rules and every trade |
| 27 | No "Live system" tab: the live record is Portfolio's, linked (decision B) | Owner decision 5, 7 Nov; audit A12 | §6 / removed | Portfolio |
| 28 | The month in progress, when shown, is dated to the long file's last session and kept out of every whole-month figure (S126 rule kept) | S126; PAGE_DESIGN §5.3 | §3, foot | prices to |
| 29 | Footer: data to the last completed month, prices to the long file's last session, indices to their last session; no source named; the Screener's data-quality footer is not shown on this page | PAGE_DESIGN §2; audit A14 | Foot | Data to |
| 30 | One name per idea on the whole page, as listed under "Naming"; a test fails on a banned synonym in `backtest_view.py` | S173 | Whole page | Largest fall from a peak |
| 31 | Headings in the serif, each a sentence stating the finding; notes 13.5 px, about 80 characters a line; tables sentence case, Plex Mono right-aligned figures, row labels never wrap to three lines; minus is U+2212 | PAGE_DESIGN §2a, §3, §8 | Sections | Ahead of the market |
| 32 | Layout audit clean at 412 and 1400 px; the page joins CI's layout and requirements step | PAGE_DESIGN §8 | Whole page | Backtest |

Order: Backtest → What was tested → 1 · Ahead of the market → 2 · Falls from a peak → 3 · Year by year → 4 · What the result depends on → 5 · Can it be trusted → 6 · Trades → Data to

## Naming (S173): every change on this page

One idea, one label, one unit. Units: % for a return or a share, **pts** for a difference of
two returns, "a year" for anything compounded to a year.

| Now (file:line) | Proposed | Why |
|---|---|---|
| "Strategy", "Strategy return", "Strategy Net" (`backtest_view.py:690`, `:717`, `:835`; `components.py:160`) | "This rule" | One name; "net" is said once, in the lede ("after 30 bps") |
| "Annualised" (`:694`); "CAGR" in the Method text and the export | "A year, compounded" | One term for a compounded yearly rate |
| "Ahead of the index" (`:698`), "Alpha" (`:722`, `components.py:161`), "Alpha vs Benchmark" (`:837`) | "Lead over the Nifty 500", in pts (a year where compounded) | Three names for one idea; "Alpha" is a regression term the page does not compute |
| "Benchmark" (`:836`), "the index" (`:698`, `:708`) | The index's name: "Nifty 500", "Nifty Total Market" | Say which index |
| "Max drawdown", "peak to trough" (`:705-706`, Method `:1024`) | "Largest fall from a peak" | PAGE_DESIGN §6a, as Portfolio |
| (none; engine's `max_drawdown_duration_days` unused) | "Days below its peak" | Shown, named |
| "Months ahead of index" with "x% up" (`:708-709`) | "Months ahead of the Nifty 500" and "up in n" | Two counts each named |
| "Cost Drag %" (`:839`), "Transaction Cost Drag" (`:1018`) | "Costs" | Plain word |
| "Turnover %" (`:838`), "turnover" in a tile | "Turnover, one way, a month" | Says the basis |
| "Rebalance periods", "Period Start/End" (`:794`, `:833`) | Removed (fill-to-fill periods beside calendar months gave two sets of monthly figures) | Audit A9 |
| "Every trade", "Closed trades", "Return %", "Holding (Days)", "Reason for Exit" | "Trades", "Trades closed", "Return", "Days held", "Why sold" | Sentence case, no units in labels where the cell carries them |
| "🟢 BUY (Entry)", "🔴 SELL (Exit)", "⚪ HOLD (Retained)", "New Momentum Leader", "Buffer Zone Retention" (`backtester.py` trade records) | "Buy", "Sell", "Keep"; "Rank n, new", "Rank n, kept (within the top 40)" | No emoji or colour-only meaning; plain words |
| "Live system" / "History from 2010" tabs (`:110-111`) | One page; the universe and months are settings | Decision B |
| "Personal closes" (`:467`, `:475`) | Removed with the Live tab; "NSE's closes" | Internal name |
| "52W high", "ATH", "50D EMA" in the Tested line (`:607-618`) | "52-week high", "all-time high", "50-day EMA" | Words, not codes, in sentences; codes stay in narrow table headers |
| "Zero Look-Ahead Execution", "Rank Persistence Buffer" (`:1012`, `:1019`) | "When it buys", "Kept while in the top 40" | Plain sentences, no title case, no LaTeX |
| "Equal Weight", "Inverse Volatility" (`:295`) | "Equal weight", "Inverse volatility" | Sentence case |
| "Sharpe … over 6.5%" sub-line | "Sharpe, over 6.5%" in the table, ± named "one standard error" | Moved to the table |

## Datasets the page reads (S172)

| Dataset | Read by | Where it lives today |
|---|---|---|
| NSE long file: `nse_long_close.parquet`, `nse_long_value.parquet` (floor only), `nse_long_report.json` | `src/loaders/nse_long.py` | **R2** `prices/nse_long_*` first, the `data-latest` release second; cached a day |
| Index membership, every index, point in time | `src/engine/membership.py`, `index_universe.py` | **Committed** `data/membership_history.json` |
| Nifty 500 and Nifty 50 daily closes (the benchmark) | `src/loaders/benchmark_store.py` | **Committed** `data/benchmarks.csv` (Kaggle to 2015, SS, NSE from Sep 2024; checked against NSE's archive from Feb 2012, S168) |
| Proposed: Total Market, Nifty200 Momentum 30, the Nifty 500's dividend yield | `src/engine/indices_page.py` store | **Committed** `data/nse_indices_history.parquet` + `data/nse_indices_recent.csv` (nightly) |
| Industry labels for the cap: today's index file, TradingView, historical | `former_members.industry_for`, `_historical_industries` | **Committed** `data/indices/ind_niftytotalmarket_list.csv`, `data/nse_tv_classification.csv`, `data/reference/historical_industries.csv` |
| The ranking table (`rank_df`: industries and the footer) | `app_source` | **R2** first, release second |
| Live tab only (proposed to go): Screener price store; NSE middle source; former members' prices; corporate-action log | `app_source`, `nse_prices.basis_frame`, `former_members`, `corporate_actions.load_events` | Screener store **R2**/release; **committed** `data/nse_prices/closes.parquet`, `actions.parquet`, `notes.json`, `data/former_member_prices.parquet`, `data/corporate_actions_log.json` |
| Track-record rules (`TRACK_RECORD_CONFIG`) | `src/engine/track_record.py` | Code |

With the Live tab gone, the page reads one R2 dataset (the long file) and five committed
files. Moving those to R2 is S172's work, not this page's.

## Audit of the current page

Wrong (a figure or statement that is false or mislabelled):

- **A1. Two benchmarks, one label, in the Live tab.** The Live tab ranks the Nifty Total
  Market 750 and measures it against the Nifty 500 (`backtest_view.py:484`); the export says
  "Nifty Total Market (the live 750 system)" with benchmark "Nifty 500" (`:762`). S165 wants
  Total Market for the live record.
- **A2. "Annualised" is raised by a 252-session year.** `backtester.py:757-758` divides by
  252; NSE averaged about 248 sessions a year over 2010-26 (4,174 accrual sessions in 16.82
  calendar years). The page shows 18.87% for the default run; the Guide quotes 18.6% for the
  same run (`guide_view.py:203`), from calendar time. Benchmark 10.22% vs 10.06%.
- **A3. "Ahead of the index" over 16 years is +1,249.5 pts** (`:698`, `stats['alpha']` =
  total minus total, `backtester.py:895`): a difference of two compounded totals, which grows
  with the window and means nothing to a reader. The lead a year is 8.5 pts.
- **A4. The rebalance is described two ways.** "monthly, first trading day" (`:598`) and "at
  each calendar month's last session" (`:293`). Both are half right: the signal is the last
  close, the purchase is the next close (`backtester.py:1261`).
- **A5. The long file's docstring says "no dividends, no rights issues"** (`nse_long.py:6-8`);
  the page caption (`:452`) and DATA_CORRECTNESS §2a say both are in. The caption is right.
- **A6. The cash note blames the caps.** "The caps left up to 50.0% of the book in cash … loosen
  the stock cap" (`:626-631`) fires on the default History run; the cause is April 2020, when
  only 10 stocks passed the rules. No cap setting changes that.
- **A7. `_tone` is decorated `@st.fragment`** (`:103`). Each call (six per page) opens a
  fragment container; the function only returns a CSS class. Not measured on the running app:
  whether it adds empty blocks to the layout.
- **A8. Profit factor is a sum of unweighted trade returns** (`:880-884`), with 0.001 put in
  for "no losses", so a run with no losing trade shows a factor in the thousands; trades of
  5% and 15% weight count alike.

Misleading or overstated:

- **A9. Two monthly series.** The "Rebalance periods" table runs fill to fill (first session
  to first session) beside the calendar grid; "Months ahead of index" (`:708`) counts the
  fill-to-fill periods (59.4%), the calendar count is 60.4% (122 of 202).
- **A10. An in-sample "Recommendation"** (`:261-262`): 30 holdings, top 90, 200D EMA came from
  a sweep of this same history (12 Oct 2026). Shown as advice, with no out-of-sample month; it
  is now the shadow record (from Nov 2026).
- **A11. "Zero Look-Ahead Execution"** (`:1012`) is true of the fill and overclaims the run:
  industry labels are today's (`:205-214`), the default rules were settled while this history
  was on screen, and settings changed on the page are tested on the data that suggested them.
- **A12. Price vs total return is said only for the rule** ("no dividends", `:469`, `:475`),
  never for the benchmark, and the dividend gap (about 0.8 pts a year in the index's favour)
  is not on the page. Taxes appear nowhere: after tax the 8.5-pt lead is 5.8 (S124).
- **A13. Costs.** 30 bps is "about 25-35 bps standard" (`:307-308`), unsourced; S123 measured
  ~22 statutory and ~8 left for the spread, never measured; the final book's sale is never
  charged (`backtester.py:484`). At 60 bps the rule makes 17.0% a year, at 100 bps 14.9%.
- **A14. The footer reports the Screener's 750** (gaps, short histories; `:1028-1032`) under a
  run on another file and, on History, another universe.
- **A15. The default rule is not the record's history.** The page applies the six-monthly
  reset from 2010 (`rebalance_rule_kwargs`, `:39-45`, `hold_cap_from=None`); the record and
  `momentum_health.csv` use the monthly reset to Oct 2026. `portfolio_history.py:5-7` and
  DATA_CORRECTNESS §5 (line 157, "19.3% a year … the same run as Backtest's History") are no
  longer the same run: 18.6% vs 18.8% (monthly) on today's file.

Duplicated elsewhere:

- **A16. The Live tab** replays the live system's recent months on a different price basis
  from Portfolio's frozen record (October −4.0% here, −4.25% recorded; S89, S126). Owner
  decision 5 (7 Nov): Backtest is research runs only.
- **A17. The calendar grid** is Portfolio's component (`components.py:132`, `:184`); on the
  Live tab it shows the same months as Portfolio with other numbers.

Unverifiable as shown:

- **A18. The Nifty 500 before Feb 2012** (`data/benchmarks.csv`, Kaggle) has not been
  checked against NSE's own files (S167 (3)); 2010 and 2011 lead figures rest on it.
- **A19. No second source for the result.** The engine is ours; the after-tax and cost tests
  are the same engine. Prices pass the long file's audits.
- **A20. The segmented view hides the trades and the Method** (`:794-801`) behind a switch that
  reruns the page (PAGE_DESIGN §6 trap; "everything visible").

Checked and fine (so they are not re-investigated):

- Survivorship: 202 of 202 rebalances on the Nifty 500 as it stood; leavers priced (1,429
  symbols, none unpriced in the 16 Nov build).
- Look-ahead in the fill: signal at T's close, bought at T+1's close, first accrual T+2
  (`backtester.py:1248-1261`); index lists from their effective date (NSE announces about four
  weeks ahead, `index_universe.py:46-50`).
- Stopped stocks: 7 sales on a price 7-19 sessions old, all 2010-12 takeovers or delistings
  (MICRO, HINVDIR, NIRMA, UTVSOF, ALFALAVAL, PATNI, CHEMPLAST).
- Drawdown: the engine uses `metrics.drawdown` (`backtester.py`, `_calculate_backtest_metrics`).

## Owner's decisions (21 Nov 2026, one item at a time)

Each item was put to the owner with a recommendation, an example and the counter-argument; all seven as recommended:

| Item | Question | Decision |
|---|---|---|
| Item 1 (A) | Benchmark | **Nifty 500 the headline** (S165: long history), plus each chosen universe's own NSE index, named "for this universe"; Total Market beside it from 2022 |
| Item 2 (B) | "Live system" tab | **Removed**; Portfolio owns the record |
| Item 3 (C) | After tax | **Shown for the default run only**, labelled an estimate for an investor with no other gains, dated, refreshed weekly; S124's rows re-run on the current file before the build ships |
| Item 4 (D) | "A year" | **Calendar time**, in the engine; every figure that moves listed in the CHANGELOG |
| Item 5 (E) | Dividends | **Price returns on both sides**, the dividend gap stated (about 0.8 pts a year; the book's yield measured 2020-25 only, said "about") |
| Item 6 (F) | "Recommendation" caption | **Removed**; the shadow record named instead |
| Item 7 (G) | Default rule | **Six-monthly reset**, named; the two places calling it the `momentum_health.csv` run corrected. Moving the signal tests to the new rule is not part of this |

## Decisions for the owner (as proposed)

- **A. Benchmark for a universe other than the Nifty 500.** Recommended: the Nifty 500 stays
  the headline benchmark (your 21 Nov decision for long history), with Nifty Total Market
  beside it from 2022, and when a size universe is chosen (Midcap 150, Smallcap 250,
  Microcap 250, Total Market) that index from NSE's store is shown beside it too, so a small-cap
  run is not credited with the small-cap premium. *Strongest counter:* two or three benchmarks
  on one page is what S165 set out to stop; one benchmark everywhere is simpler to read.
- **B. Remove the "Live system" tab.** Recommended: yes. Portfolio owns the live record; the
  tab replays it with other numbers (A16). A Total Market universe from Nov 2021 stays one
  setting away. *Strongest counter:* the long file is weekly (16 Nov on 21 Nov), so this page
  can no longer show a what-if on the live price basis up to yesterday; a reader testing a
  rule change for this month loses that.
- **C. After tax.** Recommended: show the default run's after-tax figures, dated, refreshed
  with each weekly long-file build by `cost_and_index_tax.py`; none for custom runs.
  *Strongest counter:* a figure that does not follow the settings invites misreading, and tax
  depends on the investor (rate, losses carried, holding period); the Guide already says it.
- **D. "A year" over calendar time.** Recommended: compound over calendar days in the engine
  (`ann_return`, `ann_bench`), so this page, the Guide and the research scripts agree.
  *Strongest counter:* it moves a published figure (18.9% to 18.6%) and any test or script that
  reads `ann_return`; a 252-day year is a common convention.
- **E. Price returns both sides, gap stated.** Recommended: keep both on price, print "price
  returns" with every figure, state the 0.8-pt dividend gap. *Strongest counter:* a
  total-return Nifty 500 built from NSE's daily yield would put the gap in the numbers; it was
  rejected for Indices (decision A) as our own construction, and the same applies here.
- **F. The in-sample "Recommendation" caption.** Recommended: remove it; section 5 names the
  shadow record that tests it forward. *Strongest counter:* a reader looking for better
  settings loses a pointer to the one sweep that was done.
- **G. The default rebalance rule from 2010.** Recommended: keep the six-monthly reset as the
  default (the rule the book follows from now), named, and correct the two places that call
  this the same run as `momentum_health.csv` (A15). *Strongest counter:* the Dashboard's
  signal tests read the monthly-reset run; two "since 2010" figures (18.6% and 18.8%) will
  then exist, and a reader comparing pages will find them.

## Not checked

- The page itself in a browser (the mock-up is static; the app was not run).
- The Live tab's figures (it needs the app's Screener store and R2 keys).
- The after-tax rows on the 16 Nov file (copied from the 7 Nov run).
- Total Market and Nifty200 Momentum 30 closes against a second source (niftyindices.com
  refuses this machine, S168); the momentum index is a price index too.
- The book's dividend yield outside 2020-25 (S125).
- How much the page's industry map differs from the record's for former members.
- Whether `@st.fragment` on `_tone` changes the layout (A7).
