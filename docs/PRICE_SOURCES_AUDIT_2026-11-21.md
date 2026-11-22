# Price sources audit, 21 Nov 2026

Owner, 21 Nov 2026: "which pages or internally anywhere are we using yahoo finance data?
Or any other sources? We have screener.in and NSE long file (Backtest) only and if using
other sources for price data of stocks or indices, please update here."

Method: every external host named in `src/`, `app.py`, `agent/`, `scripts/` and
`.github/workflows/` (one search over all of them), then each one traced to the file it
writes and the pages that read that file. The source of every row in the three index
files was counted from their own `source` column. Tests and research scripts excluded.

## Summary

- **Yahoo: no live use anywhere.** `yfinance` is not imported anywhere and is not in
  `requirements.txt`. Every mention is a comment, a test or old wording. The ranking's
  Yahoo fill tier still exists in code (`price_source.keep_and_fill`'s `backup_close`,
  `from_yahoo`), but its one caller passes `None` (`price_source.py:284`), so it is dead
  code (owner, 2 Oct 2026: no Yahoo).
- **Stock prices are not only Screener and the NSE long file.** Five sources feed them:
  Screener, NSE's daily files, the NSE long file, BSE (gap fill), and SS (checks only).
- **Index prices are not from NSE or Screener for most of their history.** The Nifty 500
  and Nifty 50 history behind the trend rules, the signal tests, Backtest's benchmark and
  the header strip is 4,078 days from a **Kaggle** dataset (1999 to 7 Oct 2015) and
  2,511 days from **SS** (8 Oct 2015 to 18 Sep 2026). Only 243 days are NSE's own
  (25 Sep 2024 on), and 1 is Screener's. The size and momentum indices are Screener's
  index charts, which are **weekly before 16 Oct 2025**. *(Update, S167 (b), later on
  21 Nov: `benchmark_indices.csv` now reads NSE's own daily closes from each index's
  launch; Screener only after the store's last session. See the table below.)*

## Stock prices

| Source | What it supplies | File / store | Read by |
|---|---|---|---|
| Screener (screener.in) | Daily closes of every ranked stock, about ten years; the ranking's basis | R2 published store (`screener_loader`, `sync_screener.py`) | Every page that shows a price or a rank |
| NSE daily files (nsearchives / archives.nseindia.com) | Closes that fill Screener's gaps and its weekly stretch; corporate actions | `data/nse_prices/` (`nse_prices.middle_close`, `price_source.keep_and_fill`) | The ranking, so every page |
| NSE long file | NSE's own closes, point-in-time members, for the 2010+ history | R2 (`nse_long`, `nse_long_prices.yml`) | Backtest; Breadth's point-in-time history; Momentum health |
| BSE bhavcopy (bseindia.com) | Fills days NSE's file lacks, where BSE traded the stock | inside the NSE long file (`bse_fill`, `build_nse_long_prices.py`) | Backtest |
| Screener, then NSE | Prices of stocks that have left an index | `data/former_member_prices.parquet` | Backtest, Track record |
| SS (address in a secret) | Daily OHLCV of every stock | R2 store (`ss_prices`, `sync_ss.py`, weekly) | **No page.** The nightly reconciliation compares Screener with SS and NSE |

## Index prices

| File | Indices | Sources, by row count and dates | Read by |
|---|---|---|---|
| `data/benchmarks.csv` | Nifty 500, Nifty 50 | **Kaggle** 4,078 (7 Jun 1999 to 7 Oct 2015); **SS** 2,511 (8 Oct 2015 to 18 Sep 2026); NSE 243 (25 Sep 2024 to 20 Nov 2026); Screener 1 (8 Nov 2026) | Breadth's trend rules (history from 2000), Dashboard signals and signal tests, Backtest benchmark, RRG's Nifty choices, header strip, Portfolio, Sectors, the stock page |
| `data/benchmark_indices.csv` | Nifty 50, Nifty 200, Total Market, Midcap 150, Smallcap 250, Microcap 250, four momentum indices | Screener's index charts: **weekly** 1,106 rows (3 Dec 2021 to 10 Oct 2025), daily 2,868 (16 Oct 2025 to 20 Nov 2026). **Replaced later on 21 Nov (S167 (b))**: NSE's all-indices archive, 19,462 daily rows from each index's launch plus 24 derived; all 3,974 Screener rows equalled NSE's within 0.003% | Dashboard, Breadth "By size" and size charts, Sectors |
| `data/nse_total_market.csv` | Nifty Total Market | NSE's archive, daily from 14 Oct 2021 | Breadth "ahead of the market", Sectors |

The seams in `benchmarks.csv` are continuous: 7 to 8 Oct 2015 (Kaggle to SS, Nifty 500
6,835.8 to 6,793.8) and 24 to 25 Sep 2024 (SS to NSE, 24,389.7 to 24,371.3). The RRG check
of 21 Nov found the file equal to NSE's own daily files on all 552 sessions from 2 Sep 2024
to 20 Nov 2026, which covers SS's last two years. **SS before Sep 2024 and all of Kaggle
were not checked against NSE.**

## Not prices, for completeness

NSE (market caps, holidays, index membership notices, F&O list, DII), NSDL and MSEI (FPI
flows), TradingView's scanner (sector classification, `classify_missing.py`), IIM
Ahmedabad's factor data (a research check). A TradingView chart link on the stock page
opens TradingView; it reads nothing.

## Not checked

- Kaggle's Nifty 500 and Nifty 50 (1999 to 2015) and SS's index history before Sep 2024
  against NSE's own index closes (niftyindices.com historical data).
- How many cells BSE fills in the NSE long file (`bse_fill_verify.json` is a workflow
  output, not in `data/`).
- SS's licence and terms of use; Kaggle dataset's licence.
- Whether the weekly stretch of `benchmark_indices.csv` moves any figure on the pages
  (a 200D EMA or 52W high read over weekly points).
