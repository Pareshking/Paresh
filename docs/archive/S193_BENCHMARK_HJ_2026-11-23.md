# Benchmark H (charts) and J (accessibility): evidence

Date seen for every item: 23 Nov 2026 (unless a published date is given). "HTML" means the
server-rendered page was fetched and the markup read. That shows the buttons, their labels and which
one is marked selected, but not what JavaScript does after load. "Not seen" means it was not verified.

## H. Charts

### H1. Default range and range labels for stock and index price charts

| Site | Choices (exact labels) | Default | Source |
|---|---|---|---|
| Google Finance (NIFTY 50) | 1D 5D 1M 6M YTD 1Y 5Y MAX | **1D** (`aria-label="1D" aria-selected="true"`) | HTML, google.com/finance/quote/NIFTY_50:INDEXNSE |
| Yahoo Finance (^NSEI) | 1D 5D 1M 6M YTD 1Y 5Y All | **1D** (`id="tab-1d-qsp" aria-selected="true"`) | HTML, finance.yahoo.com/quote/%5ENSEI/ |
| TradingView symbol page (NSE-NIFTY) | 1 day, 5 days, 1 month, 3 months, 6 months, Year to date, 1 year, 5 years, 10 years, All time | **1 day** (class `selected`) | HTML, in.tradingview.com/symbols/NSE-NIFTY/ |
| TradingView help ("Chart view mode") | "1 day", "5 days", "1 month", "3 months", "6 months", "YTD", "1 year", "5 years", "All data" | not stated | in.tradingview.com/support/solutions/43000724233 (undated) |
| Screener.in (RELIANCE) | 1M 6M **1Yr** 3Yr 5Yr 10Yr Max | **1 year** (chart.js: `// set and load data for last 365 days` … `days: 365`) | HTML and cdn-static.screener.in/js/chart.6948de972d84.js |
| Groww (RELIANCE) | 1D 1W 1M 3M 6M 1Y 3Y 5Y All | **1D** (first key highlighted) | HTML, groww.in/stocks/reliance-industries-ltd |
| FT Markets (RELIANCE:NSI) | 1D 3D 1W 1M 6M 1Y 3Y 5Y | **6M** (`aria-selected="true" aria-controls="180-panel"`) | HTML, markets.ft.com/data/equities/tearsheet/summary?s=RELIANCE:NSI |
| Moneycontrol (RELIANCE) | Price history: 1W 1M 3M 6M (default **6M**). PE/PB charts: 1M 3M 6M 1Y 5Y MAX (default **1Y**). Returns chart: 1M 3M 6M 1Y 3Y 5Y MAX (default **1Y**) | as listed | HTML, moneycontrol.com/india/stockpricequote/refineries/relianceindustries/RI |
| Groww blog | "One day (1D), One week (1W), One month (1M), Six Months (6M), One year (1y), Three years (3Y), Five years (5Y), All" | n/a | groww.in/blog/how-to-read-stock-charts (undated) |
| Tickertape | not seen (CloudFront returned 403) | not seen | |
| NSE India | not seen (the page needs JavaScript; WebFetch got 503) | not seen | |
| Morningstar, Koyfin, Bloomberg public, Zerodha Kite | not seen (JavaScript or login; the Bloomberg site returned 403). Koyfin help: dates are set by "selecting the start and end dates on top of the chart"; no default stated (koyfin.com/help/charts-and-graphs, updated 19 Dec 2024) | not seen | |

On "1Y" versus "12M": every site seen writes years as 1Y, 1Yr or "1 year". None writes "12M" on screen.
TradingView uses `12M` only as an internal id (`time-range-button-12M`), with the visible label "1 year".
Count: 7 sites, 0 visible "12M".

### H2. Portfolio and fund performance charts
- **Portfolio Visualizer** backtest form (HTML): defaults `startYear` `1985` (the earliest year offered) and end `2026` / `Dec`. The sample results say "The time period was constrained by the available data". This is effectively the full history.
- **Zerodha Console** performance curve (z-connect post, 11 Apr 2025): the curve starts "from July 1, 2022, or from the date your account first reaches ₹1,000". You can "hover over the curve to view changes for any specific time period" and zoom. This is a full history, with no preset buttons. A forum request for 1M…Max buttons got the reply "we'll review".
- **Morningstar Advisor Center** "Return Growth" (search snippet only; the page returned 522): "defaults to 10 years ago through last month end". A Morningstar snapshot help page says growth of $10,000 "begins at the date of the fund's inception". Both are second-hand snippets, so treat them as leads.
- **Groww** portfolio analysis (June 2025 update): value against amount invested over time. The default window is not stated.
- Count: 2 verified defaults are full history (Portfolio Visualizer, Console). 1 lead is a fixed 10 years (Morningstar Advisor). No fixed short window was found.

### H3. Breadth charts (share above the 200-day average, A/D, highs and lows)
- TradingView INDEX-S5TH (S&P 500 share above the 200-day average), HTML: only "1 year", "5 years", "10 years" and "All time" are offered. None is marked selected in the HTML, so the default was not seen. The short ranges (1D to 6M) that its price pages offer are left out.
- StockCharts SharpCharts: the range menu offers "Fill the Chart" or presets "from 1 Day up to 100 Years" (help.stockcharts.com/charts-and-tools/editing-sharpcharts, undated). The factory default was not seen; the workbench needs JavaScript.
- Barchart $S5TH, Chartink, Investing.com, MarketInOut: not seen (blocked, or JavaScript only).

### H4. Picker behaviour
All seen pickers redraw in place on the client side:
- Google Finance: `role="tab"` buttons with `jsaction="click:..."`.
- Yahoo Finance: `role="tablist"` / `role="tab"`.
- FT: `role="tab"` with `aria-controls="180-panel"`.
- Screener: `onclick="CompanyChart.setActive(event)"`, which fetches with `Utils.ajax` and redraws.
- Moneycontrol: `onclick="durChange('1m')"` and `showTTMGraph(...)`.
- Groww: div keys.
None reloads the page. Count: 6 of 6.

### H5. Readout and legend
- Screener: crosshair, plus a tooltip row reserved above the plot. Its labels match the legend (chart.js: "Height reserved above the plot for the tooltip row", "[label, value HTML] pairs shown in the tooltip, labelled as in the legend").
- TradingView Charting Library docs: the legend sits at the top left of the chart and shows close, change and change % (with OHLC unless overridden). Values follow the crosshair. The Data Window also updates on hover (tradingview.com/charting-library-docs/latest/ui_elements/Legend).
- Koyfin: "Crosshair" and "Mouseover" settings display the axis and data values (help, updated 19 Dec 2024).
- Zerodha Console: hover readout (11 Apr 2025).
- FT: the comparison series are shown as chips with a coloured border (`mod-symbol-chart__current-comparison`, `border-color:{color}`). This is a legend chip, not an end-of-line label.
- End-of-line labels were found on none of these sites. Count: 4 have a hover readout or crosshair; 2 have a heading or top-left legend readout.

## J. Accessibility

### J1. Colour alone
- **WCAG 2.2 SC 1.4.1** (Understanding page, updated 16 Sep 2025): "Color is not used as the only visual means of conveying information, indicating an action, prompting a response, or distinguishing a visual element." Failure F13 is "a chart that conveys information by color". Red against green passes only if they also differ in lightness by at least 3:1.
- **GOV.UK Design System warning text**: a "!" icon, a bold `<strong>` message and a visually hidden word "Warning". Icon colours "use the root text and background colours" (v5.3.1, Apr 2024). In other words, the warning is black and white: shown by the icon and the word, not by colour.
- **USWDS alert** (latest update 18 Aug 2026): "Users should be able to understand the purpose of the alert without relying solely on its color or the shape of its icon". It recommends starting alert text with a word that names the type, such as "Warning" or "Error".
- **Atlassian section message** (undated, © 2026): "Don't rely on color alone to convey the severity of the message". Text should "clearly explain when the message is a warning or error". Foundations/colour: "Pair selected colors with another visual cue, such as a checkmark, underline, border, or change in shape."
- **IBM Carbon notifications** (updated 30 Sep 2026): "Each status is associated with a specific color and icon". Informational is blue with an info icon, success green with a checkmark, warning yellow with a warning icon, error red with an error icon.
- **Bloomberg Terminal** (Tech at Bloomberg, 2021; the page returned 403 here, so this comes from search snippets): red and green are the default down and up colours, and about 20,000 or more users may have red-green colour blindness. Bloomberg offers alternative colour schemes for deuteranopia and protanomaly (`PDFU COLORS <GO>`). Whether it adds symbols was not seen.
- **Economist Impact** (Nightingale, 13 Jul 2023): green for good and red for bad means "we have an accessibility problem". It built Cassy to check 3:1 contrast across each pair of palette colours.
- **FT**: no FT rule was found; the Visual Vocabulary has no colour section. FT's markup, though, pairs colour with an arrow and a sign: `mod-format--neg` + `icon--arrow-downwards` + `-26.50 / -1.92%`.

### J2. Warning styling: icon plus text in every system
GOV.UK uses "!" plus bold text plus a hidden word, in black. Carbon uses a filled icon plus a colour for each status. Atlassian's warning is yellow with an exclamation icon, and its text names the severity. USWDS uses an icon, colour and a leading type word. Material was not seen: the page needs JavaScript.

### J3. Up/down on Indian and global finance sites (HTML)
| Site | Colour | Sign | Arrow |
|---|---|---|---|
| Google Finance | green / red classes | "+2.58%", "-0.34%" | `arrow_upward` / `arrow_downward` icon |
| FT Markets | `mod-format--pos` / `neg` | "-1.92%" | arrow-downwards icon (some cells have none) |
| Yahoo Finance | `txt-positive` | "+4.75%", "-450.95 (-1.75%)" | none |
| Groww | `contentPositive` / `contentNegative` | "+28%", but "-26.50 (1.92%)", so the % has no minus | none |
| Moneycontrol | `oia_greentext` / `oia_redtext` | "-5.43%", but the positive "5.43%" has no plus | some `arrow down` icons |
| Screener, Tickertape, NSE, Kite | not seen | | |

Every site seen uses green for up and red for down. None uses blue/red. Signs are applied unevenly on the Indian sites.

### J4. Contrast
WCAG 1.4.3 (updated 4 Oct 2026) requires 4.5:1 for text and 3:1 for large text. The only exemptions are inactive, decorative and logo text. Placeholder text is not exempt, so muted text has no exemption. WCAG 1.4.11 asks 3:1 for "parts of graphics required to understand the content". Its Understanding page says "The lines should have 3:1 contrast against their background". The lines need not contrast with each other.

Measured tokens:
- Carbon: `$text-secondary` Gray 70 #525252 (about 7.5:1 on white) and `$text-helper` Gray 60 #6f6f6f (about 5:1), from search snippets.
- GOV.UK: `secondary-text` #484949, about 9:1.
- Atlassian: "text smaller than 24px must pass 4.5:1".

### J5. Automated checks on finance sites
One fintech example was found: Opto (advisor platform, 31 Mar 2025) runs Playwright + axe in CI, "we could catch issues before they reached production". No evidence was found for any broker or market-data site (Zerodha, Groww, Tickertape, Moneycontrol, NSE, TradingView, Yahoo, FT). That counts as not found.

## Recommended convention to follow
1. **Default range, recent-price charts:** the convention depends on what the page is for. Quote pages open on 1D (Google, Yahoo, TradingView, Groww: 4). Research pages open on 6M or 1Y (FT 6M, Moneycontrol 6M/1Y, Screener 1Y: 3). For a daily-close momentum site, **1Y (Screener) or 6M (FT)**. A 1D intraday view does not apply to end-of-day data.
2. **Default range, track-record charts:** **full history / since inception** (Portfolio Visualizer, Console: 2 verified; Morningstar 10Y is an unverified lead).
3. **Range labels:** **"1Y", not "12M"** (7 of 7 sites; TradingView keeps 12M internal only). Sites differ on "Max", "MAX", "All" and "All time".
4. **Picker:** **tabs that redraw in place**, with `role="tab"` and `aria-selected` (6 of 6). None reloads the page.
5. **Readout and legend:** a **hover or crosshair readout in a row above or at the top left of the plot, labelled like the legend** (Screener, TradingView, Koyfin, Console: 4). No end-of-line labels were seen.
6. **Warnings beyond colour:** an **icon plus a leading word ("Warning") plus text that names the severity** (GOV.UK, USWDS, Atlassian, Carbon, WCAG 1.4.1: 5).
7. **Up/down beyond colour:** an **explicit +/− sign on every value, plus an arrow** where space allows (Google and FT do both; Yahoo signs only; Groww and Moneycontrol are inconsistent). Count: 3 sign consistently, 2 also use arrows.
8. **Muted text contrast:** **4.5:1 minimum, with no exemption for secondary text**. Design-system secondary greys are 5:1 to 9:1. Chart lines need 3:1 against the background (WCAG 1.4.3/1.4.11, Carbon, GOV.UK, Atlassian: 4).

**Not verified:** the defaults on Tickertape, NSE, Kite, Morningstar (live), Koyfin, the Bloomberg public site and Investing.com; the defaults of every breadth chart (StockCharts, Barchart, Chartink, the TradingView S5TH default); Material Design guidance; FT's and The Economist's own colour rules; whether Bloomberg adds symbols; Screener's up/down styling; any axe use on market-data sites; how pickers behave after the page has loaded (only the markup was read).
