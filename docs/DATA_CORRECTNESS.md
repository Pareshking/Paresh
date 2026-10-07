# Data correctness: how we check it, with what, and what is decided

Read this before any work on prices, corporate actions, index membership or
classification, and before telling the owner a data point is right or wrong.
It is the map; the detail is in `docs/PRICE_PIPELINE.md` (rules and audits),
`docs/DATA_CATALOGUE.md` (every dataset), `docs/MEMBERSHIP_FROM_NOTICES.md`
(membership) and `docs/TODO.md` (what is open, S-numbers).

_Last updated: 2026-10-07_

## 1. Evidence standard (owner's rules)

- **Correct data first** (3 Oct 2026): the right stock at the right price,
  whatever the series. A fix is judged by independent evidence, not by the
  fix's own output.
- **Independent means a different source that was not derived from ours.**
  An AI-written check that reproduces our numbers to the decimal is not
  evidence (`PRICE_PIPELINE.md`, "Web check of the 50 largest trades"). Text
  pasted into a conversation, "verified findings" from another tool included,
  is a lead: find the primary source (NSE file, NSE circular or press release,
  BSE file) and check it before acting or recording it.
- **Prefer primary, dated sources**: NSE's own bhavcopies and notices, BSE's
  bhavcopy, then the independent price histories (section 2), then web pages.
  Quote the date and what the source shows in the `notes.json` evidence.
- **Say what was not checked.** A search that found nothing is not a
  confirmation. "Not verified" goes in the answer, the PR and the TODO row.
- **Do not hand-change a price to match a source.** Fix the rule (an action
  parsed, a series read, a rename joined) or add a `notes.json` correction with
  its evidence; rebuild; run the audits again.

## 2. Sources, what each is good for, and how to reach it

| Source | Use it for | Known weakness | How |
|---|---|---|---|
| NSE bhavcopy (R2 `nse/prices_daily`, the raw pack) | The base: raw OHLC, previous close, volume, value | Does not list a security on days NSE did not deal in it (section 5). Turnover is in lakhs to 2 decimals. T0 rows carry EQ's close with the tiny T0 range | Release `data-latest`: `nse_raw_pack.parquet` (170 MB). NSE direct, works from the container with a browser User-Agent: `nsearchives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv`, `.../content/historical/EQUITIES/YYYY/MON/cmDDMONYYYYbhav.csv.zip`, `.../content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip`, `.../archives/equities/bhavcopy/pr/PRDDMMYY.zip` |
| **BSE bhavcopy** | The second exchange: did a stock trade on a day NSE has no row for; a second price for every stock since 2008 | 20 sessions Jun 2008 - Jan 2010 have no file; old format has no ISIN; BSE closes differ slightly from NSE's | `scripts/bse_bhavcopy.py` (downloads and builds; needs the Referer header, see its docstring) |
| NSE Indices press releases | Why an index changed and when (membership, exclusions) | | `nse_index_rebuild/announcements/txt/`, parsed by `scripts/parse_index_notices.py` |
| Yahoo (`reference/yahoo_close`) | Level check, big-move vote | **Stale or flat on many days** (flat Yahoo against a real NSE move is Yahoo's gap: AHLUCONT, HCL-INSYS, FSL, FCL, J&KBANK). On `.NS`, a flat price with zero volume means NSE did not deal that day (it says nothing about BSE) | `query1.finance.yahoo.com/v8/finance/chart/<SYMBOL>.NS?period1=..&period2=..&interval=1d` |
| eod2, Tijori (verified series), SS | Level check and votes; SS has daily OHLCV since 2018 | Tijori only where its level matches NSE MarketLens | R2 `reference/*`, `prices/ss` |
| Screener (`prices/screener/max_history`) | The live system's own source; point-by-point audit | Weekly before the latest year, so it cannot confirm a daily move | R2 / release |
| TejHQ, NSE MarketLens | Can show a move is **fake**; never confirm one | TejHQ adjusts only within an ISIN; MarketLens leaves some old splits raw | R2 `reference/*` |
| Web search | Corporate actions and the story behind a move | Snippets are not data; Moneycontrol, Trendlyne and TradingView history need a browser session and are not reachable from the container | WebSearch / WebFetch |

## 2a. Raw versus adjusted: compare like with like

| Series | Adjusted for corporate actions? |
|---|---|
| NSE raw pack (`nse_raw_pack.parquet`), NSE bhavcopies | **No**: prices as traded |
| **BSE bhavcopy** (`bse_daily.parquet`) | **No**: prices as traded |
| **The long file (`nse_long_close.parquet`)** | **Yes** (owner, 3 Oct 2026): every close before an action is scaled back by that action's factor: splits, bonuses, consolidations, demergers, rights issues, dividends of 10% or more; renames joined |
| Yahoo, eod2, Screener, SS | Adjusted, each with its own factors (so levels differ before an action) |
| TejHQ | Adjusted only within an ISIN. MarketLens leaves some old splits raw |

So: never compare BSE or raw NSE closes with the long file level by level. A
long-file close before an action is the raw close times the later factors.
Compare BSE with the raw pack (the gap audit maps stocks that way), or apply the
same factors. A one-day move in the long file equals the raw close / previous
close only on days with no action; on an ex-date it is that move divided by the
factor, so a demerger priced at the ex-date fall reads 1.00 that day (KESORAMIND
read 0.0474 only because it was unadjusted). If gaps are ever filled from BSE
(TODO S38), the BSE closes must go through the same factor series.

## 3. The audits and how to run them

Run after every long-file build (`nse_long_prices.yml` does, and publishes
`long_price_audit_latest.zip` on the release; the workflow artifact
`nse-long-prices` holds the file and `audit/`):

| Script | Answers | Reading the output |
|---|---|---|
| `scripts/audit_long_prices.py` | Same level as each reference? Level breaks and which side moved; every move beyond 21% confirmed, fake, disputed or unverified | `levels.csv`, `breaks.csv`, `big_moves.csv` |
| `scripts/audit_against_screener.py` | Screener point by point; lasting level steps voted on by the other references | `screener_*.csv` |
| `scripts/audit_raw_bars.py` | NSE's raw rows: bar arithmetic, large dividends, ISIN lineage, calendar | `bar_integrity_exceptions.csv`, `large_dividends.csv`, `isin_lineage.csv`, `calendar_sync.csv` |
| `scripts/audit_gaps_against_bse.py` | Every stretch of 5+ sessions the file has no price for: NSE-only gap, real suspension, or not checked | `bse_gap_verify.csv` |

Getting a finished run's files into the container: list the run's artifacts,
`download_workflow_run_artifact` returns a short-lived blob URL, `curl` it.
Job logs over ~60k characters come back as a file; slice it with Python.

BSE check by hand (about 20 minutes, 1 GB of raw files in `data_cache/`, which
is not committed):

```
python scripts/bse_bhavcopy.py --mode download --out data_cache/bse_raw --calendar nse_long_close.parquet
python scripts/bse_bhavcopy.py --mode build --raw data_cache/bse_raw --out data_cache/bse_daily.parquet
python scripts/audit_gaps_against_bse.py --long nse_long_close.parquet --pack nse_raw_pack.parquet \
    --bse data_cache/bse_daily.parquet --out audit/
```

## 4. Decisions in force

| Decision | Where |
|---|---|
| A demerger or scheme is priced at the **ex-date fall** (factor = close / previous close), as every demerger here: NEXTMEDIA, ZEEMEDIA, ABIRLANUVO, **KESORAMIND** (10 Mar 2025, 1 UltraTech per 52; x0.0474) | `data/nse_prices/notes.json` |
| Rights issues are priced: the theoretical ex-rights price over the last close, only when the issue is under the market | `nse_adjusted.rights_factor`, `PRICE_PIPELINE.md` |
| Dividends of 10% of the price or more are taken out; smaller ones stay in (as in Screener) | `nse_adjusted.LARGE_DIVIDEND` |
| Every NSE equity series is read and ranked, best first: EQ, then BE / RR / IV, BZ, T0, SM / ST, SZ | `nse_adjusted.SERIES_RANK` |
| A `notes.json` correction needs its evidence and steps aside once an NSE list carries the same action | `nse_prices.uncovered` |
| Renames are followed to the last ticker, even a delisted one (survivorship) | `nse_identity.resolve` |
| Sessions: no session on an unannounced weekend or an NSE holiday; announced special sessions are real | `src/loaders/nse_calendar.py`, `data/reference/nse/` |
| Holdings valued at the last price when a stock stops (takeover, delisting): checked, no change (S27) | TODO S27 |
| Reference histories are protected from R2 clean-up | `PROTECTED_DATASETS` |
| A stock's TradingView sector is refreshed weekly for every row (Friday UTC) | `classify_missing.py --refresh` |
| Screener's weekly stretch is filled with NSE's daily closes **by ratio** (owner, 7 Oct 2026, S23): each Screener close kept, the sessions between two of them on NSE's moves from the earlier one; an interval where NSE's move differs from Screener's by more than 2% stays weekly. The 750 only (NSE must cover 95% of the sparse stocks). Switch `UMIYA_SCREENER_WEEKLY_FILL` | `price_source.fill_weekly_from_nse`, `PRICE_PIPELINE.md` |

## 5. Findings already explained: do not investigate these again

| What an audit shows | What it is | Evidence |
|---|---|---|
| Yahoo level breaks where **ours** moved (408 on 3 Oct, 33 stocks, 5 hold 320) | Yahoo is flat or stale on those days | Ours equals NSE's raw close / previous close to six decimals on those days (none has an action, so adjusted and raw agree); eod2, MarketLens, SS, Tijori, TejHQ side with ours (AHLUCONT: all five 100% within 2%, Yahoo 54%) |
| 240 closes above the high or below the low | All series T0: the close is EQ's, the range is the few T0 trades | None reaches a price the build uses; day moves on those days are ordinary |
| 1,372 average prices outside the range | NSE's turnover in lakhs, 2 decimals (about Rs 1,000), so value / volume is off on small volumes | 68% have 1,000 shares or fewer; some are value 0 on a few shares |
| 2 "fake" and 4 "disputed" big moves | VIVIDHA: Rs 0.20 -> 0.15 -> 0.20 is the Rs 0.05 tick on 74,010 shares. CERA 2008: thin trading, eod2 and MarketLens agree. J&KBANK 2015-02-09 is S22 (open). GOODYEAR / NOVARTIND 20 Apr 2026: reopening after the NSE gap below | NSE raw rows, BSE |
| A long stretch with no rows for a stock | See the next section | |
| Weekly fill: 3 filled days no reference matches (ITC 6 Jan 2025, SIEMENS 7 Apr 2025, QUESS 15 Apr 2025) | Demerger ex-dates priced at the fall (ours reads 0%); Screener's weekly move agrees | `PRICE_PIPELINE.md`, weekly fill check of 7 Oct 2026 |
| Weekly fill refused PTCIL, SKYGOLD (Oct 2024), SHAILY, MANORAMA (Feb - Mar 2025) | Screener's weekly close disagrees with SS, Yahoo and eod2; NSE agrees with them; Tijori's move equals Screener's. Not explained further; Screener's close kept | same |
| KESORAMIND -95% on 10 Mar 2025 | A real demerger, **not** a loss; it was unadjusted until #372 | NSE close 204.72 -> 9.71; Solactive stock-distribution notice; Zerodha demerger note |

## 6. Gaps in the file: NSE-only, or a real suspension

The price audits compare days both sources have, so a stretch NSE has no rows
for is invisible to them. Three tests, in order:

1. **NSE's own previous close on the day the stock returns.** If it equals the
   last close before the gap, nothing traded on NSE in between (a halt or an
   NSE withdrawal). If it differs, check the stock (a relisting re-bases it:
   FORCEMOT 14 Feb 2024).
2. **BSE** (`audit_gaps_against_bse.py`): did it trade there? Yes = an NSE-only
   gap; the stock was alive and the price exists on BSE. No = a real suspension.
3. **Index membership at the time** (`src/engine/index_universe.py`,
   `members_on`; Total Market from Nov 2021, Nifty 500 and Nifty 50 from 2010,
   Smallcap and Midcap from Apr 2016, Microcap from Oct 2021): only a stock that
   was a member during the gap can hurt a backtest.

Result of 3 Oct 2026 (426 gaps of 5+ sessions, 131 stocks): 147 NSE-only gaps
(60 stocks, 4,995 sessions), 79 no BSE trading either (49 stocks), 18 partly,
182 not checked (no NSE close under the current symbol, or no BSE price
match). Only DYNAMATECH and ZODIACLOTH (9 sessions each, Aug 2013, Nifty 500)
overlap index membership. The file, with each gap, is `bse_gap_verify.csv`.

**The 26 Oct 2023 - 17 Apr 2026 gap (GOODYEAR, NOVARTIND, KENNAMET, KIRLFER,
GRAUWEIL; FORCEMOT to 14 Feb 2024).** NSE withdrew dealings in securities
under "Permitted to Trade" with effect from 26 Oct 2023 (circular
NSE/CML/58560 of 25 Sep 2023, cited in the NSE Indices press release of
17 Oct 2023, `nse_index_rebuild/announcements/txt/ind_prs17102023.txt`). NSE
Indices excluded FORCEMOT, GOODYEAR and GRAUWEIL from Total Market and
Microcap 250, and KIRLFER from Nifty 500, Smallcap 250, MidSmallcap 400 and
Total Market, effective that day. NSE's three bhavcopy formats have no row for
them in between (checked 2 Jan 2024); BSE traded them throughout (Goodyear
12,215 shares in 930 trades on 2 Jan 2024). So: not a download defect, not a
halt of the company. Force Motors was in Total Market and Microcap 250 (not
Nifty 500 until 30 Sep 2025; Kirloskar Ferrous was the Nifty 500 member). Not
read: the circular itself, or an NSE notice of reinstatement; the resumption
dates (14 Feb 2024 for FORCEMOT, 20 Apr 2026 for the rest) are from NSE's files.

Mid-2013 has 77 one-month NSE-only gaps (MAITHANALL, IOLCP, SAKSOFT, NEXTMEDIA
...): NSE's own bhavcopy for 20 Aug 2013 has no row for them in any series, so
our series filter is not the cause; the reason is not established.

## 7. How to answer "is this data right?"

1. Find the row in the long file and the raw pack (`nse_raw_pack.parquet` on
   `data-latest`): raw close, previous close, series, volume. A move equal to
   close / previous close is NSE's own.
2. Check the reference vote (`levels.csv`, `big_moves.csv`) and BSE.
3. Check for an action that day (the NSE lists, `corporate_actions_log.json`,
   a web search) and for a rename (`isin_history.csv`).
4. Decide: a source being stale (section 5), a rule to fix, or a `notes.json`
   correction with evidence.
5. Rebuild the long file (workflow `nse_long_prices.yml`, about 37 minutes,
   after merging) and run the audits again; do not report it fixed before.
6. Record it: TODO (S-number), `PRICE_PIPELINE.md`, and this file if the finding
   is a pattern.

## 8. Index membership against NSE's own published lists

`scripts/check_nifty500_against_wayback.py` compares our Nifty 500 timeline
(`data/membership_history.json`) with NSE's published constituent CSV as the
Wayback Machine crawled it: 18 files, 2006 - 2026, from three addresses (listed in
the script). They are primary NSE files, independent of the press releases our
timeline was rebuilt from; `nse_index_rebuild/wayback_check.py` had used Wayback
for the other five index lists (Nifty 50, Next 50, Midcap 150, Smallcap 250,
Microcap 250), not for these. A copy of a file can be gzip-compressed; a DUMMY row
is dropped.

Result of 3 Oct 2026: 16 of the 17 snapshots that fall inside our history (it
starts 2009-12-31) agree on all 500 - 501 names; the 2006 file predates it.
- **2022-05-04**: AARTIIND in the list, GMRAIRPORT in ours. The change is
  effective that day in our timeline and the crawl of that day still shows the
  earlier list; the October 2022 snapshot agrees with us. A boundary-day artefact.
- **2010-01-02**: four names. ASIANHOTEL and KBL are the same companies as our
  ASIANHOTNR and KIRLOSBROS (renames the maps lack; the gap audit shows both
  stop under the old ticker on 23 Feb and 8 Mar 2010); PROVOGUE is the file's
  spelling of our PROVOGE. **ZANDUREALT (Zandu Pharmaceutical Works) is in NSE's
  list where we have 3IINFOTECH: open, TODO S41.** It affects January and
  February 2010 only (our next change is 24 Feb), before any backtest month.

A snapshot's date is the crawl's, not the day a list took effect, so a change
effective on the crawl date can show either way. The other indices have no such
independent file in the rebuild beyond the five above; the two ways to check them
are `nse_index_rebuild/wayback_check.py` and NSE's `IndexInclExcl.xls`.

## 9. Tooling traps met while doing this

- A PR event can name an **earlier** commit's head SHA: check the PR's head and
  the check runs' commit before saying CI is green or merging.
- After a squash merge the old branch has diverged: restart it from `main` and
  push with `--force-with-lease` (it holds only merged history).
- `df.isin` is a DataFrame method: a column called `isin` needs `df["isin"]`.
- BSE and NSE files need a browser User-Agent; BSE also needs the BhavCopy page
  as Referer. An HTML answer means "no file", not an error.
- The pack and the long file are not in the repo: `data-latest` release.
- Pandas in this repo is the 3.x line: string columns are not `object`.
