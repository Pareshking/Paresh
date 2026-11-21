# Indices page: research brief (literature, industry practice, shortlist)

Prepared 21 Nov 2026 for the owner's ask: "Like sector page, we should have indices page.
What you want to show on that page which gives greater insights to the investors?"
Research only; nothing in the repository was changed.

## 0. How to read this brief

Each source carries a tag for how far it was checked in this session:

- **[P]**: primary source read this session (the PDF or the publisher's page).
- **[S]**: the finding comes from a search-result summary or a secondary write-up of the
  primary source. The citation is right but the exact numbers were not read in the original.
- **[K]**: a well-known published paper or book that I cite from prior knowledge. It was not
  opened this session. Check the quoted finding against the original before it goes on the page.

**Data fact checked this session [P].** NSE's daily all-indices file (`ind_close_all_DDMMYYYY.csv`,
which has 169 index rows on 20-11-2026) carries these columns: `Index Name, Index Date, Open, High,
Low, Close, Points Change, Change(%), Volume, Turnover (Rs. Cr.), P/E, P/B, Div Yield`. The values are
**price-index** values, not total-return (TRI). Example: Nifty 50 on 20-11-2026 closed at 25800.6,
with P/E 21.02, P/B 3.17 and dividend yield 1.32.

---

## 1. What predicts or explains index and factor returns, and what is noise

### 1.1 Time-series momentum and trend at the index level

| Source | Finding used | Out of sample? | Indian test? |
|---|---|---|---|
| Moskowitz, Ooi & Pedersen (2012), "Time Series Momentum", *Journal of Financial Economics* 104(2):228-250. https://doi.org/10.1016/j.jfineco.2011.11.003 [K] | In 58 futures and forwards (equity indices, bonds, currencies, commodities), an instrument's own past 12-month excess return predicts its return over the next 1 to 12 months. The effect partly reverses over longer horizons. The diversified TSMOM portfolio did best in extreme markets. | It holds across asset classes. It was weaker after 2009 (the AQR managed-futures drawdown of the 2010s). | The 58 instruments do not include Indian indices. |
| Hurst, Ooi & Pedersen (2017), "A Century of Evidence on Trend-Following Investing", *Journal of Portfolio Management* 44(1); AQR working paper 2014. https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing [S] | A trend strategy in 67 markets (11 equity indices among them) since 1880 had positive returns in every decade. It had low correlation to stocks and bonds. It did well in 8 of the 10 largest 60/40 drawdowns (the "trend smile"). Drawdowns of about 25% lasted for years. | It is an extended-sample test across decades, which counts as out of sample relative to MOP. | No Indian index is in the sample. |
| Huang, Li, Wang & Zhou (2020), "Time-Series Momentum: Is It There?", *Journal of Financial Economics* 135(3):774-794 [K] | The counterpoint. Asset-by-asset predictive regressions show little evidence that an asset's own past return predicts its own future return. Most of TSMOM's profit comes from a pooled-regression effect: assets with high average returns are mostly long. | It casts doubt on the "predicts" reading of TSMOM. | No. |
| Kim, Tse & Wald (2016), "Time series momentum and volatility scaling", *Journal of Financial Markets* 30 [K] | Much of the TSMOM alpha comes from scaling positions by volatility, not from the sign of the trend. | Same caveat as above. | No. |
| Faber (2007), "A Quantitative Approach to Tactical Asset Allocation", *Journal of Wealth Management* 9(4); SSRN 962461, updated 2013. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461 [K] | Holding an asset class only when its monthly close is above its 10-month simple moving average gave equity-like returns with much smaller drawdowns, 1901 to 2012 (US). The benefit is **risk reduction**, not higher return. | After 2009 the rule had whipsaw losses (2010, 2011, 2015-16, 2018, 2020 in the US). Faber's own update says the main value is avoiding deep bear markets. | No. |
| Zakamulin (2017), *Market Timing with Moving Averages*, Palgrave Macmillan [K] | Out-of-sample tests of moving-average rules on US stocks: they beat buy-and-hold mainly by sitting out bear markets. In-sample results overstate the edge, and performance varies widely over time. | It is an out-of-sample study. | No. |
| Slivka, Keswani & Li (2014), *Indian Journal of Finance*: 80 trend rules on Nifty, 2005-2012 [S] (https://www.indianjournalofcapitalmarkets.com/index.php/IJF/article/download/71980/58008/125426) | The rules helped in the sharp 2008 decline. They did poorly in gradually rising or trendless markets. | It is in-sample only, as far as the summary shows. | **Yes. This is the only Indian academic test I found, and it is short and weak.** |

**Verdict.** Index trend is the best-documented single signal for *risk* (it avoids the deep part
of bear markets). It is weak as a *return* predictor, and it whipsaws in range-bound years.
**I found no rigorous out-of-sample test on Nifty.** Our own test is required.

### 1.2 Factor momentum

| Source | Finding used |
|---|---|
| Ehsani & Linnainmaa (2022), "Factor Momentum and the Momentum Factor", *Journal of Finance* 77(3):1877-1919, NBER WP 25551. https://www.nber.org/papers/w25551 [S] | Factors with positive returns over the prior year keep earning positive returns. Factors with negative returns earn about zero. Factor momentum is concentrated in the factors that explain most of the cross-section. Stock momentum largely reflects factor momentum: "momentum is not a distinct risk factor; it times other factors". |
| Gupta & Kelly (2019), "Factor Momentum Everywhere", *Journal of Portfolio Management* 45(3), Quant special issue. https://www.aqr.com/Insights/Research/Working-Paper/Factor-Momentum-Everywhere [S] | 49 of 65 factors show significant time-series momentum. A **1-month** lookback is strongest. The effect holds internationally and survives transaction costs. It complements stock momentum. |

**Out of sample:** both papers use long US and international samples, and the international data
act as a partial out-of-sample test. **Indian test:** none found. NSE has factor indices (Momentum,
Quality, Value, Low Volatility, Alpha, Equal Weight) with back-calculated history from 2005 and live
history only from launch (e.g. Nifty200 Momentum 30 launched 25 Aug 2020 [S, NSE press release
https://niftyindices.com/Press_Release/ind_prs25082020.pdf]). A "factor index relative strength"
table is therefore **a candidate signal that must be tested on our data.**

### 1.3 Industry (sector) momentum

- Moskowitz & Grinblatt (1999), "Do Industries Explain Momentum?", *Journal of Finance* 54(4):1249-1290 [K]:
  industry portfolios show strong momentum, including at a 1-month horizon, where individual stocks
  instead reverse. Industry momentum accounts for much of individual-stock momentum.
- Grundy & Martin (2001), *Review of Financial Studies* 14(1) [K]: stock momentum is **not** fully
  explained by industry momentum. Both effects exist.
- **Indian test:** none found in a peer-reviewed source. NSE's sector indices are cap-weighted and
  some are very concentrated (e.g. Nifty Bank, Nifty IT). Our test of sector-index relative strength
  should use the sector page's existing data.

### 1.4 Valuation spreads and factor timing

| Source | Finding |
|---|---|
| Arnott, Beck, Kalesnik & West (2016), "How Can 'Smart Beta' Go Horribly Wrong?", Research Affiliates. https://www.researchaffiliates.com/content/dam/ra/publications/pdf/442-how-can-smart-beta-go-horribly-wrong.pdf [S] | Much of the recent return of many factors came from rising relative valuation, which is not repeatable. Relative valuation (factor P/B divided by market P/B) predicts 5-year factor returns, and this is shown for US, developed and emerging markets. |
| Arnott et al. (2016), "Timing 'Smart Beta' Strategies? Of Course! Buy Low, Sell High!" https://www.researchaffiliates.com/content/dam/ra/publications/pdf/541-timing-smart-beta.pdf [S] | Follow-up: valuation-based timing of factors. |
| Asness, Chandra, Ilmanen & Israel (2017), "Contrarian Factor Timing is Deceptively Difficult", *Journal of Portfolio Management* 43(5):72-87. https://www.aqr.com/Insights/Research/Journal-Article/Contrarian-Factor-Timing-is-Deceptively-Difficult [S] | Value-spread timing looks good in isolation only because it repeats the value factor. In a multi-style portfolio that already holds value, it adds little and cuts diversification. They found no robust evidence that it delivers meaningful outperformance, even at extreme valuations or over longer holding periods. |
| Haddad, Kozak & Santosh (2020), "Factor Timing", *Review of Financial Studies* 33(5) [K] | The counterpoint. The book-to-market spreads of the **dominant principal components** of factors predict their returns, with modest out-of-sample R². This is the strongest academic case for factor timing, and it is about PC portfolios, not single long-only indices. |
| Ilmanen, Israel, Moskowitz, Thapar & Lee (2021), "How Do Factor Premia Vary Over Time? A Century of Evidence", *Journal of Investment Management* [K] | Over 100+ years and many asset classes, factor premia are robust. Timing them with value spreads, momentum, volatility or macro variables gives weak and statistically fragile gains. |
| AQR, Asness (2020), "Is (Systematic) Value Investing Dead?" and "The Long Run Is Lying to You" (2021) [K] | Value spreads are shown as a percentile chart (the cheap-minus-expensive ratio against its history). AQR uses them as context and as a risk warning, not as a switching rule. |

**Verdict.** A factor index's relative valuation (its P/B or P/E divided by its parent's) is
**context, not a timing signal**. The out-of-sample evidence for timing long-only factor exposure
with it is weak (Asness 2017; Ilmanen 2021). The supporting evidence (Arnott 2016; Haddad 2020) is
about long horizons or long-short PC portfolios. It has not been tested in India.

### 1.5 Valuation and long-horizon market returns

| Source | Finding |
|---|---|
| Campbell & Shiller (1988, 1998), "Valuation Ratios and the Long-Run Stock Market Outlook", *Journal of Portfolio Management* 24(2) [K] | P/E10 (CAPE) and dividend yield predict 10-year real returns in US data. They do not predict 1-year returns usefully. |
| Goyal & Welch (2008), "A Comprehensive Look at the Empirical Performance of Equity Premium Prediction", *Review of Financial Studies* 21(4) [K] | Most valuation predictors (D/P, E/P, B/M) **fail out of sample** at the 1-year horizon. They do not beat the historical mean. |
| Asness (2012), "An Old Friend: The Stock Market's Shiller P/E", AQR [K] | Higher CAPE goes with lower average 10-year returns, but the spread of outcomes within each band is very wide. It is a poor tactical timing tool. |
| Sharma (2025), "Multi-Scale Analysis of Nifty 50: Return Characteristics, Valuation Dynamics and Market Complexity (1990-2024)", arXiv 2509.00697. https://arxiv.org/abs/2509.00697 [S] | Nifty P/E bands give conditional forward-return distributions over 1-7 years. Below P/E 13 no loss was observed. Above 27, returns were unstable and break-even periods long. **This is a preprint, not peer-reviewed. The sample has few independent observations.** |
| StableInvestor (2019), "Nifty P/E Ratio & Returns: 20-year analysis 1999-2019". https://www.stableinvestor.com/2019/01/nifty-pe-ratio-returns-analysis-updated.html [S] | Practitioner work, not academic. High P/E entry gave lower 3-10 year returns. At the same P/E (17.5), 7-year returns ranged from 7.7% to 26.1%. |
| Asian Journal of Management, NSE 200 2015-2018 (https://indianjournals.com/article/ajm-10-1-003) [S] | This is a price-level regression, not a forward-return test. **Not usable as evidence.** |

**A major Indian data break [S, several sources agree, with NSE's own page as the methodology
reference https://www.nseindia.com/products-services/indices-price-earnings-ratio]:** NSE computed
index P/E from **standalone** trailing-4-quarter earnings until March 2021 and from **consolidated**
earnings from April 2021. Nifty 50 P/E went from about 40.1 (Mar 2021) to about 32.7 (Apr 2021)
because of the method change alone (Capitalmind, https://www.capitalmind.in/nifty-pe-ratio/). P/B
also moved to consolidated book value (Angel One). **Any P/E or P/B percentile that spans April
2021 compares two different numbers.** It has to be split at that date or adjusted, and the
adjustment cannot be independently verified. NSE's P/E also counts losses ("including profits and
losses"), so small-cap and thematic index P/Es jump when a few constituents swing to loss.

**Overlapping windows.** From 1999 (Nifty P/E history) to 2026 there are fewer than three
independent 10-year windows and about five independent 5-year windows. From our file's Oct 2012
start, there are 2.8 independent 5-year windows. "P/E band → 5-year forward return" tables built
from overlapping daily windows look precise but rest on a handful of real observations.

**I found no peer-reviewed study that tests NSE P/E bands out of sample, and no SEBI study on this.**

### 1.6 Size and style cycles; momentum crashes

- Daniel & Moskowitz (2016), "Momentum Crashes", *Journal of Financial Economics* 122(2):221-247 [K].
  Momentum crashes happen in "panic states": after a market decline (negative 24-month market return),
  at high volatility, and when the market rebounds. The short side (past losers) then rallies. A
  dynamic, volatility- and state-scaled momentum strategy roughly doubles the Sharpe ratio. This is
  **directly relevant to a 20-stock momentum book.** Our book is long-only, so the crash shows up as
  sharp underperformance, not as a loss on short positions.
- Barroso & Santa-Clara (2015), "Momentum Has Its Moments", *Journal of Financial Economics*
  116(1):111-120 [K]. Scaling momentum by its own realised volatility over the past 6 months removes
  most crash risk.
- **India, NSE white paper [P]** (NSE Indices, "Momentum Strategy" white paper, data to 27 Feb 2026,
  https://www.niftyindices.com/docs/default-source/indices/nifty200-momentum-30/momentum-strategy-whitepaper_2026.pdf).
  Quotes:
  - Nifty200 Momentum 30 returned "19.19% versus 15.08% for Nifty 200" since April 2005 (TRI).
  - Maximum drawdowns: Nifty200 Momentum 30 68%, Nifty Midcap150 Momentum 50 73%, Nifty500 Momentum 50 70%.
    Their parents: Nifty 200 64%, Nifty Midcap 150 73%, Nifty 500 64%.
  - "during downward market phases, the same momentum exposure can lead to sharper drawdowns".
  - The momentum indices underperformed in 2008 and 2018.
  - The paper gives "Inception date is April 01, 2005" while the index was **launched 25 Aug 2020**.
    **About 15 of the 21 years are back-calculated**, and the white paper does not separate them.
- **IIMA data [S]:** Agarwalla, Jacob & Varma (2013), "Four Factor Model in Indian Equities Market",
  IIMA WP 2013-09-05, https://www.iima.ac.in/publication/four-factor-model-indian-equities-market.
  The data library is at https://web.iima.ac.in/~iffm/Indian-Fama-French-Momentum/ (new series from
  Dec 2021, data from Oct 1993; the legacy series was suspended in 2020). The library publishes
  factor returns (SMB, HML, WML) and a factor drawdown page
  (https://web.iima.ac.in/~iffm/Indian-Fama-French-Momentum/drawdown.php). It is **the independent
  Indian source** for checking our factor-index claims. I did not download the series in this session.
- **Size cycles.** I found no peer-reviewed Indian evidence that small- versus large-cap
  leadership can be timed. Asness et al. (2018), "Size Matters, If You Control Your Junk", *JFE*
  129(3) [K], find that the size premium is weak unless quality is controlled for. Showing the
  small/large ratio is descriptive; showing it as a cycle signal is not supported.

### 1.7 Dispersion and correlation regimes

- Stivers & Sun (2010), "Cross-Sectional Return Dispersion and Time Variation in Value and Momentum
  Premiums", *JFQA* 45(4) [K]: high recent cross-sectional dispersion goes with a **lower** subsequent
  momentum premium and a higher value premium (US).
- Pollet & Wilson (2010), "Average Correlation and Stock Market Returns", *JFE* 96(3) [K]: average
  correlation between stocks predicts market returns in-sample (US).
- Out of sample: modest and not robustly replicated. India: no test found. **Test before showing.**
  Our 750-stock ranking and breadth history already give us the inputs.

### 1.8 General warnings about evidence that applies to every item

- McLean & Pontiff (2016), "Does Academic Research Destroy Stock Return Predictability?", *Journal
  of Finance* 71(1) [K]: anomaly returns are about 26% lower out of sample and about 58% lower after
  publication.
- Huang, Song & Xiang (2024), "The Smart Beta Mirage", *JFQA* 59(6):2515-2546 [S]
  (https://ideas.repec.org/a/cup/jfinqa/v59y2024i6p2515-2546_2.html). For US smart-beta indices, the
  CAPM alpha was about +2.7% a year on paper before ETF listing and about -0.4% to -0.6% after.
  Factor premia, timing and capacity do not explain the drop. The authors attribute it to data
  mining in index design. **This is the single most important caution for an Indian strategy-index
  page**, because NSE's strategy indices are typically launched with 10-15 years of back-filled history.
- Israel, Jiang & Ross (2017), "Craftsmanship Alpha: An Application to Style Investing", *Journal of
  Portfolio Management* 44(2) [K]: construction details (signal definition, weighting, rebalance
  frequency, sector neutrality) change factor-portfolio returns about as much as the choice of factor.
  NSE's own momentum paper [P] shows this: quarterly rebalancing raised turnover by 20-50% and did not
  improve returns over semi-annual. So two "momentum" indices are not the same exposure.

---

## 2. Industry practice: how professionals present index and factor performance

| Publisher | What they show | Why | Status |
|---|---|---|---|
| **S&P DJI, SPIVA India** (https://www.spglobal.com/spdji/en/spiva/article/spiva-india-mid-year-2025) | Tables, not charts. (1) % of active funds underperforming the benchmark over 1, 3, 5 and 10 years, by category (large-cap, mid/small-cap, ELSS, government and composite bond). (2) Survivorship: % of funds merged or liquidated. (3) Equal- and asset-weighted fund returns against the index. (4) Quartile breakpoints. A persistence scorecard comes separately. | Survivorship-free and horizon-matched, with a TRI benchmark. | [S]. The mid-year 2025 report gives ELSS underperformance of 35.9% (1y), 52.6% (3y), 68.3% (5y) and 86.8% (10y), with the S&P BSE India BMI up 5.2% in H1 2025. The mid-year 2026 PDF exists but returned 403 to my fetch. |
| **NSE Indices factsheets and white papers** (e.g. above [P]; factsheet https://www.niftyindices.com/Factsheet/Factsheet_Nifty200_Momentum30.pdf) | Factsheets give: price and TRI returns at QTD, YTD, 1y, 5y and since inception; standard deviation and beta; P/E, P/B and dividend yield; top constituents; sector weights; methodology summary; base date and launch date. White papers give: calendar-year return tables against the parent; rolling 3, 5 and 10-year return/risk; Sharpe; drawdown charts; outperformance-instance counts. | They market the index. They report since base date, not since launch. | [P] for the momentum white paper; the factsheet contents are [K]. |
| **MSCI factor indexes and factor monitors** (MSCI "Factor Focus" and Barra factor reports) | Factor index returns over 1M, 3M, YTD, 1Y, 3Y and 5Y against the parent; active risk; factor valuation versus history (relative P/B, P/E); crowding (MSCI "Integrated Factor Crowding Model": Bayraktar, Doole, Kassam & Radchenko 2015, "Lost in the Crowd?", MSCI research). | They separate the return, the valuation and the crowding of each factor. | [K]. Not opened this session. |
| **Morningstar Style Box** | A 3 × 3 grid (size: large/mid/small × style: value/blend/growth), built from holdings. The "ownership zone" shows a fund's spread. | A quick descriptive map of where an index or fund sits. | [K]. Descriptive only. It carries no return-forecasting claim. |
| **J.P. Morgan AM, "Guide to the Markets"** (US quarterly; an Asia edition with an India page) | Forward P/E now against its 25-year average ±1σ. A scatter of forward P/E against subsequent 1-year and 5-year returns, with R² printed (low for 1y, higher for 5y). **Calendar-year return against largest intra-year decline** (bars and dots). An asset-class return quilt. | They show investors that valuation matters for long horizons and not for 1 year, and that intra-year drops are normal. | [K]. I did not confirm that a current India-specific edition exists. |
| **Goldman Sachs, Morgan Stanley and other sell-side "factor monitors"** | Weekly factor long-short returns, factor crowding, factor valuation spreads, and correlation and dispersion indicators. | Used for risk management by professional desks. | Proprietary. **Not reached.** Known only from press descriptions. |
| **AQR** (value-spread articles 2018-2021; "Craftsmanship Alpha" 2017) | The value spread as a percentile line chart over time, with long-run median bands. Comparison of construction choices. | It shows how cheap a factor is relative to its history, and the authors themselves warn against timing on it. | [K]. |

**What carries over to our page:** horizon-matched return tables on a total-return basis; a
launch-date marker; drawdown and recovery; calendar year against intra-year drop; valuation shown as a
percentile with an honest R² or spread, not as a forecast; and factor-versus-parent relative lines.

---

## 3. Books (relevant chapters)

All [K]: none of the books was opened this session. Check chapter numbers before citing them on the page.

- **Faber, *The Ivy Portfolio* (2009, Wiley), with Richardson.** The timing chapters apply the
  10-month SMA rule to five asset classes. The relative-strength chapter ranks asset classes by
  3-, 6- and 12-month returns. This is the source of the "trend status" and "relative strength
  table" layouts. Main finding: lower drawdowns and similar returns.
- **Faber, *Global Asset Allocation* (2015).** Most well-known strategic allocations had similar
  long-run returns. Costs and behaviour matter more than the choice of mix. This argues against
  presenting any one index as "the best".
- **Antonacci, *Dual Momentum Investing* (2014, McGraw-Hill).** Relative momentum (12-month, between
  US and international equities) combined with absolute momentum (against T-bills). After
  publication, secondary reviews report long whipsaw periods (2018, 2020). I did not verify these
  from a primary source.
- **Ilmanen, *Expected Returns* (2011, Wiley).** Uses three views at once: historical average,
  theory, and forward-looking indicators such as yields and valuation. He separates rewarded risk
  premia from timing, and finds value-spread timing weak.
- **Ilmanen, *Investing Amid Low Expected Returns* (2022, Wiley).** The chapters on factor timing
  and "tactical" calls find modest gains at best. Contrarian valuation timing helps only at extremes
  and over long horizons. He recommends diversified strategic factor exposure.
- **Swedroe & Berkin, *Your Complete Guide to Factor-Based Investing* (2016).** A factor qualifies
  if it is persistent, pervasive, robust, investable and intuitive. The appendices cover momentum
  crashes and factor drawdowns. Useful as the page's "what counts as a factor" test.
- **Marks, *Mastering the Market Cycle* (2018).** The cycle position is judged qualitatively
  (credit, sentiment, valuation). It supports showing valuation *context*, and Marks himself says
  timing is rarely possible.
- **Indian books.** I found nothing rigorous that is specific to index-level evidence. Monika
  Halan, *Let's Talk Money* (2018), argues for index funds for retail investors, but it is not
  evidence. **Gap: no Indian book was located that tests index signals.**

---

## 4. Shortlist for the Indices page (ranked by decision value of the evidence)

Legend: **TEST** = must pass our own record test before it is shown as a signal (the page then shows
Pass or Not confirmed). **CONTEXT** = descriptive and shown with no predictive claim.

### 1. Return table on a total-return basis, with the launch date marked (CONTEXT)
- **Question:** what has this index actually delivered, over comparable horizons?
- **Calculation:** returns over 1M, 3M, 6M, 1Y, 3Y annualised and 5Y annualised, plus "since live
  launch" annualised. Approximate TR = price return + accrued dividend yield, using daily
  `Div Yield/100/365` from the file, or NSE's TRI series where we have it. Rank within each group
  (broad, size, sector, thematic, strategy).
- **Indices:** all 169.
- **Evidence:** this is the industry standard (SPIVA uses TRI benchmarks; NSE factsheets give price
  and TRI; JPM).
- **How it misleads:** price return understates by about 1-1.5% a year (Nifty 50 DY 1.32% [P]).
  "Since inception" includes back-filled pre-launch history (Huang, Song & Xiang 2024). Indices
  launched recently have short histories. Discontinued indices drop out (survivorship), so a
  "strategy indices beat Nifty" claim based on today's 169 is biased.

### 2. Live versus back-tested split for strategy and thematic indices (CONTEXT, an honesty item)
- **Question:** how much of this index's record is real?
- **Calculation:** for each index, the launch date (from NSE press releases and methodology) and
  the base date. Annualised excess return over the parent before launch and after launch, side by
  side, with the % of history that is back-filled.
- **Indices:** strategy, factor and thematic indices (e.g. Nifty200 Momentum 30: base 1 Apr 2005,
  launched 25 Aug 2020 [S]).
- **Evidence:** Huang, Song & Xiang (2024); McLean & Pontiff (2016).
- **How it misleads:** a launch-date table is needed and has to be sourced per index. Our daily file
  only starts in Oct 2012, so pre-2012 back-fill is not in our data at all. Say so.

### 3. Trend status of each index (TEST)
- **Question:** is this index in an up-trend or a down-trend now?
- **Calculation:** (a) month-end close against its 10-month SMA of month-end closes (Faber).
  (b) 12-month return excluding the last month, in absolute terms (TSMOM sign; MOP 2012). Show
  "above/below" and the number of months in the current state.
- **Indices:** broad (Nifty 50, 500, Midcap 150, Smallcap 250) first; then sectors.
- **Evidence:** MOP 2012; Hurst, Ooi & Pedersen 2017; Faber 2007; Zakamulin 2017. Counter-evidence:
  Huang et al. 2020. India: only the weak Slivka et al. 2014 study.
- **How it misleads:** whipsaw in range-bound markets. Look-ahead if the current month's close is
  used before month end. Results are sensitive to SMA length (data snooping if we pick the best).
  Price versus TR changes the crossing dates slightly. **Test:** drawdown reduction and return
  against buy-and-hold on Nifty 50, Nifty 500 and Midcap 150, Oct 2012 onward (an older Nifty 50
  price history, if we have one, as an out-of-sample check). Fix the rule (10 months) *before*
  testing.

### 4. Drawdown and recovery panel (CONTEXT)
- **Question:** how bad has it got, and how long did recovery take?
- **Calculation:** current drawdown from all-time high (on a TR basis); maximum drawdown; days to
  recover; worst 12-month return. A JPM-style chart of calendar-year return against the largest
  intra-year decline for each year.
- **Indices:** all, with emphasis on broad and factor indices.
- **Evidence:** NSE momentum white paper drawdowns [P]; JPM Guide practice [K]; Daniel & Moskowitz 2016.
- **How it misleads:** a short history (from 2012) misses 2008 (Nifty about -60%). Say that the
  2008 drawdown is outside our data and quote NSE's figure with its source and date.

### 5. Factor index against its parent: relative strength and factor momentum (TEST)
- **Question:** which styles (momentum, quality, value, low vol, alpha, equal weight) are leading,
  and does leadership persist?
- **Calculation:** the ratio of the factor index (TR) to its parent (e.g. Nifty200 Momentum 30 /
  Nifty 200; Nifty100 Low Volatility 30 / Nifty 100; Nifty200 Quality 30 / Nifty 200;
  Nifty50 Value 20 / Nifty 50; Nifty 50 Equal Weight / Nifty 50). Show the 1M, 6M and 12M relative
  return and a rolling chart. Ranking the factors by trailing 1-month and 12-month relative return
  is the factor momentum signal.
- **Evidence:** Ehsani & Linnainmaa 2022; Gupta & Kelly 2019 (1-month lookback strongest). Not
  tested in India.
- **How it misleads:** only about 6-8 factor indices make a tiny cross-section. Pre-launch
  back-fill. Craftsmanship differences. Long-only indices hold the factor diluted by market beta.
  **Test** on post-2012 data, from each index's launch date onward wherever possible.

### 6. Momentum-crash risk regime (TEST, the item closest to our own book)
- **Question:** is this a market state in which momentum strategies historically crash?
- **Calculation:** the Daniel & Moskowitz bear-state flag: Nifty 500 trailing 24-month return < 0,
  **and** Nifty 500 realised volatility (126-day) in its top tercile of history. Alongside it, the
  realised volatility of Nifty200 Momentum 30 relative to Nifty 200 (the Barroso & Santa-Clara
  input).
- **Indices:** Nifty 500, Nifty 200, the Momentum indices.
- **Evidence:** Daniel & Moskowitz 2016; Barroso & Santa-Clara 2015. NSE [P] confirms deeper
  momentum drawdowns in India.
- **How it misleads:** there are very few bear states since 2012 (2020 is the main one), so the test
  will have little power. It may have to show "Not confirmed (too few events)". It is useful to show
  as a risk light, not a switch.

### 7. Sector/industry relative-strength table (TEST; it may live on the Sector page)
- **Question:** which sectors are leading, and is that persistent?
- **Calculation:** 1M, 6M and 12M-ex-1M relative return of each sector index against Nifty 500 (TR),
  ranked with a rank-change arrow.
- **Evidence:** Moskowitz & Grinblatt 1999. Not tested in India.
- **How it misleads:** concentrated sector indices (one stock can be 20-30%); overlap with our stock
  ranking; whipsaw. Coordinate with the existing Sector page to avoid duplication.

### 8. Valuation percentile with an honest forward-return panel (CONTEXT for under 3 years; TEST for 5 years)
- **Question:** is the market (or a segment) cheap or expensive against its own history, and what
  did that mean for long-horizon returns?
- **Calculation:** the percentile of today's P/E, P/B and DY in each index's own history,
  **computed separately for the post-April-2021 consolidated regime** (pre-April-2021 values shown
  as a separate series, not spliced). For Nifty 50 only, a scatter of P/E against subsequent 5-year
  TR CAGR, with R² and the number of *independent* windows printed.
- **Indices:** Nifty 50, Nifty 500, Midcap 150, Smallcap 250, the major sectors.
- **Evidence:** Campbell & Shiller 1998; Asness 2012; Goyal & Welch 2008 (1-year horizon fails).
  India: practitioner and preprint evidence only (StableInvestor 2019; Sharma 2025).
- **How it misleads:** the April 2021 standalone-to-consolidated break; overlapping windows; P/E
  swings from losses in small-cap and thematic indices; mixing trailing and forward P/E; showing it
  as a 1-year forecast.

### 9. Factor relative valuation (value spread) (CONTEXT)
- **Question:** has a style's outperformance come from re-rating, so that it is now expensive
  against its parent?
- **Calculation:** the factor index's P/B (or P/E) divided by the parent's P/B, as a percentile in
  its own history, shown next to item 5.
- **Evidence:** Arnott et al. 2016 (supporting); Asness et al. 2017 and Ilmanen et al. 2021
  (timing weak).
- **How it misleads:** a momentum index's valuation changes at each rebalance, so a jump in the
  ratio is often turnover, not re-rating. It is not a timing rule. Label it "context".

### 10. Breadth, dispersion and correlation regime (TEST)
- **Question:** is the market's move broad or narrow, and is stock-picking (dispersion) rewarded now?
- **Calculation:** % of Nifty 500 stocks above their 200-day average (from our breadth history).
  Cross-sectional standard deviation of 1-month returns across the 750 stocks. The average pairwise
  correlation of the sector indices over 63 days.
- **Evidence:** Stivers & Sun 2010; Pollet & Wilson 2010 (US, in-sample). Not tested in India.
- **How it misleads:** many free parameters invite snooping. Show the level and its history, and
  show any claim only after a test.

### 11. Size spectrum: large against mid against small (CONTEXT)
- **Question:** where is leadership across market cap, and how do valuations compare?
- **Calculation:** TR ratio lines of Midcap 150 / Nifty 100 and Smallcap 250 / Nifty 100, plus
  relative P/E.
- **Evidence:** descriptive. Size timing is unsupported (Asness et al. 2018). Marks for cycle context.
- **How it misleads:** it invites cycle calls that the evidence does not support.

### 12. Active against passive context (CONTEXT, from SPIVA India)
- **Question:** for this index's category, how often do active funds beat it?
- **Calculation:** quote the latest SPIVA India figure (with date and link) for the category that
  maps to the index (e.g. large-cap → S&P BSE 100).
- **Evidence:** SPIVA India (e.g. ELSS 10-year underperformance of 86.8%, mid-year 2025 [S]).
- **How it misleads:** SPIVA's benchmarks are S&P BSE indices, not Nifty, so the mapping is
  approximate. Quote it; do not recompute it.

---

## 5. What NOT to show, and why

1. **Single-number P/E "buy/sell bands"** (e.g. "sell above 22"). The independent observations are
   too few, the April 2021 method change breaks the series, and it fails at 1-year horizons
   (Goyal & Welch 2008). The evidence is blog and preprint level only.
2. **Back-tested "since inception" CAGR or Sharpe for strategy indices without a launch marker.**
   Smart-beta alpha collapses after launch (Huang, Song & Xiang 2024).
3. **Short-term technical indicators on indices** (RSI, MACD, Bollinger bands, Fibonacci levels,
   candlestick patterns). After 1990 their profitability declined, and data snooping explains much
   of the earlier evidence. Park & Irwin (2007), "What Do We Know About the Profitability of
   Technical Analysis?", *Journal of Economic Surveys* 21(4) [K]. There is no Indian out-of-sample
   evidence.
4. **Valuation-based factor switching** ("value is cheap, rotate into value"). Asness et al. 2017
   and Ilmanen et al. 2021 find no robust gain. Show the value spread as context only.
5. **Calendar seasonality** (Diwali, Budget, "Sell in May", month-of-year heatmaps presented as
   expected returns). Few observations, and highly snooped.
6. **FII/DII flows as a predictor of index returns.** Flows largely follow returns (feedback
   trading) and are reported with delay. I found no out-of-sample Indian test in this session. Show
   flows as context next to returns; do not show a "flows predict" claim without our own test.
7. **Market-cap-to-GDP ("Buffett indicator") for India.** It mixes listed coverage changes and
   SME/PSU listings, with few independent observations. There is no robust evidence.
8. **"Best index next year" forecasts or return quilts framed as predictions.** A return quilt is
   fine as history; leadership in calendar returns does not persist reliably at 1-year (Faber 2015
   on allocation; the factor-timing literature).
9. **Crowding scores.** They need holdings and flows data we do not have (MSCI and sell-side
   methods are proprietary).
10. **Sharpe ratios on price-only series, or over windows shorter than 3 years.** They are noise,
    and a price-only series biases yield-heavy indices (PSU, dividend) downward.

---

## 6. What I could not reach or did not verify

- SPIVA India Mid-Year 2026 PDF: HTTP 403. Mid-year 2025 figures are from S&P's article page as
  summarised by search [S].
- The full texts of Ehsani & Linnainmaa, Gupta & Kelly, Asness 2017 and Arnott 2016: findings were
  taken from abstracts and summaries [S].
- MSCI factor reports, JPM Guide to the Markets (India/Asia edition), and Goldman and other
  sell-side factor monitors: not opened. They are described from prior knowledge [K], and the
  sell-side reports are proprietary.
- The IIMA factor series: located but not downloaded. It is the right independent dataset for
  checking any factor-index claim before 2012 and for momentum-crash episodes.
- Peer-reviewed Indian studies of P/E band forward returns, index trend rules out of sample, or FII
  flow predictability: **none found** in this session. There is no SEBI study on these topics either.
- Launch dates of each NSE strategy and thematic index: only Nifty200 Momentum 30 was confirmed
  (25 Aug 2020, base 1 Apr 2005 [S, NSE press release]). A sourced launch-date table is a
  prerequisite for items 1, 2 and 5.
- Every [K] item needs a quote check against the original before it appears on the page.
