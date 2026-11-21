# Indices page: design research (S170)

21 Nov 2026. Read-only research for the S170 Indices page. Rules applied: `docs/PAGE_DESIGN.md`, `docs/THEME.md`.
Dashboard sections compared: `src/ui/views/dashboard_home_view.py` (section 3 `section_momentum`, section 5 `section_size`, `_glance`).

## 0. What could and could not be reached

| Site | Reached? | How it was read |
|---|---|---|
| tipsheet.markets (home, /valuation, /factors/) | Yes | Fetched and summarised |
| niftyindices.com (index page, factsheet PDF) | **No** (timed out; the PDF URL returned a JS stub) | NSE's own daily file `nsearchives.nseindia.com/content/indices/ind_close_all_DDMMYYYY.csv` fetched instead (20 Nov 2026, 19 Oct 2026, 20 Aug 2026, 31 Dec 2025, 20 Nov 2025, 15 Mar 2013). The factsheet layout below is **from prior knowledge, not re-checked today** |
| Morningstar India markets | **No** (`morningstar.in/markets.aspx` is a 404; morningstar.com/markets 403) | Style-box method from Morningstar's glossary/methodology search results; the Market Barometer layout from prior knowledge |
| Koyfin | Partly (features page only) | Dashboard list confirmed (World Equity Indices, Sectors, **Factors**, Countries); column/chart detail from prior knowledge |
| TradingView indices overview | Yes | Fetched |
| StockCharts | Help pages yes; the live summary page 429 | Sector Summary help page and search results |
| Finviz groups | Yes (controls only; table not in the text) | Fetched |
| JPMorgan Guide to the Markets | Landing page only; chart pages via search snippets of past editions | "Returns and valuations by style" and valuation slides from search plus prior knowledge |
| MSCI factor pages | **No** (empty page) | Not used, except general knowledge of its factor charts |
| Tickertape | Yes (Nifty 50 index page) | Fetched |
| sharpely | **No** (client-rendered; only the title came back) | Not used |
| Trendlyne heatmaps | **No** (405) | Not used |
| Bloomberg / FT markets data | **No** (403 / blocked) | Not used |

Where a row says "prior knowledge", treat it as a lead rather than evidence (CLAUDE.md rule).

## 1. What each site does

### tipsheet.markets (the owner's model)
- **First answer:** a one-line, number-led verdict for the day ("The Nifty 50 rose 1.1%; small caps fell 0.1%."), then the drawdown from the 52-week high, the year-to-date move and the count above 200-day averages. Its section headings are questions: "How the main indices have moved", "Which sectors lead?", "Is leadership changing?", "Which investing styles are paying?", "Is the market cheap or dear against its own past?".
- **Devices that work:**
  1. *Valuation against its own past.* The headline states the finding: "The Nifty 50 trades at 21.0 times trailing earnings, higher than 72% of readings since 1999." The page gives a usual range (14.9 to 21.4), the record (34.9, Feb 2021) and a year ago (22.8), then a dot plot of P/E and P/B percentiles for 22 indices. It explicitly **never compares indices on raw multiples** ("sectors earn differently").
  2. *Factor scoreboard against the parent.* It shows each factor's total-return lead over its parent index at 3M, 1Y, 3Y and 5Y. A calendar-year league table runs 2003 to 2026, with each factor's launch year in its header. A relative line (factor ÷ parent = 100 from a common start) and a "worst relative fall" give the factor's drawdown against its parent, not an absolute loss.
  3. *Size on one scale* (large, mid, small, micro), with total-return indices stated as such.
- **Clutter or misleading:** the home page is very long (16+ sections). It shows 8 return windows (1D…5Y) in one table, which is more columns than any one question needs. The factor page has a weakness of its own: back-calculated years before launch sit in the same table as live years, and the page admits the difference is not visible in the table. Its honest caveats are worth copying: back-tested leads are "the less reliable guide"; mid/small live records are too short to judge.

### niftyindices.com / NSE factsheets (from the daily file; factsheet from prior knowledge)
- **First answer:** the index's methodology blurb, then a returns table. Price return and total return are shown over QTD, YTD, 1Y, 5Y and since inception. Beside them sit statistics (std dev, beta and correlation against the Nifty 50) and fundamentals (P/E, P/B, dividend yield). A chart shows the index against its parent since the base date; sector weights and the top 10 constituents follow.
- **Devices that work:** price and total return side by side; P/E, P/B and yield for every index, daily. The daily file has 169 indices on 20 Nov 2026, with columns `P/E, P/B, Div Yield`. The 2013 file has the same columns but only 33 indices under the old "CNX" names.
- **Clutter or misleading:**
  - "Since inception" returns mix back-tested years and live years without saying so.
  - A factor index's P/E jumps at each rebalance. Nifty500 Momentum 50 went from **45.03 on 20 Nov 2025 to 30.02 on 31 Dec 2025**, and Nifty200 Momentum 30 from 40.24 to 26.59: the stocks changed, not the prices. A P/E band over a factor index's own history is therefore not meaningful.
  - P/E also differs by source: Tickertape shows Nifty 50 P/E **20.02** on 20 Nov 2026, NSE's file **21.02**.
  - NSE moved its index P/E to consolidated earnings around April 2021. **This is not verified here**; a lead to check against NSE's circular, because it would put a break in any band that crosses 2021.

### Morningstar (style box; Market Barometer from prior knowledge)
- **First answer:** "which part of the market did best", as a 3×3 grid of large/mid/small × value/core/growth returns, coloured by return, for a selectable period (1D, 1W, 1M, YTD, 1Y…). The US site adds a price-to-fair-value reading.
- **Devices that work:** the size × style matrix. It shows two dimensions at once and is readable in two seconds.
- **Clutter or misleading:**
  - The grid's heat colour carries the meaning on its own.
  - Its value/growth split comes from Morningstar's own scoring, which no NSE index replicates.
  - An Indian version built from NSE indices has gaps. There is no mid or small value index with history, and no "growth" in mid or small caps: Nifty500 Growth 50 appears in the daily file only from Oct 2026 in my samples. A 3×3 box would therefore be mostly empty cells or proxies.

### Koyfin
- **First answer:** "today's markets", one screen across asset classes. A dedicated **Factors** dashboard lists factor ETFs or indices with returns over several windows.
- **Devices that work (prior knowledge):** dense tables with returns at 1D/1W/1M/3M/YTD/1Y and "% off 52-week high". The valuation chart plots a P/E series with its average and ±1 and ±2 standard-deviation bands.
- **Clutter or misleading:** a terminal look, with too many columns for a reader who is not a trader. Standard-deviation bands assume a normal shape; percentile bands do not.

### TradingView indices overview
- **First answer:** a map of index moves today (−3% to +3% colour scale), then lists of US and world indices.
- **Device that works:** the market-breadth table per index (regime, advancing/declining, above 50D/200D, net 52-week highs, "outperforming the index, 1M"). That is Breadth's ground, not Indices'.
- **Clutter:** community ideas, news and an FAQ on the same page; only one return window; colour-only meaning.

### StockCharts (Sector Summary, PerfCharts, MarketCarpets)
- **First answer:** "which sector is strongest over the chosen period", a ranked list that drills down to industries and then stocks.
- **Devices that work:**
  1. *PerfCharts:* up to 10 lines rebased to 0% from a chosen start, with an absolute or relative switch. It is the clearest way to compare a few indices.
  2. *MarketCarpets:* tiles coloured by return, for spotting outliers.
  3. *Ranked table with a period selector.*
- **Clutter or misleading:** the period selector hides the other periods, so readers see one window at a time (against PAGE_DESIGN's "everything visible" and "3M, 1M, now"). Carpets are colour-only.

### Finviz groups
- **First answer:** "which group led", for sector, industry or **capitalisation**. Views are Overview, Valuation, Performance and Performance Chart (bars).
- **Devices that work:**
  - Performance over Week, Month, Quarter, Half, Year and YTD in one row per group.
  - A valuation view (P/E, forward P/E, PEG, P/S, P/B) for the same groups.
  - A bar view of one period.
- **Clutter:** tabs split one question across views; raw P/E across groups invites the cross-sector comparison tipsheet warns against.

### JPMorgan Guide to the Markets (chart pages)
- **First answer:** each slide has a title that states the topic, plus a short "key takeaway". The relevant slides:
  - *Valuation measures:* forward P/E over 25 years, with the average and ±1 std dev lines. A small table lists today's reading, the 25-year average and how many standard deviations away it is, for several measures.
  - *Returns and valuations by style:* a 3×3 size × style grid of returns (QTD, YTD, 1Y). A second grid shows **current P/E as a % of its own 20-year average**.
  - *Asset-class returns, periodic table:* a calendar-year league table with coloured tiles.
  - *Annual returns and intra-year declines:* bars for each year's return and a dot for its worst fall within the year.
- **Devices that work:**
  - The valuation chart against the index's own history.
  - "P/E as % of its own average", which solves tipsheet's cross-index problem in another way.
  - **Intra-year declines.** They answer "how bad do normal years get?" without a forecast.
- **Clutter:** the periodic table's colours carry the identity and the eye has to hunt for one asset. Slides pack 3 or 4 exhibits each.

### MSCI factor pages, sharpely, Trendlyne, Bloomberg, FT
Not reached (see section 0). From prior knowledge, which is a lead only:
- MSCI's factor dashboards show cumulative factor-vs-parent lines and a calendar-year factor table, i.e. the same devices as tipsheet's /factors/.
- Trendlyne's heatmap is a market-cap-sized tile map of an index's stocks, coloured by day change. That is a stock view, which our Sectors page already covers by industry.
- Bloomberg and FT data pages are index lists with last, change and %; they are reference pages, not answers.

### Tickertape (Nifty 50 page, reached)
- **First answer:** level and day change, then ETFs tracking the index, tabs, and P/E, P/B and yield as **today only** with no history.
- **Works:** constituents with weight and **return attribution**, i.e. which stocks moved the index.
- **Clutter or misleading:**
  - The chart and return panels did not load without script.
  - News headlines and an upsell are on the page.
  - Its P/E (20.02) disagrees with NSE's (21.02).
  - A P/E with no history cannot say cheap or dear.

## 2. Devices worth taking, ranked

1. **The answer-first sentence with the number in it** (tipsheet, JPM key takeaway). PAGE_DESIGN 2 already requires this.
2. **P/E and P/B as a percentile of the index's own history, broad and size indices only.**
   - Band chart: weekly P/E with the usual range (middle half) shaded, the record marked, and a crosshair.
   - A dot or line-bar row per index showing its percentile, with 3M, 1M and now as numbers.
   - **Not for factor indices**: their P/E resets at each rebalance (the 45.0→30.0 example above). For a factor, show P/E against its parent today, as tipsheet does.
3. **Lead over the parent, not raw return,** for factor indices.
   - Line bars at 3M, 1M and now.
   - Then a calendar-year league table of leads, with live years marked apart from back-calculated years.
4. **A relative line (index ÷ parent) with its worst relative fall.** It answers "how long can this style lag?" (tipsheet, MSCI).
5. **Intra-year decline per year** (JPM), for the market and each size. It shows how deep a normal year's fall goes, without forecasting.
6. Size × style matrix: **reject** for India. NSE has no mid or small value or growth indices with history, so most cells would be empty or proxies.
7. Return heat table across 8 windows and colour-only carpets: **reject**. Too many figures, and meaning carried by colour alone (PAGE_DESIGN 3: "not with colour alone").

## 3. What our other pages already answer (so the Indices page does not)

- **Breadth** (`breadth_view.py`, `market_questions.py`): "Are most stocks taking part?" and "Is the market in an uptrend?" (10-month rule, 200D gap, from high). Plus participation charts and highs/lows.
- **Sectors:** industries, equal-weighted medians over the ranked 750; leadership map.
- **Dashboard 3, "Is momentum still working?":** the top-100 lead over the Nifty 500 at 12M, 3M and last month. The month so far is Nifty500 Momentum 50 against Nifty Total Market. Then monthly lead bars and the tested signals table.
- **Dashboard 5, "Size, and where momentum works":** the book's share by size; each size against the market at 1/3/6M (`di.WINDOWS = (1, 3, 6)`); each momentum index against its size index at 1/3/6M.
- **Dashboard "At a glance":** the day's change for Total Market, Nifty 50, Midcap 150, Smallcap 250 and Microcap 250. It links to *Breadth*, and should link to Indices once that page exists.

## 4. The questions an Indices page answers that the others do not

1. **Is the market cheap or dear against its own past, and for which size?** No page shows valuation today.
2. **Which investing styles are paying, against their own parent index?** Value, quality, low volatility, alpha, equal weight and momentum. Momentum stays as one row here; the Dashboard keeps the depth.
3. **Which size is leading, over the long run as well as this month?** Calendar years, and how bad a normal year's fall gets per size. Dashboard 5 covers only 1/3/6 months and only as the book's context.
4. **How long and how deep can a style lag?** Worst relative fall and its recovery, so a reader can put momentum's current lag in proportion.
5. (Optional) **What moved the Nifty 50 / Nifty 500 this month?** Contribution by constituent or sector. This needs weights, which we do not store, so it is out of scope unless S168 adds NSE's weights.

## 5. The proposed page

The kicker "Indices"; then a title that answers question 1 or 2. A verdict paragraph and pills follow. The numbers below are **real readings from NSE's daily files, price returns, one source and not cross-checked**. 19 Oct stands in for "1 month ago" because the 20 Oct file returned no data. They are for the mock-up only and need the section 5 checks of PAGE_DESIGN before they ship.

**Title (example):** "Large caps led the month's rally; every style index trailed its parent."
(Nifty 50 +12.7% and Microcap 250 −1.0% from 19 Oct to 20 Nov. Every factor index in the sample trailed its parent over that month, from −0.5 pts for Nifty500 Low Volatility 50 to −11.9 pts for Nifty Alpha 50.)

### Section 1. Valuation: "The market is cheaper than a year ago, except small caps."
- **Proof:** P/E for Nifty 50, Total Market, Midcap 150, Smallcap 250 and Microcap 250. One row each, three columns, 3M ago, 1M ago and now (20 Aug, 19 Oct, 20 Nov), then the percentile of its own history as line bars (0–100%, 2% steps per PAGE_DESIGN 4.2). P/B and dividend yield go in "Show the table".
  - Readings: Nifty 50 20.48 / 19.33 / 21.02 (22.80 a year ago).
  - Midcap 150: 29.80 / 27.71 / 28.21 (33.45).
  - Smallcap 250: 33.84 / 33.26 / 32.14 (29.55 a year ago: dearer than then, even though its price is up only 5%).
- **Then one band chart:** the Nifty 500's (or Total Market's) weekly P/E since 2012 from the S168 store. The usual range is shaded, with a crosshair readout of date, P/E and percentile.
- **Before it ships:**
  - Confirm the 2021 consolidated-earnings break.
  - Name the history's start, which differs per index: Midcap 150 and Smallcap 250 enter the file later than 2012.
  - Map the old CNX names.
  - **No claim that low P/E means higher returns** unless S150-style tested on our record (next-12-month return by P/E tercile, fixed rule, both halves). Otherwise say "describing is not forecasting".

### Section 2. Styles: "Value led over the year; quality and momentum lag their parents."
- **Proof:** one row per factor (Value, Quality, Low volatility, Alpha, Equal weight, Momentum), with its NSE index and parent named under the label. Columns: lead over parent at 3M ago (window), 1M and 1Y; the 1Y lead drawn as line bars from a zero line (negatives fill left, 0.5 pt steps).
  - 1Y leads on 20 Nov: Nifty200 Value 30 +6.3, Nifty Alpha 50 +2.9, Nifty100 Low Volatility 30 −1.2, Nifty200 Momentum 30 −6.8, NIFTY200 Quality 30 −7.7 pts.
  - Prefer total return. Price leads understate value by its higher yield (3.3% against about 1.2%).
  - P/E against the parent today goes in "Show the table". Not as a band, because of rebalances.
- **"3M, 1M, now" here means the lead over the trailing 12 months as read 3 months ago, 1 month ago and now.** That gives one window seen at three dates, not three windows. Three windows would be the Dashboard 5 layout and a different figure.

### Section 3. Calendar years: "Since 2013, no style led its parent in more than N of the years."
- **Proof:** a league table of leads by calendar year, rows by year, columns by style, figures in Plex Mono, right-aligned. Live years plain, back-calculated years muted and named in the header row ("live since 2020"). This year is year to date.
- No heat colours: only the sign colour on the figure. Headline N to be computed (it is not computed here).

### Section 4. Drawdowns: "Momentum is N pts below its best against the Nifty 200; its worst was M pts, in YYYY."
- **Proof:** a two-pane chart with one crosshair, for the selected style (chips): the relative line (style ÷ parent = 100) and the fall from its relative peak.
- Beside it, a small table per style: worst relative fall, its dates, and months to recover.
- This puts the Dashboard's "momentum has lagged" in proportion without repeating its figures.

### Section 5. Size by year: "In an ordinary year, small caps fall twice as far within the year as large caps."
- **Proof:** a JPM-style chart for each size index. Each calendar year's return is a bar and its worst fall within the year a dot, drawn as small multiples on one scale.
- The "twice" in that headline is a placeholder, to be computed.
- The headline must be a tested description (computed over all years), not a forecast.

**Removed on purpose:**
- Day changes. They are on the Dashboard's glance and the strip.
- A sector heatmap (Sectors owns industries).
- An 8-window return table.
- A size × style matrix.
- Constituent lists.

**Foot:** "Data to 20 Nov 2026." Nothing else.

## 6. What goes on the Dashboard instead

- **Replace the freed Leadership space (S169) with a three-line block: "Indices: valuation and styles".**
  - The Nifty 500 P/E percentile now, with 1M and 3M beside it.
  - The best and worst style by 1Y lead over its parent.
  - A link: "Valuation and styles, on Indices →".
  - No chart; the Indices page owns it.
- **Dashboard 3 stays as is.** It is about this ranking's top 100, not about NSE's momentum indices. Its month-so-far tile is the only NSE-index figure in it. The Indices page must not repeat that tile; its momentum row uses 12-month leads at three dates instead.
- **Dashboard 5 stays, narrowed to the book.** Keep the book's size mix and "momentum against its size index". Size against the market at 1/3/6M is index data; it should be owned by Indices section 5 or linked from there. If kept on the Dashboard, the Indices page shows size only by calendar year and intra-year fall, so no figure appears twice.
- **"At a glance → Indices"** should link to Indices, not Breadth.

## 7. The owner's alternative: add indices to Breadth and rename it "Market"

| | New Indices page | Breadth + indices = "Market" |
|---|---|---|
| Reader questions | Valuation, styles, size over years, style drawdowns: 4 questions, none overlapping Breadth's two | 6 questions on one page. Breadth's are about *today's participation and trend*; indices' are about *levels against history and styles against parents*. Different time scales on one page |
| Page length | About 5 sections, similar to Sectors | Breadth already has 2 question blocks, charts with settings, highs/lows and lists. Adding 5 sections roughly doubles it; tipsheet's home page shows the cost of that length |
| Duplication with Dashboard 3 and 5 | Manageable: Indices owns index data, the Dashboard keeps book-specific figures and links | Same overlap, plus Breadth's trend answer already reads Nifty 500 / size index levels (`trend_answer(bench, size_closes)`). A "Market" page would show the same index's trend twice in two framings |
| Naming | "Indices" says what is on it | "Market" is vague; readers would expect flows (Dashboard 4) and sectors too |
| Cost | A new page, requirements list, mock-up | Rework of a recently redesigned page; the menu loses "Breadth" |

**View: a separate Indices page.**
- The questions differ in kind and time scale: participation and trend now, against valuation and style over years.
- Combining them makes the longest page on the site.
- The duplication problem is the same either way and is solved by ownership: Indices owns index figures, and the Dashboard links.
- The one argument for merging is fewer menu items. That can be met by grouping Breadth, Sectors and Indices under one "Market" menu heading, without merging the pages.

## 8. Not checked
- Every figure above is from NSE's daily file alone, as price returns, and has not been checked against a second source. Total-return series were not fetched.
- The 2021 P/E-basis change is not confirmed.
- How far back each index's P/E history goes in the archive: only 2013 (33 indices) and 2025–26 were sampled.
- tipsheet's valuation and factor numbers were not reproduced.
- Sites in section 0 marked "No" were not seen today.
