# Portfolio requirements: everything agreed, in one list

Built 20 Nov 2026 from the Dashboard's rules (`docs/PAGE_DESIGN.md`), the
owner's messages about Portfolio, and the review of the live page that day.
A mock-up or a build is not shared until every row passes:

    node scripts/check_dashboard_requirements.mjs <page.html | url> docs/PORTFOLIO_REQUIREMENTS.md

Each row's **Marker** is text that must appear on the rendered page (case
insensitive, `|` separates alternatives). Change a row only with the owner's
word.

Order: 1 · the record → 2 · month by month → 3 · day to day against the market → 4 · the book now → 5 · what the trades say → 6 · the systems side by side → 7 · every rebalance and trade

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 1 | A verdict first: since inception after costs against the market, months ahead, where it stands today | PAGE_DESIGN §2 | Top | after costs |
| 2 | The live record against Nifty Total Market, named | Owner 20 Nov (S149) | §1, §2 | Nifty Total Market |
| 3 | Frozen months stay as recorded against the Nifty 500; Total Market beside, labelled | Owner 20 Nov | §2 | as recorded |
| 4 | Drawdown: three measures, each named (today below the peak, worst daily, worst month-end) | S146, settled 20 Nov | §1 | Below its peak today |
| 5 | The worst daily fall named as such | S146 | §1 | worst fall, daily |
| 6 | The worst month-end fall named as such | S146 | §1 | worst at a month-end |
| 7 | ₹100 since 1 Jan: the book, the market and a momentum index, with the drawdown under it | Moved from the Dashboard, owner 19 Nov | §1 | ₹100 on 1 Jan |
| 8 | Month by month: the book, the market, the lead; losing months read leftward | Owner 20 Nov (line bars) | §2 | Month by month |
| 9 | Daily movement against the index, kept (owner) and given context: today, 5 sessions, sessions ahead in 20, capture | Owner 20 Nov ("day's P&L was kept to measure daily movement vs index") | §3 | Last 20 sessions |
| 10 | Up-day and down-day capture | Proposed 20 Nov | §3 | capture |
| 11 | Holdings: one figure per cell; industry status, weight, return since entry, rank trail | PAGE_DESIGN §3 | §4 | Rank trail |
| 12 | The rupee mark explained in one short note | Live page | §4 | a mark, not a cost |
| 13 | The book by industry status and by size | Dashboard §5, §6 | §4 | The book by size |
| 14 | Trades: win rate, average win against average loss, holding period | 20 Nov review | §5 | Average win |
| 15 | Which exit rule fired, and what each earned | 20 Nov review | §5 | Trend breakdown |
| 16 | Best and worst trades | 20 Nov review | §5 | Best trades |
| 17 | Systems: only months with a record; shadow systems on one line until they have one | 20 Nov review | §6 | Shadow systems |
| 18 | Rebalances: turnover per rebalance, newest first; the full log one tap away, with export | 20 Nov review | §7 | Rebalances |
| 19 | Every chart gives values on touch and pointer | Owner 20 Nov | Charts | Latest|DashCharts.render( |
| 20 | Every chart: what it is, how to read it, its table | Owner 20 Nov (tipsheet) | Charts | Show the table |
| 21 | No duplicated figure: since inception and the month once each | Owner 19 Nov ("don't show repeated information") | Page | Month so far |
| 22 | Data date only, no sources | Owner 20 Nov | Foot | Data to |

**Not on this page, by decision:** the Dashboard's market sections (signals,
flows, size leadership); the 13-column "Ranks by month" table (its ranks are the
rank trail in §4).
