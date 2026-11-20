# Actions requirements: everything agreed, in one list

Started 20 Nov 2026, before any design, from three places: every item on the live
Actions page that day (`src/ui/views/actions_view.py`), the owner's decisions about
Actions recorded in `CHANGELOG.md` (dated below), and the rules in
`docs/PAGE_DESIGN.md`. A mock-up or a build is not shared until every row passes:

    node scripts/check_dashboard_requirements.mjs <url> docs/ACTIONS_REQUIREMENTS.md

Each row's **Marker** is text that must appear on the rendered page (case insensitive,
`|` separates alternatives, ` + ` joins texts that must all appear; `[click X]` reads
the page after tapping X, `[phone]` reads it at 412 px; a row the page cannot show
today names the test that covers it). A row is changed
or dropped only with the owner's word. The section order is set when the owner
approves the design, and then added here as an `Order:` line.

## What a reader comes with

1. What do I sell at the next rebalance, and why?
2. What do I buy, and how much (rupees, shares), ready to place?
3. Which holdings could become a sale before then, and how close are they?
4. When exactly, and what can still change before the close that counts?
5. The same answers for my own holdings, not only the model book.

## From the live page (20 Nov 2026)

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 1 | Plain title and the condition the plan rests on | Live page | Top | Actions + If today's prices hold |
| 2 | Model book or my holdings, one switch | Live page | Top | Model book + My holdings |
| 3 | My holdings: typed list with an optional buy price, or the Kite holdings CSV; kept in this browser only | Live page | Top, My holdings | [click My holdings] Upload from Kite |
| 4 | Counts: sell, buy, hold, and how many holds are close to a rule | Live page | Figures | Sell + Buy + Hold + close to a rule\|all clear of the rules |
| 5 | Next rebalance: the check day, sessions away (NSE holidays counted), the fill day; a caveat when NSE's holidays are not yet published | Owner 13 Oct (holidays), live page | Figures | Next rebalance + sessions away\|session away + fills |
| 6 | Kite basket: capital box starting at the model book's ₹1 crore, buy orders at target weight, CSV | Owner 12 Oct, 7 Nov | Top | Kite basket + [click Kite basket] Download basket CSV |
| 7 | Sell: each holding, its industry, the rule it broke, held since, return since entry; "sell in full" | Live page | Sell | Sell in full |
| 8 | Buy: each stock, industry, qualified rank, price, 3M, 6M, distance from the 52W high | Live page | Buy | Qualified + From 52W high |
| 9 | Next in line after the buys | Live page | Buy | Next in line |
| 10 | Hold: status, rank buffer (place among the qualified, places to go), cushion to the 50D EMA, cushion to the 52W-high line, the closest rule, return since entry | Live page | Hold | Rank buffer + 50D EMA + from 52W high + Closest to |
| 11 | Holds ordered by least room on any rule, a full rank buffer counted as a 20% fall, said on the page | Owner Nov (CHANGELOG, PVRINOX order) | Hold | least room on any rule |
| 12 | A holding that cannot be ranked is said so, not hidden (today's book has none; the case is covered by `tests/test_actions_requirements.py`) | Live page | Figures | Hold |
| 13 | Buy candidates: the qualified list, collapsed | Live page | End | Buy candidates |
| 14 | A phone drops columns only with a note saying which | Design audit 9 Nov | Sell, Buy | [phone] On a wider screen |
| 15 | Plans say Buy / Sell / Hold (trades that happened say Bought / Sold / Held) | Owner Oct (CHANGELOG) | Everywhere | Buy + Sell + Hold |
| 16 | Works for each system (750, Nano Cap, Combined) | Owner 7 Oct (CHANGELOG) | Whole page | Actions |

## Decided elsewhere that Actions must honour

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 17 | The plan is the Dashboard's plan: same sells, buys, holds, next in line, from one function (`src/ui/model_plan.py`) | S154, found 20 Nov 2026 | Whole page | Sell + Buy |
| 18 | Between the six-monthly resets, weights are the record's: held names keep their drift up to the hold cap, each buy gets the record's buy size of today's account | Owner 8 Nov (S154 fix 20 Nov: the book's fill date was missing, the plan fell back to equal weight; the weights are covered by `tests/test_model_plan_one_source.py`) | Kite basket, Buy | [click Kite basket] target weight |
| 19 | Ranks are the one rank among filter-passers, the same trail as Dashboard and Portfolio | S154 | Hold, Buy | Qualified |
| 20 | No data sources on the page; the data date only | Owner 20 Nov (Dashboard) | Footer | Data to |
| 21 | Numbers right-aligned under right-aligned headings; no label wrapping to three lines; nothing past the screen edge (layout audit clean at 412 and 1400 px) | Owner 20 Nov (Portfolio review) | Whole page | Actions |

## Added by the owner, 20 Nov 2026 ("add all five")

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 22 | The Kite basket carries the model book's sells too, with share counts from the book (your own holdings: buys only, as their counts are not known) | Owner 20 Nov | Kite basket | [click Kite basket] sell orders |
| 23 | Each buy shows its rupee amount and share count on the page, at the record's weight, not only in the CSV | Owner 20 Nov | Buy | Amount + Shares |
| 24 | Each hold shows its rank trail, 3M · 1M · now, from the same function as Dashboard and Portfolio (`dashboard_insights.rank_trails`) | Owner 20 Nov; PAGE_DESIGN §7 | Hold | 3M · 1M · now |
| 25 | What could still change before the close: holds within a few places or percent of a line, and the next-in-line names that would come in | Owner 20 Nov | After the counts | could still change |
| 26 | The data date shown; the data-quality counts (gaps, short histories) kept, with no sources named (read from "add all five"; to confirm) | Owner 20 Nov | Footer | Data to |

Why a buy is under 5% (owner asked, 20 Nov): the 8 Nov rule gives a buy the smaller
of (a) 5% of the account at the last reset fill in rupees (₹7.19 lakh, 4.92% of
today's ₹1.46 crore) and (b) an equal share of the cash the sells free, since no kept
name is trimmed to fund a buy (four sells worth 19.08% → 4.77% each). The page says
which applied.

## Every figure on the page, where it is made, and where else it appears (S154 (a) for Actions)

| Figure on Actions | Made by | Also shown on | Same function there? |
|---|---|---|---|
| Sells, buys, holds, next in line | `src/ui/model_plan.py` → `engine.actions.plan_rebalance` | Dashboard §2 "What happens on 30 Nov" | Yes, since 20 Nov (before: Dashboard omitted held weights) |
| Target weights, Kite basket ₹ | `model_plan` (held weights, hold cap, buy size) → `buy_orders` | — | — |
| Buy size base: the account today | `actions_view._book_equity` → `ui.book_series` | Portfolio value, Dashboard "Below its peak" | Yes (one daily series, S154) |
| Status (Sell / Watch / Clear), the rule broken, closest rule | `engine.exit_watch.assess`, `nearest_rule` | Dashboard §2 rows | Yes (`assess`) |
| Qualified rank, rank buffer | `exit_watch.qualified_ranks` / `assess` | Dashboard §2 ("ranks #52 of the qualified"), Portfolio rank trail (now) | **To check**: Portfolio's "now" comes from `dashboard_insights.rank_trails` (rank_history snapshots), Actions' from today's ranking; a test that both give the same place today |
| 50D EMA cushion, 52W-high cushion | `assess` (`EMA cushion`, `High cushion`) | Portfolio "vs 50D EMA", "From 52W high"; Dashboard §2 "below its 50D EMA" | **To check**: Portfolio reads its own columns; same-value test |
| Return since entry | `book["Return %"]` (model book) | Portfolio "Since entry" | **To check**: Portfolio computes from entry price and today's price |
| Held since | `book["Entry Date"]` | Portfolio "Entry date" | Same column |
| Next rebalance, sessions away, fill day | `actions_view.next_rebalance`, `_sessions_between` | Dashboard §2 heading | Yes (Dashboard imports them) |
| Buy row: price, 3M, 6M, from 52W high | `rank_df` columns `CMP`, `3M Return`, `6M Return`, `% High` | Screener | Same ranking frame |

The three **To check** rows become one test before the build: for every holding, the
label shared by two pages gives the same value (S154 (b)).
