---
name: page-redesign
description: Redesign or restyle any page of the NSE Momentum Terminal (Dashboard, Actions, Screener, stock page, Portfolio, Market, Indices, Sectors, Watchlist, Backtest, Configuration, Guide). Use before changing a page's sections, headings, charts, tables or wording, and before showing the owner a preview.
---

# Redesigning a page

The owner, 28 Nov 2026, on the redesigns so far: "lots of information and sections we lost which was really useful for insights",
"I am talking about silent drops by you". A redesign removes nothing silently. Approving a preview approves what it shows, not what
was taken out.

Do every step, in order. Write down each step's result; the owner reads the list.

## 1. Inventory first

- Read the page's rows in `docs/PAGE_INVENTORY.md` and its part file in `docs/archive/S238/`. Read them all, first screen to footer:
  the sections most often missed are the last ones (lists at the bottom, "Today's charts", footers, expanders, dialogs, empty states).
- Read `docs/PAGE_INVENTORY.md` §1. Nothing on that list is dropped again.
- Read the page's `docs/<PAGE>_REQUIREMENTS.md` and `docs/PAGE_DESIGN.md`.

## 2. The owner's rules before any benchmark

A choice is "decided by benchmark" only when no owner rule covers it. Before calling it that, search:

- `docs/*_REQUIREMENTS.md`
- `docs/PAGE_DESIGN.md`
- `docs/TODO.md`
- `docs/HANDOVER.md`

Search for the item's words (for example "source", "heat", "line bars", "tick"). Where an owner rule exists, it stands; a change to it goes to the owner as a question. Example of getting this wrong: S237 G4 put source lines under every chart against "Let's not show source" (owner, 20 Nov), and had to be reverted on 28 Nov.

The patterns allowed from tipsheet.markets, and what may not be taken from it: CLAUDE.md, "tipsheet.markets may be copied". The gaps and their names (G1-G8): `docs/archive/S237_COMPARISON_2026-11-28.md`.

## 3. Build on real data, on a branch

- Work in a separate git worktree when a PR is open on the working branch. A push to an open PR restarts its full CI.
- Run the app on the committed data: `UMIYA_DATA_DIR=/tmp/claude-0/cicache streamlit run app.py --server.port <port>`.
- Inline SVG is stripped by `st.html`. Draw small lines as an image: `src/ui/record_line.spark_svg`, the same way as the Dashboard's rank trail.
- Every date chart states its range (`"range": {...}` in the spec literal; `tests/test_s193_h_chart_ranges.py`).
- Font sizes come from `tokens.TYPE` (`var(--fs-…)`); colours from the tokens.
- Build each section to `docs/PAGE_DESIGN.md` §2b (one function, a heading that answers, history as a line with its
  usual range, the detail folded, no source line), so the full-page redesign places it and does not redo it.
- Charts: load the `dataviz` skill. Copy: the `design:ux-copy` skill.

## 4. Before and after

Write a table for the owner with one row per section and per figure in the inventory, and one column each for before and after. Each row reads kept, changed (how), moved (where) or **left out (owner to decide)**.

Never leave a row out of this table. A figure that leaves a section is a row too (for example the P/E 3 months and a month ago).

Then run the machine check, the main-branch app against the preview:

    node scripts/section_diff.mjs http://localhost:<main-port>/<page> http://localhost:<preview-port>/<page>

It lists every heading, kicker, chart, word a chart prints (column heads, readout names), table column, tile, expander, button,
download and image the preview lacks. It exits 1 while anything is missing. Every "-" line must be a row of the table: kept under
another name, moved (where), or left out for the owner to decide. Its first run, 28 Nov, on the Indices preview found the 36 dropped
parts that the eye had missed (the P/E 3 months and a month ago, the month-ago percentile, dividend yield, the yield gap).

## 5. Check the preview

- Screenshots at 1400 px, full page, and iPhone 13, full page, of the local run.
- Check the screenshots for:
  - `stMain` scroll width (no sideways drag);
  - "Traceback", "nan", "undefined";
  - page errors.
- Run `design:design-critique` and `design:accessibility-review` on the screenshots. Fix what they find, or note why not.
- Check two figures against an outside source (for example the Nifty 50 P/E against tipsheet's, or a close against BSE). Use the `data-check` skill.

## 6. Show the owner

Send:
- the screenshots;
- the before/after table;
- the weak points first: what is not checked, what changes an approved template, which owner rule it touches.

Ask one decision at a time. No PR or CI run before the owner approves (owner, 28 Nov: "I will approve re design pages first with real data").

## 7. After approval

- Update the tests that pin approved templates, the requirement rows and their markers, `docs/PAGE_INVENTORY.md` and its part file, `CHANGELOG.md` and `docs/TODO.md`.
- Run `bash /tmp/claude-0/s203/ci.sh` (or the checks it lists: pytest, ruff, `headless_smoke.py`, the layout, requirement, number-format and glossary audits).
- Then one PR. Merge rules: CLAUDE.md.
