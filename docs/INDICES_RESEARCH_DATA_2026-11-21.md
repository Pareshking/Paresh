# Indices page: data and methodology research (21 Nov 2026)

This is read-only research. Nothing in the repo was edited.

Evidence used. Each item was fetched on 21 Nov 2026 unless another date is given:
- **NSE Indices equity methodology** at niftyindices.com `/Methodology/Method_NIFTY_Equity_Indices.pdf`. The cover reads "November 2026" and the footer reads "20260821". It is cited below as **MD**.
- **40 NSE Indices factsheets**, each dated "October 30, 2026", fetched from `/Factsheet/...`. Cited as **FS**. The list came from `/reports/index-factsheet`.
- **niftyindices.com pages:** the index-concept pages (P/E, P/B, dividend yield, TRI), `/reports/historical-data` and `/reports/daily-reports`.
- **IISL press releases:**
  - `ind_prs11022013.pdf`: the S&P licence ended.
  - `ind_prs22092015.pdf`: the CNX indices became Nifty.
  - `ind_prs22032013.pdf`: Defty moved to end-of-day calculation.
- **SEBI circular SEBI/HO/IMD/DF3/CIR/P/2018/04**, fetched from sebi.gov.in.
- **Nifty Total Market whitepaper** (2021) on niftyindices.com.
- **Every daily all-indices file on disk**, 803 parseable files in all:
  - `scratchpad/ind/` (samples);
  - `scratchpad/ind_raw/` (282 files at the time of writing, 21 Feb 2012 to about Apr 2013; the download is still running);
  - `scratchpad/dl/indclose/` (552 files, 1 Jan 2025 to 20 Nov 2026, daily).

  These files were parsed with `python3 -I` only. The parsing scripts are in `scratchpad/rs/`.

Downloaded documents are in `scratchpad/nidx_docs/`, with the text extracted alongside each PDF.

---

## 0. File facts the collector must know (from the files themselves)

- **Header.** Every one of the 803 files has the same 13 columns. The real names are `Index Name, Index Date, Open Index Value, High Index Value, Low Index Value, Closing Index Value, Points Change, Change(%), Volume, Turnover (Rs. Cr.), P/E, P/B, Div Yield`. The short names in the brief (Open, Close, and so on) are not the real ones. `scripts/collect_nse_total_market.py` already reads `Closing Index Value`.
- **Placeholder and number format.** `-` is the placeholder for no value. Across the files:
  - Open/High/Low are `-` on 12,910 rows: indices calculated at end of day only, such as Nifty 1000 and the Alpha/High Beta/Low Volatility 50 in 2012-13.
  - P/E is `-` on 13,017 rows and P/B on 12,398.
  - Volume and Turnover are `-` on 12,953 rows.

  Decimals can have no leading zero (`.82`). Dates are `DD-MM-YYYY`. Every file holds one date.
- **First file.** The archive's first file is **21 Feb 2012**: `ind_raw/20120221.csv`, with 30 indices. Earlier dates in `scratchpad/ind/` (2004 to 3 Jan 2012) return an HTML page, not a CSV.
- **A mislabelled row: 8 Feb 2013.** That file has two `CNX Alpha Index` rows (4713.18 and 1572.90) and no `CNX High Beta` row. The second row is High Beta: 1594.85 (7 Feb) − 21.94 = 1572.91. NSE's file can mislabel a row, so names cannot be trusted blindly (see the guard in section 6).
- **Indices go missing on some days.** Several indices are absent on single sessions and then return:
  - BHARAT Bond indices on 27 Mar 2025 and 1 Aug 2025;
  - Nifty50 USD on 1 Aug and 5 Sep 2025;
  - Nifty Smallcap 500, present 1 Jan 2026, absent until 28 Jan 2026.

  On the Muhurat session of **8 Nov 2026 (a Sunday)** the file has 147 rows, not 167. Twenty mostly end-of-day indices are missing, including Nifty AI Catalysts, Capital Goods, Next 100 and Nifty500 Growth 50. A missing row is therefore not by itself a download fault.
- **First appearance tracks the launch date.** Nifty Alpha 50, High Beta 50 and Low Volatility 50 first appear on 19 Nov 2012, their FS launch date. Other examples of first appearance against FS launch date:
  - Nifty500 Growth 50: 27 Aug 2026 (launched 26 Aug);
  - Nifty High Dividend Yield 15: 1 Oct 2026 (launched 30 Sep);
  - Nifty1000 Equal Weight: 16 Nov 2026 (launched 12 Nov);
  - Nifty Total Market: 14 Oct 2021 (launched 13 Oct; first row of `data/nse_total_market.csv`).

  **The daily archive contains no back-calculated history.** Each index enters at its launch-day level, which is far above its base value of 1000 because the history before launch was back-calculated.

## 1. Classification of the 169 indices in the 20 Nov 2026 file

I used NSE's own grouping: the MD table of contents and its "Index Characteristics" tables (MD pp. 288-292). The same five headings appear on every factsheet: Broad Market, Sectoral, Thematic, Strategy and Fixed Income. The counts below are mine, from the 20 Nov 2026 file.

- **Broad / size (25):**
  - Nifty 50, Next 50, Next 100, 100, 200, 500, 1000, Total Market;
  - Midcap 50, Midcap 100, Midcap 150, Midcap Select;
  - Smallcap 50, Smallcap 100, Smallcap 250, Smallcap 500, Microcap 250;
  - LargeMidcap 250, MidSmallcap 400, MidSmallcap400 50:50;
  - Nifty500 Multicap 50:25:25, Nifty500 LargeMidSmall Equal-Cap Weighted, Nifty India FPI 150;
  - NIFTY SME EMERGE (MD lists it under thematic; it is a size segment).
- **Sector (35):** Auto, Bank, Private Bank, PSU Bank, Financial Services, Fin Services 25/50, Fin Services Ex-Bank, FMCG, IT, Media, Metal, Pharma, Healthcare Index, Nifty500 Healthcare, Realty, REITs & Realty, Oil & Gas, Chemicals, Consumer Durables, Capital Goods, Cement, Commercial & Transport Services, Construction, Consumer Services, Hospitals, Housing Finance, Insurance, NBFC, Power, Retail, Telecommunications, MidSmall Financial Services, MidSmall Healthcare, MidSmall IT & Telecom, Small Finance Banks & Microfinance Institutions.
  - MD lists the last one as thematic.
  - Nifty Power, Nifty Retail, Nifty Consumer Services and Nifty Telecommunications are in MD's sector list.
- **Thematic (47):**
  - Energy, Infrastructure, Commodities, India Consumption, MidSmall India Consumption, MNC, PSE, CPSE, Services Sector;
  - Shariah 25, Nifty50 Shariah, Nifty500 Shariah;
  - Nifty100 Liquid 15, Midcap Liquid 15;
  - Nifty100 ESG, Nifty100 Enhanced ESG, Nifty100 ESG Sector Leaders;
  - the four Corporate Group indices (Aditya Birla, Mahindra, Tata, Tata 25% Cap), India Select 5 Corporate Groups (MAATR), Conglomerate 50;
  - India Digital, India Internet, IPO, Mobility, EV & New Age Automotive;
  - India Defence, India Defence Equal Weight, India Manufacturing, Nifty500 Multicap India Manufacturing 50:30:20, Nifty500 Multicap Infrastructure 50:30:20, India Infrastructure & Logistics, Transportation & Logistics;
  - Housing, Core Housing, Rural, Non-Cyclical Consumer, India New Age Consumption, India Tourism, India Railways PSU;
  - Capital Markets, Sugar & Ethanol, Waves, AI Catalysts, Nifty500 Ahimsa;
  - REITs & InvITs, REITs & InvITs 90:10.
- **Strategy / factor (39 in the file; MD's strategy list is the same less the asset-allocation indices, which are not in the file).** The table below covers each one.
- **Nifty 50 variants (9):** Nifty50 USD, Nifty50 Dividend Points, PR 1x Inverse, PR 2x Leverage, TR 1x Inverse, TR 2x Leverage, Nifty 50 Arbitrage, Nifty 50 Futures Index, Nifty 50 Futures TR Index. MD's variants table (p. 289) lists Nifty50 Equal Weight as well; I put it under strategy.
- **Fixed income (12):** the 8-13 yr, 4-8 yr, 11-15 yr, 15 yr+, Composite and 10 yr Benchmark G-Sec indices; the 10 yr Benchmark (Clean Price); BHARAT Bond Apr 2030, 2031, 2032 and 2033; Nifty 1D Rate.
  - The historical-data page says "All fixed income indices [except Nifty 10 yr Benchmark G-Sec (Clean Price)] are Total Return."
- **Volatility (1):** India VIX.

### Strategy indices: methodology, launch, base, back-calculation

Launch and base dates are from each FS ("Launch Date", "Base Date"), cross-checked against the MD base-date table. The one-line methodologies paraphrase the FS opening paragraph. "Rebal" is the FS "Index Rebalancing" field.

**Back-calculated?** Every index whose base date is before its launch date has history before launch that NSE computed afterwards, by applying today's rules to past data. Three pieces of evidence:
- FS "Since inception" returns run from the base date.
- The Total Market whitepaper says "* Based on inception date of Apr 1, 2005. Returns based on TRI values", with data as of 29 Oct 2021, two weeks after the 13 Oct 2021 launch.
- MD p. 75-ish says of Nifty Growth Sectors 15: "The index has base date of 01-Jan-2009 ... Back testing of the index is carried out since 01-Jan-2004", and the Value 20 FS says "computed historically from January 01, 2009".

NSE does not print a "back-tested" disclaimer on the factsheets.

| Index | Factor family | Method (one line) | Rebal | Launch | Base | Years back-filled |
|---|---|---|---|---|---|---|
| Nifty200 Momentum 30 | Momentum | Top 30 of Nifty 200 by normalised momentum score (6m and 12m return ÷ daily volatility); weight = free-float cap × score, cap lower of 5% or 5× cap weight | Semi-annual (Jun/Dec) | 25 Aug 2020 | 1 Apr 2005 | 15.4 |
| Nifty Midcap150 Momentum 50 | Momentum | Top 50 of Midcap 150 by normalised momentum; score × free-float cap | Semi-annual | 16 Aug 2022 | 1 Apr 2005 | 17.4 |
| Nifty500 Momentum 50 | Momentum | Top 50 of Nifty 500 by normalised momentum; score × free-float cap | Semi-annual | 4 Jun 2024 | 1 Apr 2005 | 19.2 |
| Nifty Smallcap250 Momentum Quality 100 | Momentum + quality | 100 of Smallcap 250 by combined momentum and quality (ROE, D/E, 5-year EPS-growth variability); cap 3% | Semi-annual | 21 Dec 2023 | 1 Apr 2005 | 18.7 |
| Nifty MidSmallcap400 Momentum Quality 100 | Momentum + quality | 100 of MidSmallcap 400, same scoring | Semi-annual | 8 Feb 2024 | 1 Apr 2005 | 18.9 |
| Nifty500 Multicap Momentum Quality 50 | Momentum + quality | 50 across large, mid and small caps of Nifty 500 (50:30:20 segments, MD), momentum + quality | Semi-annual | 4 Sep 2024 | 1 Apr 2005 | 19.4 |
| Nifty Total Market Momentum Quality 50 | Momentum + quality | 50 of Nifty Total Market by composite momentum + quality score × free-float cap | Semi-annual | 6 Aug 2025 | 1 Apr 2005 | 20.3 |
| Nifty100 Quality 30 (was "NSE Quality 30" / "Nifty Quality 30") | Quality | Top 30 of Nifty 100 by ROE, D/E and 5-year EPS-growth variability; weight from score and √ free-float cap, cap 5% | Semi-annual | 19 Mar 2015 | 1 Oct 2009 | 5.5 |
| NIFTY200 Quality 30 | Quality | Same as above, on Nifty 200 | Semi-annual | 17 Apr 2018 | 1 Apr 2005 | 13.0 |
| NIFTY Midcap150 Quality 50 | Quality | Top 50 of Midcap 150 by quality (leverage test skipped for financials) | Semi-annual | 24 Oct 2019 | 1 Apr 2005 | 14.6 |
| Nifty Smallcap250 Quality 50 | Quality | Up to 50 of Smallcap 250 by quality | Semi-annual | 15 Mar 2023 | 1 Apr 2005 | 18.0 |
| Nifty500 Quality 50 | Quality | Top 50 of Nifty 500 by quality × free-float cap | Semi-annual | 20 Dec 2024 | 1 Apr 2005 | 19.7 |
| Nifty500 Flexicap Quality 30 | Quality | Top 10 by 6-month average free-float cap from each of Nifty100 Q30, Midcap150 Q50 and Smallcap250 Q50 | Semi-annual | 4 Apr 2025 | 1 Oct 2009 | 15.5 |
| Nifty50 Value 20 (was "NV 20") | Value | 20 value companies from Nifty 50 (score from ROCE, P/E, P/B, dividend yield; MD); free-float cap × value score, cap 15% | Semi-annual | 28 Mar 2014 | 1 Jan 2009 | 5.2 |
| NIFTY500 Value 50 | Value | 50 of Nifty 500 by value score (E/P, B/P, S/P, dividend yield) | Semi-annual | 24 Oct 2018 | 1 Apr 2005 | 13.6 |
| Nifty200 Value 30 | Value | 30 of Nifty 200 by the same value score × free-float cap | Semi-annual | 12 Jun 2024 | 1 Apr 2005 | 19.2 |
| Nifty Low Volatility 50 (was "CNX Low Volatility") | Low volatility | 50 least-volatile liquid NSE stocks; weight by score | Quarterly | 19 Nov 2012 | 31 Dec 2003 | 8.9 |
| Nifty100 Low Volatility 30 | Low volatility | 30 least-volatile Nifty 100 stocks in F&O (1-year σ of daily log returns); cap 3% | Quarterly | 8 Jul 2016 | 1 Apr 2005 | 11.3 |
| Nifty500 Low Volatility 50 | Low volatility | 50 of Nifty 500 by inverse 1-year σ × free-float cap | Semi-annual | 20 Dec 2024 | 1 Apr 2005 | 19.7 |
| Nifty Alpha 50 (was "CNX Alpha Index") | Alpha | 50 high-alpha liquid NSE stocks; weight by alpha | Quarterly | 19 Nov 2012 | 31 Dec 2003 | 8.9 |
| NIFTY100 Alpha 30 | Alpha | 30 of Nifty 100 by Jensen's alpha (1-year trailing) × free-float cap | Quarterly | 28 Jun 2019 | 1 Apr 2005 | 14.2 |
| Nifty200 Alpha 30 | Alpha | 30 of Nifty 200 by Jensen's alpha; cap lower of 5% or 5× cap weight | Quarterly | 21 Jul 2022 | 1 Apr 2005 | 17.3 |
| Nifty High Beta 50 (was "CNX High Beta") | Beta | 50 highest-beta liquid stocks against Nifty 50 | Quarterly | 19 Nov 2012 | 31 Dec 2003 | 8.9 |
| NIFTY Alpha Low-Volatility 30 | Multi-factor | 30 from Nifty 100 + Midcap 50 by alpha + low volatility; weight from factor scores, cap 5% | Semi-annual | 10 Jul 2017 | 1 Apr 2005 | 12.3 |
| NIFTY Quality Low-Volatility 30 | Multi-factor | Same universe; quality + low volatility | Semi-annual | 10 Jul 2017 | 1 Apr 2005 | 12.3 |
| NIFTY Alpha Quality Low-Volatility 30 | Multi-factor | Same universe; alpha + quality + low volatility | Semi-annual | 10 Jul 2017 | 1 Apr 2005 | 12.3 |
| NIFTY Alpha Quality Value Low-Volatility 30 | Multi-factor | Same universe; alpha + quality + value + low volatility | Semi-annual | 3 Jul 2017 | 1 Apr 2005 | 12.3 |
| Nifty500 Multifactor MQVLv 50 | Multi-factor | 50 of Nifty 500 by momentum + quality + value + low volatility; weight by composite score | Semi-annual | 6 Feb 2025 | 1 Apr 2005 | 19.9 |
| Nifty500 Growth 50 | Growth | Top 50 of Nifty 500 by 3-year PAT growth, 3-year sales growth and 1-year risk-adjusted return | Semi-annual | 26 Aug 2026 | 1 Apr 2005 | 21.4 |
| Nifty Dividend Opportunities 50 (was "CNX Dividend Opportunities") | Dividend | 50 high-yield stocks with stability and tradability screens; cap 10% | Annual | 22 Mar 2011 | 1 Oct 2007 | 3.5 |
| Nifty High Dividend Yield 15 | Dividend | Top 15 of Total Market by trailing 12-month dividend ÷ market cap; tilt weight | Semi-annual | 30 Sep 2026 | 1 Apr 2005 | 21.5 |
| Nifty Growth Sectors 15 (was "NI15") | Sector tilt | 15 F&O stocks from sectors whose P/E and P/B beat Nifty's; cap 15% (back-tested from 2004) | Semi-annual | 22 May 2014 | 1 Jan 2009 | 5.4 |
| NIFTY50 Equal Weight | Equal weight | Nifty 50 constituents, equal weight | Semi-annual | 13 Apr 2017 | 3 Nov 1995 | 21.4 |
| Nifty100 Equal Weight (was "CNX 100 Equal Weight") | Equal weight | Nifty 100, equal weight | (no FS found) | **not found**; first seen in the file between 1 Apr 2013 and 2 Jan 2014 | 1 Jan 2003 | ≥10 |
| Nifty500 Equal Weight | Equal weight | Nifty 500, equal weight | Semi-annual | 31 May 2024 | 1 Apr 2005 | 19.2 |
| Nifty1000 Equal Weight | Equal weight | Nifty 1000, equal weight, end-of-day | Semi-annual | 12 Nov 2026 | 24 Sep 2007 | 19.1 |
| Nifty Top 10 / 15 / 20 Equal Weight | Equal weight | Top 10, 15 or 20 of Nifty 50 by 6-month average free-float cap, equal weight | Semi-annual | 24 Jun / 15 Oct / 22 Oct 2024 | 2 Mar 2006 | 18.3 to 18.6 |

**What this means for the page.** For nearly every factor index, most of the history NSE publishes is back-fill. The momentum indices have 15 to 20 years of back-fill against 2 to 6 years of live data. A chart or CAGR that starts at the base date mixes in-sample history with live performance. The page should start every strategy series at its **launch date** by default, and shade the earlier stretch if it is ever shown.

## 2. Total-return indices

- **SEBI circular**, quoted from the PDF (SEBI/HO/IMD/DF3/CIR/P/2018/04, 4 Jan 2018):
  - para 3(b): "The performance of the schemes of a mutual fund shall be benchmarked to the Total Return variant of the Index chosen as a benchmark";
  - para 4: "This circular is applicable to all schemes of Mutual Funds with effect from February 1, 2018";
  - para 3(c)(i) lets funds use "a composite CAGR figure of the performance of the PRI benchmark (till the date from which TRI is available) and the TRI (subsequently)".
- **NSE's definition of TRI** (niftyindices "Total Return Index" concept page): "Dividend payouts as they occur are indexed on ex-date. Indexed dividends are then reinvested in the index to give TR Index. Base for both the Price index close and TR index close will be the same."
- **TRI is not in the daily all-indices file.** None of the 169 rows is a TRI, apart from Nifty50 TR 1x Inverse/2x Leverage, the Futures TR index and the fixed-income indices. TRI is published:
  1. On niftyindices.com → Reports → Historical Data, in the "Total returns Index Values" tab. Its table columns are "Date | Total Returns Index | Net Total Return Index" (page HTML, 21 Nov 2026). The page's XHR endpoint is `POST https://www.niftyindices.com/Backpage/getTotalReturnIndexString` (with `.aspx/` in older clients). The body is `{"cinfo": "{'name':'<INDEX NAME>','startDate':'DD-Mon-YYYY','endDate':'DD-Mon-YYYY','indexName':'<INDEX NAME>'}"}`, the same shape as the price endpoint the repo already uses in `scripts/build_nse_index_prices.py`. The third-party BharatFinTrack documents the same endpoint, and its start date "defaults to the index base date".
  2. On the factsheets, as the TR return figures only (QTD, YTD, 1y, 5y, since inception).
- **Unverified:**
  - From this container, `POST .../Backpage.aspx/getHistoricaldatatabletoString`, `getTotalReturnIndexString` and `getpepbHistoricaldataDBtoString` each returned **HTTP 302 with `{"Message":"There was an error processing the request."}`**. My retry with a browser-like session was blocked by the session's permission policy.
  - So I could not confirm how far back TRI goes, or that the endpoint still answers. This matches the repo's own notes: `benchmark_indices.py` says "niftyindices.com refuses requests from the container and from the nightly job (5-7 and 20 Nov 2026)".
  - **Lead to check:** `scripts/build_nse_index_prices.py` calls the same `Backpage.aspx` URL. If that URL now always answers 302, the nightly `r2_nse_index_prices` job is running on its Screener fallback. Look for `INDEX_SOURCE_FALLBACK` in its logs.
- **Can we collect TRI for Nifty 500, Total Market and the factor indices?**
  - Each FS names a TRI variant, e.g. "Index Variant: Nifty Total Market Total Returns Index" and "Nifty500 Multifactor MQVLv 50 Total Returns Index". The Nifty 500 factsheet says "Index Variants: Nifty 500 Total Ret…". So NSE computes TRI for all of them.
  - Collection needs the niftyindices endpoint from a runner it accepts. A GitHub Actions run would have to be tried, since the 20 Nov failure was from the nightly job.
  - The other way is one paid EOD subscription: NSE Indices' "EOD Index File" via connect2nse.com/iislNet, linked from the niftyindices menu.
  - Do not build TRI ourselves from PRI plus dividends. That reproduces nothing independent.

## 3. Nifty Total Market before 14 Oct 2021

- **It exists.** MD p. 288: "Nifty Total Market | Apr 01, 2005 | 1000". FS: "Launch Date October 13, 2021 / Base Date April 01, 2005". The whitepaper (data as of 29 Oct 2021) shows yearly returns for CY2005-2021 and says "Since April 01, 2005 till Oct 29, 2021, the Nifty Total Market Index has returned 15.3%" (TRI).
- **It is back-calculated.** It is built from Nifty 500 + Microcap 250 membership as it would have been. The whitepaper footnote warns: "Prior to April 1, 2016, there may be overlap between the portfolios of these indices."
- **How to fetch it (not verified working; see the 302 above).** The niftyindices Historical Data page, Equity, "NIFTY TOTAL MARKET", from 01-Apr-2005. As an API call:
  `POST https://www.niftyindices.com/Backpage.aspx/getHistoricaldatatabletoString` (or `/Backpage/...`). Headers: `Content-Type: application/json; charset=UTF-8`, `X-Requested-With: XMLHttpRequest`, `Referer: https://www.niftyindices.com/reports/historical-data`. Body:
  `{"cinfo":"{'name':'NIFTY TOTAL MARKET','startDate':'01-Apr-2005','endDate':'13-Oct-2021','indexName':'NIFTY TOTAL MARKET'}"}`
  - The response is `{"d": "[{HistoricalDate, OPEN, HIGH, LOW, CLOSE}, ...]"}`, parsed exactly as `_fetch_official` does.
  - For TRI, use `getTotalReturnIndexString` with the same body.
  - The request must be chunked: clients commonly use one year or less per request. This is unverified.
- **Acceptance test for whatever is fetched.** Its close on 14 Oct 2021 must equal `data/nse_total_market.csv` (8769.06) to the paisa. It must also be continuous with the archive (Points Change on 14 Oct). A level that joins at 8769.06 is the evidence the two series are one.
- **Present it as back-fill.** Pre-launch values must be stored with a flag such as `basis='backcalc'` and shown as such.

## 4. P/E, P/B and dividend yield in the file

Quoted from niftyindices index-concept pages on 21 Nov 2026:
- **P/E:** "Index market capitalization / Gross earnings … The earnings (including profits and losses) reported by each index constituent in trailing 4 quarters (consolidated financials) are cumulated and adjusted for factors such as free-float, capping factor etc. … In case, consolidated financials are not available, standalone financials for trailing 4 quarters will be considered. In case overall earnings value (of all constituents put together) for any index is negative, PE ratio for such indices are not computed and published by NSE Indices."
  - So a loss-making company is **netted into** the aggregate. It is not excluded, and its P/E is not floored.
  - The ratio is cap-weighted aggregate earnings yield inverted: a "harmonic" P/E, not an average of stock P/Es.
  - The file shows the rule working: **Nifty Waves**, 20 Nov 2026, has P/E `-` with P/B 2.56.
- **P/B:** "Index market capitalization / Gross book value or net-worth … The networth reported by each index constituent in the annual financial report (consolidated financials) … In case consolidated financials … are not available, standalone".
  - Book value comes from the **annual** report, so it moves in steps once a year.
- **Dividend yield:** "Gross Dividend / Index market capitalization × 100 … final, interim and any other special dividend … on rolling 12 months basis (calculated based on ex. dividend date)".
  - Special dividends are included, so the yield spikes for a year after one is paid.
- **Breaks in the series:**
  1. **Standalone to consolidated P/E, about 31 Mar / 1 Apr 2021.** The concept page now says "consolidated", which is primary evidence of the current basis. The date comes **only from secondary sources** (Capitalmind, Stableinvestor, Upstox and others): standalone "till March 2021", consolidated "from April 2021", Nifty P/E falling from about 40 to about 32 overnight. I did not find NSE's own notice. **Test, once `ind_raw/` reaches 2021:** Nifty 50 P/E on 30 Mar, 31 Mar and 1 Apr 2021 against the price change. A step of about −20% with a flat price confirms the date.
  2. **P/B moved to consolidated book value, effective 29 Sep 2023.** Source: Angel One news, 3 Oct 2023. It reports Nifty 50 P/B going from 4.31 to 3.45 and cites no NSE source. Not verified; test the same way on 28-29 Sep 2023.
  3. **"-" spells.** P/E is not published while aggregate earnings are negative.
  4. **Changes in what each index holds.** Midcap 100 and Smallcap 100 were redefined in April 2016 (section 5). This shifts the valuation of the same index name.

  A long P/E chart therefore needs a vertical rule at 1 Apr 2021, a second series basis, or both. "Nifty P/E today vs its 2008-2020 average" is a like-for-unlike comparison.

## 5. Name changes and series breaks (join table)

| Old name in file | New name in file | When | Evidence | Level continuous? |
|---|---|---|---|---|
| S&P CNX Nifty, S&P CNX 500, S&P CNX Nifty Dividend, S&P CNX Nifty Shariah, S&P CNX 500 Shariah | CNX Nifty, CNX 500, CNX Nifty Dividend, CNX Nifty Shariah, CNX 500 Shariah | Licence expired 31 Jan 2013. The file still said "S&P" on 3 Jan 2013 and no longer did on 1 Apr 2013; the exact first day comes from the full download | IISL PR 11 Feb 2013 ("licensing arrangement … expired with effect from 31st January 2013") | Yes (rename only) |
| S&P CNX Defty / CNX DEFTY | Nifty50 USD | Rename 9 Nov 2015 (real-time calculation stopped 1 Apr 2013, PR 22 Mar 2013) | PRs | Yes |
| CNX Nifty | Nifty 50 | **9 Nov 2015** | IISL PR 22 Sep 2015, "effective from November 09, 2015", annexure of 49 names | Yes |
| CNX Nifty Junior | Nifty Next 50 | 9 Nov 2015 | same | Yes |
| CNX 100 / CNX 200 / CNX 500 | Nifty 100 / 200 / 500 | 9 Nov 2015 | same | Yes |
| CNX Midcap / CNX Smallcap | Nifty Midcap 100 / Nifty Smallcap 100 | 9 Nov 2015 | same | Yes |
| NIFTY Midcap 50 | Nifty Midcap 50 | 9 Nov 2015 (case only) | files | Yes |
| LIX 15 / LIX15 Midcap | Nifty100 Liquid 15 / Nifty Midcap Liquid 15 | 9 Nov 2015 | PR | Yes |
| CNX Auto, Bank, Finance, FMCG, IT, Media, Metal, Pharma, PSU Bank, Realty | Nifty Auto … ("CNX Finance" became **Nifty Financial Services**) | 9 Nov 2015 | PR | Yes |
| CNX Energy, Infrastructure, Service Sector, Commodities, Consumption, MNC, PSE; CPSE | Nifty Energy …; "Service Sector" became **Nifty Services Sector**; "Consumption" became **Nifty India Consumption**; Nifty CPSE | 9 Nov 2015 | PR | Yes |
| CNX Nifty Shariah / CNX 500 Shariah / CNX Shariah25 | Nifty50 Shariah / Nifty500 Shariah / Nifty Shariah 25 | 9 Nov 2015 | PR | Yes |
| CNX Dividend Opportunities, CNX Low Volatility, CNX Alpha Index, CNX High Beta, NV 20, NI15, CNX 100 Equal Weight | Nifty Dividend Opportunities 50, Low Volatility 50, Alpha 50, High Beta 50, Nifty50 Value 20, Growth Sectors 15, Nifty100 Equal Weight | 9 Nov 2015 | PR | Yes |
| Nifty PR/TR 1X Inverse, 2x Leverage; CNX Nifty Dividend | Nifty50 PR/TR 1x Inverse, 2x Leverage; Nifty50 Dividend Points | 9 Nov 2015 | PR | Yes |
| NSE Quality 30 → Nifty Quality 30 | NIFTY100 Quality 30 | PR 9 Nov 2015 for the first step; second step between 1 Apr 2016 and 1 Jul 2019 (files) | PR, files | Yes, by level (2024.70 in Apr 2016 to 2670.4 in Jul 2019; check the seam day) |
| GSEC10 NSE / GSECBM NSE / NSE GSECBM Clean Price | Nifty 8-13 yr G-Sec / 10 yr Benchmark G-Sec / … (Clean Price) | 9 Nov 2015 | PR | Yes |
| Nifty Midcap 100 / Nifty Smallcap 100 | **Nifty Free Float Midcap 100 / Free Float Smallcap 100** (1 Apr 2016), later **NIFTY Midcap 100 / NIFTY Smallcap 100** (by Jul 2019) | Between 4 Jan and 1 Apr 2016, then between 2016 and 2019 | Files: 13,429 on 4 Jan 2016, then "Free Float Midcap 100" 12,792 on 1 Apr 2016, then "NIFTY Midcap 100" 17,684 on 1 Jul 2019 | Level yes. **Rules changed**: from Apr 2016 the 100 are drawn from Midcap 150 / Smallcap 250 (MD) |
| (new 1 Apr 2016) Nifty Full Midcap 100, Nifty Full Smallcap 100 | Gone by 2019 | Files | **Separate series** (3,935 / 2,615 on 1 Apr 2016); do not join to Midcap 100 |
| Nifty Aditya Birla Group / Mahindra Group / Tata Group / Tata Group 25% Cap | Nifty India Corporate Group Index - Aditya Birla Group / … | Between Jan 2020 and Sep 2024 (files) | Files | Probably a rename; check Points Change on the seam |
| Nifty India Internet & E-Commerce | **Nifty India Internet** | **2 May → 5 May 2025** | Files: 1201.35 on 2 May; 1234.74 with Points Change +33.39 on 5 May = 1234.74 − 1201.35 | **Yes, proven** |
| S&P ESG India | discontinued | Between 1 Apr 2013 and 2 Jan 2014 | Files | Series ends |
| Nifty BHARAT Bond Index - April 2025 | matured, removed | Last row 15 Apr 2025 | Files | Series ends (target-maturity index) |
| CNX Alpha Index printed twice on 8 Feb 2013 | the second row is CNX High Beta | 8 Feb 2013 only | Files (continuity) | Fix with a `notes.json`-style correction |

**Join rule for the collector.**
- Key every series on a stable `index_key` held in a committed alias table (`name_raw → index_key`, `valid_from`, `valid_to`, evidence).
- Accept a seam only when the new name's first `Points Change` equals its close minus the old name's last close, to 0.01. The India Internet seam above shows the test in action.
- Anything else is a new series.
- The gaps 3 Jan to 1 Apr 2013, Apr 2013 to Jan 2014, Jan 2016 to Apr 2016, and 2016 to Sep 2024 must be read from the full download to date each seam to the day. I could not do that yet: the download was at about Apr 2013 when I stopped.

## 6. Repo today, and a proposed store

**What exists (read 21 Nov 2026):**
- `data/benchmarks.csv`, through `benchmark_store.py`: Nifty 500 and Nifty 50.
  - Kaggle 1999-2015, then SS 2015-2024, then NSE's Pd bundle from 25 Sep 2024.
  - Source-ranked merge.
  - `docs/PRICE_SOURCES_AUDIT_2026-11-21.md` says Kaggle and SS before Sep 2024 were never checked against NSE.
- `data/benchmark_indices.csv`, through `benchmark_indices.py`: 11 indices from Screener charts.
  - Weekly before 16 Oct 2025.
  - Checked against an ETF with a 1.5-point tolerance.
- `data/nse_total_market.csv`, through `scripts/collect_nse_total_market.py`: the first user of `ind_close_all`.
  - Adds missing sessions.
  - Refuses to write if a close differs from the Screener file by more than 0.05%.
- R2 `indices/prices/research`, through `scripts/build_nse_index_prices.py` and `r2_nse_index_prices.yml` at 20:30 UTC: 5 size indices plus 13 sectors.
  - niftyindices historical endpoint first, then the Screener fallback.
  - Read by `src/loaders/index_levels.py` (`R2DatasetReader.resolve_current`, `st.cache_data(ttl=3600)`; returns None, and the page says so, on failure).
- `indices/` is in `PROTECTED_DATASETS` (`scripts/r2_retention.py`), so a new dataset under it is never pruned.
- `r2_publish.py` takes `--dataset --source --key-root --pipeline-version`.

**Proposal.** One NSE record replaces three partial ones.

1. **Raw: `indices/nse_close_all/raw`.** Key root `archive/indices/nse_close_all/raw`.
   - One object per session: NSE's CSV bytes unchanged, plus `sha256` and `fetched_at` in the manifest.
   - Same shape as `nse/prices_daily` in `scripts/nse_collect.py`: one small immutable file per day.
   - Weekdays with no file go to the existing `nse/closed_days`. Cross-check them against `data/reference/nse/holidays.csv` and `special_sessions.csv`; Muhurat 8 Nov 2026 is a session.
2. **Built: `indices/nse_close_all`.** Key root `archive/indices/nse_close_all`.
   - One parquet holding the whole table: about 3,550 sessions × about 30-169 rows, roughly 350k rows, under 15 MB.
   - Rebuilt from raw. Pipeline `nse_close_all_v1`.
   - Schema:

   | column | type | note |
   |---|---|---|
   | date | date32 | from `Index Date`, must equal the file's date |
   | index_key | string | stable id from the alias table |
   | name_raw | string | as printed that day |
   | category | string | broad / sector / thematic / strategy / variant / fixed_income / volatility (MD grouping) |
   | open, high, low | float64, nullable | `-` becomes null |
   | close | float64 | required |
   | points_change, change_pct | float64 | kept for the continuity check |
   | volume | int64, nullable | |
   | turnover_cr | float64, nullable | |
   | pe, pb, div_yield | float64, nullable | |
   | pe_basis | string | `standalone` before the verified switch date, `consolidated` after |
   | basis | string | `live` for rows from the daily file; `backcalc` only for niftyindices rows dated before `launch_date` |
   | source | string | `nse_ind_close_all` or `niftyindices_hist` |
   | raw_sha256 | string | ties a row to its raw object |

   - A small reference table is committed in git, as the R2 spec allows for small reference data: `data/reference/nse_index_catalogue.csv`. Columns: index_key, current name, category, base_date, base_value, launch_date, first_seen, last_seen, factsheet URL, and the alias rows with evidence.
3. **Daily incremental.**
   - A step in `daily_sync`, or its own workflow after 18:30 IST.
   - It fetches every trading day after the newest raw object, through today. Use `nsearchives` first; `niftyindices.com/Daily_Snapshot/ind_close_all_DDMMYYYY.csv` serves the same file (seen on `/reports/daily-reports`, 21 Nov 2026) and is the second copy.
   - A 404 on a day NSE traded is retried the next run. It is never recorded as closed until a week has passed, which is the `nse_collect` rule.
4. **Guard.** It refuses to publish and exits 1 with `::error::` when any of these fail:
   - (a) **Restated close.** A (date, index_key) already stored has a different close (tolerance 0.005: same source, so it must match to the paisa). This includes the same day's file fetched again from the second host. A real NSE restatement goes in a notes.json-style corrections file with evidence, per CLAUDE.md.
   - (b) **Duplicate name.** A name appears twice in one file (as on 8 Feb 2013).
   - (c) **Broken continuity.** `points_change` ≠ close − previous stored close by more than 0.02. A new name with no alias is reported, not joined.
   - (d) **Nifty 50 / 500 against the bundle.** Nifty 50 and Nifty 500 must equal the NSE Pd bundle rows in `data/benchmarks.csv` to 0.01. This is a second NSE file, independent of this one.
   - (e) **Total Market.** Nifty Total Market must equal `data/nse_total_market.csv`.
   - (f) **Row count.** The row count must not fall more than 10% below the previous session's, except on announced special sessions.

   It also prints, without refusing, the Screener/ETF comparison already in `benchmark_indices.etf_check`.
5. **How pages read it.**
   - A loader `src/loaders/nse_indices.py`, modelled on `index_levels.fetch_index_levels`: `R2DatasetReader.resolve_current("indices/nse_close_all")`, `st.cache_data(ttl=3600)`, an env-var local file for development, and None plus a stated reason on failure.
   - The Indices page reads closes, P/E, P/B and yield from it.
   - Strategy series start at `launch_date` from the catalogue unless the user asks for back-fill, which is shaded.
   - P/E charts draw the 2021 basis line.
   - Later, with S165, `benchmark_store` and `benchmark_indices` can read Nifty 50/500/Total Market/momentum closes from this dataset. Screener stays as the cross-check, not the record.

## Not verified / open

1. **TRI and back-filled price history.** The niftyindices historical endpoints (price, TRI, P/E-P/B) returned 302 from here, so I could not confirm how far back TRI and the pre-launch history go, or the request limits. Whether `r2_nse_index_prices` is currently on its Screener fallback is a lead to check in its logs.
2. **The April 2021 P/E switch.** I found no primary NSE notice. The date is from secondary sources; test it on the files once downloaded.
3. **The 29 Sep 2023 P/B switch.** One secondary source with no NSE citation.
4. **Exact seam dates** for the 2013 S&P drop, the Nifty Quality 30 → NIFTY100 Quality 30 change, the 2016 Midcap/Smallcap 100 redefinition and the Corporate Group renames. These need the full download (`ind_raw/` was at about Apr 2013).
5. **Nifty100 Equal Weight launch date.** There is no factsheet in NSE's list. Nifty Smallcap 500's launch date was not fetched either; it was present on 1 Jan 2026, absent, then back from 28 Jan 2026.
6. **One MD page reference** (Growth Sectors 15 back-testing) was quoted from the text extract and not checked against the page image.
7. **Other strategy indices' scoring details.** Value 20's score components and Multicap MQ50's 50:30:20 split are from MD summaries, not re-read line by line.
8. **Classification is my mapping onto NSE's headings.** NSE puts a few indices (SME Emerge, Small Finance Banks & MFIs) under different headings than I did.
