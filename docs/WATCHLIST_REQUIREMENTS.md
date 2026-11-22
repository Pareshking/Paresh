# Watchlist requirements: everything agreed, in one list

Started 21 Nov 2026, before any change, from three places: every item on the live
Watchlist that day (`src/ui/views/watchlist_view.py`, `src/ui/watchlist_store.py`, the
Screener's table `src/ui/screener_table.py`), the owner's decisions about the Watchlist
recorded in `CHANGELOG.md` and the audits in `docs/archive/` (dated below), and the rules
learned on the redesigned pages (`docs/PAGE_DESIGN.md`). Checked with:

    node scripts/check_dashboard_requirements.mjs <url> docs/WATCHLIST_REQUIREMENTS.md

Each row's **Marker** is text that must appear on the rendered page (see
`docs/ACTIONS_REQUIREMENTS.md` for the syntax). A row is changed or dropped only with
the owner's word. Rows marked **Proposed** wait for the owner's approval of the mock-up
(PAGE_DESIGN §1 step 4); until then they describe the mock-up, not the page. The
`Order:` line is added when the owner approves the section order.

Scope: `/watchlist`. The stock page's "Add to watchlist" button belongs to the stock
page's redesign; this list only requires that it keeps working.

## The honest question first: what is this page for?

The page is about 100 lines and every figure on it is the Screener's: it filters the
Screener's table to the reader's symbols. The Screener was redesigned on 21 Nov, so a
reader can already find any one stock's rank, filters and returns there. What the
Screener cannot do is answer for **a set of names the reader chose**, at a glance:
which of *my* names the book would buy, keep or sell on the 30th, how far each is from
its line, and why some of my names are missing. That is the page's job. It needs no
new data for most of it: the qualified place, the lines and the plan already exist
(`exit_watch.qualified_ranks`, `model_plan`, `rank_trails`).

What the data does **not** support, said plainly:

- **"How my names moved since I added them."** The list is stored as symbols only
  (`watchlist_store`: `"ABB,TCS"`), with no date added. It would need a storage change
  (a date per symbol in the browser), and lists saved before it would have no date.
- **Alerts on rank changes.** The list lives only in the reader's browser; the server
  never stores it (decided after the 25 Sep 2026 code audit, U2: one visitor's saved list
  became everyone's default). Nothing can notify a reader who is not on the page.
- **A rank for a stock outside the chosen system.** Each system ranks its own list; a
  name in another system can be pointed to, not ranked here.

The case against adding anything: the page reuses one table, so it cannot drift from
the Screener; every new element is a chance to repeat the Screener or Actions (PAGE_DESIGN
§2, "no figure twice"). The minimum this page owes is to **fix the two places where it
already disagrees with the Screener** (rows A1, A2 below) and give it the redesigned
pages' title and foot. Everything else in "Proposed" is the owner's call.

## What a reader comes with

1. Which of my names would the book buy, keep or sell on the 30th, if today's prices hold?
2. How close is each to the book's lines (the 20th and 40th qualified), and which fail a
   filter, by how much?
3. How have my names moved: rank and qualified place 3 months and a month ago, against now?
4. Why is a name I typed not on the list (renamed, in another system, too new to rank,
   not a symbol)?
5. Is anything due for my names before the fill (results, ex-dates)?

## From the live page (21 Nov 2026)

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 1 | The page's name, and how many of the saved symbols are shown | Live page | Top | Watchlist |
| 2 | Type comma-separated symbols and save; Save stays enabled while the box is empty (a disabled button swallowed the click after typing) | Live page; audit 8 Nov 2026, U-L22 | Top | Save watchlist |
| 3 | Remove one stock from a list of the saved symbols | Live page | Top | Remove a stock |
| 4 | Export CSV of the rows shown | Live page | Top | Export CSV |
| 5 | The list is kept in the reader's browser only, never on the server | Code audit 25 Sep 2026, U2 (a server file made one visitor's list everyone's default); `watchlist_store` docstring | Top, empty state | this browser |
| 6 | Add a stock from its page ("Add to watchlist"); an old `?wl=` link is merged into the saved list once and leaves the address (covered by `tests/test_watchlist_in_the_browser.py`) | Live page; `watchlist_store` | Empty state | Add to watchlist |
| 7 | Symbols that are not ranked are named, cleaned to ticker characters before they are shown | Code audit 25 Sep 2026, U22 | After the table | not in the Nifty 750\|not found |
| 8 | An empty list says so in a plain line, not an alert box | Owner's decision 5, CHANGELOG 7 Nov 2026 ("Watchlist: an empty list says so in a plain line, not a blue alert box") | Empty state | empty |
| 9 | The page ends like every other page, the empty state too | CHANGELOG 10 Nov 2026 ("Watchlist has the same footer as every other page"); owner 8 Nov 2026 kept the long data line for the Screener only | Foot | © Paresh Patel |
| 10 | The Screener's own table (one component, Core columns), rank order, a header click sorts every row, a row opens its stock | UI overhaul 1.2 (`docs/archive/UI_OVERHAUL_PLAN.md`); owner 7 Nov 2026 (sorting) | Table | Rank + 1M return + From 52W high |
| 11 | Follows the system chosen in Configuration; the list is shared by all four systems | Owner 27 Sep 2026; `docs/THREE_SYSTEMS.md` ("Holdings and watchlist are shared") | Whole page | Nifty 750 |

## Where the live page disagrees with the Screener (found 21 Nov 2026; fix whatever the design)

Fixed 22 Nov 2026 in S184 (#606), before the redesign: `ranking_view.with_book_columns` gives the Watchlist the Screener's qualified place and Held marks, and `tests/test_qualified_place_same_everywhere.py` is the test A1 asks for. Seen live 22 Nov 07:23 UTC: CUPID 4th and Held, DIACABS 44th and Held, KOTAKBANK 10th.

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 12 | A1. The qualified place is the Screener's (`exit_watch.qualified_ranks`). Today every row reads "Out": the view passes the raw ranking, which has no "Qualified Rank" column. The marker cannot catch this (the heading passes); the build adds a test that both pages give the same place | Data check below; PAGE_DESIGN §5.4 ("same number as the owning page") | Table | Qualified |
| 13 | A2. The model book's stocks carry "Held", as on the Screener (`app._screener_book`). Today none do | Data check below; owner 7 Nov 2026 (S87) | Table | Held |

## Rules learned on the redesigned pages that the Watchlist must honour

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 14 | The title answers the first question; "Watchlist" is the small kicker above it | PAGE_DESIGN §2a | Top | [css .qp-kick] Watchlist |
| 15 | Section headings in the serif, each a sentence stating the finding | PAGE_DESIGN §2, §2a | Sections | is the one buy |
| 16 | The rank and the qualified place 3M ago, 1M ago and now, as numbers in their own columns, on the Dashboard's dates (on or before) | PAGE_DESIGN §2, §6a; Screener decision A, 21 Nov 2026 | Table | 3M ago + 1M ago + Now |
| 17 | No internal names: index tags as the Screener writes them ("Microcap 250"), no "NANO" | PAGE_DESIGN §2; Screener row 17 | Table | Microcap 250 |
| 18 | Tables: sentence-case headers, headings over their columns, figures in Plex Mono right-aligned, row labels never wrap; colour only the cell that carries the meaning | PAGE_DESIGN §3 | Table | Rank |
| 19 | A phone drops columns only with a note saying which | Actions row 14; design audit 9 Nov 2026 | Table | [phone] On a wider screen |
| 20 | The data date at the foot, no source named | Owner 20 Nov 2026 ("Let's not show source"); Screener row 24, Actions row 26 | Foot | Data to |
| 21 | Layout audit clean at 412 and 1400 px, and the page joins CI's step | Owner 20 Nov 2026; PAGE_DESIGN §8 | Whole page | Watchlist |

## Approved with mock-up v1 (owner, 22 Nov 2026: "Watchlist approved")

The owner confirmed the whole mock-up the same day: "Full" (the grouped table, the "30 Nov" column and the "Not ranked" section, with "Before the fill"). The owner's number rules and style sheet also apply (rows 27-28).

| # | Requirement | Source | Where | Marker |
|---|---|---|---|---|
| 22 | Rows grouped by the book's lines, in rank order: top 20 qualified, 21st to 40th, qualified past the 40th, fails a filter; each group a heading row with its count and what it means; a note under each name says how far it is from its line, without repeating a figure from a column | Reader questions 1, 2; PAGE_DESIGN §3 (group rows with a heading row) | Table | Top 20 qualified + kept if held + Fails a filter |
| 23 | A "30 Nov" column: Buy, Sell, Hold or Next in line, from the plan Actions shows (`src/ui/model_plan.py`), not a second plan; the lede says "if today's prices hold" | Reader question 1; S154 (one plan) | Table | 30 Nov + prices hold |
| 24 | "Not ranked" says why and where for each symbol: renamed (NSE's `symbolchange.csv`, with the new symbol and a button to replace it), in another system (its rank there), too new to rank, or not a known symbol | Reader question 4; data check below (the live page tells a > ₹2,000 Cr reader that CUPID is "not found") | After the table | Not ranked + Replace with |
| 25 | "Before the fill": board meetings and ex-dates for the listed stocks up to the fill day, the check Actions row 28 runs for the book, with the same wording of its limits | Reader question 5; Actions row 28 | After Not ranked | Before the fill |
| 26 | The lede names the system and the session ("Ranked in the Nifty 750 at the 20 Nov close") | PAGE_DESIGN §5.3; data check below (Nifty 1000 falls back to the 750 without saying so) | Top | Ranked in the |
| 27 | Prices and moving averages in whole rupees, below ₹100 too; returns to at most one decimal; display only, the CSV export and calculations exact | Owner 22 Nov 2026: "price etc, Moving averages etc should be in round numbers, return only with Max one decimal values like 11.1% not 11.11%"; then whole rupees for all prices | Table | Watchlist |
| 28 | The owner's style sheet, through the one shared formatter (S173) and its page-scanning test: ₹ Cr without decimals; dates as "20 Nov 2026"; true minus and explicit +; "–" for missing with the reason in a footnote; one word per thing; the standard foot | Owner 22 Nov 2026, the 8-rule style sheet | Whole page | Data to |

Not proposed, for the owner to decide (see "The honest question"): a date added per
symbol and "since you added it"; a one-click "start from the model book" on the empty
state; anything that needs the server to keep the list.

## Data checks run on 21 Nov 2026 (prices to 20 Nov)

Method: the running app (`streamlit run app.py`, this branch at `454b3fc`), read in
Chromium. The Screener at `/screener` with "Show all 750", Full Quant columns; the
Watchlist at `/watchlist` with the list CUPID, KOTAKBANK, GLAND, EMCURE, AUROPHARMA,
DIACABS, SYRMA, TCS, SPECTRUM, TATAMOTORS, given once as a `?wl=` link and once written
into the browser's storage (`mt_watchlist_v1`) before the page opened; both gave the
same page. Each system through `?sys=`.

- **Watchlist rows against the Screener's, same symbols, same date.** 8 rows × 20 columns:
  154 of 160 cells equal. The 6 that differ are all the qualified place: the Watchlist
  reads "Out" for CUPID, KOTAKBANK, GLAND, EMCURE, AUROPHARMA and DIACABS; the Screener
  reads 4, 10, 20, 21, 40 and 44 (SYRMA and TCS fail a filter and read "Out" on both).
  Cause: `app._page_watchlist` passes the raw ranking; the Screener adds "Qualified
  Rank", the qualified trail and "Held" in `ranking_view` before drawing the same table.
  **"Held" is missing too**: CUPID, GLAND, DIACABS and SYRMA are in the model book
  (Screener and Actions agree), the Watchlist marks none. Rows A1, A2.
- **Figures the mock-up shows that the Screener does not.** (a) "30 Nov" words: read from
  the live Actions page the same day (sells DIACABS, SYRMA among five; buys KOTAKBANK
  among five; holds CUPID, GLAND; next in line LENSKART, EMCURE, SAREGAMA, ICICIBANK; check
  Mon 30 Nov, fill Tue 1 Dec, `actions_view.next_rebalance`). (b) TATAMOTORS → TMPV on 24
  Oct 2025: `data/reference/nse/symbolchange.csv` line 973 (NSE's file); TMPV ranks 697th
  and fails both filters on the Screener. (c) SPECTRUM: 1st of 377 on the > ₹2,000 Cr
  Screener, marked Held there; member in `data/nanocap_membership.json`. (d) Results and
  ex-dates: `data/results_calendar.csv` (NSE's board meetings, fetched 21 Nov, 2,663 rows,
  22 Sep to 5 Dec) has no meeting for any listed stock after 20 Nov; the last results
  meetings run from 8 Oct (TCS) to 11 Nov (CUPID), and 13 Nov for TMPV.
  `data/reference/nse/corporate_actions_recent.json` has TCS (ex 14 Oct) and AUROPHARMA
  (ex 11 Nov) only, both past. None of (a)–(d) was checked against a second source.
- **Empty state.** A fresh browser shows "Saved in this browser", the input, "Save
  watchlist", "Nothing saved yet. Type symbols above and save, or open any stock and press
  "Add to watchlist"." and the ©. No data date on the page (the header chip has "closes of
  20 Nov").
- **A symbol not in the ranked universe.** "2 not found among the 750 ranked stocks:
  SPECTRUM, TATAMOTORS", in an amber box. True, but it does not say that TATAMOTORS is now
  TMPV or that SPECTRUM is ranked in another system.
- **The four systems** (`src/engine/systems.py`).
  - Nifty 750: as above.
  - Nifty 1000 (`?sys=1000`): the list is not on disk yet (`THREE_SYSTEMS.md`), so the app
    ranks the 750. The Watchlist says "750 ranked stocks" and nothing about the fallback;
    the Screener's foot reads "Nifty 1000 · 750 of 750 stocks ranked as one list", which
    reads as if the Nifty 1000 were shown. Found on the Screener, left for its owner.
  - > ₹2,000 Cr (`?sys=nano`): 1 row (SPECTRUM, rank 1); "9 not found among the 377 ranked
    stocks" lists CUPID, GLAND and the rest, which are ranked, in the 750. The index cell
    reads "NANO", an internal tag (rule 17). SPECTRUM shows no Held, though that system's
    book holds it.
  - Combined: 9 rows, TATAMOTORS not found; ranks differ from the 750 by design (CUPID 8th
    of 1,127). Industry names change with the system (SHREEJISPG "Services" in the 750,
    "Transportation" in Combined, the TradingView sector), the Screener's issue too.
- **Data health of the listed rows.** Every ranked symbol: price gap ✓, 0.0% filled, 5/5
  horizons scored on the Screener's Full Quant columns.
- **Not checked:** prices against a second source (the nightly checks own that; this page
  shows the ranking's closes, and KOTAKBANK at ₹515.80 was not checked against a corporate
  action); the CSV export's columns against the Screener's; the 60-day line's points
  against the Screener's; a symbol too new to rank (none on this list; > ₹2,000 Cr has 34);
  the stock page's "Add to watchlist" button (another agent is redesigning that page);
  the Nifty 1000 itself (not on disk); the Watchlist on a real phone.

## The mock-up

v1, 21 Nov 2026: claude.ai artifact `3FST6Ls42b3u8kTHF8RbSt`, approved by the owner on
22 Nov 2026 ("Watchlist approved"), with this order (title, lede and edit bar under "Watchlist"):

Order: Watchlist → Against the book's lines → Not ranked → Before the fill → Data to

Audited on 21 Nov 2026 in Chromium: `scripts/layout_audit.mjs` clean at 412 and 1400 px;
the PAGE_DESIGN §8 checks (fonts by role, true minus signs, + on gains, % with no space,
headlines ending in a full stop, text colours only ink, secondary, muted, up and down,
no sideways scroll) clean in light and dark at both widths; this list's checker, 27 of 27 (26 rows and the order).
The live page with the same list meets 12 of 27. Rows 5, 6 and 8 are the empty state's
text, so a check with a list cannot see them; row 12 passes on the live page only because
the heading reads "Qualified #" while every value is "Out": A1 needs a test that the
Watchlist's qualified place equals the Screener's for the same symbol, not a marker.
