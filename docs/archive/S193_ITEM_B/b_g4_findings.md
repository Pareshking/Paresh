# S193 item B, group 4: Indices, Backtest and Guide sentences checked against the data (23 Nov 2026)

App on `main` at 2c91ca2. Prices are the 20 Nov 2026 closes. Nothing in the repo was edited.

**How each figure was recomputed**

- **Indices:** recomputed with pandas from the raw `data/nse_indices_history.parquet`; `nse_indices_recent.csv` has no rows. Index families come from `data/reference/nse_index_groups.csv`. Scripts: `scratchpad/aud/ix.py` and `ix2.py`.
- **Backtest, the Nifty 500 side:** from `data/benchmarks.csv`, cross-checked with the NSE index store (identical on 30 Oct and 20 Nov).
- **Backtest, the rule's side:** I ran the default run once through the engine (`scripts/build_backtest_reference._run` on `data_cache/nse_long_close.parquet`, last session 20 Nov). I then worked out every statistic myself from its equity curve and trade list: a year, months ahead, the two halves, years, drawdown, trades and win share. Scripts: `scratchpad/aud/run_bt.py` and `bt_stats.py`. The replay itself has no second source, as the page's own trust table says. The stored tests in `data/backtest_reference.json` (60 and 100 bps, the monthly reset, after tax) were read, not re-run.
- **Guide:** checked against `src/core/config.py`, `src/engine/track_record.py` (`TRACK_RECORD_CONFIG`), `src/engine/backtester.py`, `src/engine/momentum.py`, `src/engine/calendar_momentum.py` and `src/ui/views/actions_page.py`.

All text is identical across 750, 1000 and Nano except the one system note (rows 2 and 89).

| # | page | systems | sentence (short) | verdict | evidence (recomputed value, source) | code | fix (FALSE / MISLEADING) |
|---|---|---|---|---|---|---|---|
| 0 | backtest | all | Since 2010 18.8% a year vs Nifty 500 10.1% | TRUE | Equity curve 4 Jan 2010 → 30 Oct 2026: 18.75%; Nifty 500 4,367.65 → 21,895.90 over 16.82 yrs = 10.06% (benchmarks.csv) | backtest_view.py:443 | |
| 1 | backtest | all | Replayed on Nifty 500 as it stood, 4 Jan 2010–30 Oct 2026, 30 bps | TRUE | First fill 4 Jan 2010, last 30 Oct 2026; `pit_periods` 202 of 202; cost 30 | backtest_view.py:447 | |
| 2 | backtest | 1000 | Nifty 1000 system does not change these runs | TRUE | The run's universe comes from the page's own setting (`_history_inputs`); nano and 1000 figures are identical to the 750's | backtest_view.py:958 | |
| 3 | backtest | all | Minimum traded value label | TRUE-static | | backtest_view.py:296 | |
| 4 | backtest | all | Rules · to buy … keep rules | TRUE-static | | backtest_view.py:332 | |
| 5 | backtest | all | Within this % of its all-time high | TRUE-static | | backtest_view.py:350 | |
| 6 | backtest | all | All-time-high rule: years on file | TRUE-static | | backtest_view.py:357 | |
| 7 | backtest | all | 30-holding settings recorded forward as a shadow book | TRUE | `SHADOWS["recommendation"]`: top_n 30, buffer 90, 200D EMA, from Nov 2026 | backtest_view.py:372 | |
| 8 | backtest | all | Lead 8.7 points a year; ahead in 122 of 202 months | TRUE | 18.754 − 10.059 = 8.69 pts; monthly leads from month-end values: 122 > 0 of 202 | backtest_view.py:463 | |
| 9 | backtest | all | ₹100 chart, weekly closes, log scale; lower pane on daily closes | TRUE | `bp.weekly_chart`: drawdown taken on daily values, sampled on Fridays | backtest_view.py:514 | |
| 10 | backtest | all | Dividend yield 1.3% since Feb 2012 vs about 0.5% for the book; lead about 0.8 smaller | TRUE | Mean NSE Nifty 500 dividend yield 21 Feb 2012 → 20 Nov 2026 = 1.25%; book 0.49% (DATA_CORRECTNESS §5, S125); 1.25 − 0.5 = 0.75 | backtest_view.py:486 | |
| 11 | backtest | all | 16.8 years from the first fill | TRUE | (30 Oct 2026 − 4 Jan 2010) / 365.25 = 16.82 | backtest_view.py:491 | |
| 12 | backtest | all | Nifty Total Market "beside it from 2022 in section 3 and in section 4" | MISLEADING | Section 3 starts in 2022 (true). Section 4's window is "1 Nov 2021 – 30 Oct 2026" (page text and `backtest_reference.json` `total_market_universe.from` 2021-11-01). Nifty Total Market starts 14 Oct 2021 (nse_total_market.csv) | backtest_view.py:493 | "…beside it from 2022 in section 3 and from Nov 2021 in section 4." |
| 13 | backtest | all | Led 0.91 pts a month to May 2018 and 0.50 after; median +0.9 | TRUE | 101 months each: mean 0.906 / 0.503 pts; median 0.917 | backtest_view.py:498 | |
| 14 | backtest | all | 20.9% below its July 2024 peak; max drawdown not recovered | TRUE | Peak 5 Jul 2024; now −20.92%; max drawdown −38.79% (23 Mar 2026), after that peak | backtest_view.py:527 | |
| 15 | backtest | all | Ahead in 13 of 17 years; 2025 the worst, "−28.9 pts behind" | MISLEADING | Figures right (13 of 17; 2025 −28.93 pts). But (a) "−28.9 pts behind" is a double negative (a minus sign plus "behind"); (b) 2026 is Jan–Oct only (+24.2 pts) and is counted as a year; over whole years it is 12 of 16 | backtest_view.py:596 | Write "2025 was the worst, 28.9 pts behind" (absolute value). Say "13 of 17 years, 2026 to October". |
| 16 | backtest | all | November to 20 Nov: rule +5.9%, Nifty 500 +10.0% | TRUE | `live_meta.strategy_mtd` 0.0587; Nifty 500 21,895.90 → 24,088.80 = +10.02% (benchmarks.csv and NSE store agree) | backtest_view.py:600–605 | |
| 17 | backtest | all | Tax costs the lead 2.8 points a year; costs matter more than the rebalance rule | TRUE | (18.75 − 10.06) − (15.23 − 9.35) = 2.81 pts. 30 → 60 bps costs 1.56 pts; monthly against six-monthly is 0.32 pts (backtest_reference.json, built 22 Nov) | backtest_view.py:649 | |
| 18 | backtest | all | Other rows re-run weekly (run of 22 Nov); tax rates | TRUE | `built` 2026-11-22; `rates` string matches; `replay_gap_pts` 0.0 | backtest_view.py:680 | |
| 19 | backtest | all | Momentum 30 is the nearest index a fund tracks; windows include the max drawdown | TRUE | Recomputed 31 Aug 2020 → 30 Oct 2026: rule 23.6% / −38.8%, Nifty200 Momentum 30 15.7% / −31.8%, Nifty 500 14.8% / −18.8%. Both windows contain the Jul 2024 → Mar 2026 fall | backtest_view.py:698 | |
| 20 | backtest | all | "Survivorship and look-ahead are handled; costs, tax and the choice of rules are the soft spots" | MISLEADING | Survivorship is right (202 of 202 rebalances on members of the day). But the same table marks three more rows "Not checked" that the heading leaves out: sector labels are today's; the Nifty 500 before Feb 2012 is the Kaggle copy (S167); there is no second source for the result | backtest_view.py:745 | "…are the soft spots, and sector labels, the index before 2012 and a second source are not checked." |
| 21 | backtest | all | 1,583 trades closed; fewer than half won; winners paid for the rest | TRUE | 1,583 Closed + 20 Open; 47.1% with return > 0; gains over losses, weighted by entry size, 2.09 | backtest_view.py:757 | |
| 22 | backtest | all | Every trade and rebalance log are below | TRUE-static | | backtest_view.py:768 | |
| 23 | backtest | all | Download (ZIP of 2 CSV files) | TRUE-static | `export_zip(rules, trades)` | backtest_view.py:933 | |
| 24 | backtest | all | Show the table · every trade and the rebalance log | TRUE-static | | backtest_view.py:997 | |
| 25 | backtest | all | Data to 30 Oct 2026 · long file · prices to 20 Nov · indices to 20 Nov | TRUE | Long file last session 20 Nov; index store last row 20 Nov | backtest_view.py:772–775 | |
| 26 | backtest | all | Each line is 0.5%; dashed line is the Nifty 500 | TRUE | Highest row 19.07% → `_step` 0.5 (38 lines) | backtest_view.py:677 | |
| 27 | guide | all | Universe … "Prices are daily closes, adjusted for splits and bonuses" | MISLEADING | Both price bases also adjust rights issues and demergers, and the long file also takes out dividends of 10% or more (PRICE_PIPELINE.md; the Backtest's own note, row 10, and the export's `price_basis`) | guide_view.py:82–84 | "…adjusted for splits, bonuses, rights issues and demergers (the Backtest's long file also for dividends of 10% or more)." |
| 28 | guide | all | Score: return ÷ volatility over 1/3/6/9/12M; weights 10/30/30/20/10 | TRUE | `config_weights` [0.10, 0.30, 0.30, 0.20, 0.10]; `calendar_momentum` log return ÷ (population SD × √n) | guide_view.py:85 | |
| 29 | guide | all | Above 50D EMA and within 20% of 52-week high | TRUE | `ema_period` 50, `high_pct` 0.80 | guide_view.py:87 | |
| 30 | guide | all | Top 20, at most 8 per sector, kept within top 40; reset to 5% in Mar/Sep from 30 Nov 2026 | TRUE | top_n 20; sector_cap 0.40 × 20 = 8; buffer_n 40; weight_reset_months [3, 9]; hold_cap_from 2026-11-30 | guide_view.py:88–91 | |
| 31 | guide | all | "The figures these steps produce are on Portfolio and Backtest; none is quoted here" | FALSE | The Guide's Weighting paragraph (row 47) quotes 15.4% and 15.3% a year after tax | guide_view.py:95 | Drop "none is quoted here", or move the S111 figures to the Backtest and link to them. |
| 32 | guide | all | Clip at 3 SD, then z-score, then cap ±3, in that order | TRUE | `_winsorise_z_matrix`: clip at mean ± 3 SD, z on the clipped values, then `clip(-3, 3)` | guide_view.py:107–108 | |
| 33 | guide | all | score = weighted z ÷ sum of available weights | TRUE | As code | guide_view.py:110 | |
| 34 | guide | all | Missing windows rescaled; Configuration changes Screener and Backtest weights only | TRUE | Backtest takes `weights` from the app; the record uses `TRACK_RECORD_CONFIG`. Actions not traced | guide_view.py:111–114 | |
| 35 | guide | all | Members-only scoring from 30 Nov 2026 | TRUE | `members_only_scoring_from` 2026-11-30 | guide_view.py:115–117 | |
| 36 | guide | all | EMA explained; "50D EMA and 200D EMA" | TRUE-static | ewm(span=50) | guide_view.py:121–123 | |
| 37 | guide | all | Near the high: close at or above 80% of the 52-week high | TRUE | backtester `_p >= _hi * high_pct`; screener `x >= -20.0` | guide_view.py:124 | |
| 38 | guide | all | A stock needs 30 closes before it has a 50D EMA | TRUE | `ewm(span=50, min_periods=30)`; `ema_warmup_from` 2026-11-30 | guide_view.py:128 | |
| 39 | guide | all | "A recent listing therefore waits about six weeks of trading before the model will look at it" | FALSE | The 30-close EMA is not the binding rule. A 52-week high needs `HIGH_52W_MIN_OBSERVATIONS` = 126 closes (config.py:227; backtester.py:60; momentum.py:328), and with no high the near-high filter fails. The Screener ranks nobody under `MIN_OBSERVATIONS` = 63 (momentum.py:96). So a listing waits about 6 months (126 sessions), not 6 weeks. DATA_CORRECTNESS §5 already records "New listings … never near the 52W high: under 126 sessions" | guide_view.py:131–133 | "…cannot pass the trend filter before 30 closes, or the near-high filter before 126 (about six months), so a new listing waits about six months." |
| 40 | guide | all | The 52-week high is the highest close, not intraday; header counted the same way | TRUE | momentum.py:299 `high_src = close_src`; backtester `_rolling_high_at` on closes | guide_view.py:135–140 | |
| 41 | guide | all | "Size: 20 stocks, each 1/20 of the account at the rebalance, then held" | MISLEADING | True only at a reset (Mar/Sep) or before 30 Nov 2026. Between resets kept holdings keep their drift up to 15% (`hold_cap` 0.15, `_fixed_buys`). This contradicts rows 42 and 47 on the same page | guide_view.py:144–145 | "20 stocks; at a reset each is 1/20 of the account, and in between kept holdings run (see Weighting)." |
| 42 | guide | all | "a new buy is never above 5% of the account" | FALSE | Under the six-monthly rule a buy is `buy_size × base_acct / acct` (backtester.py:1402), capped at 15% (`hold_cap`), not at 5%. It is above 5% of today's account whenever the account is below its value at the last reset. The default replay has 21 entries above 5.0% of the account (max 5.16%, e.g. 2 Jul 2012) | guide_view.py:146 | "a new buy is 5% of the account as it stood at the last reset (more than 5% of today's if the book has fallen since)". |
| 43 | guide | all | Buffer: kept while its rank among stocks passing both filters stays within 40 | TRUE | `full_ranked` holds only `valid` names; `_select_holdings` with buffer 40 | guide_view.py:152–153 | |
| 44 | guide | all | "Every return on the site is before tax; tax was estimated only in the one test named under Weighting" | FALSE | The Backtest (section 4) shows weekly after-tax rows, rule 15.2% and Nifty 500 9.4%, and "Tax costs the lead 2.8 points a year" (backtest_reference.json `after_tax`). The Guide's own row 47 points to them | guide_view.py:154–155 | "Every return is before tax except the Backtest's after-tax rows (section 4)." |
| 45 | guide | all | No stops: a holding leaves only at a monthly rebalance | TRUE | Exits only at rebalance fills in the engine; a stopped stock is valued at its last price until then | guide_view.py:156 | |
| 46 | guide | all | Equal weight sets each new book's targets: 1/20 | TRUE | | guide_view.py:160 | |
| 47 | guide | all | Six-monthly reset; tested: monthly 15.4%, six-monthly 15.3% a year after tax; 2026 six-monthly best | MISLEADING | The rule text matches the code (resets, 15% trim, buys from cash, sector cap kept in `_fixed_buys`). The figures are S111's dated test (config comment: 15.41 / 15.30). The Backtest's weekly re-run of the same rule after tax reads 15.2% (`after_tax.rule` 0.1523), so the two pages disagree by 0.1 pts. "In 2026 the six-monthly reset did best" was not checked | guide_view.py:161–171 | Date and source the test ("S111, 8 Nov 2026"), or quote the Backtest's weekly figure instead. |
| 48 | guide | all | Inverse volatility over the last 63 sessions | TRUE | backtester.py:312–314 | guide_view.py:172–173 | |
| 49 | guide | all | "the Backtest shows both side by side" | MISLEADING | The Backtest runs one weighting at a time (a select box, backtest_view.py:313). Volatility is in a table and max drawdown in section 2, for that run only; nothing compares equal weight and inverse volatility side by side | guide_view.py:175–176 | "…run it both ways in the Backtest to compare." |
| 50 | guide | all | "Place the sells by hand … download the Kite basket (buy orders only …)" | FALSE | `actions_page.basket` writes SELL rows (the model book's share counts) and then BUY rows. The Actions page says "The basket carries these sells with the model book's share counts" | guide_view.py:181 | "The Kite basket carries the sells (the model book's share counts) and the buys at their target weight of the capital you enter; check the sells against your own holdings." |
| 51 | guide | all | Orders on the next session; the record fills at that close | TRUE | `fwd_start = start_idx + 1`, fill at the T+1 close | guide_view.py:183 | |
| 52 | guide | all | "after tax the outcome is lower than every figure shown" | MISLEADING | Most gains are short term: 99.8% of 1,583 closed trades were held 365 days or less (median 61). But "every figure shown" includes the Backtest's after-tax rows, which are already after tax | guide_view.py:192 | "…lower than every before-tax figure; the Backtest's section 4 gives an after-tax estimate." |
| 53 | guide | all | Not in the book: fails a filter, or book full inside the buffer of 40 | TRUE | `_select_holdings` | guide_view.py:196 | |
| 54 | guide | all | Book and buffer use the qualified rank | TRUE | `full_ranked = score[valid]` | guide_view.py:200 | |
| 55 | guide | all | Header's Nifty 500 vs 200D EMA is context only; no cash target | TRUE | Header "5.3% above": recomputed from benchmarks.csv 20 Nov, 24,088.80 vs EMA(200) = +5.31% | guide_view.py:203 | |
| 56 | guide | all | +20.0% vs +5.0% = 15.0 pts; relative 14.3% | TRUE | 1.20 / 1.05 − 1 = 14.29% | guide_view.py:206 | |
| 57 | guide | all | Max drawdown definition | TRUE-static | | guide_view.py:210 | |
| 58 | guide | all | 30 bps covers fees; STT and stamp duty about 22 bps; 60 and 100 bps re-run weekly | TRUE | 10 + 10 + 1.5 = 21.5 bps; cost_60 and cost_100 in backtest_reference.json, built 22 Nov | guide_view.py:213 | |
| 59 | indices | all | Nifty 50 below its usual P/E; Nifty Smallcap 250 above it | TRUE | Share of days since 31 Mar 2021 with a lower P/E: Nifty 50 21.02 → 25.6th percentile (median 22.11); Smallcap 32.14 → 75.9th. Note: the template only tests the 50th percentile, so a 49th would also read "below its usual"; today the Nifty 50 sits just inside the middle half (q25 20.97) | indices_view.py:66 | |
| 60 | indices | all | Read at the 20 Nov close; price returns, no dividends | TRUE | Last store date 20 Nov | indices_view.py:74 | |
| 61 | indices | all | Nifty 50 at 21.0, cheaper than 74%; Smallcap dearer than 76% | TRUE | 74.0% of 1,400 days above 21.02 (100 − 25.6 = 74.4); 75.9% below 32.14 | indices_view.py:84 | |
| 62 | indices | all | Basis change 31 Mar 2021: Nifty 50 40.4 → 33.2 with the price flat; P/B changes 29 Sep 2023 and 23 Sep 2024 | TRUE | P/E 40.43 → 33.20 while the close went 14,845 → 14,691 (−1.0%). P/B Nifty 50 4.31 → 3.45 (29 Sep 2023, price +0.6%) and 4.08 → 3.83 (23 Sep 2024, price +0.6%) | indices_view.py:98–103 | |
| 63 | indices | all | Nifty 500 P/E weekly since 2012; middle half 22.6 to 25.2 | TRUE | P/E from 21 Feb 2012; q25 22.60, q75 25.16 since 31 Mar 2021 | indices_view.py:115 | |
| 64 | indices | all | Above the band = dearer than three days in four | TRUE | Definition of q75 | indices_view.py:118 | |
| 65 | indices | all | Value and equal weight lead; momentum and quality trail by 7–8 points | TRUE | 12M leads: Value +4.23, Equal weight +3.80, Low volatility −1.20, Alpha −3.36, Momentum −6.75, Quality −7.71 | indices_view.py:134 | |
| 66 | indices | all | Lead = 12M return minus the parent's; only live history from first publication | TRUE | Formula matches. First dates are each index's first day in NSE's archive; NSE's launch notices were not checked | indices_view.py:146 | |
| 67 | indices | all | Momentum 24.2% behind the Nifty 200 from its June 2024 peak, deepest since launch 2020 | TRUE | Relative line (Momentum 30 ÷ Nifty 200): peak 14 Jun 2024, now −24.19% = worst since 25 Aug 2020 | indices_view.py:159 | |
| 68 | indices | all | Quality at its worst too (−26.9%); Value fell 38.8% in 2018–20, back July 2023 | TRUE | Quality −26.94% now = worst. Value −38.81%, 15 Nov 2018 → 14 Oct 2020, regained 26 Jul 2023 | indices_view.py:165–169 | |
| 69 | indices | all | No style led every year; equal weight closest, 7 years of 9 | MISLEADING | 7 of 9 counts 2026 to 20 Nov (+3.4 pts) as a year. Whole years 2018–2025: 6 of 8. Equal weight is still the closest (Value 5 of 7 whole years, 6 of 8 with 2026) | indices_view.py:198 | Count whole years only ("6 of 8 whole years"), or say "7 of 9, 2026 to date". |
| 70 | indices | all | In a median year since 2017 Small Cap fell 22%, twice Large Cap's 11% | TRUE | Median max drawdown within whole years 2017–2025: Smallcap 250 −21.91%, Nifty 100 −11.11%, ratio 1.97. Wording: glossary entry 3 asks for the index name ("Nifty Smallcap 250") in text | indices_view.py:223 | |
| 71 | indices | all | Medians −11.1 / −14.8 / −21.9 / −18.9; micro from 2022 | TRUE | Recomputed: −11.11 / −14.81 / −21.91 / −18.95 (Microcap from 11 May 2021, so 2022 is the first whole year) | indices_view.py:251 | |
| 72 | indices | all | Large Cap Nifty 100 median max drawdown −11.1% | TRUE | As above | indices_view.py:235 | |
| 73 | indices | all | Mid Cap Nifty Midcap 150 −14.8% | TRUE | As above | indices_view.py:235 | |
| 74 | indices | all | Small Cap Nifty Smallcap 250 −21.9% | TRUE | As above | indices_view.py:235 | |
| 75 | indices | all | Micro Cap Nifty Microcap 250 −18.9% | TRUE | As above | indices_view.py:235 | |
| 76 | indices | all | From 2017; Midcap 150 and Smallcap 250 start Apr 2016, Microcap 250 May 2021 | TRUE | First rows 1 Apr 2016, 1 Apr 2016, 11 May 2021 | indices_view.py:242 | |
| 77 | indices | all | Nifty Total Market +0.8% over 12M; Nifty IPO leads +16.6%, Railways PSU trails −23.9% | TRUE | Nifty Total Market +0.77%; theme family: Nifty IPO +16.58, Nifty India Railways PSU −23.95 | indices_view.py:268 | |
| 78 | indices | all | 110 indices, three families; window rule; younger than 12M listed last | TRUE | 23 + 39 + 48 = 110 published on 20 Nov. "Younger" means under 12 months in NSE's file; real launch dates not checked | indices_view.py:272 | |
| 79 | indices | all | Broad market 16 of 19 up; Smallcap 50 +13.4%, SME Emerge −8.3% | TRUE | 19 with 12M (4 younger): 16 up; +13.43 / −8.27 | indices_view.py:282 | |
| 80 | indices | all | Theme 19 of 35 up; IPO +16.6%, Railways PSU −23.9% | TRUE | 35 with 12M: 19 up | indices_view.py:282 | |
| 81 | indices | all | Strategy 14 of 44 up; High Beta 50 +11.5%, Nifty50 Shariah −8.9% | TRUE | 44 with 12M: 14 up; +11.53 / −8.86 | indices_view.py:282 | |
| 82 | indices | all | Data to 20 Nov 2026 · NSE · 110 indices | TRUE | | indices_view.py:312 | |
| 83 | indices | all | Nifty200 Momentum 30 · live since 25 Aug 2020 | TRUE | First row in the store 25 Aug 2020 (launch notice not checked). Wording: "NIFTY200" and "Nifty200" are both used across rows 83–88 because `_short` is not applied here | indices_view.py:136 | |
| 84 | indices | all | NIFTY200 Quality 30 · 18 Apr 2018 | TRUE | First row 18 Apr 2018 | indices_view.py:136 | |
| 85 | indices | all | NIFTY500 Value 50 · 24 Oct 2018 | TRUE | First row 24 Oct 2018 | indices_view.py:136 | |
| 86 | indices | all | Nifty100 Low Volatility 30 · 11 Jul 2016 | TRUE | First row 11 Jul 2016 | indices_view.py:136 | |
| 87 | indices | all | NIFTY100 Alpha 30 · 28 Jun 2019 | TRUE | First row 28 Jun 2019 | indices_view.py:136 | |
| 88 | indices | all | NIFTY50 Equal Weight · 18 Apr 2017 | TRUE | First row 18 Apr 2017 | indices_view.py:136 | |
| 89 | backtest | nano | > ₹2,000 Cr system does not change these runs | TRUE | As row 2 | backtest_view.py:958 | |

## Contradictions between pages

- **Tax:** the Guide (rows 31, 44, 52) says no figure is quoted there, that tax was estimated in one test only, and that every figure is before tax. The Backtest, section 4, shows weekly after-tax rows. The Guide's Weighting paragraph (row 47) quotes figures and points to those rows.
- **Six-monthly reset after tax:** the Guide gives 15.3% a year (S111). The Backtest's weekly re-run shows 15.2% (`after_tax.rule` 0.1523).
- **Kite basket:** the Guide says "buy orders only" (row 50). The Actions page says the basket carries the sells.
- **Weight of a holding:** within the Guide, row 41 ("each 1/20 at the rebalance") contradicts rows 42 and 47 (kept holdings run to 15% between resets).
- **Counting 2026 as a year:** the Backtest (row 15) and the Indices page (row 69) both count 2026 to date as a year in an "N of M years" count. The two pages are consistent with each other, but neither says the year is partial.

## Not checked

- NSE's launch notices for the style and young indices; the first date in NSE's archive was used instead.
- "In 2026 the six-monthly reset did best" (row 47).
- The stored after-tax and cost tests: read from `backtest_reference.json`, not re-run.
- The replay itself has no second source; its statistics were recomputed from its own equity curve.
- Whether the Actions page uses the record's weights (row 34).

## Counts by verdict (90 sentences)

| Verdict | Count |
|---|---|
| TRUE | 67 |
| TRUE-static | 9 |
| FALSE | 5 (rows 31, 39, 42, 44, 50) |
| MISLEADING | 9 (rows 12, 15, 20, 27, 41, 47, 49, 52, 69) |
| NOT CHECKED (whole sentence) | 0 (the parts not checked are listed above) |
