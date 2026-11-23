# S203: sentence templates for the Dashboard and Portfolio (draft for the owner)

Drafted 23 Nov 2026 on main `d39554b`, read-only. Nothing is built. Sources: TODO S203, GLOSSARY.md,
PAGE_DESIGN.md §2a, §3a and §8, `src/ui/missing_words.py`, and the S193 item B audit.

**How to read the tables.** `now` is the code's pattern today, with its slots in `{}`. `proposed` is the
template; **KEEP** means the current text stays, **DROP** means the sentence goes, and the reason is given.
Slot formats (see "Proposed rules"): `:r1` an unsigned return to one decimal with %, half up (5.5%);
`:p1` an unsigned gap in points to one decimal (3.2); `:s0` a whole share (44%); `:n` a whole count;
`:cr` money in the Cr and lakh forms (₹38,000 Cr, ₹1.22 lakh Cr); `:day` "20 Nov"; `:date` "20 Nov 2026";
`:mon` a month name in full (November); `:my` "Nov 2026". A slot in **bold** is the coloured verdict phrase.
Cases: up, down, level (rounds to 0.0), tie, missing (None), young system (its record is too short), and
the three systems (750, 1000, > ₹2,000 Cr list; `{uni}` from `UNIVERSE_SHORT`).

**Not counted here.** Single-word or two-word labels that are not sentences: the rank-trail words in
`dashboard_insights.rank_trail_word` ("Sliding fast", "Back in"...), sector states ("ahead on both",
"gaining"), tile labels, and the column headers. They are a vocabulary, not templates. One fault among
them: "Out of the filters" (`dashboard_insights.py:466`) should read "Out", which is `mw.OUT` (S193 E R1).

---

## 1. Dashboard (`src/ui/views/dashboard_home_view.py`, `src/engine/dashboard_insights.py`)

### 1a. Today in brief (`_brief`)

| id | where | now | proposed | cases |
|---|---|---|---|---|
| dash.brief.1 | :1324-1329 | (a) "So far in {mon} the book is keeping pace with momentum, and momentum is losing to Nifty Total Market." (b) "The book is ahead of Nifty Total Market so far in {mon}." (c) "The book is behind Nifty Total Market and behind momentum so far in {mon}." | (a) "So far in {mon}, the book is behind Nifty Total Market but level with the best momentum index." (b) "So far in {mon}, the book is ahead of Nifty Total Market." (b') when the rounded gap is 0.0: "So far in {mon}, the book is level with Nifty Total Market." (c) "So far in {mon}, the book is behind Nifty Total Market and {momentum_place}." with `{momentum_place}` from dash.book.4: "within the range of NSE's momentum indices" / "behind all of NSE's momentum indices". **REWRITE**: (c) said "behind momentum" when the book was inside the indices' range; (a) said "keeping pace" when the book was ahead of the best index | up; down; level; book above the best index (a reads "ahead of every momentum index"); missing: no sentence; all 3 systems (the 1000's first month: "Since the {fill:day} fill," in place of "So far in {mon},") |
| dash.brief.2 | :1331 | "{n} holding(s) go on {check}." | "{n_sells} holding(s) would be sold at the {check:day} check." **REWRITE**: "go on 30 Nov" read as a trade on the 30th; they fill the next session (S193 B, §5). "would" because it holds only if prices hold | 0: no sentence; 1: "1 holding would be..." |
| dash.brief.3 | :1337-1342 | "Of the {n} signals that pass our own test, on today's readings {good} point(s) to a stronger month for momentum[, record foreign buying among them,] and {bad} to a weaker one[; at the last month-end, which the tests read, {a} and {b}]." | Two sentences. "{n_pass} of our tested signals pass. On today's readings, **{good:n} point to a stronger month for momentum** and **{bad:n} to a weaker one**." Optional third: "Record foreign buying is one of them." (only when the FPI signal is among `good` and `flows.month_rank == 1`; "Heavy foreign buying is one of them." otherwise). The month-end clause moves to dash.mom.3 only. **REWRITE**: 50 words with three ideas; the month-end clause needed the reader to know which test reads what | good = 0 ("none point to a stronger month"); bad = 0; n = 1 (singular); missing tests: no sentence |
| dash.brief.4 | :1346 | "The rally is narrow: only {b1:s0} of the {uni} beat Nifty Total Market over the past month." | **KEEP** (true, one idea; shown under 40% only). See Question 2 on repeating it in section 5 | above 40%: no sentence; missing: no sentence |

### 1b. Section 1, the book this month (`section_book`, `_against_momentum`, `index_late_note`)

| id | where | now | proposed | cases |
|---|---|---|---|---|
| dash.book.1 | :307-312 | h1: (a) "{Month}'s lag is **momentum's**, not **this book's**." (b) "The book is **{gap:p1} points ahead** of Nifty Total Market so far in {mon}." (c) "The book is **{gap:p1} points behind** Nifty Total Market so far in {mon}." | (a) "The book trails Nifty Total Market in {mon} because **momentum does**, not **its stock picks**." (b) **KEEP**. (b') level: "The book is **level with** Nifty Total Market so far in {mon}." in ink. (c) **KEEP**. (d) missing gap: "The book so far in {mon}." is not a sentence; use "Nifty Total Market has no close for {mon} yet." **REWRITE** (a) and add (b'), (d): (a) is a riddle until the lede is read; with the gap missing the code today raises an error (`abs(None)`, :312) | up; down; level; missing (crash today); 1000 first month: "since the {fill:day} fill" for "so far in {mon}" |
| dash.book.2 | :319-320 | "[Since the {fill} fill, ]Nifty Total Market is up {mkt:r1}." | "Nifty Total Market is {up/down} {mkt_mtd:r1} so far in {mon}." / "...since the {fill:day} fill." **KEEP** the content. "up/down" comes from the sign; rounding moves to the half-up helper (now `:.1f`, glossary 12) | up; down; level ("unchanged"); missing: sentence dropped |
| dash.book.3 | :316, :320 | "{All five} NSE momentum indices are up {lo} to {hi}%;" | All up: "NSE's {n_mom} momentum indices are up {lo:r1} to {hi:r1}." All down: "...are down {hi:r1} to {lo:r1}." Mixed: "NSE's {n_mom} momentum indices range from {lo:signed} to {hi:signed}." **REWRITE**: a fall read "up −1.2 to 3.4%"; "All 1" when one index has a close | all up; all down; mixed; one index ("Of NSE's momentum indices, only {name} has a close: {v:signed}."); missing: dropped |
| dash.book.4 | :281-294, :320 | "the book, {up/down} {x}, is level with the best of them. / is ahead of them. / is behind all of them. / is within their range." | New sentence: "The book is {up/down} {book_mtd:r1}, {place}." with `{place}` = "ahead of all of them" / "level with the best of them" / "within their range" / "behind all of them". **REWRITE** (split from dash.book.3; "ahead of them" said "all") | the four branches; book missing: dropped |
| dash.book.5 | :322-323 | "What lagged is the style, not the stock picking." | **DROP**: it says the h1 again (dash.book.1 a) | - |
| dash.book.6 | :327-339 | Tile subs: "{gap:p1} pts behind / ahead of Nifty Total Market", "Ahead of {k}, level with {m}", "They rose {lo} to {hi}%", "{p:sgn} pts on Nifty Total Market", "Behind in {months}" / "Ahead every month", "The month in progress counts as it stands" | **KEEP** all but "They rose {lo} to {hi}%": use dash.book.3's three forms in tile form ("Up 4.3 to 5.7%", "Down 0.8 to 2.1%", "From −1.2 to +3.4%"). Level gap: "Level with Nifty Total Market" | as dash.book.3; 0 indices: blank sub |
| dash.book.7 | :382-388 | "Nifty Total Market to {idx_end:day}: NSE's closes for {as_of:day} are not in yet, so the index figures end a session early; the book's are to {as_of:day}." | **KEEP**, and make it the one template both pages use (Portfolio's dash is pf.ret.3). It builds on `mw.not_in_yet` | late; on time: no sentence |
| dash.book.8 | :370 | "Each line is {step}%; filled lines right of the dark zero line are a gain, left a fall." | **KEEP** | step 0.25, 0.5, 1, 2 |
| dash.book.9 | :376-379 | "{frozen} stay(s) as recorded against the Nifty 500; the Nifty Total Market comparison is worked out beside them." | **KEEP** (printed only for frozen months, S193 B) | no frozen month (1000): no sentence; one month: "stays" |
| dash.book.10 | :359-366 | "– in {column}: the system is too young (its record starts {my})." / "...: not published yet." | **KEEP** (from `missing_words`) | per column |

### 1c. Section 2, the next rebalance (`section_rebalance`, churn and results in `render_home_view`)

| id | where | now | proposed | cases |
|---|---|---|---|---|
| dash.next.1 | :458-461 | h2: "**{s} sells**, **{b} buys**, **{w} on the edge**, {n} sessions away." | "**{s:n} sells** and **{b:n} buys** at the {check:day} check, {n_sess:n} sessions away." Then, if any: "{w:n} more holdings are on the edge." in ink. **REWRITE**: a list, not a sentence (§8); three or four coloured phrases against "at most two" (S219 2) | 0 sells ("No sells and 2 buys..."); 0 buys; 0 both: "No change at the {check:day} check, {n} sessions away."; 1 session: "1 session away" |
| dash.next.2 | :462-464 | "**{sym} fell from #{a} to #{b} in a month**, {k} places from the cut-off." | **KEEP**, with k = 0: "...in a month, and sits at the cut-off." and k = 1: "1 place" | k ≥ 2; 1; 0 |
| dash.next.3 | :466-472 | "; **both / all {n} {sector} holdings go** as their sector slides." | Its own sentence: "Both / All {n:n} {sector} holdings go; the sector is behind all ranked stocks over 6M and 1M." **REWRITE**: "slides" had no measure; the measure is the strong/weak rule | 2 ("Both"), 3+ ("All 3"); not all sold: no sentence |
| dash.next.4 | :500-505 | "Checked at the {check:%a %-d %b} close, filled {fill:%a %-d %b}. The other {k} holdings have more room than {sym}." + the rank explanation | **KEEP** | k = 0: second sentence dropped |
| dash.next.5 | :1010-1016 | "[A light month. ]{b} of {n} would change; {avg} in an average month." / "{b} of {n} would change; {last} at the last rebalance." / "{b} of {n} would change." | "{b:n} of {n:n} holdings would change, against {avg:n} in an average month since {first_reb:mon}." (3+ rebalances); "...against {last:n} at the {last_reb:mon} rebalance." (1-2); "{b:n} of {n:n} holdings would change." (none). "A light month." only under 75% of the average (Question 5). **REWRITE**: say which months the average covers, as Portfolio's tile does ("on average, from February") | 3+, 1-2, 0 rebalances; b = 0: "No holding would change." |
| dash.next.6 | :1021-1022 | "No results are due from the holdings or the buys before the check." / "Results due before the check: {syms}." | "No holding or buy has results announced before the {check:day} check." / "Results are due before the {check:day} check from {syms}." **REWRITE** light: "announced" says what the calendar can know | none; some; calendar missing: no sentence |
| dash.next.7 | :416 | "Leadership turnover · {new} of today's top {top} were not there a month ago" | **KEEP** (a caption) | new = 0: "all of today's top {top} were there a month ago" |
| dash.next.8 | :408-415 | "{A} and {B} are climbing in, {k} each of the {n}; {j} of the {m} falling out are {C} names." | Two sentences. "{k:n} of the {n:n} stocks climbing in are {sector}." (tie: "{A} and {B} lead those climbing in, {k:n} each of the {n:n}.") "{j:n} of the {m:n} falling out are {sector}." **REWRITE** (one idea each; "names" dropped) | tie (S193 B); k < 2: no sentence; no fallers: second dropped |

### 1d. Section 3, is momentum still working (`section_momentum`, `_lag_note`, `_long_record_line`, `system_momentum.record_note`)

| id | where | now | proposed | cases |
|---|---|---|---|---|
| dash.mom.1 | :584-589 | h2: "Ahead over a year[, but **{n} losing months in a row**]." / "Behind over a year." / "No year of this system's own record yet[; it has ...]." / "...and {mon} so far" | "Momentum is ahead over 12 months[, but **has trailed {run}**]." / "Momentum is behind over 12 months[, and **has trailed {run}**]." / "This system's record is under 12 months old[; momentum **has trailed {run}**]." with `{run}` = "for {k:n} months in a row" or, with the month in progress, "in {last_mon} and so far in {mon}" (k = 2), "for {k−1:n} months and so far in {mon}" (k ≥ 3). **REWRITE**: no subject ("Ahead over a year" said what, of what?); glossary 6 says "12 months" in sentences. See Question 1 | ahead; behind; young (the 1000, the list); streak 0-1: no run; month in progress included or not |
| dash.mom.2 | :591-594 | "We tested each signal on the Nifty 500's record since 2010: {p} pass, {q} are not confirmed[, one of them a reading the page used to count for momentum]." | Moves out of the h2 into a lede: "We tested each signal on the Nifty 500's record since 2010: {p:n} pass and {q:n} are not confirmed." **DROP** the bracketed clause: it is about the page's past, which no data on the page shows (S193 B g1 row 12, not checked) | q = 0 ("all {p} pass"); q = 1 ("1 is not confirmed"); none tested: no sentence |
| dash.mom.3 | :595-597, :513-526 | "On today's readings **{g} point(s) to a stronger month**, **{b} to a weaker one**[; at the last month-end, which the tests read, {a} and {c}]." | "On today's readings, **{g:n} point to a stronger month** and **{b:n} to a weaker one**." Then, when they differ: "At the {me:day} month-end, which the tests read, it was {a:n} and {c:n}." **REWRITE** (split; the month-end named by its date) | g or b = 0 ("none"); counts equal at the month-end: second dropped; a signal with no month-end reading: second dropped |
| dash.mom.4 | :634-637 | "Tiles: each month-end, the top fifth of the {uni} by this site's score, its members of that day, against all of them, equal weight (this system's own record, from {mon year}): over 12 months, the last 3 months and the last finished month; the month so far ranks at the last month-end." | "Each tile is the top fifth of the {uni} by this site's score, less all its members, equal weight, in points. Members are those of each month-end. This system's record starts in {first:mon} {year}. The month so far uses the ranks of the last month-end." **REWRITE** (one 60-word sentence into four) | young: "This system's record has not begun." in place of the third |
| dash.mom.5 | :561-562 | "Against the {uni}, equal weight, the top fifth is {d:r1} below its {best:mon year} best (month-ends to {mon year})." | **KEEP**; at its best: "Against the {uni}, equal weight, the top fifth is at its best (month-ends to {mon year})." | at the best (0.0); below |
| dash.mom.6 | :563-571 | "Its deepest fall since {since} was {d}%, {peak} to {low}, not yet made back / made back by {rec}; the one before, {d2}% in {yr}–{yy}, took {m} months from its peak to recover." | "Its deepest fall since {since:mon year} was {d:r1}, from {peak:my} to {low:my}." + "It was made back by {rec:my}." / "It is not yet made back." + "The one before, {d2:r1} from {peak2:my} to {low2:my}, took {m:n} months to recover." **REWRITE**: the "{yr}–{yy}" span adds a year to a December peak (`prev.peak.year + (prev.peak.month == 12)`, :569), so a Dec 2023 peak reads "2024–"; name both months instead | no fall; recovered; not yet; no earlier fall |
| dash.mom.7 | :542-549 | "Over the longer record, the Nifty 500's members since 2010 by the same rule: the deepest fall, {d}% from {peak:mon year}, is not yet made back / was made back by {rec}; the {k} other fall(s) of 5% or more took {lo} to {hi} months to recover." | Its own two sentences: "On the Nifty 500's record since 2010, by the same rule, the deepest fall was {d:r1} from {peak:my}; it {is not yet made back / was made back by {rec:my}}." "The {k:n} other falls of 5% or more took {lo:n} to {hi:n} months to recover." **REWRITE** (split; the content is true, S193 B g1 row 15) | k = 1 ("The other fall ... took {m} months"); lo = hi |
| dash.mom.8 | `system_momentum.py:164-177` | "This system's own record begins with its first finished month. Its deepest fall and recovery are shown from {N} months." / "This system's own record is being collected from {mon year}: {n} month(s) so far. ..." | **KEEP** | n = 0; 1; under N |
| dash.mom.9 | :1471-1478 | Row cell: "Higher than {p}% of {days/month-ends} since {yr}" / "Lower than {100−p}% ..." | **KEEP** | p = 50 reads "Higher than 50%"; fine |
| dash.mom.10 | :612-620 | Row cell: "{on:sgn} on vs {off:sgn} off; both halves; on in {k} of {n} months" / "...; the halves disagree / under the 1-point bar" | **KEEP** (a table cell; "vs" is the table's short form) | pass; not confirmed (two reasons); not tested |
| dash.mom.11 | :1528-1529 | Row sub, no reading today: "· 3M and 1M ago are month-ends; today's share is not worked out yet, so Now reads –" | "– in Now: {mw.NOT_PUBLISHED} (today's share is worked out each night)." as the column's footnote, and the sub keeps only the rule. **REWRITE** to the R1 form (one footnote per column, fixed cause words) | today's share present: no footnote |
| dash.mom.12 | :1202 | "shaded: the usual range since {yr}, {q1:sgn} to {q3:sgn} pts (the middle half of all months)" | **KEEP** | - |

### 1e. Section 4, money flows (`section_flows`)

| id | where | now | proposed | cases |
|---|---|---|---|---|
| dash.flow.1 | :671-673 | h2: "Foreign investors have bought **{mtd:cr} so far in {mon}[, the most in any month since {yr}]**[, after selling {before:cr} over the 11 months before]." | Bought: "Foreign investors have bought **{mtd:cr} so far in {mon}**[, the most in a month since {yr}]." Sold: "Foreign investors have sold **{−mtd:cr} so far in {mon}**." Then its own sentence: "They sold {−before:cr} over the 11 months before." / "They bought {before:cr} over the 11 months before." **REWRITE**: a month of selling printed "have bought −₹5,000 Cr" (no branch); the record clause stays in the colour, the "before" sentence in ink | bought; sold; record; the 11 months bought or sold; flows missing: section not drawn (today) |
| dash.flow.2 | :674-675 | "**Domestic institutions are selling into it.**" | "**Domestic institutions are net sellers so far in {mon}.**" and "into it" only when foreign investors are buying. **REWRITE**: "into it" is wrong when both sell | DII sell + FPI buy ("...selling into the foreign buying"); both sell; DII buy: no sentence |
| dash.flow.3 | :677-679 | Tile subs: "Record: largest month since {yr}", "Rank {k} of {n} months", "Previous high {cr}, {my}" | **KEEP** | record; not |
| dash.flow.4 | :681 | "Highest 20-day total since {yr}" | "Highest 20-session total since {yr}" **REWRITE**: the signal row (:1497) already says "20-session"; one word per thing | - |
| dash.flow.5 | :685 | "{mon} so far has bought back {x}%" | "{mon} so far has bought back {x:s0} of that selling" **REWRITE** (of what was not said) | before ≥ 0 or mtd ≤ 0: blank (today) |
| dash.flow.6 | :687-689 | "Bought / Sold so far in {mon}", "The 11 months before: sold / bought {x}% of it" | **KEEP** | - |
| dash.flow.7 | :691-693 | "Net sellers on {k} of {n} sessions", "Taking the other side of foreign buying" | **KEEP** | - |
| dash.flow.8 | :698-701 | "**Better / No better months for momentum next.** After the quarter of months with the most foreign buying ({thr:cr} or more), momentum beat the Nifty 500 the next month by {h:p1} points on average, against {r:p1} after the rest; ahead {hh:s0} of the time against {hr:s0}." | Heading **KEEP**. Body: "After the quarter of months with the most foreign buying ({thr:cr} or more), momentum's lead over the Nifty 500 the next month averaged {h:signed} points, against {r:signed} after the rest." "Momentum was ahead after {hh:s0} of those months, against {hr:s0} of the rest." **REWRITE**: "beat ... by −0.3 points" had no branch; split | h, r negative; equal (heading "No better") |
| dash.flow.9 | :702 | "It held / did not hold in both halves ({p}: {h} vs {r}; ...)." | **KEEP** | - |
| dash.flow.10 | :703-704 | "Tested here · {months} months of flows, {heavy} heavy, in-sample; the latest has no next month to test yet" | "Tested here · {tested:n} months with a next month, {heavy:n} heavy, in-sample" **REWRITE**: 130 against the row's 129 (S193 B g1 row 24, not fixed) | - |
| dash.flow.11 | :705-706 | "**No forecast for the Nifty 500.** Flows move with the Nifty 500 in the same month (correlation {c0}) and say nothing about the next ({c1})." | **KEEP** while abs(c1) < 0.2; at 0.2 or more: "...and only loosely with the next ({c1})." **REWRITE** by adding the branch: "say nothing" is a claim the number must keep meeting | abs(c1) < 0.2; 0.2 or more |
| dash.flow.12 | :707-709 | "**Not a large-cap story / A large-cap tilt.** In those heavy-buying months the Nifty 50 trailed / beat the Nifty 500 by {x:p1} points on average." | **KEEP**; level (0.0): "**Not a large-cap story.** In those months the Nifty 50 and the Nifty 500 did about the same." | trailed; beat; level |
| dash.flow.13 | :713 | "dashed line: a heavy-buying month, ₹{thr} Cr or more" | **KEEP**, with `cr()` for the amount (now `₹{thr:,.0f} Cr`, which writes ₹14,372 Cr where rule 2 rounds to ₹14,000 Cr; see Question 6) | - |

### 1f. Section 5, size (`section_size`, `_shared_parts`, `_shared_html`)

| id | where | now | proposed | cases |
|---|---|---|---|---|
| dash.size.1 | :819-821 | "**Large Cap momentum is failing**: {lo:p1} to {hi:p1} points behind the Nifty 200 over every window[, even as the Nifty 100 is now the broadest of NSE's size lists]." | "**Large Cap momentum is failing**: the Nifty200 Momentum 30 is {lo:p1} to {hi:p1} points behind the Nifty 200 on 3M, 6M and 12M." **REWRITE**: name the index the claim is about; the Nifty 100 clause goes to dash.size.5 (one idea) | failing (all ≤ −3); not: no sentence; lo = hi ("{x} points behind ... on every window") |
| dash.size.2 | :757-758 | phrase ", even as the Nifty 100 is now the broadest of NSE's size lists" | **DROP** here; it is the same fact as dash.size.5 two blocks down | - |
| dash.size.3 | :822-823 | "**In Mid Cap and Small Cap it keeps level with its index**; that is {ms:s0} of this book." | "**In Mid Cap and Small Cap, momentum is within 2.5 points of its index** on every window." "They hold {ms:s0} of the book." **REWRITE**: "level" elsewhere means 0.0 (dash.book.1); here it meant 2.5 points either way (Question 4) | within; not: no sentence |
| dash.size.4 | :824 | Fallback h2: "Momentum within each size, against its own index." | Not a finding (§2). See Question 3; recommended: "{size} momentum is furthest from its index: {gap:p1} points {ahead/behind} over 12M." | when neither size.1 nor size.3 holds |
| dash.size.5 | :797-799 | "A month ago the {was_best} held up best; now **{hi} is the broadest** and **{lo} the narrowest**[, where {held:s0} of the book sits]." | "Now **{hi} is the broadest** and **{lo} the narrowest** of NSE's size lists." "A month ago the broadest was {was_best}." (only if different) "{held:s0} of the book is in {lo_size}." (20% or more) **REWRITE**: "held up best" and "broadest" were two words for one measure; three ideas in one sentence; "the {was_best}" with an article, "{hi}" without | tie at the top or bottom ("{A} and {B} are the broadest, at {x:s0}"); hi = lo: no sentence; missing a month ago: second dropped |
| dash.size.6 | :754-756 | "Now {hi} is the broadest and {lo} the narrowest[, where ...]." (in `_shared_html`'s left table) | **DROP**: built but never drawn (`section_size` discards `shared`); delete with the code | - |
| dash.size.7 | :769-771 | "[Only ]{b1:s0} of the {uni} beat Nifty Total Market over the past month." | **KEEP** (see Question 2) | under 40% ("Only"); missing: no sentence |
| dash.size.8 | :772-774 | "Over 12 months the equal-weighted {uni} beat it by {g:p1} points while **the median stock fell {m:r1}**: a few big winners lift the average, the field a momentum book picks from." | "Over 12 months the equal-weighted {uni} beat Nifty Total Market by {g:p1} points, but **the median stock fell {m:r1}**." "A few large winners lift the average." **REWRITE**; **DROP** "the field a momentum book picks from" (no measure behind it). "A few large winners" is true when the equal-weighted return is above the median, which the branch already requires | shown only when ew > market and median < 0; else no sentence |
| dash.size.9 | :845 | "; Nano Cap and Ultra Nano Cap are our own groups, with no NSE index" | **KEEP** | shown when the book holds them |

### 1g. Section 6, strong and weak, and At a glance

| id | where | now | proposed | cases |
|---|---|---|---|---|
| dash.sec.1 | :870-872 | h2: "**{s:s0} sits in sectors beating all ranked stocks.** **{w:s0} sits in {k} that lag.**" | "**{s:s0} of the book is in sectors ahead of all ranked stocks** over 6M and 1M; **{w:s0} is in {k:n} behind on both**." **REWRITE**: the window was not named; "sits" twice | k = 1 ("1 sector"); k = 0: "No sector the book holds is behind on both."; s = 0: "None of the book is in a sector ahead on both." |
| dash.sec.2 | :878, :881 | "Ahead of all ranked stocks over six months and one month." / "Behind all ranked stocks on both windows." | "Ahead of all ranked stocks over 6 months and 1 month." / "Behind all ranked stocks over 6 months and 1 month." **REWRITE** (figures, as glossary 6 writes 12 months) | - |
| dash.sec.3 | :879-880 | "Ahead on one window only: {A} over the month, {B} over six months." | "Ahead on one window only: {A} over 1 month, {B} over 6 months." **REWRITE** as dash.sec.2 | none turning: card not drawn |
| dash.gl.1 | :916-917 | "counted over the members of each date, leavers included." / "counted over today's members (this list's members of each date are not kept far enough back for this chart)." | **KEEP** | 750; 1000 and list |
| dash.gl.2 | glance rows (:1643) via `mw.book_too_short` | "– in Beta and volatility: the system is too young: the figure needs {need} sessions of the book, it has {have}." | "– in Beta and volatility: the system is too young (the figure needs {need:n} sessions; the book has {have:n})." **REWRITE** in `missing_words.book_too_short`: two colons in one sentence; the same fix serves pf.eq.13 | young; old enough: no note |
| dash.gl.3 | :1593-1599 | "Nifty 500 P/E, percentile since 2021: {p}th · 1M · 3M"; "Leading / Trailing style: {style}, {name}" | **KEEP** (labels) | - |
| dash.empty | :952 | `mw.NO_MODEL_BOOK` + `mw.NO_MODEL_BOOK_WHY` | **KEEP** | - |

---

## 2. Portfolio (`src/ui/views/portfolio_page.py`; `portfolio_view.py`)

`portfolio_view.py` draws nothing itself now (its `render` hands over to `portfolio_page`). Its
`basis_note`, `tile_labels` and `_month_labels` write "MTD" and "Return since Entry %", but nothing
calls them. **DROP** (pf.view.1): delete them rather than give them templates.

| id | where | now | proposed | cases |
|---|---|---|---|---|
| pf.head.1 | :383-387 | h1: "The book is **{up/down} {since:r1}** since {begun:%-d %B}, **{lead:p1} points ahead of / behind** Nifty Total Market." / "The model book" | "The book is **{up/down} {since:r1}** since {begun:date}, **{lead:p1} points ahead of / behind** Nifty Total Market." Level: "..., **level with** Nifty Total Market" in ink. Missing: "The model book's record starts on {begun:date}." **REWRITE**: the date without its year breaks glossary 7 ("Since 1 Jan 2026") once a record spans two years; "The model book" is not a sentence (§8) | up; down; level; market missing (first clause only); since missing; all 3 systems |
| pf.head.2 | :378-379 | "The model book: ₹1 Cr put in on {begun:%-d %B %Y}, run by the {system} rules, {n} stocks. Returns are after costs." | "₹1 Cr was put in on {begun:date}. The book follows the {system_name} rules and holds {n:n} stocks. Returns are after costs." **REWRITE** (date form; one idea a sentence) | - |
| pf.head.3 | :322-328 | " {span} {year} were worked out from the rules[ on {date}]; later months were recorded as they happened." | "The months {first:mon} to {last:mon} {year} were worked out from the rules[ on {on:date}]. Later months were recorded as they happened." (one month: "{first:mon} {year} was worked out...") **REWRITE**: "Jan to Oct 2026 were" | backfill; one month; none: no sentence |
| pf.head.4 | :329-332 | " November is reconstructed: its 30 Oct book uses a list NSE first published on 16 Nov." | "{first:mon} is reconstructed: its {base:day} book uses a list NSE first published on {published:day}." **REWRITE**: the three dates are typed into the code; read them from the membership file (`membership_history.json`), or the sentence goes false next month | the 1000 with no frozen month; else no sentence |
| pf.head.5 | :363-374 | Tile subs: "Started with {cap}", "{x} not invested", "Nifty Total Market {r}", "Nifty Total Market for {day} not in yet", "{gap} pts ahead of / behind Nifty Total Market", "Peak {day}", "Max drawdown {r}" | **KEEP**; level: "Level with Nifty Total Market" | late index |
| pf.book.1 | :456-457 | "{n} holdings · tap a column to sort · red: past a sell rule's line today (the rules are checked at month-end)" | **KEEP** | - |
| pf.book.2 | :450-455 | "Entry price and since entry are from the day the stock was first bought. P&L in rupees starts at the {fill} fill, where today's share counts were set: the record keeps returns and weights, so rupee figures are a mark, not a cost. Holdings {h} + {c} not invested = portfolio value {v}. Sell rules, checked at each month-end: below its 50D EMA (trend breakdown), more than {hc}% below its 52-week high, or out of the top {cut} by rank. Rank: ..." | Keep the five ideas, one sentence each: "P&L in rupees starts at the {fill:day} fill, where today's share counts were set." "The record keeps returns and weights, not costs, so rupee figures are a mark." Rest **KEEP**. "52-week high" stays in sentences, "52W" in figures; write "the 52-week high" in `EXIT_NAMES` (:44) too | - |
| pf.exp.1 | :510-523 | "The book {began the year / began {Mon} {yyyy}} {lm:s0} in Large Cap and Mid Cap and is now {small:s0} {groups}." | "At its first rebalance, {first:my}, the book held {lm:s0} in Large Cap and Mid Cap." "Now {small:s0} is in {groups}." **REWRITE**: "began the year" reads as a calendar claim; and when the book is now mostly Large Cap, the sentence still reports only the small groups; then: "Now {lm_now:s0} is in Large Cap and Mid Cap." | lm = 0 ("held none in Large Cap and Mid Cap"); the larger group now is large or small; one group ("Now 100% is in Nano Cap.") |
| pf.exp.2 | :524-525 | "Each rebalance's sector and size weights are worked out ... Size is by NSE's index lists on each date; sectors are the record's own." | **KEEP** | - |
| pf.ret.1 | :570-571 | "From the record's second year the table adds 12 months, 3 years, 5 years and a yearly rate since {begun} by itself; nothing is annualised before then." | "Once the record is a year old, the table adds 12 months, 3 years, 5 years and a yearly rate since {begun:date}." "Nothing is annualised before then." **REWRITE** ("by itself" reads as a second actor) | young; a year old (pf.ret.2) |
| pf.ret.2 | :572 | "A yearly rate since {begun} compounds the whole record to a return per 12 months." | **KEEP** | - |
| pf.ret.3 | :575-576 | "Nifty Total Market and Momentum 50 to {day}: NSE's closes for {day} are not in yet, so Today shows no Nifty Total Market figure and the longer windows end a session early on the index side." | dash.book.7's template, with "Nifty Total Market and Momentum 50" as `{names}`, then "Today shows no Nifty Total Market figure." **REWRITE**: one sentence for one cause on both pages (S193 E) | late; on time: none |
| pf.ret.4 | :586 | "The book is mostly {A} and {B}, so Nifty Total Market is not its only fair yardstick." | "Most of the book is in {A} and {B}, so Nifty Total Market is not its only fair yardstick." when A + B ≥ 50%; else "The book's largest size groups are {A} and {B}, so ...". **REWRITE**: "mostly" is checked nowhere; the code takes the two largest groups, whatever they add up to | ≥ 50%; under; one group; none (falls back to "Small Cap and Micro Cap" today, :598-604, a claim with no data: say nothing instead) |
| pf.ret.5 | :587-589 | "The mix holds the four NSE size indices in the book's own size split, reset at each rebalance (see Sector & size)." / "A mix of NSE's size indices cannot be built for it: Nano Cap and Ultra Nano Cap have no NSE index." | **KEEP** | mix; no mix |
| pf.eq.1 | :682 | "The growth chart starts once the book has two sessions; it has {n}." | **KEEP** | n = 0 or 1 |
| pf.eq.2 | :642-650 | Fall tiles: "Nifty Total Market is at a new high ({day})" / "Nifty Total Market {r}, below its {day} peak"; "{peak} → {low}, recovered {day}" / ", not yet recovered"; "Nifty Total Market {r} that day"; "Counting month-end values only" | **KEEP** | new high (rounds to 0.0); below |
| pf.eq.3 | :654 | "Swings about {x} times as much as the index" | **KEEP**; under 1: "Swings about {x} times as much as the index" still reads; at 1.0: "Swings about as much as the index" | - |
| pf.eq.4 | :656 | "On average, a 1% day for the index is a {beta}% book day" | **KEEP** (the tile shows beta to one decimal, the table to two; ratios are outside rule 1 by decision) | - |
| pf.eq.5 | :658 | "About {x} pt on a typical day" | "About {x:p1} points on a typical day" **REWRITE**: "pt" is not the glossary's word (4: "pts" in figures, "points" in sentences) | - |
| pf.eq.6 | :660-661 | "Falls less / more on bad days", "Rises less / more on good days" | **KEEP**; at 100%: "Falls as much on bad days" / "Rises as much on good days" (today 100 reads "more") | under, over, at 100 |
| pf.eq.7 | :663 | "Low: the list is well spread" (under 0.3) | **KEEP** | 0.3 or more: blank |
| pf.eq.8 | :698-699 | "Worked out from {n} sessions, so a rough guide until the book has a year." | **KEEP** | under 250 sessions |
| pf.eq.9 | :700-702 | "Tracking error {te}% means: over 12 months in which Nifty Total Market makes +10%, a book like this one would usually end between about {lo}% and {hi}% (10 ± {te}, two years in three), and outside that range one year in three. On a typical day the book and Nifty Total Market differ by about {d} point (tracking error ÷ √250)." | "A tracking error of {te:r1} means the book's 12-month return usually lands within about {te:p1} points of Nifty Total Market's, two years in three." "On a typical day the two differ by about {d:p1} points (tracking error ÷ √250)." **REWRITE** (shorter; "point" singular; see Question 7) | - |
| pf.eq.10 | :702-704 | "An index fund aims for well under 1%; a 20-stock small-company momentum book cannot be close to Nifty Total Market, and that distance is where its lead comes from." | **DROP**: "where its lead comes from" is a cause no figure on the page shows; "20-stock small-company" is typed and wrong for the list (Nano Cap and Ultra Nano Cap); the index-fund figure has no source on the page | - |
| pf.eq.11 | :705 | "No risk figures yet: the system is too young: the figure needs {need} sessions of the book, it has {have}." | "No risk figures yet: the system is too young (the figure needs {need:n} sessions; the book has {have:n})." **REWRITE** (dash.gl.2's fix) | - |
| pf.cal.1 | :749-750 | "* {first:my}, the first month: from the fill, {fill:day}. A system's first month has no book before it, so the book and every index start at its first fill." | **KEEP** | first month in the grid; else none |
| pf.cal.2 | :752-758 | "– in a month: before {my}, the system is too young; after {my}, not published yet." | "– in a month: before {first:my}, the system is too young." Months after this one: a blank cell, not "–". **REWRITE**: a month still to come is "not applicable" (R2), not "not published" (Question 8) | first month January (no clause) |
| pf.cal.3 | :747-748 | "{year+1} · from January, a row group like the one above; each year adds its own" | **KEEP** | one year only |
| pf.cal.4 | :315-316 | "Frozen months stay as recorded against the Nifty 500, the benchmark when they were frozen; Nifty Total Market is worked out beside them (the Nifty 500 row shows what each was frozen against)." | **KEEP** | no frozen month: none |
| pf.cal.5 | :1026, :1090 | "Momentum 50 is NSE's Nifty500 Momentum 50, a momentum index to judge the strategy by." | **KEEP** | - |
| pf.cal.6 | :771, :782 | Row labels "{y}, so far"; "{Mon}–{Mon} only, from the start" | **KEEP** | - |
| pf.day.1 | :808 | "Day by day starts once the book has six sessions; it has {n}." | **KEEP** | n < 6 |
| pf.day.2 | :813-818 | Tile subs: "Book {r}, Nifty Total Market {r}"; "Sessions the book beat Nifty Total Market[, {p}%]" | **KEEP** | - |
| pf.day.3 | :826-827 | "One day is mostly noise; a run of bars on one side is not. The book beat Nifty Total Market on {k} of {n} sessions." | "One day says little; a run of bars on one side says more." **DROP** the second sentence: it is the "Since {day}" tile's figure again (§2, no figure twice) | - |
| pf.tr.1 | :870, :876 | "no trades yet"; "No trade has closed yet; these figures start with the first exit." | **KEEP** | - |
| pf.tr.2 | :875, :899 | "{c} closed · {o} open · {r} rebalances" | **KEEP**, with the singular: "1 rebalance" (the 1000 reads "1 rebalances" today) | r = 1 |
| pf.tr.3 | :883-884 | "A few large winners carry it" (average win over twice the median) | **KEEP** | - |
| pf.tr.4 | :888-889 | Tile "Changed at a rebalance": "{avg} of 20"; "On average, from {Month}"; "{Month} {k}, {Month} {j}" | "{avg:n} of {n_hold:n}"; "On average since {first:mon}"; "Latest {last:mon} {k:n} · fewest {low:mon} {j:n}" **REWRITE**: "20" is typed in; "November 6, March 3" did not say what the two months are | 1 rebalance: "–" with the young-system note |
| pf.tr.5 | :909-911 | `HISTORY_NOTE` | **KEEP** | - |
| pf.sys.1 | :967-969 | "“Since {day}” is the window {the A, the B and the C} have all traded, so it is the fair comparison; it grows as the systems age. A new system joins it after its first full month." | "“Since {common:day}” is the window that {systems} have all traded, so it is the fair comparison." "It grows as the systems age." "A new system joins it once its first full month is frozen." **REWRITE**: one system in the window read "the window the 750 have all traded"; none read "all of them have all traded" (`_and([])`, :942); and the rule (S194 F5) is a frozen month, not a full one | 1 system ("...the window the 750 has traded since it began"); 2; 3; none: section not drawn |
| pf.sys.2 | :957-959 | "– in Since {day}: the system is too young ({the X}: a system joins after its first full month)." | "– in Since {common:day}: the system is too young ({names})." **REWRITE**: drop the repeat of pf.sys.1's last sentence | no young system: none |
| pf.sys.3 | :268-269 | "{my} · joins once {Month} is frozen" / "{my} · joins from {Mon}" | **KEEP** | - |
| pf.sys.4 | :971 | "Shadow systems, recorded but not traded: {name} (from {my}), ..." | **KEEP** | - |
| pf.err.1 | :1052-1053, :1067-1068 | "The model book could not be read just now." + "The record itself is unchanged. Reload the page in a few minutes; the book shows again once its nightly check passes." / "The track record could not be read just now." + "The model book is unchanged. Reload the page in a few minutes." | **KEEP** | - |
| pf.err.2 | :1072 | "The model book could not be sized." | "The model book's holdings could not be valued just now. Reload the page in a few minutes." **REWRITE** ("sized" is our word, not the reader's; same form as pf.err.1) | - |
| pf.err.3 | `canonical_book.py:85-87` | "This book was formed without {n} member(s) we hold no close for on {date}." + "{names}. Their prices are being collected; the month is frozen only once every member has a close." | "This book was formed without {n:n} members: we have no close for them on {date:date}." Second **KEEP**. **REWRITE** (the relative clause read as "members we hold") | n = 1 |
| pf.empty | :1057 | `mw.NO_MODEL_BOOK` + `mw.NO_MODEL_BOOK_WHY` | **KEEP** | - |

---

## 3. Counts

| | Rows found | Kept | Rewritten | Dropped whole | Clauses dropped inside a rewritten row |
|---|---|---|---|---|---|
| Dashboard | 63 | 25 | 35 | 3 (dash.book.5, dash.size.2, dash.size.6) | 2 (dash.mom.2, dash.size.8) |
| Portfolio | 48 | 27 | 19 | 2 (pf.view.1, pf.eq.10) | 2 (pf.day.3, pf.sys.2) |
| **Both** | **111** | **52** | **54** | **5** | **4** |

A row is one reader-facing sentence pattern, with its branches; a group of tile subs counts as one row.
A row is "rewritten" if any of its branches changes. A kept row may still gain a branch for a case it
lacks (for example dash.next.2 at 0 places).

**Faults the templates also fix (code, not wording):** the h1 raises an error when Nifty Total Market has
no month figure (dash.book.1 d); a fall prints "up −1.2 to 3.4%" (dash.book.3) and "have bought −₹5,000 Cr"
(dash.flow.1); the earlier-fall year is off by one for a December peak (dash.mom.6); "130 months" against
129 tested (dash.flow.10, from S193 B, still open); two colons from `book_too_short` (dash.gl.2, pf.eq.11);
`_and([])` (pf.sys.1); typed dates and the typed "20" (pf.head.4, pf.tr.4).

---

## 4. Proposed rules

1. **Tense.** Present for a state ("The book is up 5.5%"); present perfect for a running total ("have bought
   ₹21,000 Cr so far in November"); past for a finished month or a test ("passed", "was made back");
   "would" for the next rebalance, which holds only if prices hold.
2. **Signs.** A sentence carries the sign in a word (up, down, ahead, behind, bought, sold) and the figure
   unsigned. A tile, table or chart carries the sign on the figure (U+2212, an explicit +). A mixed range
   is the one exception in prose: "from −1.2% to +3.4%".
3. **Numbers** (§3a and the glossary): returns and gaps to one decimal, half up (glossary 12; the
   templates' `:.1f` move to the half-up helper); shares of stocks and of the book whole (44%); counts
   whole; money by `cr()`; a gap is "points" in a sentence and "pts" in a figure, never "%"; a date is
   "20 Nov" within the page's year and "20 Nov 2026" otherwise and after "since"; months in full in
   sentences.
4. **Verdict words, one set.** Ahead, behind, level with. "Level" only when the rounded gap reads 0.0, and
   then in ink, not coloured. Against a group of indices: ahead of all of them, level with the best, within
   their range, behind all of them. Another band (size's 2.5 points) is named as a band, never "level".
5. **Colour.** One headline holds at most two coloured phrases (S219 2), and each is the verdict phrase
   itself, never a count of things.
6. **A tie is named as a tie:** "Finance and Health Technology lead, 2 each", "A and B are the broadest".
7. **A missing value never sits inside a sentence.** The sentence is left out; the tile or cell reads "–"
   with its cause from `missing_words`. A headline has a written fallback for its missing case.
8. **One idea a sentence**, about 25 words at most; a headline has two clauses at most. Counts take their
   singular (1 rebalance, 1 session) and 0 reads "no" or "none".
9. **Nothing typed that the data holds.** System names from `UNIVERSE_SHORT`/`SYSTEM_NAMES`, holdings
   count, months and dates from the ledger or membership file.
10. **The check (S203's "done when").** Each template has its id. A test renders each one on all three
    systems with the cases above and fails on an empty slot, "None", "nan" or "–" inside a sentence, a sign
    word that disagrees with its figure, or a template text that differs from the approved file.

---

## 5. Questions for the owner

1. **A run of momentum's losing months (dash.mom.1): name the months or count them?** (a) "has trailed in
   October and so far in November"; (b) "has trailed for 2 months in a row, November so far". I recommend
   (a): it says which month is unfinished without a second clause.
2. **The brief repeats two section figures: the signal count (section 3) and the 1M beat share
   (section 5).** §2 says no figure twice. I recommend the brief keeps both, as the page's verdict, and that
   section 3's h2 drops the count, since its table shows it. Section 5 keeps the beat share with the table
   it reads. The alternative is a brief with no numbers ("most tested signals point to a stronger month"),
   which is vaguer.
3. **The size headline when neither of its findings holds (dash.size.4).** Today it is a label. I recommend
   naming the size whose momentum index is furthest from its own index over 12M, with that gap, which the
   table already shows. The alternative is to keep the label as an exception to §2.
4. **"Level" for size (dash.size.3).** Today, 2.5 points either way reads "keeps level". I recommend
   "within 2.5 points of its index", so that "level" means 0.0 everywhere (rule 4).
5. **"A light month." (dash.next.5).** The words appear when the buys are under 75% of the average. I
   recommend keeping them, now with the average and its months beside them. The alternative is to drop
   them and let the two numbers speak.
6. **The heavy-buying cut in sentences (dash.flow.8, dash.flow.13).** Today it reads ₹14,372 Cr, exact.
   Rule 2's `cr()` would make it ₹14,000 Cr. I recommend `cr()`. The cut is a quartile, not a precise
   level, and the exact figure stays in the chart's table.
7. **Tracking error (pf.eq.9).** Keep the +10% worked example ("would usually end between −8% and +28%"),
   or use the one-line definition proposed? I recommend the definition. The example assumes the book makes
   the index's return on average, which the page does not show.
8. **Months still to come in the calendar grid (pf.cal.2).** Today they read "–, not published yet". I
   recommend a blank cell (R2: not applicable). Nothing is unpublished about December on 23 Nov.

**Not checked:** wording was judged from the code at `d39554b`, not from a page rendered on all three
systems. The case lists come from the branches in the code. Before the templates are built, each case
needs a run on the system it names (for example the list's down month for dash.book.3, and a selling
month for dash.flow.1).
