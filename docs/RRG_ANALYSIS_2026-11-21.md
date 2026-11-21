# RRG: data and method check, 21 Nov 2026

Owner, 21 Nov 2026: "Next ... is RRG, check to do list also as it shows wrong information ... you need to
have detailed analysis, check other website to validate our data and so on including formula,
calculations etc". Read with `docs/RRG_REQUIREMENTS.md` (the list the redesign is built and checked
against) and TODO S147 (reopened today), S151, S154, S164, S165, S166.

**Data date: closes of 20 Nov 2026 (a Friday), on every figure below.**

## How it was checked

- The app was run at commit `6981beb` (`streamlit run app.py --server.port 8503`) on 21 Nov 2026,
  about 09:45-10:30 UTC. This session had no R2 keys, so the app served the ranking and prices from the
  release files ("Screener ranking store: source=published_screener_https" in its log); the live site
  reads R2. `/rrg` and `/sectors` were read in Chromium at 1400 px with Playwright.
- The frames the two pages read (`adj_close`, `deep_adj_close`, `rank_df`) were saved from the same
  app script and the page's own function (`compute_rrg_data`) was run on them. It reproduces every
  RRG figure on the page to the decimal shown (Media 118.04 · 105.86 against 118.0 · 105.9 on the page),
  and Sectors' "What is leading?" figures to the decimal.
- Outside data: NSE's daily index file `ind_close_all_DDMMYYYY.csv` from
  `https://nsearchives.nseindia.com/content/indices/`, every session from 2 Sep 2024 to 20 Nov 2026
  (552 files, downloaded 21 Nov 2026). It carries 171 indices, including every NSE sector index used
  below and Nifty500 Equal Weight.
- Outside quadrants: StockCharts' licensed JdK RRG of NSE sector indices against the Nifty 500, as
  listed in Milan Vaishnav's weekly "Week Ahead" notes on articles.stockcharts.com (URLs below), seven
  dated notes from Feb to Nov 2026.
- Scratch scripts (not committed) are in this session's scratchpad: `a1_reproduce.py`,
  `a2_decompose.py`, `a3_outside.py`, `a4_more.py`, `a5_counts.py`.

## Summary

1. **The page's words for the horizontal axis are wrong for 3 of 20 industries today.** The page and the
   20 Nov CHANGELOG say 100 is the benchmark and "right of it, an industry is gaining on it over the
   lookback". The code measures something else: a 30-session average of relative strength against its own
   60-session average. Information Technology reads 101.6 (right of 100) while it is 1.8 pts behind the
   market over the 12-week lookback and 5.8 pts behind over the month. Telecommunication (100.1; −2.9 pts
   over 12 weeks) and Consumer Services (100.1; −1.1 pts) are the same. S147 (a)'s "a trailing industry
   cannot read Leading" is not what the code tests.
2. **RRG and Sectors read 10 of 19 industries differently, and neither page says why.** All 10 are
   differences of window and smoothing. None is construction: both pages use the same equal-weighted
   industry and the same equal-weighted market (daily returns differ by at most 0.03%). No arithmetic
   error was found.
3. **Our RRG does not reproduce the licensed JdK RRG.** On NSE's sector indices against the Nifty 500,
   our method put 35 of 101 index-weeks (35%) in StockCharts' quadrant over seven dated notes. Chance is
   25%. The RS-Ratio side agreed 74% of the time; the RS-Momentum side 55%, about a coin toss. Two open
   reimplementations do no better (36 of 101). The JdK formula is not published; ours is a
   reconstruction and must not be presented as the JdK numbers.
4. **The "weekly" tail is not weekly.** Its points are every fifth session counted back from the as-of
   date, with an off-by-one: on 20 Nov the tail runs Fri 9 Oct, Fri 16 Oct, Mon 26 Oct, Mon 2 Nov,
   Sun 8 Nov (the Diwali session), Mon 16 Nov, Fri 20 Nov. The last step is 4 sessions, the others 5.
   The momentum figure compares with Fri 13 Nov, a date the tail does not show.
5. **The numbers change with which industries are on the chart.** Each axis is scaled by the spread of
   today's cross-section. Textiles reads 107.1 · 108.7 with all 20 industries and 112.2 · 109.7 without
   Utilities and Media. A reading cannot be compared across days, across scopes or with any outside RRG.
   The quadrant does not change.
6. **Our industries are not NSE's sector indices.** Equal-weighted "Financial Services" returned −1.5%
   over three months; Nifty Financial Services returned +10.2% (a gap of −11.6 pts). This is the S147
   decision, but the page uses NSE's names without saying so.
7. **Dates are current.** Every point ends on 20 Nov, the page's session. No week is dropped, because
   nothing is resampled to weeks. The tail starts on 9 Oct 2026; the 12-week lookback on 26 Aug 2026.

**Recommendation (owner's decision, D1 below): (c).** One reading of an industry across the site. The
RRG page draws the figures Sectors reports, the industry against the market over six months and over
one month, with a tail of weekly (Friday-close) positions, so the two pages agree by construction and
anyone can check a point on a price chart. Keep the JdK-style reconstruction only if the owner wants it,
named as a reconstruction, with the fixes in findings 1, 4 and 5.

## Readings on 20 Nov 2026, both pages, every industry

RRG: default settings (weekly, tail 6, lookback 12 weeks, against all ranked stocks equal-weighted).
Sectors: "What is leading?", the industry's return less all ranked stocks', each equal-weighted, over
six months and one month, in points; it reads industries with five or more stocks, so Utilities (4) is
not there. "12w" and "1w" are the plain relative returns over the last 60 and 5 sessions on the RRG's own
series, in points, added here to show what each axis is near.

| Industry | RRG RS-Ratio · Momentum | RRG quadrant | Sectors 6M · 1M | Sectors group | 12w | 1w | Same? | Which axis differs, and why |
|---|---|---|---|---|---|---|---|---|
| Media Entertainment & Publication | 118.0 · 105.9 | Leading | +18.6 · +4.1 | ahead on both | +14.0 | +0.3 | Yes | |
| Textiles | 107.1 · 108.7 | Leading | +13.3 · +7.6 | ahead on both | +9.7 | +4.5 | Yes | |
| Services | 105.9 · 100.5 | Leading | +13.1 · +1.4 | ahead on both | +5.5 | −0.6 | Yes | |
| Automobile and Auto Components | 102.9 · 107.3 | Leading | +10.1 · +6.0 | ahead on both | +3.5 | +1.9 | Yes | |
| Fast Moving Consumer Goods | 101.6 · 101.8 | Leading | −1.8 · +0.5 | gaining | +0.5 | +1.2 | No | Across: 12-week trend up, six months behind. Window |
| Construction Materials | 101.3 · 109.2 | Leading | −6.2 · +7.2 | gaining | +3.4 | +4.1 | No | Across: same as FMCG. Window |
| Financial Services | 101.2 · 107.0 | Leading | +0.9 · +3.0 | ahead on both | +2.2 | +1.0 | Yes | |
| Realty | 101.2 · 107.6 | Leading | +2.5 · +4.8 | ahead on both | +1.6 | +2.1 | Yes | |
| Consumer Durables | 98.8 · 101.0 | Improving | +4.1 · −2.0 | fading | −1.6 | +0.1 | No | Both: behind over 12 weeks but ahead over six months; ratio rose this week, behind over the month. Window |
| Power | 96.9 · 101.2 | Improving | −19.1 · −0.4 | behind on both | −2.3 | +0.1 | No | Up: ratio rose this week; behind over the month. Window |
| Construction | 94.1 · 102.2 | Improving | −14.0 · −1.9 | behind on both | −5.1 | −1.3 | No | Up: momentum reads up although relative strength fell 1.3 pts this week (smoothing lag). Window and smoothing |
| Healthcare | 103.6 · 99.7 | Weakening | +7.1 · +6.3 | ahead on both | +4.7 | +0.8 | No | Up: momentum reads down although it gained 0.8 pts this week (smoothing lag). Window and smoothing |
| Oil Gas & Consumable Fuels | 103.5 · 99.8 | Weakening | +3.4 · +1.8 | ahead on both | +4.2 | +1.3 | No | Up: same as Healthcare (+1.3 pts this week). Window and smoothing |
| Information Technology | 101.6 · 90.5 | Weakening | −2.6 · −5.9 | behind on both | −1.8 | −1.8 | No | Across: right of 100 although behind over 12 weeks, 3 months and 6 months; the 30-session average still holds October's +9.0 pt month. Smoothing lag; the page's wording is wrong here |
| Consumer Services | 100.1 · 98.7 | Weakening | +3.0 · +0.4 | ahead on both | −1.1 | +0.3 | No | Up: momentum down while it gained 0.3 pts this week and is ahead over the month. Window and smoothing |
| Telecommunication | 100.1 · 89.5 | Weakening | −4.7 · −6.1 | behind on both | −2.9 | −3.6 | No | Across: right of 100 although behind over 12 weeks (−2.9) and six months (−4.7). Smoothing lag; wording wrong |
| Capital Goods | 96.1 · 91.5 | Lagging | −2.1 · −6.0 | behind on both | −3.9 | −2.2 | Yes | |
| Chemicals | 94.7 · 98.8 | Lagging | −5.3 · −3.4 | behind on both | −4.4 | −0.1 | Yes | |
| Metals & Mining | 93.1 · 97.7 | Lagging | −17.8 · −3.1 | behind on both | −7.6 | −1.6 | Yes | |
| Utilities (4 stocks) | 84.0 · 85.9 | Lagging | not shown | | −12.9 | −5.6 | n/a | Sectors needs five stocks |

**Count: 9 agree, 10 differ, 1 not on Sectors.** The other session's count (10 of 20) is confirmed. The
readings the TODO quotes are confirmed: Healthcare Weakening on RRG, ahead on both on Sectors; Power and
Construction Improving on RRG, behind on both on Sectors.

**Construction is not the cause, measured.** Sectors' 6M and 1M figures recomputed on the RRG's price
frame (`adj_close` rather than `deep_adj_close`) move by at most 0.05 pts. The two frames' daily returns
agree on all 192,941 stock-days since 1 Nov 2025 (none differs by 0.1 pt). The RRG's market (stocks in
industries of two or more) and Sectors' market (every stock with an industry) differ by at most 0.03% on
any day.

**What each axis measures, in plain terms.** RRG across: is relative strength above its own recent
average (a relative uptrend, lagged by smoothing)? Sectors across: is the industry ahead of the market
over six months? RRG up: did that across-figure rise over the last five sessions? Sectors up: is the
industry ahead over the last month? These are different questions. Matching them is a choice, not a fix.

**Two more readings of an industry, seen on the way.** Sectors' leaderboard ranks by the median stock's
3-month and 6-month return, and its leadership map by one month against the market with breadth. The
Dashboard's section 7 reads `compute_rrg_data` (the same RRG). The Dashboard's "Which sectors lead?"
reads NSE's sector indices against the Nifty 500 over three months and one month (S109).

## 1. Formula: what our code computes

`src/ui/views/rrg_view.py`, `compute_rrg_data`, default settings:

| Step | Ours |
|---|---|
| Input prices | Daily closes from the ranking's price store (`adj_close`, Screener, NSE for gaps), all sessions; nothing is resampled to weeks |
| Industry series | Mean of member stocks' daily returns each session (equal weight, rebalanced daily); industries with at least 2 ranked stocks; today's members and today's industry for every past date |
| Benchmark | Default: every stock on the chart, built the same way. Options: Nifty 500 and Nifty 50 closes from `data/benchmarks.csv` |
| RS line | Cumulative product of (1 + industry return) ÷ cumulative product of (1 + benchmark return), over sessions both have |
| Smoothing | Exponential average of the RS line, span = lookback ÷ 2 = 30 sessions (pandas `ewm(span=30)`, adjusted) |
| RS-Ratio (raw) | Smoothed RS ÷ its own 60-session simple average (lookback 12 weeks × 5); 1 = at its own recent average |
| RS-Momentum (raw) | RS-Ratio ÷ RS-Ratio five sessions earlier ("weekly") or one session earlier ("daily") |
| Normalisation | 100 + (raw − 1) ÷ σ × 6.5, where σ is the population SD of today's raw values across the industries shown; the same σ scales every tail point |
| Meaning of 100 | Raw ratio of 1: relative strength at its own 60-session average; raw momentum of 1: the ratio unchanged over five sessions. Not "level with the benchmark" over any fixed window |
| Quadrant | Sign of raw − 1 on each axis (unchanged by σ) |
| Tail | Six earlier points at positions −30, −25, −20, −15, −10, −5 sessions, then the last session (−1) |
| "Daily" setting | Same lookback (60 sessions) and smoothing, so the same RS-Ratio; momentum over one session; tail of six sessions though the caption says "6w" |

## 2. Formula: what the published sources say

All read on 21 Nov 2026.

| Source | What it says (quoted) | Ours | Changes a quadrant? |
|---|---|---|---|
| StockCharts ChartSchool, "RRG Relative Strength" (https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/rrg-relative-strength) | "RS-Ratio is an indicator that measures the trend for relative performance." "RS-Momentum is an indicator that measures the momentum (rate-of-change) of RS-Ratio." "RS-Ratio and RS-Momentum are 'normalized,' which means these indicators are expressed in the same unit of measure" and "fluctuate above/below the same level (100), regardless of the specific security being assessed." "there will already be upward movement in the price relative before RS-Ratio crosses above 100." "At least 50 data points are required ... about 50 days of historical data for daily charts and 250 days for weekly charts." No formula given | Same idea: a lagged trend of RS, and its rate of change, around 100. Ours normalises across the industries shown, not per series | The cross-section scale: no. The lag: it is the method, but the page must describe it |
| StockCharts ChartSchool, "Relative Rotation Graphs (RRG Charts)" (https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-types/relative-rotation-graphs-rrg-charts) | "A sector is in the leading quadrant (green) when RS-Ratio and RS-Momentum are above 100 (+/+)"; weakening "+/-", lagging "-/-", improving "-/+". "This indicator reflects an uptrend in relative performance when above 100." "The chosen timeframe affects RRGs just like regular bar charts." | Same quadrant rule | No |
| Julius de Kempenaer, "What does a stock with an RS-Momentum value of 105 equate to in respect of time?", StockCharts, 14 Dec 2015 (https://articles.stockcharts.com/article/articles-rrg-2015-12-what-does-a-stock-with-an-rs-momentum-value-of-105-equate-to-in-respect-of-time/) | "A JdK RS-Ratio value over 100 signals an uptrend in the relative strength line". "a value of 105 (or any other value for that matter) does not relate to any performance over a period of time". The lines "are normalized which makes them comparable across the universe on which they are applied". No formula | Our page says right of 100 is "gaining on it over the lookback", a statement about performance over a period, which the author says the value is not | The wording, not the quadrant |
| de Kempenaer and Neil, Asset Allocation presentation, Technical Analyst, 29 Apr 2019 (cited in TODO S147) | As quoted in S147: Leading, "Security is outperforming the benchmark" and "one of the best in the group"; JdK RS-Momentum "a normalized version of the Rate of Change of JdK RS-Ratio" | Momentum as rate of change of the ratio: same | No |
| Thomson Reuters Eikon RRG guide, 2013 (cited in TODO S147) | As quoted in S147: both formulas "proprietary and cannot be revealed", normalised so constituents compare like for like | Ours is a reconstruction | Cannot be known |
| sharpely, "RRG Explained: RS-Ratio and RS-Momentum, Broken Down" (https://sharpely.in/blogs/understanding-engine-rrg-complete-breakdown-rs-ratio-rs-momentum/; no date shown) | "The JDK RS-Ratio is a proprietary indicator designed to measure the trend strength of a security's relative performance". "It acts as a lagging indicator, confirming trends rather than predicting them". "RS-Momentum measures the rate of change of the RS-Ratio itself". No formula. Our function's docstring names "Sharpely / JdK" | Same description; no formula to compare | n/a |
| An0n1mity/RRGPy, `RRGIndicator.py` (https://raw.githubusercontent.com/An0n1mity/RRGPy/main/RRGIndicator.py) | Weekly closes (`interval="1wk"`); `rs = 100 * ticker / benchmark`; RS-Ratio `100 + (rs - rs.rolling(14).mean()) / rs.rolling(14).std(ddof=0)`; ROC of the ratio against its second value; RS-Momentum `101 + z-score(ROC, 14)` | Theirs: weekly closes, a 14-week z-score per series. Ours: daily, an EMA over its own average, scaled across industries | Measured below: 36 of 101 against StockCharts, ours 35 |
| BennyThadikaran/RRG-Lite, `src/RRG.py` and README (https://raw.githubusercontent.com/BennyThadikaran/RRG-Lite/main/src/RRG.py) | `rs = (stock / benchmark) * 100`; ratio `((rs - mean_14) / std_14) + 100`; momentum a z-score of the ratio's change from 52 periods back; README: weekly, "a 14-week average", and the calculations are "not yet at the level of the original Relative Rotation Graph (RRG) implementation" | As above | Same as RRGPy here: 36 of 101 |
| Pineify, "Relative Rotation Graph" workflow (https://pineify.app/tradingview/workflows/relative-rotation-graph, "last verified 2026-10-21") | A teaching proxy: `X = 100 × r / mean(r over 3)`, `Y = 100 × X[t] / X[t-1]`; "It is not an exact implementation of the proprietary JdK indicators or an official RRG product." | Ours has the same shape (ratio over its own average; momentum as a ratio of ratios) with longer windows | n/a |
| Optuma, "Scripting Guide for Relative Rotation Graphs" (https://www.optuma.com/blog/scripting-for-rrgs, 21 May 2021) | Exposes `JDKRS().Ratio` and `.Momentum`; no formula | n/a | n/a |

**Where ours matches.** Two axes, a trend of relative strength and its rate of change, 100 as the line,
the same quadrant rule and names, a benchmark chosen by the reader.

**Where ours differs.** (1) Daily data with a five-session step, not weekly closes. (2) An exponential
average over its own 60-session average, not a z-score. (3) Scale from the cross-section of today's
industries, not from each series' own history; de Kempenaer says the licensed lines are comparable
"across the universe", which a per-series normalisation gives and ours does not. (4) Sessions, not
weeks, set the tail. None of (1)-(3) is wrong in itself, since the licensed formula is not public; (4)
is an error.

**Does a difference change a quadrant?** The scale (3) cannot. The others can, and do: the "Daily"
setting changes 4 of 20 industries' quadrants against "Weekly" on 20 Nov (the RS-Ratio side is
identical; only momentum differs). Against StockCharts, see the next section.

## 3. Data: against an outside RRG and NSE's own indices

### 3.1 NSE's index closes against our files

| Series | Shared sessions | Largest difference |
|---|---|---|
| Nifty 500, NSE file vs `data/benchmarks.csv` | 552 (2 Sep 2024 to 20 Nov 2026) | 0 |
| Nifty 50, same | 552 | 0 |
| Nifty Total Market, NSE file vs `data/nse_total_market.csv` | 549 | 0 |

Our files carry NSE's closes without error. This is the same origin (both are NSE), so it confirms the
copy, not the price.

### 3.2 Our method on NSE sector indices, against StockCharts' licensed RRG

The StockCharts notes (Milan Vaishnav, "Week Ahead", benchmark "the CNX500 (NIFTY 500 Index)"):

| Note | Published | Session charted (assumed) | URL |
|---|---|---|---|
| Nifty's Resilience Stands Out; A Healthy Pause May Strengthen the Rally | 14 Nov 2026 | Fri 13 Nov | https://articles.stockcharts.com/article/week-ahead-niftys-resilience-stands-out-a-healthy-pause-may-strengthen-the-rally/ |
| After Nifty's Vertical Rally, Focus Shifts to Holding Recent Gains | 8 Nov 2026 | Fri 6 Nov (the Sun 8 Nov Diwali session may be in it; not known) | https://articles.stockcharts.com/article/week-ahead-after-nifty-vertical-rally-focus-shifts-to-holding-recent-gains/ |
| Five earlier notes, 7 Feb to 17 Oct 2026 | | as listed in `scripts/research/rrg_vs_stockcharts.py` (S109) | |

14 Nov note, quoted: "the Nifty Financial Services Sector has rolled into the leading quadrant. Besides
this, the IT Services Sector, BankNifty, Media, and Pharma sector indices are also inside the leading
quadrant." "The Nifty Realty Index is the only sector index in the weakening quadrant." "The Nifty
Energy, Midcap100, Auto, and Metal Indices are inside the lagging quadrant." "The FMCG, PSE, and
Infrastructure Sector Indices are inside the improving quadrant of the RRG."

13 Nov 2026, NSE sector index against the Nifty 500 (our method's raw values ×100, unscaled):

| Index | StockCharts | Ours | Ours ratio · momentum | RRGPy | RRG-Lite |
|---|---|---|---|---|---|
| Financial Services | Leading | Leading | 101.5 · 100.9 | Leading | Leading |
| IT | Leading | Weakening | 105.2 · 98.8 | Weakening | Weakening |
| Bank | Leading | Leading | 101.5 · 100.5 | Leading | Leading |
| Media | Leading | Weakening | 105.2 · 99.5 | Leading | Leading |
| Pharma | Leading | Weakening | 103.2 · 99.9 | Weakening | Weakening |
| Realty | Weakening | Improving | 99.6 · 100.7 | Leading | Leading |
| Energy | Lagging | Lagging | 98.0 · 99.4 | Lagging | Lagging |
| Midcap 100 | Lagging | Lagging | 97.8 · 99.6 | Lagging | Lagging |
| Auto | Lagging | Improving | 98.4 · 100.6 | Lagging | Lagging |
| Metal | Lagging | Lagging | 97.6 · 99.4 | Lagging | Lagging |
| FMCG | Improving | Lagging | 98.7 · 100.0 | Improving | Improving |
| PSE | Improving | Lagging | 98.4 · 99.4 | Lagging | Lagging |
| Infrastructure | Improving | Leading | 100.6 · 100.1 | Leading | Leading |
| **Same quadrant** | | **5 of 13** | | 8 of 13 | 8 of 13 |

All seven notes (101 index-weeks):

| Method | Same quadrant | Same side of 100 across (RS-Ratio) | Same side of 100 up (RS-Momentum) |
|---|---|---|---|
| Ours | 35 (35%) | 75 (74%) | 56 (55%) |
| RRGPy (weekly, 14-week z-scores) | 36 (36%) | 72 (71%) | 57 (56%) |
| RRG-Lite (weekly, 14-week z-scores) | 36 (36%) | 72 (71%) | 57 (56%) |

S109 (8 Nov 2026) tried about 380 variants on Screener's closes; the best reached 70% on four notes and
64% on a held-out note, below the owner's 80% bar, and the Dashboard dropped the RRG for plain returns.
Today's result is the same finding on NSE's own closes and two more notes: no public formula
reproduces the licensed RRG, and ours reproduces it least on the momentum axis.

### 3.3 Our industries against NSE's matching sector index

Closes to 20 Nov 2026. "Ours" is the equal-weighted industry of today's ranked members; NSE's indices
are free-float cap-weighted. Correlation of daily returns; return over the window; gap = ours − NSE.
NSE's daily file carries several of these indices only from 15 Jun 2026 or 17 Feb 2026, so their
12-month figures are not available here.

| Our industry (stocks) | NSE index | Corr 3M | Ours 3M | NSE 3M | Gap 3M | Corr 12M | Gap 12M |
|---|---|---|---|---|---|---|---|
| Automobile and Auto Components (49) | Nifty Auto | 0.80 | −2.1% | −1.8% | −0.3 | 0.86 | +12.3 |
| Capital Goods (121) | Nifty Capital Goods | 0.95 | −8.1% | −9.6% | +1.5 | 0.92 | n/a |
| Chemicals (44) | Nifty Chemicals | 0.87 | −7.7% | −5.3% | −2.5 | 0.90 | +5.2 |
| Construction (23) | Nifty Construction | 0.97 | −7.9% | −5.7% | −2.2 | 0.97 | n/a |
| Construction Materials (12) | Nifty Cement | 0.98 | −1.6% | −0.4% | −1.2 | 0.98 | n/a |
| Consumer Durables (40) | Nifty Consumer Durables | 0.74 | −5.3% | −5.0% | −0.3 | 0.84 | −2.4 |
| Consumer Services (43) | Nifty Consumer Services | 0.85 | −4.1% | +1.7% | −5.8 | 0.83 | n/a |
| Fast Moving Consumer Goods (43) | Nifty FMCG | 0.73 | −3.6% | +1.4% | −5.0 | 0.73 | +14.7 |
| Financial Services (117) | Nifty Financial Services | 0.77 | −1.5% | +10.2% | −11.6 | 0.86 | +1.4 |
| Healthcare (67) | Nifty Healthcare Index | 0.80 | +0.6% | +6.1% | −5.6 | 0.79 | +8.1 |
| Information Technology (40) | Nifty IT | 0.61 | −6.5% | +2.1% | −8.6 | 0.74 | +2.1 |
| Media Entertainment & Publication (8) | Nifty Media | 0.98 | +9.1% | +8.3% | +0.9 | 0.96 | +9.8 |
| Metals & Mining (27) | Nifty Metal | 0.93 | −10.9% | −6.0% | −4.8 | 0.92 | −10.8 |
| Oil Gas & Consumable Fuels (19) | Nifty Oil & Gas | 0.78 | +0.2% | +3.2% | −3.1 | 0.86 | +7.0 |
| Power (23) | Nifty Power | 0.91 | −5.7% | −2.4% | −3.3 | 0.89 | n/a |
| Realty (20) | Nifty Realty | 0.91 | −1.6% | +3.4% | −5.0 | 0.93 | −9.9 |
| Telecommunication (12) | Nifty Telecommunications | 0.88 | −5.0% | 0.0% | −5.1 | 0.88 | n/a |
| Services (24) | Nifty Services Sector | 0.29 | +2.2% | +6.9% | −4.8 | 0.66 | +24.4 |
| All ranked stocks (750) | Nifty500 Equal Weight | 0.98 | −3.9% | −3.6% | −0.3 | 0.99 | +5.5 |

Reading: 14 of 18 industries correlate 0.77 or more with NSE's index over three months; three-month gaps
run from +1.5 to −11.6 pts. The equal-weighted market tracks NSE's Nifty500 Equal Weight closely (0.98;
−0.3 pts over three months), so the market construction is a recognised one; over 12 months it is
5.5 pts ahead, as ours adds about 250 smaller stocks. "Services" is not NSE's Services Sector index
(0.29): NSE's index holds banks and IT; our NSE industry "Services" holds logistics and similar.

Quadrants on 20 Nov, our method, each pair built alike:

| Industry | Page (equal weight vs equal-weighted market) | NSE index vs Nifty Total Market |
|---|---|---|
| Same quadrant | 11 of 18 | |
| Differ | Auto, Construction, Construction Materials, FMCG, Oil Gas, Power, Services | |

Against a cap-weighted benchmark, equal-weighted industries read Lagging in 16 of 18 (17 of 20 on the
page's Nifty 500 option), the size effect S147 found. The page's Nifty 500 and a Nifty Total Market
benchmark give the same counts today (17 Lagging, 1 Leading, 1 Weakening, 1 Improving).

## 4. Findings, ranked by how much they would mislead a reader

1. **Horizontal axis described as "ahead of the benchmark"; it is a lagged trend.** Help text (Chart
   settings): "100 on each axis is the benchmark: right of it, an industry is gaining on it over the
   lookback". CHANGELOG 20 Nov: "RRG: Leading now means ahead of the benchmark". Measured: IT, Consumer
   Services and Telecommunication sit right of 100 while behind over the 12-week lookback by 1.8, 1.1
   and 2.9 pts. No industry sits left of 100 while ahead over 12 weeks. A reader would buy into IT as a
   relative uptrend that ended in October. **Fix:** under (c), the axis is the plain return gap, which
   says what it is; under (b), the words become "its strength against the market is above its own
   12-week average (a relative uptrend, which lags)", and S147 (a)'s test is rewritten to what the code
   can promise.
2. **Two pages, two answers, no reason given** (S147 reopened). 10 of 19 industries. All windows and
   smoothing (table above). **Fix:** D1.
3. **Implied JdK equivalence.** Docstring "Sharpely / JdK", the ® in the module title, S147 "follow the
   real RRG method". Measured: 35% quadrant agreement with the licensed RRG over 101 index-weeks.
   **Fix:** name it as our measure; no JdK, no ®; a note that published RRGs use a proprietary formula
   and can differ.
4. **Tail off the weekly grid, off by one** (`rrg_view.py`, `range(-n_trail * step, 0, step)` with the
   current point at `iloc[-1]`). On 20 Nov: Mondays and the Diwali Sunday; last step 4 sessions; the
   momentum's base (13 Nov) not on the tail. On a Wednesday (18 Nov as of) the points fall on Wed 7 Oct,
   Wed 14 Oct, Thu 22 Oct, Thu 29 Oct, Thu 5 Nov, Thu 12 Nov, Wed 18 Nov. **Fix:** tail points on each
   week's last session (Friday or the last session before a holiday), the current point on the data
   date, labelled "week to date" when the week is not complete; momentum from the same points.
5. **Momentum's direction against the week's move.** In 5 of 20 the momentum side is opposite to the
   week's relative move: Healthcare +0.8 pts, Oil Gas +1.3, Consumer Services +0.3 read momentum down;
   Services −0.6 and Construction −1.3 read up. This is the smoothing, not an error; the page must not
   call the vertical axis "this week's change".
6. **Numbers scaled by the cross-section** (Textiles 107.1 → 112.2 with two industries removed). The
   page's figures look like JdK values (105 = strong) and are not comparable across days or scopes, or
   with the Dashboard's section 7 when its set differs. **Fix:** show plain points (pts ahead) under (c);
   under (b), normalise each series on its own history.
7. **"Daily" is mostly the same chart.** Same RS-Ratio as weekly; the caption says "tail 6w" for six
   sessions. **Fix:** drop "Daily", or give it daily windows and a caption in sessions.
8. **NSE's names on equal-weighted groups.** "Financial Services" −1.5% against Nifty Financial Services
   +10.2% over three months. **Fix:** one line on the page: industries are NSE's classification,
   equal-weighted, not NSE's sector indices (S166 item 8).
9. **Benchmark labels and sources.** The Nifty 500 option reads `data/benchmarks.csv` (keys named after
   Yahoo tickers; no Yahoo download), other pages `data/benchmark_indices.csv`; both equal NSE's archive
   on every shared day (3.1). No Total Market option (S165). **Fix:** one loader (S154); Nifty Total
   Market in place of the Nifty 500 (S165), named.
10. **Survivorship in the tail and the as-of slider.** Today's members and today's classification are
   used for every past date, up to 120 sessions back (PAGE_DESIGN §5.1). Not measured; a lead.
11. **The Dashboard reads the same function** (`dashboard_home_view.py` section 7 and the strong/weak
   cards: "the RRG quadrant over 12 weekly readings, 3 months ago → 1 month ago → now"; caption "100 = all
   ranked stocks, equal weight"). Every fix here moves the Dashboard; its requirements list must be
   re-run.

## 5. Dates and staleness (S164 standard)

| Element | Ends on | Class | Note |
|---|---|---|---|
| Every industry's current point | 20 Nov (the data date) | CURRENT | Reproduced |
| Caption "Weekly · tail 6w · lookback 12w · 20 Nov 2026" | 20 Nov | CURRENT | |
| Tail | starts Fri 9 Oct 2026; points 9 Oct, 16 Oct, 26 Oct, 2 Nov, 8 Nov, 16 Nov, 20 Nov | FAULT | Not week ends (finding 4) |
| Momentum | 20 Nov against 13 Nov | CURRENT | Base not on the tail |
| 12-week lookback | 26 Aug to 20 Nov 2026 (60 sessions) | CURRENT | |
| Mid-week behaviour | as-of 18 Nov: ends 18 Nov, tail on Wednesdays and Thursdays | CURRENT, by computation | Not seen in a browser on a mid-week day (today is Saturday, data Friday) |
| Weekly sampling drops the current week? | No: nothing is resampled | | A fix that samples Friday closes must keep the current session as the last point |
| As-of slider | last 120 sessions of `adj_close` | | Past dates use today's members (finding 10) |

## 6. What a fund manager brings to this page

1. Which industries are gaining on the market now, and which are losing ground?
2. Which are turning: improving from behind, or rolling over from ahead, and since when?
3. Where do the book's industries sit (PAGE_DESIGN §4.3: held industries filled and sized by holdings)?
4. Can I trust it: does it agree with Sectors and with a published RRG, and what is it built from?
5. Has a quadrant meant anything for the next month? Not tested (PAGE_DESIGN §5.6). Until a test
   passes, the page says "describing is not forecasting" and makes no claim about what follows.

## 7. Decisions for the owner (recommendation first)

- **D1. One reading or two (S147).** Recommended **(c)**: the page draws Sectors' two figures (six months
  and one month against all ranked stocks) as a rotation chart with weekly tails; the pages agree by
  construction, any point can be checked on a price chart, and Sectors links here instead of repeating
  the chart. Evidence: the JdK-style reconstruction matches the licensed RRG on 35% of quadrants; its
  axis words are wrong for 3 of 20 industries today; and S109 already chose plain returns for the
  Dashboard on the same grounds. Second choice **(b)**: keep the reconstruction, fix findings 1, 4, 5, 6,
  and state on both pages why they differ, with each industry's plain 12-week and 1-week figures beside
  its point. Not recommended **(a) as asked in S147**, making the reconstruction agree with Sectors by
  forcing its windows: that is (c) with extra smoothing nobody can check.
- **D2. Default benchmark.** Recommended: keep all ranked stocks, equal-weighted (S147), named on the page;
  offer Nifty Total Market in place of the Nifty 500 (S165), with one sentence that cap-weighted
  benchmarks put most equal-weighted industries behind (17 of 20 today). Drop Nifty 50 unless wanted.
- **D3. Name.** Recommended: "Relative rotation", no ®, no JdK; one note that published RRGs use a
  licensed formula and can place an industry differently.
- **D4. Scopes.** Recommended: keep Industries and Top stocks; keep TradingView sectors only if the
  owner wants a second taxonomy on this page (Sectors already offers it).
- **D5. Daily setting.** Recommended: remove it (finding 7).

## Not checked

- The deployed site; this run used the release files, not R2 (no R2 keys in this session).
- Any public RRG of our own industry groups: none exists, since the groups are ours. The comparison
  used NSE's sector indices as a stand-in.
- sharpely's own RRG figures (the site is a script-drawn app; only its explainer text was read).
- The 2019 Technical Analyst presentation and the 2013 Eikon guide were not re-read today; their quotes
  are from TODO S147. No copy was found by web search on 21 Nov 2026.
- Which session StockCharts' 8 Nov note charts (6 Nov, or including the 8 Nov Diwali session).
- Whether StockCharts' India RRG uses weekly closes for these notes (assumed, as their default).
- Survivorship in the tail (finding 10) and its size.
- Price adjustments for corporate actions in `adj_close` (owned by the nightly checks).
- The Top stocks and TradingView sectors scopes, and benchmarks other than the default, in a browser.
- The page at 412 px, dark theme, and the layout audit (the redesign will run them).
- Whether the RRG quadrant predicts anything (no signal test exists).
- Whether "Relative Rotation Graph" or "RRG" may be used without a licence (StockCharts: "registered
  trademarks of RRG Research"); a legal question, not checked.
