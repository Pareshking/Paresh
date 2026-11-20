# Page design: what the Dashboard taught, to apply to every page

Owner, 20 Nov 2026: "after dashboard, we will improve other pages also for all
the improvements we did so make a notes of each improvements we did including
checking data etc so it will be more useful when it comes to page design."

This file is that note. Read it before redesigning any page, with
`docs/DATA_CORRECTNESS.md` (data) and `docs/THEME.md` (tokens). Each rule says
where it came from, so a later change can tell a decision from a habit.

Mock-ups the owner has seen: Dashboard v7 (approved 20 Nov, built in PR #570),
v8 with interactive charts and line bars (claude.ai artifact
`Mn1juwLgZq1RjyT83XWQep`, sent for approval 20 Nov).

---

## 1. The order of work on a page

1. **Read the page as a fund manager first.** Write down the 3 to 5 questions
   a reader comes with ("is the book ahead?", "what do I do on the 30th?",
   "is momentum working?"). Every section answers one of them; anything that
   answers none goes.
2. **Check the data behind every figure before drawing anything** (section 5).
   Most of the Dashboard's fixes were data, not design: RRG and Sectors
   disagreed, breadth history was flattered, a signal was counted the wrong
   way.
3. **Mock-up with real data**, never placeholders (owner, 19 Nov: "Remember to
   use real information for mock up"). One page, desktop and phone, light and
   dark. Show what was removed and why.
4. **Owner approves the mock-up; then build.** Mock-up first, always (owner,
   19 Nov).
5. **Before sharing a new version, list everything the previous version had and
   check it is still there.** v8 lost the strong/weak cards, the leadership
   numbers, the size table and five notes from v7; the owner caught it (20 Nov:
   "confirm nothing is missing from previous dashboard"). Then run the audit in
   section 8.
6. **Verify on the running app**: Chromium at 412 and 1400 px, no element past
   the right edge outside a scroll box; `scripts/headless_smoke.py`; full tests.
7. Record what changed in `CHANGELOG.md`, what is left in `docs/TODO.md`, and
   any new rule here.

## 2. Content

| Rule | Why / source |
|---|---|
| Open with a one-paragraph verdict that says what the page concludes, then numbered sections in the order a reader asks | Owner, 19 Nov: "dashboard must be insightful, not showing same data but inference from that data" |
| Every section heading is a sentence that states the finding ("November's lag is momentum's, not this book's"), with the key words coloured by what they mean | Owner liked v6 headlines; tipsheet.markets pattern |
| No figure twice on a page; no section that repeats another page — link to it ("The plan, share by share, on Actions →") | Owner, 19 Nov: "no duplicate", "don't show repeated information" |
| Everything visible: no "More" buttons that hide content a reader needs | Owner, 19 Nov: "people required to click it. Let's everything is there" |
| A reading that moves shows **3 months ago, 1 month ago, now** side by side | Owner, 20 Nov: "A month before values will add great information and 3M" |
| A rank in a trail means "how today's rule ranks it on that day" and says so; it can differ by a place from what the site showed then | Owner chose this, 20 Nov (option 1, not stored ranks) |
| Compare against the right benchmark and name it: live record against Nifty Total Market (the 750 we rank); 2010+ history against the Nifty 500; frozen track-record months stay as recorded, the other benchmark shown beside | Owner, 20 Nov |
| A claim about what a reading means for next month must be **tested** on our record (section 5.6), and say Pass or Not confirmed; failures stay on the page | 20 Nov, S150 |
| Say "describing is not forecasting" wherever signals are shown; the live rules stay fully invested | Standing caveat |
| Write for an investor: no internal names ("peer index", "spreads file"), short plain sentences, numbers with units | Owner feedback on v5 copy |

## 3. Tables

| Rule | Why / source |
|---|---|
| One figure per cell; numbers right-aligned in IBM Plex Mono with tabular figures; headers right-aligned over numbers | Owner, 20 Nov: the size table is the model ("Clean tables like first image required everywhere") |
| No sentence fragments inside number cells; a note under the name in small muted text instead | Owner rejected the v6 signals table |
| Sentence case for headers and labels; capitals only for the small kicker over a section | Owner, 20 Nov: "Fonts, typography, capital letter etc required" |
| Group rows with a heading row (Strong · 69.8% · what it means), not with colour alone | v7 strong/weak table |
| Colour only the cell that carries the meaning (now, the value that crossed a line); past columns muted | v7 |
| Wide tables scroll inside their own box; the page never scrolls sideways | Phone check |

## 4. Charts

### 4.1 Every chart

- **Values under the pointer.** A crosshair (or highlighted bar or row) and a
  readout of the date and every series' value. On touch the readout sits
  **above** the chart, not under the finger; vertical swipes still scroll
  (`touch-action: pan-y`). Arrow keys move it. At rest it shows the latest
  values, so a screenshot is complete. (Owner, 20 Nov: "Tipsheet website
  charts you can touch / pointer and get values".)
- **A headline that says what it shows**, then the chart as evidence.
- **Labels on the lines** at their right ends instead of a legend.
- **Faint grid**, axis numbers small and muted, gradient area under the main
  series, the latest point emphasised.
- **Folded under it:** "What it is · how to read it", and "Show the table".
- Light and dark themes both designed; colours from tokens only.
- Time series stay on Lightweight Charts (`src/ui/lw_chart.py`), restyled;
  small bar charts can be plain SVG in the same frame.

### 4.2 Line bars (owner's "IIIIIIIII" chart, 20 Nov)

For a few values on one scale (returns this month, size against the market,
breadth by size):

- Straight vertical lines, **two colours only**: ink where filled, light grey
  (`--rule`) where empty. Owner, 20 Nov: "simple straight lines and all in two
  colours ... light gray for empty area and dark black for filled area".
- **Negatives must work** (owner, 20 Nov: "Yes it must be there"): a dark zero
  line; a fall fills leftward from it. Use one scale for every row and every
  period shown, so rows and months compare.
- Each line is a stated step (0.25% for monthly returns, 0.5 pt for gaps,
  2.5% for shares); say it on the chart.
- The last line fills part of its height, so values less than a step apart
  still differ; the exact figure always sits at the end of the row.
- Markers in the same two colours: a small muted triangle for "a month ago",
  dashed lines for thresholds (40% / 60%).
- The number at the end of a row may carry the up/down colour; the lines do not.
- Lines evenly spaced with no extra gap, about 5 to 6 px apart: pick the step so a
  row holds 40 to 60 lines (owner, 20 Nov: "chart lines should be closer";
  2.5% steps looked sparse, 2% is right for a 0-100% share).
- Where earlier readings matter, show them as numbers beside the bar (3M ago,
  1M ago, now) rather than only on tap: everything visible.

### 4.3 Which chart for what

| Question | Chart |
|---|---|
| A few returns on one scale, this period | Line bars (4.2) |
| How a value moved over months or years | Line with area, crosshair, 6M / 1Y / 3Y |
| Two related series (index and breadth) | Two panes, one crosshair |
| Monthly flows or monthly leads | Bars from a zero line, up colour and down colour, the latest labelled, a threshold line where a test defines one |
| Industries' relative strength | RRG scatter, held industries filled and sized by holdings, quadrant lists beside |
| Composition of the book | Stacked bar or one mark per 1%, grouped by status |
| A rank over time | A three-point trail beside the numbers, the cut-off dashed |

## 5. Data checks before a figure ships

Each of these caught a real fault on the Dashboard. Run the relevant ones on
every page.

1. **Survivorship.** Any history over "the stocks" must count the members of
   each date, leavers included (`src/engine/pit_breadth.py`,
   `data/breadth_history.csv`). Today's members back in time made breadth
   look about 5 points broader and flipped two signal tests (S150, 20 Nov).
   A list that cannot be point-in-time is labelled ("size lists are NSE's as
   of today").
2. **Units.** `peer_index.window_return` returns a fraction,
   `dashboard_insights.window_return` a percent; a first EW-vs-market figure
   mixed them (20 Nov). Check the unit at every boundary.
3. **One source, one date.** Every index figure on a page ends on the same
   session from one source; the old strip mixed 18 and 19 Nov (S148). Drop
   rows for a session that has not closed (`session_is_complete`; Screener
   served a pre-open Nifty 50 dated 20 Nov at 08:20 IST).
4. **Same number as the owning page.** A figure shown on two pages comes from
   the same function with the same inputs: the Dashboard's book weights come
   from Portfolio's `build_portfolio_tracker` with Portfolio's clipping
   (34.4% vs 29.8% before, 20 Nov).
5. **The construction behind a comparison.** RRG and Sectors disagreed because
   one compared industries with the cap-weighted Nifty 500 and the other with
   an equal-weighted peer index; both now use the equal-weighted index of all
   ranked stocks (S147). RRG's 100 is the benchmark, not the cross-section
   average (JdK method).
6. **Test a signal before it is shown.** Rule fixed before looking: next-month
   lead differs by at least 1 point between on and off months, in the claimed
   direction, same sign in both halves (`src/engine/signal_tests.py`). Report
   n and say in-sample.
7. **A second, independent source.** Each momentum index is checked nightly
   against an ETF that tracks it (tolerance 1.5 pts); Screener's Nifty 500
   was checked against NSE's own close.
8. **Say what was not checked**, on the page where a reader needs it and in
   the PR.

## 6. Streamlit traps met on the Dashboard

- A `<style>` block whose CSS comment contains tag-shaped text (`<p>`) is
  dropped whole by DOMPurify; 119 KB of CSS vanished (19 Nov).
- The theme forces `h1`–`h6` font and colour with `!important`; page headings
  need `.dh .dh-h1 { ... !important }`.
- Style-only `st.html` goes to the event container; content renders through
  the Markdown chunk, which loads later.
- `app.py`'s code reloader needs view imports at the top, before
  `mark_loaded()`.
- `st.html` runs no script: interactive charts go in the iframe component
  (`lw_chart.render`) or a small custom component.
- Cache keys must include the revision of any data file read inside the
  cached function (`_past_stamp()` for breadth history).

## 7. Pages to do next, and what applies

| Page | First data checks | Design carried over |
|---|---|---|
| Portfolio | Weights and returns agree with the Dashboard; drawdown shows one value (S146) | Verdict, line bars for months, ₹100 chart, clean tables |
| Actions | Rank trails as on the Dashboard; buys and sells match the plan | Holdings table with rank trail, turnover |
| Breadth | Point-in-time history done (S150); charts restyled | Two-pane crosshair chart, line bars by size |
| Sectors / RRG | Equal-weight construction shared (S147) | RRG scatter with held industries; strong/weak table |
| Backtest / Track record | Nifty 500 for 2010+; frozen months as recorded, Total Market beside | ₹100 chart, monthly bars, tested claims only |
| Stock page | Prices against a second source | Crosshair readout, rank trail |
| Every page's index strip | One source, one date (S148) | — |

## 8. The audit before a mock-up or page is shared

Owner, 20 Nov: "Ensure to have colours, text, typography, formatting etc
audited first before you share it with me." Run it in a browser
(the Dashboard used a Playwright script over the rendered page):

- **Fonts by role:** headings Source Serif 4; text IBM Plex Sans; every figure
  in a table, tile or readout IBM Plex Mono with tabular figures.
- **Signs:** a minus is U+2212, never a hyphen (axis labels included); a gain
  carries "+".
- **Units:** "crore" in headlines and sentences, "Cr" in tiles, tables and
  notes; "pts" for points; % with no space.
- **Case:** sentence case everywhere; capitals only in the small kicker over a
  section, and in tickers.
- **Headlines:** each a full sentence ending in a full stop.
- **Colours:** text uses only the theme's ink, secondary, muted, up, down and
  caution; count them. Caution and down must be told apart in both themes:
  #B54708 and #A4441A were too alike, the Dashboard mock-up moved caution to
  #A86A00 (light) and #E3B341 (dark), a theme change waiting for the owner.
- **One name, one thing:** the same quadrant word in the same colour in table,
  badge, list and chart (Leading and Improving blue, Weakening amber,
  Lagging rust).
- **Layout:** no sideways scroll at 390 px; nothing clipped; labels that do not
  fit are hidden and named on tap; light and dark both looked at.
