# Launch test plan — 10 Nov 2026

Owner, 10 Nov 2026: "we are going to launch website tomorrow. Plan all types of
test in next 5 hours and make half hourly schedule to continue working in it."

The site already has 2,607 unit and engine tests, and they pass. What a launch
needs on top of that is the kinds of failure a unit test cannot see: a page that
throws only with real data, a number that two pages report differently, a
control nobody can tap, a job that dies quietly, a secret in a log.

Each slot below says **what it proves** and **how we will know it passed**, so a
slot that finds nothing is still a result and a slot that finds something leaves
evidence. Findings go to `docs/TODO.md` the same day, as CLAUDE.md requires.

## Standing rule for every slot

- A failure is written down with the measurement that found it, not a
  description. "Portfolio drags sideways" is not a finding; "main 1307px in a
  390px viewport" is.
- Nothing merges to `main` without the full suite green and the pages rendered.
- **Launch day is the wrong day for a refactor.** Anything that changes a number
  the site reports stops and waits for the owner, however obviously right it
  looks.

## The schedule (UTC)

| Slot | Time | What |
|---|---|---|
| 1 ✅ | 02:35 | **This plan, and the pre-launch gate.** One command that answers "is the site fit to launch right now": every page renders, no page wider than its viewport, data freshness inside tolerance, no secret in the repo. |
| 2 ✅ | 03:05 | **Functional sweep, desktop.** All 12 pages at 1400px: every control exercised once (filters, pickers, tabs, expanders, downloads, popovers), deep links (`?stock=`, `?owner=`), and the nav. Proves: nothing throws when touched, not merely when loaded. |
| 3 ✅ | 03:35 | **Functional sweep, phone.** The same at 390px, plus tap-target measurement and the menu. Proves: the phone is a first-class reader, not a resized desktop. |
| 4 ✅ | 04:05 | **Cross-reading consistency.** Take every figure that appears on more than one page (the EMA distance, the qualified count, returns, drawdown, the book's value) and assert the pages agree. Proves: no second EMA bug. |
| 5 ✅ | 04:35 | **Resilience.** Run the app against a missing price file, a stale one, an empty ranking, no R2 credentials, and a benchmark with a gap. Proves: it degrades with a sentence, not a traceback. |
| 6 ✅ | 05:05 | **Accessibility.** Contrast on every text colour actually used, heading order, alt text, keyboard-only navigation, focus visibility, screen-reader labels on icon buttons. Target: WCAG 2.1 AA. |
| 7 ✅ | 05:35 | **Performance and weight.** Cold start, time to content per page, page bytes, memory at the heaviest page, test-suite runtime. Records the numbers the owner's 10%/20%/20% targets are measured against. |
| 8 ✅ | 06:05 | **Security and privacy.** Secret scan over the repo and the built page, the owner-gated controls, query-parameter injection through `?stock=`, what the published page exposes, and what the logs print. |
| 9 ✅ | 06:35 | **The jobs.** Every scheduled workflow's last run, the failure alert itself, and a dry run of the two that matter tomorrow (the daily sync and the monthly freeze). Proves: a silent job failure is impossible. |
| 10 | 07:05 | **Content.** No placeholder text, no "TODO" or "lorem", every external link resolves, every date on the page is the date it claims, the Guide matches what the model does. |
| 11 | 07:35 | **Launch report.** One page: what was tested, what was found, what is fixed, what is known and accepted, and the single sentence on whether it is fit to launch. |

## What this plan does NOT cover, and why

- **Real iOS Safari and Android Chrome.** Owner, 10 Nov 2026: "Safari not
  required to be tested." Phone-width Chromium is therefore the standard, and
  slot 3 holds it.
- **Load.** Streamlit Cloud serves one container; a load test would mostly
  measure their queue, and running one against production the night before
  launch risks the thing it is meant to protect. Out of scope deliberately.
- **The strategy's returns against an independent source.** None exists
  (`docs/AUDIT_2026-11-08.md`, "What was not checked").


## Slot results

### Slot 1 — the gate (02:35 UTC, done)

`scripts/launch_gate.py` answers the question in one command, and
`scripts/_launch_pages.js` draws every page for it. First run, 4/4:

| Gate | Result |
|---|---|
| No secret in the repository | 2,022 tracked files scanned, none |
| The committed fallback prices are usable | last session 5 Nov, 4 trading days behind |
| Pages at 1400px | 11 drawn, none throws, none over its viewport |
| Pages at 390px | 11 drawn, none throws, none over its viewport |

One thing the first version of this gate got wrong, worth recording because it
is the kind of mistake a launch gate must not make: it failed the price check at
"4 trading days behind" as though the site were serving stale prices. It is not.
`data/nse_prices/closes.parquet` is the **fallback**
(`src/loaders/nse_prices.py:8`); the app reads the R2 pin or the release copy
first, and the live footer said 8 Nov. A gate that cries wolf about the wrong
file would have been worse than no gate, so it now names the source it read and
fails only if the fallback is old enough to mislead on a day R2 is unreachable.
What a reader actually sees is the footer, which the page sweep reads.

### Slot 2 — every control touched, desktop (03:05 UTC, done)

`scripts/_launch_controls.js` clicks each pill, tab, expander and ordinary
button once at 1400px and waits for the rerun. Loading a page proves little:
most Streamlit failures happen on the rerun a control triggers.

| Page | Controls clicked | Failures |
|---|---|---|
| Dashboard | 0 (it has links, no controls) | — |
| Screener | 7 | none |
| Portfolio | 9 | none |
| Actions | 4 (5 skipped as destructive) | none |
| Sectors | 11 | none |
| Breadth | 6 | none |
| Backtest | 6 | none |
| Watchlist | 1 | none |
| Configuration | 6 | none |
| Guide | 0 | — |
| Sectors rotation (RRG) | 10 | none |

**60 controls, nothing thrown.** Destructive controls are never clicked: a
label matching sync, clear, delete, reset, remove, download or export acts
site-wide or writes a file.

One failure was reported and then withdrawn, which is worth recording. The
first run said a Configuration control could not be clicked (an 8s timeout).
It was the harness: an earlier click had opened a dialog, and the modal covered
everything after it. With dialogs dismissed between clicks, Configuration
passes 6/6. A test that blames the app for its own mess is worse than no test.

**Two 404s on every page, explained and left alone**: Streamlit's own client
asks for `_stcore/health` and `_stcore/host-config` relative to the page path
(`/screener/_stcore/health`) before falling back to the root. It is Streamlit's
behaviour, not ours, the app works, and it accounts for the "console errors: 15"
that production QA reports. Recorded so nobody chases it as a symptom later.

**The owner gate holds.** With no `OWNER_KEY` set, `?owner=`, `?owner=guess`,
`?owner=1`, `?owner=true` and `?owner=admin` all leave the two site-wide
controls hidden ("Sync from niftyindices.com", "Clear cached files"). A visitor
cannot guess their way to a button that clears everyone's caches.

### Slot 3 — the phone (03:35 UTC, done)

**Controls at 390px: 61 clicked across 11 pages, nothing thrown.** The same
sweep as slot 2, at phone width; Backtest exposes one more control there.

**Tap targets, measured with touch emulation so the coarse-pointer rules are in
force.** Before and after, counting only targets a finger actually aims at (an
element clipped to a sliver — the focus-only skip link, a checkbox hidden
behind its own label — is not one, and counting them made the number
meaningless):

| Page | Under 44px before | After |
|---|---|---|
| Dashboard | 24 | **0** |
| Screener | 21 | **0** |
| Actions | 30 | **0** |
| Portfolio, Sectors, Breadth, Guide, Watchlist | 1–4 each | **0** |
| Sector rotation | 2 | 1 |
| Configuration | 13 | 12 |

Three causes, each a real bug rather than a near miss:

1. **Padding cannot make a 16px line box 44px tall.** `.db-sym a` came out
   38.2px and `.mq-more` 42.8px with 11px of padding top and bottom. They set
   `min-height: 44px` with the text centred now, and `.t50-chip` (32px on
   Actions) joins them.
2. **The menu button's phone rule never won.** Its base rule is
   `min-height: 40px !important`; the phone override was not `!important`, so
   the computed height stayed 40px while the CSS claimed 44.
3. **The download button's rule sits *after* the coarse-pointer block.** Equal
   specificity, later wins — so the touch override had to move below it, not
   above. The header brand link needed its height set rather than padded.

**What is left, and why it stays.** Configuration's twelve are Streamlit's own
widget internals on the one page made of sliders: the slider track (16px, seven
of them), a multiselect's "×" (7px), "Clear all" (24px), a help icon (22px).
Their labels and thumbs are what a finger uses, and giving a slider track a
44px box changes what the control looks like. It is a settings page, not the
reader's path. The one on Sector rotation is a 32px Streamlit button in a
narrow container. Both are recorded rather than bodged the night before a
launch.

### Slot 4 — do the pages agree with each other? (04:05 UTC, done)

`scripts/launch_consistency.py` takes each figure that appears on more than one
page, reads it from the rendered text of every page that shows it, and asserts
they match inside a stated tolerance. This is the generalisation of the 8 Nov
bug, where the header said 2.9% above the 200-day EMA and the uptrend table
said +3.0.

**6/6 agree.**

| Figure | Pages | Value |
|---|---|---|
| Nifty 500 above its 200D EMA | Dashboard, Breadth | 3.4% / +3.4 |
| Nifty 500 index level | Dashboard, Screener, Portfolio | 23,567 |
| The universe's size | Dashboard, Screener, Actions | 750 |
| Stocks above their 50D EMA | Dashboard, Screener | 368 |
| Stocks near their 52W high | Dashboard, Screener | 371 |
| Stocks above their 200D EMA | Dashboard, Breadth | 45% |

**Two of those "failed" first, and both were the check's fault.** The by-size
table on Breadth is tab separated with two columns per measure — a month ago,
then now — so reading the first number after the heading gave the month-ago
column (−4.6) and reported an 8-point disagreement with the header's +3.4. The
second rule read a figure out of a chart's alt text (87%) instead of the table
(45%). Both regexes now address the cell they mean.

That is the second time in three slots that the harness, not the app, was
wrong, which is itself the finding: an automated check reports what it matched,
not what it meant to match, and the night before a launch a false alarm costs
more than a missing test. Every rule here names where it looked, and a rule
that cannot find its figure fails loudly instead of passing on an empty match.

**Not covered by this slot**: figures that appear on only one page (nothing to
compare), and the record's own returns, which no second source reports.

### Slot 5 — resilience (04:35 UTC, done). Four bugs, all launch-relevant

Run in a throwaway git worktree on its own port, so the real tree was never
broken. Each case removes or truncates one file the app reads, then sweeps the
pages for a thrown exception.

| Case | Result |
|---|---|
| `closes.parquet` removed | no effect — see below |
| `track_record.json` removed | pages degrade, nothing thrown |
| `momentum_health.csv` removed | the two cards say so, nothing thrown |
| **`benchmarks.csv` truncated mid-row** | **Dashboard, Breadth and Sectors all threw** |

**The price case proved the opposite of what it set out to.** Deleting
`closes.parquet` changed nothing, because the app's live source is Screener,
fetched at run time: `Ranking price source selected: source=screener
as_of=2026-11-09 high_basis=closing prices intraday=no`. The committed parquet
is only the fallback. Worth recording twice over, because the same log line
independently confirms the 52-week-high change: `high_basis=closing prices`.

**A half-written `benchmarks.csv` took three pages down, in three different
places.** The file still parses when it is cut mid-row — but its dates come
back as strings, and nothing downstream expects that:

1. `dashboard_view` wrote `(bench or {}).get("nifty500")`, and `bench` is a
   DataFrame. Python only evaluates that branch when the primary series is
   empty — the degraded case — so the crash was invisible until the file
   broke. `breadth_view` and `sector_view` had the same line. Now one
   `_series_of` helper, which never asks a frame whether it is true.
2. `market_questions._on_or_before` called `searchsorted` on a string index:
   *"'<' not supported between instances of 'str' and 'Timestamp'"*. It
   returns None now rather than raising.
3. `sector_breadth` called `asof` through the **other** reader of the same
   file, `benchmark_store.read`, which my first guard did not cover. One file,
   two readers — exactly the duplication the 10 Nov audit flagged. Both now
   reject an undated file.

**And the worst of the four, which was not a crash at all.** With no usable
benchmark the header read **"Nifty 500 0.0% above its 200D EMA"** beside a
level of **"0"**. A traceback tells a reader something is broken; a confident
zero tells them the Nifty 500 is at zero. It reads **"Nifty 500 — no reading"**
now, with "—" for the level.

Three regression tests cover the undated file, both readers, and the honest
header. The healthy path is unchanged: 2,609 tests pass and all six
cross-page figures still agree.


### Slot 6 — accessibility (05:05 UTC, done). The site is clean; the check was not

`scripts/launch_a11y.py` with `scripts/_launch_a11y.js` measures four things on
the rendered page, at 1400px and at 390px, over the same eleven pages the gate
draws. It measures what a reader meets rather than what the stylesheet claims:
the computed colour of each text run against the background actually painted
behind it, and the accessible name a screen reader would announce.

| Measured | 1400px | 390px |
|---|---|---|
| Text runs below 4.5:1 (3:1 for large text) | 0 of 16,159 | 0 of 15,443 |
| Controls with no accessible name | 0 of 360 | 0 of 275 |
| Images with no `alt` | 0 | 0 |
| Heading order (one h1, no skipped level) | 11/11 pages, 86 headings | 11/11 |
| Keyboard stops with no focus ring | 0 of 266 | 0 of 268 |
| `lang` on `<html>` | `en` on all 11 | `en` |

**11/11 pages clean, both widths.** The 390px column doubles as the WCAG 1.4.10
reflow case: 390 CSS pixels is what 1400px looks like at 360% zoom, and slot 3
already proved nothing there scrolls sideways.

**The one change to the site**: `textarea:focus-visible` was missing from the
focus-ring rule in `src/ui/theme.py` — `input` was there, `textarea` was not.
Nothing on a reader's path is a textarea today, so nothing looks different; it
is one word, and the next text area would have been invisible to a keyboard.

**And one change withdrawn.** The first version also added
`iframe:focus-visible` to that rule, on the strength of "12 keyboard stops with
no focus ring" on Screener. The rule is inert: `document.activeElement` points
at the IFRAME while focus is really inside the frame's own document, so the
iframe element is never `:focus-visible`. Shipping a selector that cannot match
to fix a bug that does not exist is worse than shipping nothing, so it came out
again.

**Five faults in the check itself, which is the real content of this slot.**
Every one of them would have been reported to the owner as a site bug:

1. **Nine well-labelled buttons reported as unnamed.** The accessible name was
   read from `innerText`, which is layout dependent and comes back empty for a
   control below the fold. `Top 10`…`Top 30` on Actions and the backtest's
   submit button all have text; `textContent` sees it.
2. **The header nav reported at 1.51:1.** Same cause, other end: an element
   that has a text node but an empty `innerText` has not been laid out, and its
   computed colour is not what gets painted. A screenshot of the backtest
   header shows `Dashboard  Actions  Screener  Portfolio` in near-black on
   white. The check now skips a run with no laid-out text, because a contrast
   claim about text nobody can read is not a contrast claim.
3. **A slider's value label reported at 1.51:1.** This one was not a timing
   artefact: the ancestor walk found a real painted background, the dark filled
   track of the slider, eight pixels tall and nowhere near the label floating
   above it. An ancestor's background now counts only if its own box contains
   the text's box. The screenshot shows `0.10` in dark grey on white.
4. **Two pages reported as having no headings at all.** An over-broad "clipped
   ancestor" rule, borrowed from slot 3, called an element hidden when any
   ancestor was 0px tall with `overflow: hidden` — and `<html>` is 1400×0 on
   every page of this app.
5. **Two of the eleven pages were the dashboard.** The page list said `config`
   and `sector_rotation`; the routes are `configuration` and `rrg`. Streamlit
   served the dashboard for both, so the check measured one page three times
   and two pages never. Both tables above use the gate's own page list now.

That is five in one slot, after three in the previous four, and the pattern is
no longer a coincidence: a measurement of a rendered page is a model of what a
reader sees, and every one of these was the model being wrong in a way that
produced a confident number. Hence the last addition:

**The check can now prove it is looking.** `--self-test` plants one
`#c9c9c9`-on-white paragraph in each page's main block and requires the
contrast check to catch it. It is caught on 11/11 at 1.66:1. (That plant needed
`!important` to stick: the site's own `p { color: … !important }` wins over an
inline style, so the first plant came out perfectly legible and was "not
caught" for the right reason.) A contrast check that reports nothing is now
distinguishable from one that matched nothing, which is exactly the failure
mode slot 4 warned about.

**What this slot does not cover**, and will not before launch: a real screen
reader (NVDA, VoiceOver — Chromium's accessibility tree is not the same thing
as what a reader hears), colour-blind simulation, and the WCAG 1.4.12 text
spacing override. Contrast is measured against the 4.5:1 and 3:1 thresholds
only; nothing here says the palette is comfortable, only that it is compliant.


### Slot 7 — performance and weight (05:35 UTC, done). The baseline, and one more wrong number

`scripts/launch_perf.py` with `scripts/_launch_perf.js`. Nothing here passes or
fails: a baseline that can fail is a baseline nobody records. Owner, 9 Nov
2026: *"I want my code to be 10% faster, 20% less resources usage and 20% less
space."* These are the numbers those targets are measured against.

#### Start and memory

| | |
|---|---|
| Server answers HTTP | 1.1 s after launch |
| Cold start to the dashboard's content, from process start | **14.6 s** |
| Server RSS after the first page | **316 MB** |
| Test suite | **163 s**, 2,609 tests |
| Everything git tracks | **25,650 KB** |

#### Per page, at 1400px

Two numbers each, because a reader pays each once: **cold** is a first visit
with an empty cache, **warm** is a click from the nav after the other pages.

| Page | cold | cold over the wire | warm | warm over the wire | DOM nodes | frames | frame HTML | JS heap |
|---|---|---|---|---|---|---|---|---|
| Dashboard | 4.4 s | 3,446 KB | 4.7 s | (first in the walk) | 661 | 0 | — | 22.6 MB |
| Portfolio | 5.1 s | 4,590 KB | 4.6 s | **1,145 KB** | 715 | 7 | 382 KB | 32.3 MB |
| Actions | 4.7 s | 3,472 KB | 4.2 s | 10 KB | 872 | 1 | 74 KB | 20.0 MB |
| Watchlist | 4.3 s | 3,451 KB | 3.9 s | 21 KB | 281 | 0 | — | 22.6 MB |
| Screener | 4.7 s | 3,759 KB | 4.1 s | 198 KB | 871 | 1 | **2,327 KB** | 28.7 MB |
| Sectors | 4.5 s | 3,574 KB | 3.9 s | 2 KB | **1,467** | 2 | 84 KB | 28.7 MB |
| Sector rotation | 4.5 s | 3,435 KB | 3.9 s | 3 KB | 576 | 1 | 67 KB | 25.4 MB |
| Breadth | **5.2 s** | 3,430 KB | 4.4 s | 2 KB | 613 | 6 | 622 KB | 25.4 MB |
| Backtest | 4.5 s | 3,823 KB | 4.0 s | 116 KB | 1,032 | 2 | 47 KB | 23.9 MB |
| Configuration | 4.3 s | 3,756 KB | 4.0 s | 35 KB | 737 | 2 | 19 KB | 28.7 MB |
| Guide | 4.2 s | 3,431 KB | 3.9 s | 2 KB | 324 | 0 | — | 21.2 MB |

**A reader downloads about 3.4 MB once and then almost nothing.** The 3.4 MB
is Streamlit's own bundle, not ours: `protobuf` 816 KB, `index` 444 KB,
`styled-components` 789 KB, `lib` 253 KB, `StreamlitMarkdown` 225 KB,
`rehype-raw` 184 KB, `react-dom` 130 KB, plus the Material Symbols icon font
at 365 KB. It carries `cache-control: public, immutable, max-age=31536000`, so
it is fetched once per release and then never again.

What is *ours* and still costs on a warm visit:

- **Portfolio, 1,145 KB** — the only page that loads both chart libraries:
  `highstock.js` 373 KB and `lightweight-charts.standalone` 193 KB. Both are
  genuinely used there (the heatmap needs Highcharts, the panes need the
  other), so this is the price of that page, not a mistake.
- **Screener, 198 KB** — the 750-row table, which is also the biggest single
  framed document on the site at 2,327 KB of HTML.
- **Fonts, once per chart frame.** `ibm-plex-sans-400-latin.woff2` (45.7 KB)
  was requested 11 times on Portfolio's first visit and 4 times on the
  dashboard's. Each chart frame is its own document and links the whole
  `static/fonts.css` — eighteen faces, including Source Serif at 122 KB — and
  on a cold load the frames all ask before any answer lands, so the cache
  cannot help. Unlike Streamlit's bundle, our `/app/static/` files come back
  with **no `cache-control` at all** (ETag and Last-Modified only), so a
  browser caches them heuristically rather than by instruction. It worked in
  every measurement here; it is not guaranteed to.

#### Where the 25,650 KB git tracks actually is

| | |
|---|---|
| `nse_index_rebuild/` | **12,101 KB (47%)** |
| `data/nse_prices/` | 2,338 KB |
| `data/reference/` | 2,033 KB |
| `tests/` | 1,278 KB |
| `static/` | 1,081 KB (the two chart libraries and the fonts) |
| `reports/` | 737 KB |
| `src/ui/` | 714 KB |

Nearly half of the repository is one directory, and it is the membership
evidence trail — which is why it is an owner decision, not a cleanup.

#### And the sixth harness fault

The first version of this check reported that **nothing was cached**: a second
visit to the dashboard in the same browser "downloaded" 3,473 KB with zero 304
responses. That would have been the single most important fact about the site,
and it was false. A response served out of the browser's cache still fires a
`response` event and still hands over a body, so counting those bytes counts a
cache hit as a download. Bytes now come from the Resource Timing API, where
`transferSize === 0` with a non-zero decoded body is a cache hit — and the
warm column above, 2 KB where it had said 3,473, is what that correction is
worth.

#### Nothing was changed

Every figure above is a measurement, and the one avoidable cost (the fonts per
frame) needs a change to what every chart document links — exactly the kind of
change the standing rule puts after launch, not the night before. The
candidates, with their numbers, are in `docs/TODO.md` S114.


### Slot 8 — security and privacy (06:05 UTC, done). Nothing found, and the check says what it looked for

`scripts/launch_security.py`, with `scripts/_launch_html.js` for the served
markup and `scripts/_launch_inject.js` for the parameters.

| Check | Result |
|---|---|
| A secret committed to the repository | **0** hits over 2,033 tracked files |
| A secret in the HTML the site serves | **0** hits over 11 pages and 10,373 KB of markup, chart frames included |
| A hostile `?stock=` | 16 payloads, 0 threw, 0 injected an element, 0 dialogs |
| A hostile `?sys=`, `?wl=`, `?owner=` | 16 payloads each, same result |
| The owner-only controls | hidden in all 64 loads |

Two things make the page check worth more than a pattern match. It reads the
**served markup**, not the visible text, so a credential leaked into an
attribute, a comment or a frame's `srcdoc` would be caught. And it looks for
**the actual values this process holds**: four of ten named credentials are
set in this container, and the check searches every page for their exact
strings rather than for something that looks like a secret. None appears.

The payloads are the usual ones — `<img src=x onerror=…>`, `<script>`,
`"><svg onload=…>`, `javascript:`, `../../../../etc/passwd` and its
URL-encoded twin, `' OR '1'='1`, `'; DROP TABLE prices; --`, `{{7*7}}`,
`${jndi:ldap://…}`, a 144-character symbol, a null byte, and a CRLF
`Set-Cookie:` — against `/screener?stock=`, `/screener?sys=`,
`/watchlist?wl=` and `/configuration?owner=`.

**What the filter actually does, shown rather than asserted.** `?stock=` is
stripped to `[^A-Z0-9&._-]` (`src/ui/views/ranking_view.py:246`), so
`"><svg onload=alert('PWNED')>` arrives as the text
`SVGONLOADALERTPWNED is not in the current ranking.` inside an ordinary `<p>`,
and the address bar is rewritten to `?stock=SVGONLOADALERTPWNED`. `?sys=` is
compared against a fixed list of systems, `?wl=` goes through the same
character filter with a 20-character and 200-symbol cap, and `?owner=` is
compared with the key.

**The seventh harness fault**, and the cheapest yet: the first version
reported **two injected elements for the payload `RELIANCE`**. Its selector
included `iframe[srcdoc]`, which is Streamlit's own chart frame on a perfectly
ordinary page. A check that reports an injection for a stock symbol reports
nothing.

**What the logs print.** The server's own log over those 64 hostile loads:
28 lines, 2 KB, with **no** access key, private key, bearer token, e-mail
address, GitHub token, R2 endpoint — and no query string at all, so a payload
never reaches the log either. None of the four live credential values appears.
The only thing of note is two absolute server paths
(`/home/user/Paresh/data/track_record_shadow.json`), which name the container's
filesystem rather than anything secret, and which a reader never sees.

**Not covered**: a penetration test, Streamlit Cloud's own TLS and headers,
and whether the five R2 secrets in the repository's settings are the right
ones — `GET actions/secrets` answers 403 through this session's proxy, so a
green R2 job is a lead and not proof.

### Slot 9 — the jobs (06:35 UTC, done). The slot's own claim is false

This slot was written to prove "a silent job failure is impossible". It
disproves it. 47 workflow files, **26 scheduled**.

| | |
|---|---|
| Scheduled workflows | 26 |
| Never run on their cron | 1 (`momentum_health.yml`, added 8 Nov, cron `23 6 2-6 * *`, first fire 2 Dec) |
| Whose last *scheduled* run was not green | 3 |
| Open `scheduled-failure` issues | 12, of which **1 is live** |

**1. The daily sync is green while a step fails, and has been for six runs.**
`daily_sync.yml` holds ten `|| echo "::warning::…"` fallbacks, and the alert
fires only on `failure`, `timed_out` or `cancelled`. Line 370, verbatim:

```yaml
run: python scripts/check_corporate_actions.py --fail-on-new || echo "::warning::Corporate-actions check exited non-zero (new find or failure) -- read the step log."
```

The six most recent runs — 2026-11-10 02:28, 2026-11-10 00:45, 2026-11-09
08:54, 2026-11-09 01:19, 2026-11-08 23:10, 2026-11-08 08:23 — all concluded
`success`. The warning is by design and non-blocking; the point is that
nobody reads the log of a green run, so a new corporate action or a broken
check has been sitting in six consecutive green runs unseen.

**2. The alert board is noise, because the alert has no recovery path.**
`scheduled_failure_alert.yml`'s header says "a later green run of the same
workflow says so on that issue". Both of its steps are behind
`if: steps.gate.outputs.alert == 'yes'`, which is reachable only on a failure,
so no green run ever posts and no issue ever closes. Nine of the ten open
issues naming a scheduled workflow name one whose last scheduled run
succeeded (#502, #496, #473, #465, #464, #463, #424, #382, #257). Only #216
is live. A board where nine of ten entries are stale is a board nobody reads.

**3. A cron that stops firing is invisible.** The alert triggers on
`workflow_run: types: [completed]`. A workflow that never starts produces no
`workflow_run`, so there is nothing to react to. `momentum_health.yml` has
never fired and nothing says so.

**The three not-green crons — and here the alert worked.**

| Workflow | Last scheduled run | What happened | Alert |
|---|---|---|---|
| `nse_compare.yml` | 2026-11-08 13:49→14:34 | **45m14s against `timeout-minutes: 45`**, `cancelled` | caught it, opened #496 (audit row A3 is demonstrably closed) |
| `nse_long_prices.yml` | 2026-11-07 10:33 | `failure` in step `Build` | #473 opened at 10:45; a dispatch at 21:46 papered over it, the issue never closed |
| `v1-production-qa.yml` | 2026-11-09 22:25:35 | `failure` in step `Portfolio visual QA` | commented on #216 at 22:29 — **four minutes end to end** |

`nse_compare` has been cancelled/success/cancelled/success/cancelled over its
last five scheduled runs: it times out every other week, and has been red
since 8 Nov with nobody acting.

**The two that matter tomorrow.** `daily_sync` has `workflow_dispatch`,
`concurrency: daily-sync` with `cancel-in-progress: false`, `timeout-minutes:
45`, and hard failures on `sync_data.py`, the R2 publish (`set -euo
pipefail`), a push that fails five attempts, and `Fail when a ranking was not
precomputed`. **It is loud if the ranking or the push breaks and silent if a
feed breaks.** `monthly_track_record` does not run tomorrow — cron
`0 19 1-5 * *`, next fire 1 Dec 19:00 UTC — and is the better built of the
two: `Check the app can rank with the new NSE closes` and `Freeze newly closed
months` have no `|| echo`, so a refusal stops the job and nothing is frozen or
committed. October is already recorded (`data/track_record.json`, `"2026-10"`,
`"origin": "recorded"`, `"finalized_on": "2026-11-03"`).

**Two more for the record.** The alert workflow is **not in its own watch
list**, and its `concurrency: scheduled-failure-alert` with
`cancel-in-progress: false` has discarded 21 runs (109 success, 0 failure,
21 cancelled of 2,954); three inspected report `jobs: 0`, cancelled 2–7
seconds after creation, their `if:` never evaluated. In both bursts traced,
a surviving sibling still reported the failure, so this is a latent hole —
not proved to have lost an alert, and not proved safe. And **GitHub's cron
queue is hours late**: the 2026-11-09 `30 17` daily-sync slot was created
2026-11-10 00:45:55, **7h15m late**; a 2026-11-06 `0 2` slot fired at 08:48,
6h48m late. If launch needs fresh prices at a known hour tomorrow, dispatch
the sync by hand rather than trusting the cron.

**O-L5, measured and narrowed.** Every `uses:` across all 47 files is a
GitHub-owned action on a mutable major tag, never a SHA: `checkout@v7` ×46,
`setup-python@v7` ×46, `upload-artifact@v7` ×13, `cache/save@v6` ×3,
`cache/restore@v6` ×3, plus `upload-artifact@v4` ×2, `setup-python@v5` and
`checkout@v4`. **No third-party action anywhere, and no `@master` or
`@main`.** The two files still on v4/v5 are not scheduled.
