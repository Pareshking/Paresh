# Dashboard requirements: everything agreed, in one list

Owner, 20 Nov 2026: "each mock up lost few good items we discussed so far ...
If you will miss such things, no point in discussion further."

This is the master list of what the Dashboard must carry, drawn from every
owner message and every agreed proposal from 19 to 20 Nov 2026. A mock-up or a
build is not shared until **every row passes**:

    node scripts/check_dashboard_requirements.mjs <page.html | url>   # a mock-up, or the running app
    python scripts/headless_smoke.py                                  # the built page, in CI on every PR

Each row's **Marker** is text that must appear on the rendered page (case
sensitive, `|` separates alternatives that each count). Change a row only with
the owner's word, and note it in the Source column.

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 1 | Everything visible; no "more questions" or clicks to reach content | Owner 19 Nov | Whole page | The book this month |
| 2 | One-paragraph verdict first, with section links | Owner 19 Nov; tipsheet pattern | Top | Of the 5 signals that pass our own test |
| 3 | Sections in the agreed order, numbered | Owner 20 Nov ("correct order") | Page | 7 · Where leadership is moving |
| 4 | Headline of each section states the finding, coloured by impact | Owner 19 Nov | Each section | November’s lag is |
| 5 | Market = Nifty Total Market, named | Owner 20 Nov | §1 | Nifty Total Market |
| 6 | Frozen months kept, Total Market compared beside | Owner 20 Nov | §1 note | January to October stay as recorded against the Nifty 500 |
| 7 | NSE momentum indices against the book this month | Owner 20 Nov | §1 | Nifty500 Momentum 50 |
| 8 | Month chart as straight-line bars, two colours, negatives leftward (October shown) | Owner 20 Nov | §1 | October |
| 9 | No month-by-month portfolio returns (they are on Portfolio) | Owner 19 Nov | §1 note | month-by-month record is on Portfolio |
| 10 | Since inception and months ahead, as figures | v6, kept | §1 tiles | Months ahead of the market |
| 11 | Buy and sell design: holdings with Sell / Watch / Clear badges | Owner liked, 20 Nov (#2, #5) | §2 | Would be bought |
| 12 | Rank 3M ago, 1M ago, now for each holding, with a trail | Owner 20 Nov | §2 | Rank trail |
| 13 | Rank-trail caveat in plain words | Owner 20 Nov (option 1) | §2 note | how today’s rule ranks the stock on that day |
| 14 | Each holding's industry status under its name | v4, kept | §2 | ahead on both |
| 15 | Next in line, churn against an average month, results due | v4, kept | §2 | Next in line |
| 16 | Leadership turnover in the top 40 | v7, agreed | §2 | Leadership turnover |
| 17 | Momentum's lead over 12M, 3M, the last finished month, month so far | Owner 20 Nov | §3 tiles | Last 3 months |
| 18 | Every signal tested: Pass / Not confirmed, failures kept | v7, approved | §3 | Not confirmed |
| 19 | Each signal: 3M ago, 1M ago, now | Owner 20 Nov | §3 | 1M ago |
| 20 | Each signal: where it sits in its own history | v6 (tipsheet), restored 20 Nov | §3 | In its own history |
| 21 | Each signal: what months like this meant, against the average | v7 | §3 | Months like this |
| 22 | Each signal: what would flip it | v6 | §3 | What would flip it |
| 23 | "Describing is not forecasting" | v6 (tipsheet) | §3 note | Describing is not forecasting |
| 24 | FII data as its own section, with inference | Owner 20 Nov ("FII data is important") | §4 | Foreign investors have bought |
| 25 | Foreign buying as a share of the 750's market value | v7 (tipsheet) | §4 | Against the 750’s market value |
| 26 | Domestic institutions beside foreign | v6 | §4 | Domestic institutions |
| 27 | What heavy foreign buying has meant, tested | v6 | §4 | Better months for momentum next |
| 28 | FPI vs NSE provisional figures explained | v6 | §4 note | which also counts primary-market buying |
| 29 | Size leadership against momentum indices, 1M 3M 6M | Owner 20 Nov | §5 table | Momentum against its size index |
| 30 | The book by size bar | Owner liked (#4), 20 Nov | §5 | The book by size |
| 31 | Is the rally shared: breadth by size, with 3M ago and 1M ago | v7 (tipsheet) | §5 | Is the rally shared? |
| 32 | The typical stock: equal-weight and median against the market | v7 (tipsheet) | §5 | The typical stock against the market |
| 33 | Where the book is strong and weak, as cards with rotation | Owner liked (#1), 20 Nov | §6 | Rotation: |
| 34 | RRG quadrants, 100 = the benchmark, EW construction shared with Sectors | Owner 20 Nov | §7 | 100 = all ranked stocks, equal weight |
| 35 | Leadership lists with RS ratio · momentum and the path under each name | v7, owner's screenshot 20 Nov | §7 | Behind but turning up |
| 36 | The book's holdings marked in leadership ("what needs attention") | Owner liked (#3), 20 Nov | §7 | Held in the book |
| 37 | At a glance: index moves (one date), breadth, the book's risk | v6 | Glance | The book’s risk |
| 38 | Breadth history on each date's members | Owner 20 Nov | Glance, §3 | leavers included |
| 39 | Every chart gives values on touch and pointer | Owner 20 Nov | Charts (`static/dash_charts.js`) | Latest|DashCharts.render( |
| 40 | Every chart: what it is, how to read it, its table | v7 (tipsheet), agreed | Charts | Show the table |
| 41 | Data date in the footer; sources not shown (owner, 20 Nov) | v6; owner 20 Nov | Foot | Data to 19 Nov 2026|Data to |

**Not on the Dashboard, by decision:**

- Valuation percentiles: we hold no earnings data (20 Nov).
- Per-month portfolio returns and the ₹100 line: on Portfolio (owner, 19 Nov).
- Long tables of all industries or all breadth measures: on Sectors and Breadth (20 Nov).
- One-day index moves as tiles: only in At a glance (v5).
- Theme amber change: proposed 20 Nov, waiting for the owner.
