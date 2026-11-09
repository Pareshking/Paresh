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
| `TYPE` | `var(--fs-<step>)` | eight type sizes, each with one job |
| `SPACE` | `var(--sp-<step>)` | the spacing ladder: 4, 8, 12, 16, 24, 32, 56 |
| `RADIUS` | `var(--r-sm)`, `var(--r-round)` | one corner, and the circle |
| `SHADOW` | `var(--sh-1 / 2 / pop)` | only for something that floats above the page |
| `FONTS` | `var(--font-ui / mono / serif)` | the three families |

## How it reaches the page

- `tokens.css_root()` writes every one of them as a CSS variable, and
  `theme.inject_custom_css()` puts that on every page.
- A table or chart drawn in its own frame cannot see the page's variables, so
  the code that sends it passes the text through `tokens.resolve()`, which
  writes the values in. `resolve()` raises on a name the theme does not
  define, so a typo cannot ship as an invisible colour or a missing size.
- Python that needs a colour as a value uses `tokens.C.<name>`.

## The type scale

Eight steps, because the stylesheet had grown 39 distinct sizes, four of them
inside a 1.5px range doing the same work (design audit, 8 Nov 2026).

| Step | Size | Used for |
|---|---|---|
| `--fs-12` | 12px | column headers, labels, footnotes, chart axes |
| `--fs-13` | 13.5px | table rows, notes |
| `--fs-15` | 15px | body, a card's lede |
| `--fs-17` | 17px | a page's lede |
| `--fs-24` | 24px | card title, section heading (serif) |
| `--fs-30` | 30px | the one figure a card is about (serif) |
| `--fs-36` | 36px | page headline on a phone (serif) |
| `--fs-52` | 52px | page headline (serif) |

Nothing goes below 12px, chart labels included: that is the floor the
redesign promised and `tests/test_redesign_legibility.py` holds it.

## The rules that keep it the only source

- `tests/test_theme_tokens.py` fails if a `var(--c-…)`, `--fs-…`, `--sp-…`,
  `--r-…` or `--sh-…` is used that the theme does not define.
- The same file keeps a budget of literal `font-size: …px` left in the UI, and
  the budget may fall but never rise. What remains is the display end, which is
  judged one heading at a time; the dense end is already on the scale.
- `.streamlit/config.toml` cannot read Python, so it repeats a few colours;
  a test fails if the two disagree.

## Changing the look

Edit `src/ui/tokens.py`, run `python -m pytest tests -q`, then look at the
pages: `streamlit run app.py` and read the Dashboard, Screener, a stock page
and Portfolio at 1400px and at 390px. A change to a colour or a type step
moves every page at once, which is the point and also the risk.
