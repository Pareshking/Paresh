# Dashboard design audit, 11 Nov 2026

Owner, 11 Nov 2026: "let's have separate agent with design skills run a audit on dashboard
first and generate any rendering or suggestions ... same can be replicated later to other
pages", and "it must identify what is missing on dashboard or what we should add".

An independent agent ran the audit, using the `design:design-critique` and
`design:accessibility-review` skills, on the live site (closes of 9 Nov 2026, captured
11 Nov around 11:00 IST) at 1400 px and 390 px. It was told not to read earlier audits,
and it changed no code. Its findings were then checked against the code, the live page and
the 8 Nov audit before being written here (**Checked** column). Mockups are in
`docs/design/dashboard_2026-11-11/`; every one is marked "Illustrative — not implemented"
and uses only figures copied from the live pages.

Nothing on the page has been changed.

**Owner's decision, 11 Nov 2026:** D1-D3 (the book before the market, one heading size,
status chips) were built and shown as full pages, before and after, at desktop and phone
width. The owner rejected them: "didn't like it at all vs current one". They were reverted,
and the current layout stays. Do not propose D1-D3 again; the rest of this report is kept
for reference.

## 1. Main finding: the book comes after the market

Book at risk starts 1,945 px down the page on a desktop. On a phone it starts 3,790 px
down (4.5 screens), and Next rebalance starts at 6,082 px (7.2 screens). The book's cards
are drawn after all four market questions (`dashboard_view.py:262-287`), and their
headings are forced to 15 px (`theme.py:1976`) while the market's are 24 px. The question
a holder asks first, "is anything about to be sold?", is answered last.

Text contrast is not a problem: all 375 text nodes pass 4.5:1 (the lowest is 5.43:1), and
nothing is below 12 px. That matches the 8 Nov fixes (U-M14).

## 2. Findings

| # | Sev | Finding | Where | Fix (presentation only) | Checked |
|---|---|---|---|---|---|
| D1 | High | The book's cards come after all four market questions | `dashboard_view.py:262-287` | Draw the `db_page` columns before `render_market_questions`; reorder only | Code read |
| D2 | High | The book's card headings are forced to 15 px; market headings are 24 px | `theme.py:1976` | Remove the override | Code read |
| D3 | Med | "Sold if unchanged" (#A4441A) and "Watch" (#B54708) are 1.13:1 apart; the boldest mark on the card is the black bar of the safe rows | Book at risk, `theme.py:1987-1993` | Filled rust chip for a sale, amber outline for Watch, grey bars for Clear (M2) | Code read |
| D4 | Med | Each index tile mixes three periods: the big figure is the day (only screen-reader text says so), "1M" is a month, and the line is 3 months. Colours disagree (Nifty 500 +0.3% blue, its line rust) | Index strip, `market_questions_view.py:786-806` | Label it "Today", write "1 month", draw the line in neutral grey (M3) | Agent's |
| D5 | Med | On a phone, the 14 section links take five lines (220 px) before any content | Section menu, `theme.py:1942-1950` | One scrolling row of 44 px chips, grouped Book / Market (M4) | Agent's |
| D6 | Med | Units missing or mixed: the uptrend table's "Now" column holds −3.1 and 45%; Sectors' "1M" header has no "vs Nifty 500, pts" | Uptrend, Sectors, Size | Put the unit in the column header, one convention for every table | Live page: the column mixes points and % |
| D7 | Med | The headline says "this month"; Portfolio says "MTD return" / "Nov" and also "Since last rebalance +5.0%"; no start date is given | Headline, `dashboard_view.py:75-95` | Name the period ("Nov to 9 Nov"); one term site-wide | Agent's |
| D8 | Med | Vote cut-offs appear only on hover (`title` on a table cell), which keyboard and touch users cannot reach (WCAG 2.1.1, 1.4.13) | Market questions | Print the cut-off under the measure, or use a `<details>` | Agent's |
| D9 | Med | The same figures repeat: Nifty 500 1M +7.8% and Nifty 50 +11.2% appear in both the strip and Size; "3.4% above 200D EMA" appears in both the header and the uptrend table | Strip, Size, header | Keep each figure in one place | Live page |
| D10 | Med | Method captions are longer than the figures they explain (Momentum health about 95 words at 12 px) | Momentum health, Qualify, Risk | `st.expander("How this is measured")` | Agent's |
| D11 | Low | The trend scale's end marker is cut in half by the box edge | `.mq-scale` | Inset 7 px each side | Agent's |
| D12 | Low | A minus sign wraps away from its number | Flows, `dashboard_panels.py:56-76` | `nowrap` around each figure | Agent's |
| D13 | Low | Type sizes off the token scale (13 px on 111 elements, 28 px, a literal 36 px) | Market tables, strip, `theme.py:2022` | Use the tokens | Agent's |
| D14 | Low | The phone header strip scrolls sideways with its scrollbar hidden and cuts "23,567" mid-number | Header, `theme.py:438-451` | Fade the right edge | Left open by the 8 Nov audit (U-L17-25) |
| D15 | Low | Bar charts are fixed 300 px images: zero line at 1.2:1, no month labels | Momentum health, Flows | Darker zero line, first and last labels, full width | Agent's |
| D16 | Low | On a phone, 8 risk rows take 935 px, and `display:none` on the header row also hides it from screen readers | `theme.py:2043-2045` | Two-line rows (M2p); visually-hidden header | Agent's |
| D17 | Low | Copy: "1 of 13 … are"; "0.03 days" for the slowest exit | Leadership, Book risk | "is"; "under a day" | Agent's |

"Agent's" means the agent measured it and the measurement is in its capture, but it was
not re-measured here.

## 3. What is missing

| Question an investor asks | Dashboard | Elsewhere |
|---|---|---|
| Is my book OK this month? | Yes (headline) | Portfolio (Nov alpha −3.0 pts) |
| How did it do today? | No | Portfolio Day P&L (+0.9% vs +0.3%) |
| How has it done overall? | No | Portfolio since inception (+44.7% vs −1.4%) |
| How is each holding doing? | No | Actions "Since entry" |
| What will be sold, and when? | Yes | Actions |
| What do I trade? | No | Actions (Kite basket) |
| What is the market doing? | Yes | Breadth, Sectors, RRG |
| What changed since I last looked? | Partly | A holding's status change since yesterday is **not answered anywhere** |

Additions from figures the app already computes:

| Addition | Value | Cost | Already exists in |
|---|---|---|---|
| A. A book strip with MTD return, month alpha, Day P&L and since inception (M1) | High | About 110 px | `portfolio_view.py:608-662, 752`. Day P&L needs the table at `:305-328` moved into a shared function |
| B. A "Since entry" column in Book at risk (M2) | High/Med | One column | Actions |
| C. A Kite basket link in Next rebalance | Med | One button | `actions_view.py` |
| D. An equity spark line | Med | 120x28 px | `record["equity_curve"]`, `kit.spark_img` |
| E. The top industry weights | Low/Med | 3 lines | Portfolio, industry exposure |

These need a new calculation, outside a presentation audit:
- **F.** Each holding's status at the previous close, to show what changed since yesterday (`exit_watch.assess` on the previous day's ranking). High value.
- **G.** A "since your last visit" summary, which also needs per-viewer state. Medium value.

What could be removed or moved to make room:
- Fold "Is leadership changing?" into "Which sectors lead?": it reads the same table again (about 500 px on a phone).
- Move Size leadership to Breadth or Sectors, or cut it to its headline sentence: it repeats the strip and the uptrend question (about 470 px).
- Momentum health and Qualify: keep the figure and its sentence, and move the method text. The owner asked for these cards (S91), so this is the owner's call.
- Drop the uptrend table's 200D EMA row, which repeats the participation table.

### Reviewer's objection to addition A

M1 puts "Since inception +44.7% vs −1.4%" on the Dashboard's first screen. Nine of that
record's ten frozen months are backfilled, so the number is mostly a backtest (audit
2026-11-11, Q-H1). The owner chose to keep that headline on Portfolio without a note
(S122). Promoting it to the first thing every visitor sees is a separate decision. The
strip works with three tiles (MTD, month alpha, Day P&L); since inception can stay on
Portfolio, where the Origin column sits beside it.

## 4. What works and should be kept

- The headline is a sentence of news built from the page's own figures.
- Every market question follows one pattern: verdict, evidence table, a month ago and a
  year ago, then a link onward.
- Contrast passes and no text is below 12 px.
- Charts carry real alt text and print their highest, lowest and latest values.
- Sources and as-of dates are stated throughout.
- Phone tap targets are 44 px tall; there is a skip link and a visible focus outline.

## 5. Mockups (`docs/design/dashboard_2026-11-11/`)

| File | Shows |
|---|---|
| `m1_desktop.png`, `m1_phone.png` | The book first: headline, book strip (A), grouped menu, then Book at risk and Next rebalance above "The market" |
| `m2_desktop.png`, `m2p_phone.png` | Book at risk before and after: status chips, grey Clear bars, Rule and Room in separate columns, "Since entry" (B); two-line rows on a phone |
| `m3_desktop.png`, `m3_phone.png` | Index strip before and after; the trend scale without the clipped marker (marker positions approximate) |
| `m4_phone.png` | The phone's first screen before and after: a scrolling chip menu and the first sale on screen one |

## 6. Not checked

- Whether any calculation is correct (out of scope).
- A real screen reader. Keyboard testing went only to the 15th Tab stop.
- Zoom to 200%, forced colours and dark mode.
- Widths between 390 and 1400 px.
- Empty and error states.
- Load time.
- A real phone (touch was emulated).
- How closely the mockups match what Streamlit can render.
- "Since entry" in M2 was copied from Actions by the agent; I did not re-read it from Actions.

## 7. Method, to run the same audit on another page

1. Start a separate agent with the `design:design-critique` and `design:accessibility-review`
   skills. It must not read earlier audits, so its read is independent, and it must change
   no code.
2. Capture the live page at 1400x1000 and 390x844. The app is in an iframe titled
   `streamlitApp`; wait for the page's own title text. Capture each section.
3. Measure rather than eyeball:
   - contrast of every text node, font sizes, tap targets, overflow at 390 px;
   - where each section starts and how tall it is (`*_sections.json`);
   - keyboard focus order.
4. Rank the findings High/Medium/Low. Give each its location as file:line and its evidence,
   and a fix that works in Streamlit (st.html, CSS, the kit).
5. Write a "What is missing" table: the investor's questions, where each is answered (this
   page, another page, nowhere), and candidate additions, marking which already exist in
   the code and which need a new calculation.
6. Render three to six mockups with the page's real figures and the product's tokens, each
   marked "Illustrative — not implemented". Never use a number, signal or sentence the page
   does not compute.
7. Before reporting, the main session re-checks each finding against the code, the live
   page and the earlier audits, and marks it in the **Checked** column.
