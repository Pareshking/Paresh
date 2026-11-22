# Portfolio requirements: everything agreed, in one list

Built 20 Nov 2026 from the Dashboard's rules (`docs/PAGE_DESIGN.md`), the
owner's messages about Portfolio, and the review of the live page that day.
A mock-up or a build is not shared until every row passes:

    node scripts/check_dashboard_requirements.mjs <page.html | url> docs/PORTFOLIO_REQUIREMENTS.md

Each row's **Marker** is text that must appear on the rendered page (case
insensitive, `|` separates alternatives, ` + ` joins texts that must all appear:
a row that asks for two things tests both). Change a row only with the owner's
word.

Order: current book → industry & size → returns → equity, drawdown & risk → calendar returns → day by day against the market → trades → systems, side by side

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 1 | A verdict first: since inception after costs against the market, months ahead, where it stands today | PAGE_DESIGN §2 | Top | after costs |
| 2 | The live record against Nifty Total Market, named | Owner 20 Nov (S149) | §1, §2 | Nifty Total Market |
| 3 | Frozen months stay as recorded against the Nifty 500; Total Market beside, labelled | Owner 20 Nov | §2 | as recorded |
| 4 | Drawdown: three measures, each named (today below the peak, worst daily, worst month-end) | S146, settled 20 Nov | §1 | Below its peak today |
| 5 | The worst fall named as peak to trough on daily closes, with its dates and recovery, beside the worst single day (owner, 20 Nov: "Check worst fall daily"; −13.5% is 29 Jan → 23 Mar, the worst day −4.2%) | S146, S154 | Equity & drawdown | Largest fall from a peak + 29 Jan → 23 Mar, recovered 22 Apr + Worst day |
| 6 | The worst month-end fall named as such | S146 | §1 | Worst month-end |
| 7 | ₹100 since 1 Jan: the book, the market and a momentum index, with the drawdown under it | Moved from the Dashboard, owner 19 Nov | §1 | ₹100 on 1 Jan |
| 8 | Month by month: the book, the market, the lead; losing months read leftward | Owner 20 Nov (line bars) | §2 | Month by month |
| 9 | Daily movement against the index, kept (owner) and given context: today, 5 sessions, sessions ahead in 20, capture | Owner 20 Nov ("day's P&L was kept to measure daily movement vs index") | §3 | Last 20 sessions |
| 10 | Up-day and down-day capture | Proposed 20 Nov | §3 | capture |
| 11 | Holdings: one figure per cell; industry status, weight, return since entry, rank trail | PAGE_DESIGN §3 | §4 | 3M · 1M · now |
| 12 | The rupee mark explained in one short note | Live page | §4 | a mark, not a cost |
| 13 | The book by industry status and by size | Dashboard §5, §6 | §4 | The book by size |
| 14 | Trades: win rate, average win against average loss, holding period | 20 Nov review | §5 | Average win |
| 15 | Which exit rule fired, and what each earned | 20 Nov review | §5 | Trend breakdown |
| 16 | Best and worst trades | 20 Nov review | §5 | Best trades |
| 17 | Systems: only months with a record; shadow systems on one line until they have one | 20 Nov review | §6 | Shadow systems |
| 18 | Rebalances: turnover per rebalance, newest first; the full log one tap away, with export | 20 Nov review | Rebalances | Rebalance lines + Export CSV |
| 19 | Every chart gives values on touch and pointer | Owner 20 Nov | Charts | Latest|DashCharts.render( |
| 20 | Every chart: what it is, how to read it, its table | Owner 20 Nov (tipsheet) | Charts | Show the table |
| 21 | No duplicated figure: since inception and the month once each | Owner 19 Nov ("don't show repeated information") | Page | Month so far |
| 22 | Data date only, no sources | Owner 20 Nov | Foot | Data to |
| 23 | The page reads as a portfolio: the live page's name, the holdings first, plain section names (owner, 20 Nov: "a real portfolio hides in plain sight") | Owner 20 Nov | Top | Portfolio + Current book |
| 24 | Holdings like a broker's: quantity, entry price, price, value, weight, today, P&L since the fill, return since entry; sortable; a totals row | Owner 20 Nov | Current book | Qty + Entry price + P&L from 2 Nov + 20 holdings |
| 26 | Holdings' return since the fill, before costs | Live page | Current book | pre-costs|before costs |
| 27 | How the holdings move together (average correlation) | Live page | Current book | How they move together |
| 28 | Industry exposure by name, with each industry's holdings and status | Live page | Current book | Industry exposure now + 6 holdings |
| 29 | Returns by period: today to since start, FY included; annualised once past a year | Owner 20 Nov ("next year how are we going to show that data?") | Returns | By period + FY 2026-27 |
| 30 | The book against size-matched indices, not only the market | Review 20 Nov (90% small and micro) | Returns | size split + Microcap 250 |
| 31 | Calendar returns: one row group per year, months, quarters, CY and FY (April to March) | Live page; owner 20 Nov | Calendar returns | Calendar years + Financial years + Jan–Mar + FY 2026-27 |
| 32 | Risk: volatility, beta and tracking error, marked as an early reading | Review 20 Nov | Equity & drawdown | Volatility + Tracking error + Since 1 Jan 2026, + also the last 12 months and each year|>Window< |
| 33 | Trades filtered (all, winners, losers, open) with export | Live page | Trades | Trade history + Winners + Losers + Open + Export CSV |
| 34 | Rebalance lines filtered (buy, sell, hold) | Live page | Rebalances | Buy + Sell + Hold |
| 35 | Systems compared over the same window, not month columns (owner, 20 Nov: "difficult for past months when next year data will be there"). A system joins the window only after its first full month (owner, 22 Nov 2026: "first full month"): one that started this month shows its own figures and "joins from" the next month, so it never shrinks the others' window to a few weeks; the heading counts the systems in the window (S183) | Owner 20 Nov; owner 22 Nov | Systems, side by side | compared over the same window + after its first full month |
| 37 | Column widths fit their content: numbers sized to fit, the name column takes the rest (owner, 20 Nov: "abnormal spaces") | Owner 20 Nov | Tables | Current book |
| 38 | Holdings show the entry date and days held | Owner 20 Nov ("Portfolio must have entry date column") | Current book | Entry date + days |
| 39 | Holdings show how close each is to an exit rule: against its 50D EMA, from its 52-week high, rank against #40; a holding past a line is marked | Owner 20 Nov ("which other columns we should add, why?") | Current book | vs 50D + From 52W + past an exit rule |
| 40 | Industry and size kept at every rebalance and shown over time; size by NSE's index lists on that date | Owner 20 Nov ("we should record and save, it gives trend") | Industry & size | each rebalance |
| 41 | Industry exposure against the 750's own weights, with the large industries the book does not hold | Owner 20 Nov ("Industry exposure etc required new design") | Industry & size | The 750 + Not held |
| 42 | The market's drawdown drawn with the book's | Owner 20 Nov ("Showing only portfolio DD, not index benchmark") | Equity, drawdown & risk | market below peak |
| 43 | Drawdown terms defined: fall from a peak, largest fall from a peak, worst day, worst month-end | Owner 20 Nov ("Is our daily % fall wording correct") | Equity, drawdown & risk | (value ÷ peak) − 1 |
| 44 | Tracking error explained with an example | Owner 20 Nov | Equity, drawdown & risk | a year the market makes +10% |
| 45 | Risk measured on all the record's history, named; from January 2027 also the last 12 months and each year | Owner 20 Nov | Equity, drawdown & risk | from January 2027 also the last 12 months |
| 46 | Calendar returns last for years: a row group per year with months, quarters and the year; the momentum index beside | Owner 20 Nov ("people visiting after 5 years") | Calendar returns | each new year adds a row + Momentum 50 |
| 47 | Trades and rebalance lines in one section, hidden until opened, each view with its CSV of every field | Owner 20 Nov ("Can't it be one and hidden?", "CSV export of past trades ... so people can verify") | Trades | Trade history + 15 fields + 300 lines |

**Dropped by the owner, 20 Nov:** the cash tile and row (row 25) and the note that Backtest can differ from the record (row 36).

**Not on this page, by decision:** the Dashboard's market sections (signals,
flows, size leadership). **Dropped (owner agreed, 21 Nov 2026):** the 13-column "Ranks by month" table;
its ranks are the rank trail in Current book, under one definition (S154).
