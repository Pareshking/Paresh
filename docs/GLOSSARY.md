# Glossary: one name and one unit per thing (S193 item D)

Decided by the owner one item at a time, 23 Nov 2026, from the live pages' own text (750, 1000, Nano).
Every page follows this file; PAGE_DESIGN.md §3a rule 6 points here. The check that reads it is S193's
last step for item D: `scripts/glossary_audit.mjs` (in CI), with `tests/test_rounding_parity.py` for entry 12.

| # | Thing | Write | Not | Why |
|---|---|---|---|---|
| 1 | Benchmark | Name the index every time: **Nifty Total Market** (track record from November 2026, live figures), **Nifty 500** (backtest, long histories, and the frozen months January to October 2026, which stay as recorded against it). "The market" only after the index is named in that sentence | "the market" alone; "Total Market"; "NTM" | Two yardsticks with different histories: Nifty Total Market from Oct 2021, Nifty 500 from Jun 1999. One name for both hid which was meant |
| 2 | NSE's 22 groups (Capital Goods, Healthcare...) | **sector** | "industry" for these groups | NSE's file calls the column Industry; the Sectors page and rule 6 say sector. "industry" is kept only for TradingView's finer split on the Sectors page |
| 3 | A stock's size | **Large Cap, Mid Cap, Small Cap, Micro Cap, Nano Cap, Ultra Nano Cap** | "Small", "Smallcap" | Matches the owner's Nano Cap / Ultra Nano Cap (22 Nov) |
| 3 | An NSE index | Its full name, **Nifty Smallcap 250**; the short form only in a table column headed "NSE index" | "Smallcap 250" in text | NSE indices keep their names (owner, 22 Nov) |
| 4 | A gap between two returns | **pts** in figures (tiles, tables, axes, chart heads); **points** in sentences; explained where a reader first meets it on a page ("pts = percentage points: 12% − 8% = 4 pts") and in the Guide. **bps** only for costs | "%" for a gap | A % gap can be read as a relative return: +46.3% against +1.3% is 45.0 pts by subtraction but 44.4% relative. Owner chose pts over %, 23 Nov |
| 5 | Money | **₹1.22 lakh Cr**, **₹34.1 lakh**, axis "₹ thousand Cr": "Cr" in figures and sentences alike | "crore" spelled out; "₹1,22,000 Cr" | Rule 2 (22 Nov) and the owner's lakh forms (22 Nov); owner 23 Nov: "Cr everywhere" |
| 6 | One year | **12M** in figures; **12 months** in sentences; "From 12M high" | "1Y", "1-year", "12-month", "one year" | Matches 1M 3M 6M 9M and the ranking's own lookbacks. Calendar "this year" (since 1 Jan) is a different thing |
| 7 | Start of the record | The date, from each system's own record: **Since 1 Jan 2026** (the 750) | "since inception", "since start", "since the record began" | Each system starts on a different date; the date shows how long the record is |
| 8 | Worst fall from a peak | **Max drawdown**, in figures and sentences ("6M max drawdown") | "largest fall (from a peak)", "Max DD" | Owner, 23 Nov. Plain **drawdown** (today's distance below the peak) is a different measure and keeps its word |
| 9 | The running month | Name it: **Month so far · Nov**, "so far in November", "bought at the 30 Nov rebalance" | "this month", "MTD", "month to date" | "This month" can mean the calendar month or the rebalance month |
| 10 | Trades | Actions **Buy**, **Sell**, **Hold**; the rule that forces a sale is a **sell rule**; a stock in the book is a **holding** | "exit rule", "a hold" (noun) | The rule's name says what it makes you do |
| 11 | Moving averages | **50D EMA**, **200D EMA** in figures and sentences; the Guide explains EMA once; a simple average, where offered, is **SMA** | "200-day average", "50-day", "moving average" as a label | Rule 6; the breadth lines are exponential (`market_questions._share_above_ema`) |
| 12 | Rounding of every displayed figure | **Half up** (away from zero): ₹892.50 → ₹893, −2.45% → −2.5%; Python and the charts' JavaScript agree | Python's `round()` (half to even) | SONACOMS ₹892.50 showed ₹892 in tables and ₹893 in charts. Display only; stored prices and calculations are untouched |

## Also found while reading the pages (S173 rules already broken; fixed with item D)

- An ISO date on Actions (1000): "no close for on 2026-10-30" (rule 3).
- "None announced for any holding" on Actions (rule 5).
- Dashboard "Momentum's lead, every month": the last bar is a different pair (Nifty500 Momentum 50 less
  Nifty Total Market) from the bars before it (top 100 less the Nifty 500); PAGE_DESIGN §6a. Item A/B.
- `/stock?stock=X` shows "Page not found" before it redirects to the Screener (app.py, existed before
  #628). Item K.
