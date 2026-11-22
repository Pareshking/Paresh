# The theme file

`src/ui/tokens.py` is the one place the site's look is set: colours, type
sizes, spacing, corners, shadows and fonts. Change a value there and it
changes everywhere that value is used, on every page and inside the framed
tables and charts as well.

Owner, 9 Nov 2026: "ensure we have something like a theme file, like
WordPress has, so one can do all the changes globally."

## What is in it

| Group | Variable | Holds |
|---|---|---|
| `PALETTE` | `var(--c-<name>)` | every colour: ink, muted, rule, up, down, caution, the chart hues |
| `TYPE` | `var(--fs-<step>)` | nine type sizes, each with one job |
| `SPACE` | `var(--sp-<step>)` | the spacing ladder: 4, 8, 12, 16, 24, 32, 56 |
| `RADIUS` | `var(--r-sm)`, `var(--r-round)` | one corner, and the circle |
| `SHADOW` | `var(--sh-1 / 2 / pop)` | only for something that floats above the page |
| `FONTS` | `var(--font-ui / mono / serif)` | the three families: IBM Plex Sans, IBM Plex Mono, Source Serif 4, self-hosted (`static/fonts.css`) |

## How it reaches the page

- `tokens.css_root()` writes every one of them as a CSS variable, and
  `theme.inject_custom_css()` puts that on every page.
- A table or chart drawn in its own frame cannot see the page's variables, so
  the code that sends it passes the text through `tokens.resolve()`, which
  writes the values in. `resolve()` raises on a name the theme does not
  define, so a typo cannot ship as an invisible colour or a missing size.
- Python that needs a colour as a value uses `tokens.C.<name>`.

## The type scale

Eight steps at first, because the stylesheet had grown 39 distinct sizes, four
of them inside a 1.5px range doing the same work (design audit, 8 Nov 2026).
There are nine now: `--fs-44` ("the page's single biggest figure: a price, a
rank" in `src/ui/tokens.py`) is also the redesigned pages' title (checked 21
Nov 2026).

| Step | Size | Used for |
|---|---|---|
| `--fs-12` | 12px | column headers, labels, footnotes, chart axes |
| `--fs-13` | 13.5px | table rows, notes |
| `--fs-15` | 15px | body, a card's lede |
| `--fs-17` | 17px | a page's lede |
| `--fs-24` | 24px | card title, section heading (serif) |
| `--fs-30` | 30px | the one figure a card is about (serif) |
| `--fs-36` | 36px | section heading; page headline on a phone (serif) |
| `--fs-44` | 44px | page title on Dashboard, Portfolio, Actions, Market and Indices; the stock page's price and rank (serif) |
| `--fs-52` | 52px | page title from `page_kit.page_head` (Screener, Sectors) and the stock page's name (serif) |

The scale's smallest step is 12px. The test is looser than that:
`tests/test_redesign_legibility.py` fails on text under 11px, and only in the
CSS it slices (the top bar, the Screener, the stock page, the Screener table).
The chart kit (`src/ui/dash_charts.py`, drawn in its own frame) sets its axis
labels, band labels and tooltip date at a literal 11px, outside the scale and
outside that test (checked 21 Nov 2026).

The serif has two stand-ins, the reader's own Noto Serif or Times resized to
Source Serif 4's width (`tokens.serif_face_css`), so a headline does not
re-wrap when the real face arrives (S145, #564).

## The rules that keep it the only source

- `tests/test_theme_tokens.py` fails if a `var(--c-…)`, `--fs-…`, `--sp-…`,
  `--r-…` or `--sh-…` is used that the theme does not define.
- The same file keeps a budget of literal `font-size: …px` left in the UI, and
  the budget may fall but never rise: 24 in `theme.py`, none in `page_kit.py`,
  `components.py` and `screener_table.py`, 39 across `src/ui/views/`. The chart
  kit's frame CSS in `dash_charts.py` is not in the budget. What remains is the
  display end, which is judged one heading at a time; the dense end is already on the scale.
- `.streamlit/config.toml` cannot read Python, so it repeats a few colours;
  a test fails if the two disagree.

## Numbers

How a number reads is in `src/ui/formats.py` (Python) and `static/dash_charts.js` (`pxf`, `sg`) for charts:
prices and ₹ levels in whole rupees at every level, returns and points to one decimal, the minus
U+2212. The 8 rules and their exceptions are in `docs/PAGE_DESIGN.md` §3a (S173, owner 22 Nov 2026); CI checks every page
with `scripts/number_format_audit.mjs`.

## What is not in it

Breakpoints are not tokens. They are written in the stylesheets, the one that
matters most in `src/ui/theme.py`: from 1024px the top bar links every page and
the menu button is hidden; below it the menu (☰) is the only navigation (#592).

## Changing the look

Edit `src/ui/tokens.py`, run `python -m pytest tests -q`, then look at the
pages: `streamlit run app.py` and read the Dashboard, Screener, a stock page
and Portfolio at 1400px and at 412px. `node scripts/layout_audit.mjs <url>
412,1400` measures what the eye would miss (headings off their columns, labels
wrapping, charts leaving width empty); CI runs it on the Dashboard, Portfolio,
Actions, Market, Sectors, Screener and Indices. A change to a colour or a type
step moves every page at once, which is the point and also the risk.
