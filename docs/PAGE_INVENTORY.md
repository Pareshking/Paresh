# Page inventory (S238, 28 Nov 2026)

Owner, 28 Nov 2026:
- "make a inventory list of all the pages, section by section because I am sure you will miss lots of sections during re design
  and tell me data we already have and not using but it's really useful and website don't shows it. Everything must be documented"
- "Last time redesigning time also lots of information and sections we lost which was really useful for insights"
- "I am talking about silent drops by you"

**How to use it.** Before any redesign:
1. Read the page's rows in its part file (below).
2. List every section and figure before and after the change.
3. Name anything left out for the owner's decision (CLAUDE.md: a redesign removes nothing silently).

A preview names the rows it covers. When a page changes, update its part file in the same PR.

## Where the full tables are

Six readers built the tables on 28 Nov. Each table row gives what the section shows, its data and the function that reads it,
`file:line`, the controls, and the S237 state (G1-G7, `docs/archive/S237_COMPARISON_2026-11-28.md`). The six tables are in
`docs/archive/S238/`:

| Part | Pages | Sections (top-level / with sub-sections) |
|---|---|---|
| [A](archive/S238/A_dashboard_actions_config_guide.md) | Dashboard, Actions, Configuration, Guide; the header every page shares | Dashboard 52 (+4 header), Actions 25, Configuration 28, Guide 11 |
| [B](archive/S238/B_screener_stock_watchlist.md) | Screener, stock page (and its not-ranked, renamed and too-new states), Watchlist | Screener 19, stock page 17 (+ states), Watchlist 10 |
| [C](archive/S238/C_portfolio_backtest.md) | Portfolio, Backtest | Portfolio 15 / 44, Backtest 15 / 39 |
| [D](archive/S238/D_market_indices_sectors.md) | Market, Indices, Sectors (read from the S237 full-page preview branch, `s237-fullpage`) | Market 22, Indices 17, Sectors 19 |
| [E](archive/S238/E_unused_data.md) | Data we hold that no page shows, or shows in part; data written that nothing reads | 17 ranked items, 11 written-but-unread |
| [F](archive/S238/F_lost_in_redesigns.md) | What pages used to show and no longer do, from the git history (413 commits, 15 Sep - 28 Nov) | 13 with no owner decision for the item, 20 owner-decided, 14 moved |

**What was checked.** The readers' claims are leads (CLAUDE.md). On 28 Nov I checked these against the code, the data or git:
- **Stock page tone:** the price heading drew a fall in the up colour. RELIANCE read "its relative strength fell 11.9%" in blue (`stock_view.py`, `_h2` with no tone). Confirmed and **fixed** in #721.
- **Screener lede:** reads "The 750 ranked stocks of the 750". Confirmed in the live text. It is an owner-approved template (S203 sc.head.2), so it goes to the owner (decision 3 below).
- **Foreign flows:** NSDL's file holds 2,635 days from 1 Jan 2016, with the exchange and primary-market split. The Dashboard reads only `equity_net`, last 12 months (`dashboard_home_view.py`, `_fpi_bars`). Confirmed. In 2024, −₹1,21,210 Cr was sold on the exchange and +₹1,21,637 Cr bought in the primary market: +₹427 Cr net.
- **Momentum-health rows:** the old Dashboard's "Top 50 against the Nifty 500" and "Ranks 51–100" rows. Confirmed at `835de08d^:src/ui/views/dashboard_panels.py:150-155`. The owner asked for them on 8 Nov (`docs/MOMENTUM_HEALTH.md:14-16`).
- **Correlation heatmap:** Portfolio's heatmap. Confirmed at `f4152a80^:src/ui/views/portfolio_view.py:24`. `qualified_view.correlation` still exists.
- **Source lines:** S237 G4 put "Source:" lines under 13 charts against the owner's 20 Nov rule ("Let's not show source"; `PAGE_DESIGN.md` §2 and six requirement docs). Confirmed. **Reverted** after the owner's answer ("Revert to my rule"), in #721.

**Not checked.** Every other row is the readers' reading of the code. Also not checked:
- the live site after #720;
- Watchlist with saved stocks;
- the Screener table's columns, which sit inside a frame;
- the Nifty 1000, > ₹2,000 Cr and Combined views;
- phone layouts beyond the S237 screenshots.

## 1. Lost without the owner's decision (Part F, table 1), ranked by value to a reader

These were dropped in my redesigns. In most cases the owner approved the redesign, but the preview never named the item.

| # | Page | What was shown | Removed in | Data still held | Recommendation |
|---|---|---|---|---|---|
| 1 | Dashboard | Momentum health: "Top 50 against the Nifty 500", "Ranks 51–100", winners-against-losers, the check against IIM Ahmedabad's series | `c07710e2` 20 Nov; code `835de08d` 22 Nov | `momentum_health.csv` `top50`, `d2`, `spread` | **Restored 28 Nov (S239, owner approved the preview)**; was: Restore in §3 (asked for by the owner, 8 Nov) |
| 2 | Portfolio | "How they move together": the holdings' correlation heatmap | `f4152a80` 21 Nov | `qualified_view.correlation()` | **Restored 28 Nov (S239, owner approved the preview)**; was: Restore, collapsed (owner, 13 Oct: keep it collapsed) |
| 3 | Portfolio | Each month's provenance: recorded or backfilled, point-in-time or current list, frozen on, priced from | `074ef4f0` 6 Oct; `f4152a80` | `track_record*.json` | **Restored 28 Nov (S239, owner approved the preview)**; was: Restore as a column of the monthly table |
| 4 | Stock page | Chart: 200-day line, 20 EMA, Nifty 500 overlay; ranges 1M, 3M and All | `4098c5bf` 23 Nov | prices | **Restored 28 Nov (S239, owner approved the preview)**; was: Restore the 200-day line and the All range |
| 5 | Stock page | Rank 6 months and 2 months ago | `4098c5bf` 23 Nov | `rank_history` snapshots | **Restored 28 Nov (S239, owner approved the preview)**; was: Restore in the rank trail |
| 6 | Dashboard | "Coming up for the book": board meetings for holdings and planned buys, next 6 weeks | `c07710e2` 20 Nov | `results_calendar.csv` | **Restored 28 Nov (S239, owner approved the preview)**; was: Restore as a short list |
| 7 | Backtest | "Rebalance periods": holdings, buys, sells, turnover, costs per rebalance | `38ce0dba` 22 Nov | `run_backtest()["monthly"]` | **Restored 28 Nov (S239, owner approved the preview)**; was: Restore inside "Show the table" |
| 8 | Backtest | Trade tiles: average win and loss, best and worst | `38ce0dba` 22 Nov | closed trades | **Restored 28 Nov (S239, owner approved the preview)**; was: Restore |
| 9 | Dashboard | Sector rotation from NSE's own sector indices | `835de08d` | sector indices | Leave out (Sectors covers it) |
| 10 | Portfolio | Worst-month tile with the best month beside it | `f4152a80` | ledger | Leave out (the year grid shows both) |
| 11 | Market | New highs and new lows today, their ratio, net-new-highs chart | `07565fd9` 26 Sep; 7 Nov | `compute_hl_timeseries` | **Restored 28 Nov (S239, owner approved the preview)**; was: Restore the daily net line beside the weekly bars |
| 12 | Portfolio | Holdings CSV, monthly returns CSV | `f4152a80` | – | Owner's call: no new CSV links (owner, 28 Nov) |
| 13 | Old Qualified page | Average 3M/6M return and average correlation of the buy candidates | – | – | Leave out |

Found in today's work and listed as well:
- **Indices preview (not merged), valuation cards:** the cards dropped the P/E 3 months and a month ago, the month-ago percentile, P/B and dividend yield. To restore in the next preview.
- **#721, Indices lede:** the old lede named what the page covers; it became section links.
- **#721, Market title:** the title stated both verdicts; they moved into the lede. Both #721 items were named to the owner on 28 Nov.

## 2. Data we hold and no page shows (Part E), top items

| # | Data | Shown today | What a reader would gain | Cost |
|---|---|---|---|---|
| 1 | NSDL foreign flows since Jan 2016, split into exchange and primary market | Net only, last 12 months | Whether foreigners are selling shares or buying new issues; the record behind "the most since 2016" | low |
| 2 | Index P/B and dividend-yield history (147 indices, from 2012); P/E history beyond six indices | Today's value only | Valuation on more than one measure; sector P/E against its own past | low to medium (P/B basis breaks of 29 Sep 2023 and 23 Sep 2024 must be marked) |
| 3 | The results calendar for 2,418 stocks (results, buybacks, bonuses, fund raising) | Only for the book, the stock page and the watchlist | "Results on" in the Screener | low (not checked against a second source) |
| 4 | NSE all-indices fields: India VIX, G-sec indices, open/high/low, turnover | Dropped from the app's copy | Volatility and rates beside equities | medium |
| 5 | Company results beyond the stock page's four lines: other income, tax | Not shown | Earnings quality on the stock page | medium |
| 6 | Members-of-the-day Nifty 500 breadth since 2010 | Dashboard signal rows only | Breadth charts with 16 years instead of 5 | low |
| 7 | 20-day traded value per stock | Backtest's liquidity floor only | Liquidity in the Screener and on the stock page | medium |
| 8 | Domestic institutions' monthly flows since Jan 2021 | A readout under the foreign bars | DII as its own series | low |

Written but read by nothing (11 items, Part E): the unread NSDL columns, the momentum-health `top50` and `d2` columns, the dropped
`nse_close_all` columns, older `snapshots/rankings` in R2, `CHANGES.json`, `anchor_checks.jsonl` and others. Each needs a reader
or a reason (S195 §4). Part E also gives three corrections to `docs/DATA_CATALOGUE.md`.

## 3. Pages against the S237 rules (Parts A-D), the main open items

- **Dashboard.**
  - First screen: done (G1).
  - Section headings colour whole phrases (G2): flows, size, strong and weak, momentum.
  - §1 and §5 are tick strips (G3). §1's form is the owner's (DASHBOARD_REQUIREMENTS #8), so it goes to the owner.
  - Foreign flows show 12 of 130 months.
- **Actions, Configuration, Guide:**
  - no date line (G1);
  - the header strip colours its whole regime phrase (G2);
  - the Guide's "751 stocks" against 750 and 752 elsewhere is unexplained.
- **Screener:**
  - two-sentence headline, four-paragraph key above the table;
  - about 35 columns by default;
  - Score, Sharpe and Filled % are unexplained;
  - Stop loss and Chandelier columns may still show in the Full Quant set.
- **Stock page:**
  - returns bars, price ladder and rank trail are tick strips or single figures (G3); the line bars are the owner's own form (PAGE_DESIGN §4.2);
  - headings colour whole clauses (G2);
  - a stock with no results or no peers drops that section without a word.
- **Watchlist:** two-sentence coloured headline.
- **Portfolio:**
  - five-sentence lede;
  - the ₹100 chart has no marks for when the record started, and no labelled trough;
  - the day bars draw 20 of 223 sessions;
  - since-start is repeated in seven places.
- **Backtest:**
  - §3 and §4 are tick strips (owner rows 16, 17 and 19 fix line bars, so they go to the owner);
  - the "What was tested" line and the form sit above the headline (owner row 3).
- **Market:**
  - everything from "Today's charts" down is the old design: participation over one year with fixed 40 and 60 lines, daily highs and lows without a band;
  - the ring scale and whole-word verdict colour remain;
  - `leaders_answer` is computed and thrown away.
- **Indices (preview):**
  - the heat-tinted calendar-year and earnings cells break INDICES_REQUIREMENTS #11 ("no heat colours") and are taken out of the preview;
  - the Styles bars show today only.
- **Sectors:**
  - no S237 work yet;
  - G1, G2 and G6 open on every heading;
  - "trows" and "stable" tick strips.

## 4. Decisions for the owner (one at a time, in this order)

1. **Restore list: answered 28 Nov, "Restore the 9".** Items 1-8 and 11 of §1 come back, each previewed on real data first and each with a requirements row so a later redesign cannot drop it again; 9, 10, 12 and 13 stay out.
2. **Tick strips: answered 28 Nov, "Preview replacements".** The Dashboard §1 month strip, the stock page's returns bars and the Backtest's year and sensitivity strips each get a bars-or-lines version built on real data beside the current strip; the owner approves or rejects each; nothing changes before that.
3. **Screener lede: answered 28 Nov, "Drop the repeat"; built** ("The 750 stocks, ranked by momentum at the 27 Nov close."; a list named in words, or a count short of its number, keeps the name).
4. **Unused data: answered 28 Nov.** Show: foreign flows in full (NSDL since 2016, exchange against primary market, DII its own line), P/B and dividend-yield history with P/E for every index and sector (the 2023 and 2024 P/B basis changes marked), and the members-of-the-day Nifty 500 breadth since 2010. Not now: the Screener's results-calendar column. Each as a real-data preview first (S241).

Already answered: source lines (owner, 28 Nov: "Revert to my rule"); no new CSV links (owner, 28 Nov).
