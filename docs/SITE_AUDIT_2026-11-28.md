# Site audit, 28 Nov 2026 (S235)

Owner, 28 Nov 2026: "Let's do full website audit again and prepare to do list"; "Do it as you like".

Scope: a delta audit, not every element again. The 24 Nov audit (`docs/DATA_AUDIT_2026-11-24.md`, 13 pages,
184 elements) is the baseline; this one reads (1) what changed since, and the 24 Nov gaps, on the live site;
(2) what was never checked: live figures against sources outside our pipeline, every page's controls,
phone width and load times; (3) one ranked list. Live site read 28 Nov 2026, 09:55-11:00 UTC, showing the
27 Nov close. Code at `be41fc4`.

## 1. Live figures against outside sources (never checked before)

19 stock pages read live (`/screener?stock=X`, and `&sys=nano` for the six outside the 750): large caps
(RELIANCE, HDFCBANK, TCS, ICICIBANK); a split, bonus, demerger or rights issue in the last 12 months
(GOLDIAM, POCL, KIRLPNU, TDPOWERSYS, GOODLUCK, PGIL, TRIVENI, INDIAGLYCO, HEGAM, NATCOPHARM, BLSE, JLHL);
a new listing (VAML); > ₹2,000 Cr stocks (KIOCL, HAPPYFORGE). Set against:

- **BSE's bhavcopy of 27 Nov** (`BhavCopy_BSE_CM_0_0_0_20261127`): `ClsPric` and `SttlmPric`.
- **Screener.in**, read 28 Nov 09:56 UTC: its daily price chart (`/api/company/<id>/chart/?q=Price&days=400`)
  and the company page's Market Cap. Screener adjusts its history for corporate actions on its own, so the
  windows over a split or bonus are an independent check of our factors.

| Figure | Agree | Note |
|---|---|---|
| Close, 27 Nov | 19 of 19 | to the rupee against Screener and BSE's settlement price (BSE's last trade differs by up to ₹2, as `DATA_CORRECTNESS.md` records) |
| 1M, 3M, 6M, 12M return | 19 of 19 on every window shown | to 0.1%, across every split, bonus and demerger in the sample |
| 52W closing high and low, and their dates | 18 of 18 (VAML is too new, and says so) | HDFCBANK's high is the window's first day, 27 Nov 2025, which our window includes |
| Market cap, 750 and Nifty 1000 | 12 of 13 within 0.2% | TDPOWERSYS ₹19,299 Cr (NSE's own file) against Screener's ₹19,854 Cr: NSE's is the official figure; Screener's share count not checked |
| **Market cap, > ₹2,000 Cr and Combined** | **0 of 6** | **finding F1**: the 30 Oct month-end list's value, not NSE's 27 Nov file. JLHL ₹8,430 Cr against ₹11,320 Cr (NSE and Screener) |

Not checked: P/E (Screener's is on its own basis), results tables (from Screener, so not independent),
index levels against niftyindices.com (NSE blocks this container).

## 2. What changed since 24 Nov, and the 24 Nov gaps

The full read is in the agent's report (scratchpad `audit_delta.md`); its findings below were re-checked in
the code and, where stated, on the live page.

- **Closed** (evidence in code or live): a1, a3-a7 (the R2 pack, S172), a2, a12, 4.5, b1 (Total Market file
  equals the other copy on all 1,270 rows; 1M +9.9% on four pages), b4, b6, b7, 4.1, 4.3, 4.4.
- **Open by owner decision**: a8-a10, b3, b5. **Open and tracked**: b2 (S172), 4.2 (S175), 4.7 (S137).
- **Open and not tracked until now**: a11 (BSE fill zip overwritten each build), b8-b10 (files no page
  reads), 4.6 (Configuration's "Read by" column): now rows of S236.
- Cross-page figures that agree: breadth on Dashboard and Market; Nifty 500 P/E percentile on Dashboard
  and Indices; sector leads; month so far; 12M share beating the market; FPI flows against NSDL.

## 3. Controls, phone width and load times

(Filled from the second agent's report, below.)

## 4. Findings, ranked

| # | Severity | Finding | Evidence | State |
|---|---|---|---|---|
| F1 | Wrong number | > ₹2,000 Cr and Combined show the month-end list's market cap (30 Oct) beside 27 Nov prices, on the Screener, the stock page and every table with a market-cap column | JLHL 8,430 vs NSE 11,320; GOODLUCK 4,923 vs 5,166; `app.py:791`, `scripts/precompute_systems.py:56` | **fixed** (S236): NSE's daily file first, the list only where it has none; test |
| F2 | Wrong statement | `/screener?stock=SHUKRAMED` on the 750 says "in none of the systems' lists"; > ₹2,000 Cr ranks it 1st as SHUKRAPHAR | `stock_view.py:572-580` searched the chosen system only | **fixed**: the page names the rename and links to the list's page; test |
| F3 | Two figures for one thing | Portfolio (750): Nifty Total Market this year +0.6% (By period, from the 1 Jan fill) and +0.7% (the table beside it, from 31 Dec); the lead 46.2 and 46.0 | live page; `portfolio_page.py:584-588` | **fixed**: both from the fill (owner, 23 Nov: "2: from the fill"); test |
| F4 | Wrong statement | Indices' earnings chart note: Tata Motors left out of "Q2 and Q3 of FY26 and FY27"; the code leaves out Q2 FY26, Q3 FY26, Q2 FY27 | `scripts/screener_earnings.py:92` | **fixed** |
| F5 | Wrong statement | Sectors says the switch offers "NSE sector, TradingView sector or TradingView industry"; it offers NSE's four levels | live picker, `sector_view.py:330` | **fixed**: the sentence is built from the switch's own choices; test |
| F6 | Wording | Combined's momentum note: "This system's record starts in December 2021": Combined keeps none, its tiles read the 750's | `dashboard_home_view.py:745` | **fixed** |
| F7 | Wording | Footers "1000 stocks ranked" | three views | **fixed**: "1,000" |
| F8 | Missing data | SHUKRAPHAR, the > ₹2,000 Cr book's largest holding (5.8%), reads sector "Unclassified": NSE's classification file holds neither ticker | `data/reference/nse_classification.csv` | open: next classification sweep, under SHUKRAMED |
| F9 | Wording | One sector, two names on one page: "Metals & Mining" and "Metals" (Dashboard), "Financial Services" and "Financials" (Actions), "Fast Moving Consumer Goods" (Market) and "FMCG" (Screener) | agent's live read | open: short names are `SHORT_NAMES` by design in narrow tables; whether a page may use both is a glossary rule to settle |
| F10 | Wording | Sectors "From 52W high", Indices "From 12M high": `GLOSSARY.md` entries 6 and 14 disagree | glossary | open: one glossary entry to settle |
| F11 | Docs on a page | Configuration's "Read by": `benchmarks.csv` "Dashboard, Market", `nse_total_market.csv` "Market page" only; both are read by more pages | `config_view.py:155-159` (24 Nov 4.6) | **fixed**: traced in the code: `benchmarks.csv` is read by every page's header (the regime line) and by Dashboard, Actions, Portfolio, Market, Watchlist and Backtest; `nse_total_market.csv` by Market and Sectors |
| F12 | Backup | `track_record_1000.json` is not in the nightly R2 copy of the track records (first written at the 1-5 Dec freeze) | `track_record_r2_copy.py:22` | **fixed**: the copy takes every system's ledger; test against `systems.LEDGERS` |
| F13 | Backup | a11: the BSE fill audit zip is overwritten each build; b8-b10: files no page reads | 24 Nov audit §2 | open: S236 rows |
| F14 | Docs | TODO S224 still says "(a)-(c) left"; the R2 pack closed a1, a3-a7 | code | fixed in TODO |
