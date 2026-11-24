# S203: sentence templates for the other pages (draft for the owner)

Drafted 24 Nov 2026 on the working tree of `/home/user/Paresh`, read-only. Nothing is built. Sources: TODO S203,
GLOSSARY.md, PAGE_DESIGN.md §2a, §3a and §8, `src/ui/missing_words.py`, and the approved Dashboard and Portfolio
draft, `docs/archive/S203_TEMPLATES_DASHBOARD_PORTFOLIO.md` (called "the archive" below).

**How to read the tables.** They work as the archive's do. `now` is the code's pattern today, with its slots in `{}`.
`proposed` is the template. **KEEP** means the current text stays. **DROP** means the sentence goes, and the reason is
given. The slot formats are the archive's: `:r1` an unsigned return to one decimal with %, half up; `:p1` an unsigned
gap in points; `:s0` a whole share; `:n` a whole count; `:cr` money; `:day` "20 Nov"; `:date` "20 Nov 2026"; `:mon` a
full month name; `:my` "Nov 2026"; `:ord` an ordinal (12th); `:px` whole rupees (`formats.price`); `:signed` a figure
with its sign, for a mixed range only. A slot in **bold** is the coloured verdict phrase. `{uni}` is
`UNIVERSE_SHORT[system]` ("750", "1000", "> ₹2,000 Cr list"); `{buy}`, `{keep}` and `{gap}` come from
`watchlist_lines.lines()` (the record's `top_n`, `buffer_n` and `1 − high_pct`). Cases are named as in the archive:
up, down, level, tie, missing, young system, and the three systems. **Late** is the S148 rule: a source a session
behind the page's session reads "–", with `formats.closes_not_in` or `mw.not_in_yet` saying so.

**The owner's answers apply here too** (archive §6, 24 Nov 2026):
- A run of months is named for two and counted from three (answer 1).
- "Level" means 0.0. A band is named as a band (answers 3 and 4).
- Rule-of-thumb verdict words stay when the figures sit beside them (answer 5).
- Money in sentences goes through `cr()` (answer 6).
- A definition beats a worked example that assumes what the page does not show (answer 7).
- A figure that does not apply is a blank cell, not "–, not published yet" (answer 8).

The archive's rules (§4) 1-10 hold as written, and dash.brief.2's "would be sold at the {check:day} check" is the
form for every next-rebalance sentence.

**Not counted here.** These are a vocabulary, not templates (archive "Not counted"): column heads, tile labels,
`STATUS_LABEL` ("Sold if unchanged", "Not ranked"), the Watchlist's group headings, the Market's band words ("Very
narrow" … "Very broad", "Strong downtrend" … "Strong uptrend"), Sectors' `GROUP_WORDS`, the Backtest's settings-form
labels and help texts, and button captions. Configuration and the header's regime pill are out of scope.

**Shared rows first.** Some sentences are drawn on several pages from one function, so they get one id (`cm.`). A
page row that uses one says "cm.x".

---

## 0. Shared by several pages (`cm.`)

| id | where | now | proposed | cases |
|---|---|---|---|---|
| cm.foot.1 | `actions_page.py:333-334`, `ranking_view.py:816-819`, `market_view.py:213-215`, `sector_view.py:699-700` | "{Data to 20 Nov 2026 · NSE}. {n} stocks ranked; {g} with a price gap, {s} with a short history." | **KEEP**, one function (`formats.foot_line(rank_df, as_of)`) instead of four f-strings; counts take their singular ("1 with a short history" already reads) and 0 reads "none with a price gap" as the Watchlist writes it (wl.foot.1) | date missing (`data_to` → "Data from NSE"); g = 0; s = 0 |
| cm.rule.1 | `exit_watch.py:106-107` | "{x}% below its 50D EMA" / "below its 50D EMA" | "{x:r1} below its 50D EMA" / "below its 50D EMA" (no reading). **KEEP** the words; the `:.1f` moves to half up (glossary 12) | reading; none |
| cm.rule.2 | `exit_watch.py:109-110`, `:67-68` | "more than {20%} below its 52-week high" / "too new to have a 52-week high: {k} of {126} sessions" | **KEEP** | reading; young stock; sessions unknown ("too new to have a 52-week high") |
| cm.rule.3 | `exit_watch.py:112` | "ranks #{q} of the qualified, past the top {keep}" | "is {q:ord} among the qualified, past the top {keep}" **REWRITE**: "#45" is a table form; the stock page puts it after "it is" (st.rule.1), and "it is ranks" read wrong | - |
| cm.rule.4 | `exit_watch.py:117` | "#{q} · {room} places from the buffer" | "is {q:ord} among the qualified, {room:n} places inside the top {keep}" (room = 1: "1 place"; room = 0: "at the {keep:ord}, the last place kept") **REWRITE**: it is a sentence on the stock page ("Close to a sell rule: it #38 · 2 places from the buffer", a verb missing, st.rule.1) and an Actions list item; "from the buffer" read as the distance to the buffer's start, but it is the room left inside it | room ≥ 2; 1; 0 |
| cm.rule.5 | `exit_watch.py:121, :123` | "can fall {x}% to its 50D EMA" / "can fall {x}% to the −20% line" | "can fall {x:r1} before it reaches its 50D EMA" / "...before it reaches the −{gap}% line from its 52-week high" **REWRITE** light: "the −20% line" alone does not say of what | one or both |
| cm.rule.6 | joins of cm.rule.1-5 (`exit_watch.py:113, :124`) | "{a}; {b}" | **KEEP** | 1, 2, 3 reasons |
| cm.late.1 | `formats.closes_not_in`, `mw.not_in_yet` | "NSE’s {day} close(s) for {names} is/are not in yet." | **KEEP** (already one template, S193 E). Every page that reads an index on the page's session ends with this sentence when one is late (Market mk.size.1, Indices ix.ev.2, Sectors se.broad.2, se.ix.2, the stock page st.ret.3) | 1 name; 2-4; 5 or more (the count) |

## 1. Actions (`src/ui/views/actions_page.py`; `actions_view.py`, `qualified_view.py`, `app.py`)

| id | where | now | proposed | cases |
|---|---|---|---|---|
| ac.head.1 | :150-157 | h1: "**{s} sell(s)** and **{b} buy(s)** at the {Mon 30 Nov} close, filled {Tue 1 Dec}: {₹x lakh} out, {₹y lakh} in." / "Nothing to trade on {Mon 30 Nov}: **every holding is clear of the rules**." | "**{s:n} sells** and **{b:n} buys** at the {check:day} check, filled on {fill:day}." Then in ink, when amounts exist: "{sell_amt:cr} out and {buy_amt:cr} in." Zero on one side: "**No sells** and **2 buys** at …" in ink for the zero. Nothing: "No trade at the {check:day} check: **every holding is clear of the sell rules**." **REWRITE**: the check is named "check" as on the Dashboard (dash.next.1) and Portfolio; two ideas (the trades, the money) become two sentences; amounts go through `cr()` (owner's answer 6, glossary 5), which keeps ₹34.1 lakh and ₹1.22 Cr; "at the close" and "on {Mon}" named the same day two ways | s, b ≥ 1; s = 0; b = 0; both 0; 1 ("1 sell"); amounts missing (My holdings: no share counts, so no "out") |
| ac.head.2 | :147-148, :159 | sub: "If today's prices hold. The model book: what the record would trade at the next rebalance." / "If today's prices hold. Your holdings, under the same rules." | "What the model book would trade at the next rebalance, if today's prices hold." / "Your holdings under the record's rules, if today's prices hold." **REWRITE**: "If today's prices hold." was a sentence without a verb | model book; My holdings |
| ac.head.3 | :137-146 | Tile subs: "break a rule at today's close" / "nothing breaks a rule"; "{₹} to sell"; "best qualified, not held"; "{₹} to buy"; "{n} close to a rule" / "all clear of the rules"; "{k} session(s) away · fills {Tue 1 Dec}"; "NSE holidays not yet published" | **KEEP**, with "break a sell rule at today's close" / "none breaks a sell rule", and `cr()` for the rupee subs (now `inr`, the whole-rupee form, against the head's lakh form) | 0; 1; holiday caveat |
| ac.chg.1 | :166-167 | List item: "**{SYM}** {why}" (cm.rule.4-6) / "No holding is within reach of a line." | "**{SYM}** {why}." (cm.rule.4-6, now sentences) / "No holding is close to a sell rule." **REWRITE**: "within reach of a line" was a second name for WATCH; the tile says "close to a rule" | some; none |
| ac.chg.2 | :170-174 | Captions: "Holdings close to a line · could still change to a sale"; "Next in line · would come in if a buy drops out or another holding breaks a rule"; "Results and corporate actions before the fill · to {day}" | **KEEP**, "close to a sell rule" for "close to a line" | - |
| ac.chg.3 | :180 | "**{SYM}** ({role}) {what}, {day}" | **KEEP** (list item; the Watchlist's wl.fill.3 is the same) | - |
| ac.chg.4 | :182 | `mw.no_events("any holding, sell or buy", fill)` | **KEEP** (R5) | - |
| ac.chg.5 | :466-477 | "Board meetings: NSE's calendar, announced to {day}; ex-dates: NSE's corporate actions, collected to {day}[; dates after that are not yet in the file]. Dates are as companies announced them and can move." / "ex-dates: not available" | "Board meetings are from NSE's calendar, announced to {cal_last:day}." "Ex-dates are from NSE's corporate actions, collected to {ca_last:day}[; later ones are not in yet]." "Dates are as companies announced them and can move." **REWRITE**: three ideas in one sentence with a colon each; "not available" gets its cause: "NSE's corporate-action file could not be read just now." | both; calendar missing (first sentence dropped); ex-dates file missing; ex-dates end before the fill |
| ac.after.1 | :214-217 | "Now: each stock at its weight today, … Size by NSE’s index lists today: Large Cap is the Nifty 100, … (our own groups, not NSE indices). {PTS_NOTE}" | **KEEP** | - |
| ac.sell.1 | :222 | Head sub "none at today's close" + note "Nothing breaks a rule." | **DROP** the note: it repeats the head's tile ("nothing breaks a rule", §2, no figure twice); the section says "Sell · none at today's close" | no sells |
| ac.sell.2 | :233-234 | "Sell in full. The basket carries these sells with the model book's share counts." / "Sell in full; your share counts are not known, so sells are not in the basket." | **KEEP** (second: "Sell in full. Your share counts are not known, so the basket has no sells.") | model book; yours |
| ac.sell.3 | :240 | "On a wider screen each row also shows when it was bought." | **KEEP** | - |
| ac.buy.1 | :245 | "No new stock qualifies for a free place." | "No stock that passes both filters is free to buy: every place is taken." when sells = 0; "No stock that passes both filters is outside the book." when the qualified list is all held **REWRITE**: "qualifies for a free place" mixed the two causes | no free place; no candidate |
| ac.buy.2 | :263-264 | "Amounts are the record's target weight of the model book's value today, {₹}." / "Amounts are each buy's target weight of {₹}, the capital in the Kite basket box." | **KEEP**, with `cr()` for the value (₹1.02 Cr, not ₹1,02,34,567) | model book; yours |
| ac.buy.3 | :412-418 | "Each buy gets {w}%, less than the {5}% buy size: the record never trims a kept stock to make room, so the buys share the {c}% the sells free up (the six-monthly rule, from the 30 Nov rebalance)." | "Each buy gets {w:r1}, less than the {buy_size:s0} buy size." "The record does not trim a kept stock to make room, so the buys share the {c:r1} the sells free up." "This is the six-monthly rule, in force from the {rule_from:date} rebalance." **REWRITE**: one 45-word sentence into three; "30 Nov" is typed: read it from `TRACK_RECORD_CONFIG` (the rule's start), as the Guide's `ema_warmup_from` is | w below the buy size; at it: no sentence |
| ac.buy.4 | :266-276 | "**What swaps have added so far.** In their first month the record’s {n} buys beat Nifty Total Market by {+x} points on average; the {m} stocks it sold, by {y} in the month after the sale. Over three months: {a} against {b}. {k} of the {m} sold were bought back within two months. {X has no price here and is left out.} {first:my} to {last:my}: a short record, …; evidence, not proof." | "In their first month, the record's {n:n} buys were {up_word} {|x|:p1} points on Nifty Total Market on average." "The {m:n} stocks it sold were {word} {|y|:p1} points in the month after the sale." "Over 3 months: {a:signed} against {b:signed} points." "{k:n} of the {m:n} sold were bought back within 2 months." Unpriced sentence **KEEP**. Muted caveat **KEEP**. With `{up_word}` = "ahead by" / "behind by" / "level with" (0.0). **REWRITE**: "beat … by −0.5 points" had no branch (dash.flow.8's fault); "by {y}" left out the verb; numbers in figures (dash.sec.2) | buys ahead, behind, level; sold the same; no 3M figures (third dropped); k = 0 ("None of the {m} sold was bought back…"); unpriced 0, 1, many |
| ac.buy.5 | :285 | "On a wider screen each row also shows the weight, the 3- and 6-month returns and the distance from the 52-week high." | **KEEP** | - |
| ac.hold.1 | :304 | Cell words "off the list" / "{k} to go" / "past {keep}" | **KEEP** (cells) | - |
| ac.hold.2 | :301 | "No rule can be checked." | "No sell rule can be checked: the stock is not ranked today." **REWRITE**: give the cause (R1) | - |
| ac.hold.3 | :324-326 | "Ordered by the least room on any rule, a full rank buffer counted as a 20% fall. "To 50D EMA" and "To the 52W-high line" are how far …. Rank 3M · 1M · now: …; "Out" means it does not pass them." | "Ordered by the least room on any sell rule; a full rank buffer counts as a {RANK_SCALE:s0} fall." "“To 50D EMA” and “To −{gap}% from 52W high” are how far the price can fall from today before it crosses that line." Third **KEEP**. **REWRITE**: the note named a column "To the 52W-high line" that the table heads "To −20% from 52W high" (:321); 20% is `exit_watch.RANK_SCALE`, typed here | - |
| ac.kite.1 | :524, :526-527 | "Buy orders only, each at its target weight of the capital above; your share counts are not known." / "The model book's sell orders, with its share counts, and its buy orders, each at the record's target weight of the book's value today, {₹}." | **KEEP**, `cr()` for the value | - |
| ac.empty.1 | :508 | `kit.empty("Add your holdings above,", "or upload the holdings CSV from Kite, to see what to do with them.")` | **KEEP** (R4 form) | - |
| ac.empty.2 | `app.py:1105-1110` | "The {system} model book forms at the close of {September 2026}'s last session and its record starts with {October 2026}." | "The {system_name} model book forms at the {last_session:date} close; its record starts in {first:mon} {year}." **REWRITE**: name the day, not "the month's last session" (the calendar knows it) | before inception only |
| ac.qual.1 | `qualified_view.py:82` | "Best-ranked stocks passing both filters." | **KEEP** | - |
| ac.qual.2 | `qualified_view.py:98-99` | "No stock passes both filters today: above its 50D EMA and within 20% of its 52-week high." | "No stock passes both filters today." + "They are a close above the 50D EMA and within {gap}% of the 52-week high." **REWRITE**: 20% typed (rule 9) | - |
| ac.qual.3 | `qualified_view.py:110` | "{A} and {B}: {x:.0%} of the list." | "{A} and {B} hold {x:s0} of the list." (tie for second: "{A}, {B} and {C} …") **REWRITE** (a verb; a tie named) | ≥ 40% only; tie |
| ac.view.1 | `actions_view.py:51-61, :102-145, :190-233`; `qualified_view.py:45-55` | `fill_due_note`, `rows_html`, `sells_html`, `buys_html`, `correlation_note` | **DROP**: nothing on a page calls them (only tests). Delete them with their tests instead of giving them templates (as pf.view.1) | - |

## 2. Screener (`src/ui/views/ranking_view.py`; `screener_table.py`, `components.py`, `app.py`)

| id | where | now | proposed | cases |
|---|---|---|---|---|
| sc.head.1 | :711-725 | h1: "{q} of the top {50} can be bought[; {new} of the {50} were not in the top {50} a month ago]." / "Screener" | "{q:n} of the top {n_top:n} pass both filters." Then: "{new:n} of them were not in the top {n_top:n} on {d1:day}." **REWRITE**: "can be bought" is wrong for most of them, because the book buys only the top {buy} qualified (sc.head.2); "a month ago" is named by its date, the session the 1M rank is read on (`_month_ago`), as the movers section does; "Screener" alone is not a sentence: "No stock is ranked yet." | q = 0 ("None of the top 50 passes both filters."); q = n ("All 50 …"); new = 0 ("All of them were in the top 50 on {d1:day}."); 1M rank missing (second dropped); no ranking |
| sc.head.2 | :728-731 | "The {n} ranked stocks, by momentum at the {day} close. The book buys the top 20 qualified and keeps a holding while it is in the top 40." | "The {n:n} ranked stocks of the {uni}, by momentum at the {as_of:day} close." "The book buys the top {buy} qualified and keeps a holding while it is in the top {keep}." **REWRITE**: 20 and 40 typed (rule 9); the list named (the 1000 and the list rank other sets) | date missing ("…by momentum.") |
| sc.chip.1 | `components.py:80-89` | Chip "Fewer than 20 pass both filters", shown when fewer than **15** pass | "Fewer than {buy} pass both filters: the book cannot fill its {buy} places." shown when fewer than {buy} pass. **Unsure; changes when the chip shows**: the text says 20 and the test is 15 (Question 3) | under the line; else none |
| sc.key.1 | :739-752 (`_KEY_HTML`) | Four paragraphs: "Qualified: above the 50D EMA and within 20% of the 52W high. …"; "Rank before: the rank … {when} …"; "Held: … The book buys the top 20 qualified and keeps … top 40 …"; "Big movers: rank moved 150 places or more in a month. Volume spike: today's volume 1.5 times its 20-day average or more." | **KEEP** the text; fill {gap}, {buy}, {keep}, `BIG_MOVE_PLACES` and the volume rule's ratio and window from their constants. "within 20% of the 52W high" in a sentence reads "the 52-week high" (glossary 14); "a month" becomes "since {d1:day}" | - |
| sc.cut.1 | `screener_table.py:317-319` | Row notes "The book buys to here: the 20th qualified" / "A holding is kept to here: the 40th qualified" | **KEEP** (BUY_CUT/KEEP_CUT already from config) | - |
| sc.cell.1 | `screener_table.py:410-415` | Cell titles "{x}% below its 50D EMA"; "{x}% below its 52W high; the filter is within 20%" | "{x:r1} below its 50D EMA"; "{x:r1} below its 52-week high; the filter is within {gap}%" **REWRITE** (glossary 14 in a sentence; half up) | - |
| sc.mv.1 | :700-703 | Kicker "What moved since {19 Oct}" / "What moved in the last month" | **KEEP** | date missing |
| sc.mv.2 | :911-916 | h2: "**{n_in} stock(s) entered the top 50** and **{n_out} left**[; {SYM} climbed {k} places, from #{a} to #{b}]." | "**{n_in:n} stocks entered the top 50** since {d1:day} and **{n_out:n} left**." "{SYM} climbed furthest, {k:n} places, from {a:ord} to {b:ord}." **REWRITE**: one idea a sentence; "#170" is a table form; the date named | n_in = n_out (usual; "and as many left"); 0 entered ("No stock entered the top 50 since …"); no jump: second dropped; tie for the furthest climb ("{A} and {B} climbed furthest, {k} places each.") |
| sc.mv.3 | :917-925 | "Ranks among the ranked stocks on {d1}, the last session on or before the same date a month back, against today. Every row shown." + `mw.column_note(...)` | **KEEP** | date missing ("Every row shown."); unranked footnote |
| sc.mv.4 | :926-937 | Captions "The ten that climbed most places, 1 to 5."; "In the top 50 now, not on {day}."; "In the top 50 on {day}, not now." | "The {k:n} that climbed most places, 1 to 5." with k = `len(jumps)` **REWRITE**: "ten" printed over fewer | k < 10; k ≤ 5 (no "1 to 5") |
| sc.data.1 | :802-829 | "{foot}. **Late:** Market caps are to {date}; All-time highs are not in, so the highs shown are the last two years’; … carry no date, so they may be old." | **KEEP** (cm.foot.1 plus `behind_phrase`, S193 E) | each stale source |
| sc.sys.1 | :666-679; `app.py:1083-1094` | "{system} · {r} of {m} stocks ranked among themselves / as one list." + "{k} too new to rank (under three months of prices): A, B … and more." / the 1000: "not ranked yet (under three months of prices with us; their history is being collected)" | "{r:n} of the {system_name}'s {m:n} stocks are ranked, {among themselves / as one list}." + "{k:n} are not ranked yet: {reason}. {names}[ and {rest:n} more]." **REWRITE**: "·" in a sentence; "and more" now says how many. Use the same reason function on the Watchlist and the stock page (wl.nr.1), so the 1000's stocks are not "too new" there and "being collected" here | nano; combined; 1000; k = 0 (second dropped); k = 1; > 12 names |
| sc.sys.2 | `app.py:1181` | "The Nifty 1000's list is not available, so the Nifty 750 is ranked." | **KEEP** | - |
| sc.tool.1 | :488, :607-611 | "Click a column header to sort the table."; export help | **KEEP** | - |

## 3. Market (`src/ui/views/market_questions_view.py`, `market_view.py`; `src/engine/market_questions.py`)

| id | where | now | proposed | cases |
|---|---|---|---|---|
| mk.head.1 | mqv:540-541 | h1: "{Breadth word} participation; {trend word, lower-cased}." ("About usual participation; no clear trend.") / "Market breadth" | "Participation is {breadth_phrase}; {index} {trend_phrase}." with `{breadth_phrase}` "very narrow / narrow / about usual / broad / very broad" and `{trend_phrase}` "is in a strong downtrend / is in a downtrend / has no clear trend / is in an uptrend / is in a strong uptrend"; `{index}` = `the(name)`. Missing: "Participation is {…}; Nifty Total Market's trend cannot be read today." **REWRITE**: the trend half had no subject; a score of None printed "Not enough data participation" (`word_for`, mq:555). See Question 2 | 5 × 5 words; either answer missing; both ("Market breadth" today: "The ranked stocks' prices are not in yet.") |
| mk.head.2 | mqv:545-546 | "Two questions, answered from the ranked stocks and NSE’s index closes: are most stocks taking part, and is {index} in an uptrend. Then today’s charts." | **KEEP**; with a question mark kept out of the clause: "…taking part, and is {index} in an uptrend? Then today's charts." | - |
| mk.q.1 | mq:304-312 | "{a:.0f}% of the ranked stocks are above their 200D EMA and {b:.0f}% beat {index} over the year." | "{a200:s0} of the ranked stocks are above their 200D EMA, and {beat:s0} beat {index} over 12 months." **REWRITE**: glossary 6 ("12 months" in sentences) | both; one missing (that clause only); both missing (no sentence) |
| mk.q.2 | mq:465-468 | "{u} of {n} measures say up, {d} say down." | **KEEP**; 0 reads "none say down" / "None of the {n} measures says up" | u = 0; d = 0 |
| mk.q.3 | mq:288-297, :372-377, :440-458 | Measure rules: "60% or more is broad, 40% or less is narrow"; "+5 or more is broad, −5 or less is narrow"; "+3 pts or more is broad, −3 or less is narrow"; "today's close against the last ten monthly closes; above is up, below is down; at the {day} month-end {x}"; "within 5% is up, 15% or more below is down" | **KEEP**, with "+3 points or more" in the sentence form and the month-end tail as its own clause: "At the {me:day} month-end it read {x:signed}." | month-end missing (tail dropped) |
| mk.q.4 | mqv:195-207 | "The answer a month ago: **{word}**." + "**{measure}**: {then} a month ago, {now} now[, now {vote}]." / "A month-ago reading is not available." | **KEEP**; the missing case gets its cause: "– a month ago: {mw.NOT_PUBLISHED} (the breadth history starts {first:date})." when the history is short | moved vote; same; no reading |
| mk.q.5 | mqv:214-227 | "To **{word}**: {measure} {rising above / reaching / falling below / falling to} {x} (now {y}); or …." / "No single measure moving one step would change the answer; it would take two or more." | **KEEP** | higher; lower; at an end (one side only); none |
| mk.q.6 | mqv:63 | "● Today · ○ A month ago · dashed ring: 12 months ago" | **KEEP** | - |
| mk.q.7 | mqv:241, :245 | "Under a year of history"; title "Lowest {lo}, highest {hi}; the shaded part is the middle half" | "– : the measure is too new (under 12 months of history)." **REWRITE** to the R1 cause words (`mw.TOO_NEW`) | - |
| mk.q.8 | mqv:281-283 | "Each measure votes by its cut-offs; primary measures count twice. … The verdict is at an end when the weighted vote is 0.6 or more either way, leaning at 0.25." | **KEEP**, with the two cut-offs from `word_for`'s constants (now typed in both places) | - |
| mk.q.9 | mqv:262-265 | Sub: "{ord} percentile[ since {my}]"; "12 months ago {x}" | **KEEP** | no history |
| mk.size.1 | mqv:324-327 | "The 10-month columns read the close on each day against … Points are per cent.[ {cm.late.1}]" | Body **KEEP**; "Points are per cent." becomes "Figures are per cent of the index's level." **REWRITE**: these are distances of a price from its own average, not gaps between two returns, so they are % (glossary 4); "Points are per cent" said both | late: cm.late.1 appended (S148) |
| mk.size.2 | mqv:114-125 | "Nifty Total Market’s closes did not load, so this reads the Nifty 500, …" / "Nifty Total Market from {date}, when NSE launched it; before that the Nifty 500, scaled to meet it on that day, so the trend’s ranges reach back to {yyyy}. NSE publishes no Nifty Total Market closes before its launch." | **KEEP**; split the second at "; before": "Before that it is the Nifty 500, scaled to meet it on that day, so the trend's ranges reach back to {first_year}." | fallback; joined; no join needed (none) |
| mk.ch.1 | mqv:404-409 | "Over the year {index} {rose/fell} {x:.1f}%[ / was flat]; the share of stocks above their 200D EMA went from {a}% to {b}%" + note "The index above, the share … Members of each date, leavers included. / Today’s members throughout." | "Over 12 months, {index} {rose/fell} {x:r1}, and the share of stocks above their 200D EMA went from {a:s0} to {b:s0}." (flat: "was unchanged"; same share: "stayed at {a:s0}") Note **KEEP**. **REWRITE**: glossary 6; half up; the head ended without a stop | up; down; level; share unchanged; year-ago missing (no head) |
| mk.ch.2 | mqv:422-426 | "Net new 52W highs this week: {x}% of stocks[; 12 months ago {y}%]" + note "Each week, the stocks that made a new 52-week high in the seven days …" | "Net new 52-week highs this week: {x:signed}% of stocks[, against {y:signed}% 12 months ago]." Note **KEEP**. **REWRITE**: glossary 14 in a sentence; a stop | year-ago missing |
| mk.ch.3 | mqv:435-436 | "Shaded: the usual range since {my}, {q1} to {q3} (the middle half of all weeks)." | **KEEP** (dash.mom.12's form) | - |
| mk.ch.4 | mqv:459-465 | "{Index} is {x}% above/below its 10-month average on {day}[; at the {day} month-end it was {y}% above/below]" + note "Monthly closes against the average of the last ten, {Month} at today's close. Above … Three years; price only." | "{Index} is {x:r1} {above/below} its 10-month average on {as_of:day}." "At the {me:day} month-end it was {y:r1} {above/below}." (only when the month-end is not today) Note **KEEP**. **REWRITE** (split; half up; "0.0% above" at level reads "at its 10-month average") | above; below; level; month-end today (second dropped) |
| mk.ch.5 | mqv:486-489 | "Over 12 months, {best} did best against {index} ({+x} pts) and {worst} worst ({y} pts)" | "Over 12 months, {best} did best against {index}, {ahead/behind} by {|x|:p1} points; {worst} did worst, {ahead/behind} by {|y|:p1} points." Note **KEEP**. **Unsure on the measure**: the figure is a ratio less 100 (relative line), not a gap of two returns, the case S173 IX-2 fixed on Indices (ix.lag.1); if so it is "{x:r1} ahead of {index}'s line", in %, not points | best ahead / behind; one size only (best = worst: "{A} is the only size index with a year of closes") |
| mk.ch.6 | mqv:440-442 | `TEN_MONTH_RANGE` note | **KEEP** | - |
| mk.pit.1 | mqv:570-576 | "Today counts the stocks ranked today. Every earlier reading counts the stocks in Nifty Total Market on that date, …; counting today’s members back in time made the past look about 5 points broader than it was." / the non-750 form | **KEEP**; "about 5 points" is typed from a past measurement: name its date or compute it (Question 4) | 750; other systems |
| mk.today.1 | `market_view.py:132`, :179, :185 | `kit.empty("Pick at least one EMA or SMA", "under Chart settings.")`; "No index tags on the ranked stocks."; "No stock made a new high or low in the last 20 sessions." | **KEEP** | - |
| mk.dead.1 | mqv:582-619 | `run_example` ("For example, {name}: … so Run reads {n} ahead.") | **DROP**: no caller since the Sectors section moved (S173 K-7); Sectors has its own (se.mo.2). Delete it | - |

## 4. Indices (`src/ui/views/indices_view.py`)

| id | where | now | proposed | cases |
|---|---|---|---|---|
| ix.head.1 | :68-80 | h1: (a) "The Nifty 50 trades **below its usual P/E**; the Nifty Smallcap 250 **above it**." (b) "The Nifty 50 sits **at the {k}th percentile** of its P/E since 2021; the Nifty Smallcap 250 **at the {j}th**." (c) "NSE's indices: what each costs, and which styles pay." | (a) "The Nifty 50's P/E is **below its median** since {pe_from:my}; the Nifty Smallcap 250's is **above it**." (a') the reverse pair. (b) both on one side: "The Nifty 50's P/E is **at the {k:ord} percentile** of its days since {pe_from:my}; the Nifty Smallcap 250's **at the {j:ord}**." (c) "NSE's index P/Es are not in yet." **REWRITE**: "usual" is the 50th percentile, so say median; (a) only covered big cheap and small dear; "since 2021" is the day NSE changed the basis, `ip.PE_FROM`; (c) was a label | big < 50 ≤ small; small < 50 ≤ big; both under or both over (b); exactly 50 ("at its median"); missing (c) |
| ix.head.2 | :82-84 | "NSE's own indices, read at the {day} close: what each index costs …, which investing styles beat their parent index, and how deep a normal year's fall goes for each size. Price returns; dividends are not added." | **KEEP**, "a normal year's fall" → "a median year's max drawdown" (glossary 8; the section's own measure, ix.size.1) | - |
| ix.val.1 | :109-112 | h2: "The Nifty 50 at {pe:.1f} times earnings is cheaper than {100−p}% of days since April 2021; the Nifty Smallcap 250 is dearer than {q}%." / "Valuation against the index's own recent past." | "At {pe:.1f} times earnings, the Nifty 50 is {cheaper/dearer} than on {s:s0} of days since {pe_from:date}." "The Nifty Smallcap 250 is {dearer/cheaper} than on {t:s0}." **REWRITE**: the Nifty 50 was always "cheaper" and the small one always "dearer", whatever the figures; "April 2021" typed against the 31 Mar 2021 the note gives | each cheap or dear; at 50 ("at its median"); missing: "Each index's P/E against its own past since {pe_from:date}." |
| ix.val.2 | :131-135 | "P/E is NSE's trailing price to earnings. The percentile counts days from 31 Mar 2021, when NSE changed the earnings basis (the Nifty 50 went from 40.4 to 33.2 overnight with the price flat), … P/B gets no percentile: its basis changed on 29 Sep 2023 and again on 23 Sep 2024.{young}" | **KEEP** (dated facts about NSE's files; `PE_FROM` fills the first date) | young index appended (ix.val.3) |
| ix.val.3 | :100-101 | " – for the {name}: the index is too new for a percentile or a past reading (NSE’s daily files carry its P/E from {date})." | **KEEP** (R1) | the 1000 only |
| ix.val.4 | :149-155 | how: "The Nifty 500's trailing P/E each week since 2012. … the shaded band is the middle half of days since then ({q25} to {q75}). The Nifty 500, not Nifty Total Market, because NSE's P/E for Nifty Total Market starts at its launch, 14 Oct 2021, …" + "A line above the band is dearer than three days in four since 2021; …" | **KEEP**; "14 Oct 2021" from the index file's first date, as mk.size.2 does | - |
| ix.sty.1 | :166-171 | h2: "Over 12 months, {a} and {b} **lead their parents**; {c} and {d} **trail by {lo}–{hi} points**." / "Each style against the index it picks from, over the last 12 months." | Same pattern, with three changes: "{k:n} styles lead their parents" when more than two lead (today only the first two are named, the rest dropped); the trailing part names those more than 5 points behind as "trail by more than 5 points: {lo}–{hi}"; fallback when none trails by 5: "Over 12 months, {a} leads its parent by the most, {x:p1} points; no style trails by more than 5." **REWRITE**: the fallback was a label (§2); "and" for three names | ≥ 1 ahead and ≥ 1 behind by 5; none behind by 5; none ahead ("No style leads its parent over 12 months; {c} trails most, by {x:p1} points."); lo = hi |
| ix.sty.2 | :182-186 | note | **KEEP** | - |
| ix.lag.1 | :196-197 | h2: "{Style}’s line against the {parent} is **{x}% below its {Month Year} peak**[, its deepest since launch in {yyyy}]." | **KEEP**; at the peak (x rounds to 0.0): "{Style}'s line against the {parent} is at its peak." | below; deepest; at peak |
| ix.lag.2 | :201-206 | " {S} is at its worst too ({x}%)." + " {S} fell {d}% against the {parent} in {yyyy}–{yy} and took until {Month Year} to recover." | "{S} is at its deepest too, {x:r1} below its peak." "{S} fell {d:r1} against the {parent}, from {peak:my} to {low:my}, and was back by {rec:my}." **REWRITE**: "{yyyy}–{yy}" gives no months (dash.mom.6's form); "({−12.3}%)" a signed figure in a sentence | none; one; two |
| ix.lag.3 | :223-224 | note | **KEEP** | - |
| ix.yr.1 | :239-240 | "No style led its parent every whole year; {style} came closest, {a} of {b}." / "{Style} led its parent in every year since launch." | **KEEP**, with a tie: "{A} and {B} came closest, {a} of {b} each." and "every whole year since launch" in the second (the count is whole years) | tie; always |
| ix.yr.2 | :249-250 | note | **KEEP** | - |
| ix.size.1 | :260-265 | h2: "In a median year since {2016}, the Nifty Smallcap 250 fell {s}% at some point, {twice / k times} the Large Cap index's {l}%." / "How far each size falls within a calendar year." | "In a median year since {from_year}, the Nifty Smallcap 250's max drawdown was {s:r1}, {twice / {k:.1f} times} the Nifty 100's {l:r1}." Fallback: "In a median year since {from_year}, {size} had the deepest max drawdown, {x:r1}." **REWRITE**: "the Large Cap index" is the Nifty 100 (`ip.SIZES`), named by glossary 1 and 3; "fell at some point" is the max drawdown (glossary 8); the fallback was a label | ratio about 2; other; large ≥ 0 or missing (fallback) |
| ix.size.2 | :292-294 | "The bar is the calendar year's return; the dot is the max drawdown within it. {yyyy} is year to date. Median of whole years since {2016}: {Large Cap −8.1%, …} (micro from 2022)." | **KEEP**, "Micro Cap from 2022" (glossary 3) | no micro |
| ix.size.3 | :283-287 | how text | **KEEP** (the start months are dated facts about NSE's file) | - |
| ix.ev.1 | :310-314 | h2: "Over 12 months Nifty Total Market is up/down {x}%; among themes, {A} leads at {+a}% and {Z} trails at {z}%." / "NSE's {n} broad, theme and strategy indices over 12 months." | "Over 12 months, Nifty Total Market is {up/down} {x:r1}." "Among themes, {A} leads, {up/down} {a:r1}, and {Z} trails, {up/down} {z:r1}." **REWRITE**: a signed figure after "at" (rule 2); split. **Late**: when Nifty Total Market's close is not in, "Nifty Total Market's {as_of:day} close is not in yet." in place of the first sentence | up; down; level; one theme only (second: "{A} is the only theme with 12 months."); late |
| ix.ev.2 | :308-309, :316-320 | note + " {cm.late.1} Their figures read –." | **KEEP** (S148) | late; on time |
| ix.ev.3 | :326-328 | h3: "{Family}: {k} of {n} up over the year; {A} leads at {+a}%, {Z} trails at {z}%." / "{Family}" | "{Family}: {k:n} of {n:n} are up over 12 months; {A} leads and {Z} trails." **REWRITE**: glossary 6; the two figures are the first and last rows of the table under it (§2) | k = 0 ("none is up"); k = n ("all are up"); n = 1; no 12M figures (the family's name) |
| ix.ev.4 | :297-301 | `GROUP_NOTE` | **KEEP** | - |
| ix.foot.1 | :366 | "{Data to … · NSE} · {n} broad, theme and strategy indices" | **KEEP** | - |
| ix.empty.1 | :373-375 | h1 "No index data yet." + "The copy of NSE's daily index files this page reads is not in yet; the page fills once it is." | **KEEP** the words; move them into `missing_words` as the R4 empty-page pair (`NO_INDEX_DATA`, `NO_INDEX_DATA_WHY`) and draw with `kit.page_empty`, as Sectors does | - |

## 5. Sectors (`src/ui/views/sector_view.py`)

Every sentence here compares a group with the system's ranked stocks. Today the code writes "the 750" and a regex
(`for_universe`, :623-647) rewrites it for other systems. That pass also touches the row label "The 750 vs Nifty Total
Market" and the chart text. **Proposed (se.uni.1):** each template carries `{uni}` and the regex is deleted, so the
test renders all three systems from the templates themselves. Numbers in sentences follow dash.sec.2 ("6 months",
"1 month"). `_words` ("seven", "no") goes, because it printed "One sectors lead" and "no of the 30".

| id | where | now | proposed | cases |
|---|---|---|---|---|
| se.head.1 | :216-228 | h1: "**{A}, {B} and {C}** lead the 750 over six months and one month[; **{Y} and {Z}** trail by {k} pts or more]." / "No {sector} leads the 750 on both six months and one month[; …]." | "**{A}, {B} and {C}** lead the {uni} over 6 months and 1 month; **{Y} and {Z}** trail it by {k:n} points or more over 6 months." One leader: "**{A}** leads …". **REWRITE**: "pts" is "points" in a sentence (glossary 4); "lead" for one name; the trailing half did not say its window (6 months only) | 1, 2, 3+ leaders (first three named, "and {n} more"); none; trailing pair missing (first clause only) |
| se.head.2 | :229-240 | lede: "{Seven} of {20} sectors are ahead of the 750, equal-weighted, over both windows.[ NSE’s indices tell a different month: Nifty Total Market rose {x}% and the 750, equal-weighted, rose {y}%, so {all k / k of n} sector indices beat their sector’s ranked stocks over the month.] Price returns, closes of {date}." | "{n_both:n} of {n:n} {sectors} are ahead of the {uni}, equal-weighted, over both windows." "Over 1 month, Nifty Total Market {rose/fell} {x:r1} and the {uni}, equal-weighted, {rose/fell} {y:r1}." "{k:n} of {m:n} sector indices beat their sector's ranked stocks over the month." "Price returns, to the {when:date} close." **REWRITE**: "tell a different month" claims a contrast the figures may not show; "so" claimed a cause; "One of 20 sectors are" | n_both = 0 ("None of …"), 1 ("is ahead"); NSE part missing (TradingView grouping, the list); k = m ("All {m} …"); k = 0; late headline index (cm.late.1) |
| se.lead.1 | :253-260 | h2: "**{Seven} sectors lead on both six months and one month**; **{three} trail on both**[, {S} among them: its six-month lead read {+x} pts on {day}]." | "**{n_both:n} {sectors} lead on both 6 months and 1 month**; **{n_behind:n} trail on both**." Then: "{S} is among them; its 6-month lead was {x:p1} points on {d3:day}." **REWRITE**: plural fault ("One sectors lead"); split; points | n_both 0 ("No sector leads on both"), 1; n_behind 0, 1; no faller (second dropped) |
| se.lead.2 | :314-320 | note "Lead: the {sector}’s return less the 750’s …" + " – in 12M: {A and B} has/have under a year of prices." | **KEEP** with `{uni}`; the footnote takes `mw.column_note("12M", mw.index_too_new())`-style words: "– in 12M: too new (under 12 months of prices): {names}." | none short; one; several |
| se.lead.3 | :288-294 | "Nearest to moving ahead over six months: **{A}** {−x} pts; …" / "Nearest to falling behind: …" + "Which sizes lead, against Nifty Total Market at 1M, 3M and 6M: on the Dashboard, …" | **KEEP**, "6 months", "points" | none either side |
| se.lead.4 | :296-305 | how: "A {sector} here is the equal-weighted index of its ranked stocks, … {k} have five or more ranked stocks and are shown[; left out with fewer: A (3), …]. … For example, {Healthcare}: its {n} stocks returned {x}% over six months and the 750 {y}%, a lead of {z} pts. …" | **KEEP** the method sentences, with `{uni}`; the example names the sector at the top of the table (`ld.rows[0]`), not "Healthcare" typed with a fallback, and reads "{S}'s {n:n} stocks returned {x:signed}% over 6 months and the {uni} {y:signed}%, a lead of {z:signed} points." (Question 4) | none left out; example sector |
| se.lead.5 | :306-308 | how read | **KEEP** ("1 point a line") | - |
| se.lead.6 | :269, :347 | Row label "The 750 vs Nifty Total Market" | "The {uni} against Nifty Total Market" **REWRITE** (`{uni}`; "vs" only in table heads) | - |
| se.broad.1 | :338-343 | h2, all coloured rust: "**{Nifty Financial Services} rose/fell {x}% in three months while the sector’s {n} ranked stocks rose/fell {y}%**[; only {A} is/are narrower than the 750 against Nifty Total Market]." | "{Index} {rose/fell} {x:r1} over 3 months, while the sector's {n:n} ranked stocks {rose/fell} {y:r1}." Then: "**Only {A} is narrower than the {uni} against Nifty Total Market.**" (k sectors: "{k:n} sectors are narrower …: {names}"). The colour goes on the verdict clause only, never the figures (rule 5). Financial Services typed: the example is the sector with the largest gap (`gaps[0]`, narrowest first) **REWRITE**: the whole sentence was rust whether the index led or lagged | index ahead; behind; none narrower ("No sector is narrower than …"); late headline index (left out, se.broad.2) |
| se.broad.2 | :364-368, :325-330 | note + " {cm.late.1} Its sector is / Their sectors are left out here." | **KEEP** (S148) | late; on time |
| se.ix.1 | :378-384 | h2: "Over 12 months **{A} leads NSE’s sector indices at {+a}%** and **{Z} trails at {z}%**; {three} of the {30} are younger than 12 months." | "Over 12 months, **{A} leads NSE's sector indices**, {up/down} {a:r1}, and **{Z} trails**, {up/down} {z:r1}." "{young:n} of the {n:n} are younger than 12 months." **REWRITE**: signed figures after "at"; "no of the 30" when none is young | young 0 ("None of the {n} is younger …"), 1 ("is younger"); no 12M figure ("NSE's {n} sector indices, each beside its sector.") |
| se.ix.2 | :408-415 | note + late | **KEEP** | late |
| se.only.1 | :42, :46 | `NSE_ONLY`, `TV_ONLY` | **KEEP** | - |
| se.mo.1 | :433-441 | h2: "{S} has **beaten / trailed the 750 in each of the last {six} completed months**, the longest run." / "Each month against the 750." | "{S} has **{beaten/trailed} the {uni} in each of the last {n:n} completed months**, the longest run." Owner's answer 1: n = 2 names the months ("in {Sep} and {Oct}"). Tie: "{S} and {T} have …, the longest runs." n = 1: "{S} {beat/trailed} the {uni} in {Oct}, and no {sector} has a longer run." Fallback: "No {sector} has beaten or trailed the {uni} two months running." **REWRITE**: "the last one completed months"; ties; the fallback was a label | n ≥ 3; 2; 1; tie; none |
| se.mo.2 | :442-452 | "For example, {S}: {Oct +1.2, Sep +0.8} pts, all ahead of the 750; {Aug} was {−0.4 / behind by less than 0.05}, so the count stops there and Run reads {n} ahead. Its 12 months, {x} pts, is the twelve completed months added up." | **KEEP** (S193 B's fix kept), with `{uni}`, "points" and "the 12 completed months" | run 1 ("{Oct +1.2} points, ahead of"); no month before; hair-width |
| se.mo.3 | :462-464 | note | **KEEP** | - |
| se.map.1 | :505-509 | h2: "Breadth rose in {seven} of {20} sectors from {then} to {now}; **{A} gained most on the 750**, **{Z} lost most**." | "Breadth rose in {rose:n} of {n:n} {sectors} from {then:day} to {now:day}." "**{A} gained most on the {uni}**, **{Z} lost most**." **REWRITE**: "no of 20"; split. Tie at the top: "{A} and {B} gained most" | rose 0 ("in none of"), all; tie |
| se.map.2 | :513-516 | note | **KEEP** | - |
| se.map.3 | :471-497 (`MAP_TEXT`, read by `static/dash_charts.js:531-540`) | The frame's worked example: "Across: did it beat the 750 over the {p}? …", the four readings ("broad strength building" …), "breadth fell in {n} of {of}." | **KEEP** the words (already fixed strings with slots); `{uni}` for "the 750"; "fell in {n} of {of}" gets the 0 case ("breadth fell in none of {of}") in the JS | per reading; n = 0 |
| se.in.1 | :530-532 | h2: "{x}% of the 750 are above their 200D EMA, up/down from {y}% a month ago, today’s members; **{A} has the most at {a}%**, **{Z} the fewest at {z}%**." | "{x:s0} of the {uni}'s stocks are above their 200D EMA, {up from / down from / the same as} {y:s0} a month ago." "**{A} has the most, {a:s0}**, and **{Z} the fewest, {z:s0}**." The "today's members" clause moves to the note, which already says it. **REWRITE**: "up from" when equal; four ideas in one sentence | up; down; same; tie at top or bottom |
| se.in.2 | :570-575, :564-566 | note + "– in the filter columns and Leaders: fewer than 2 of its stocks are ranked today ({names})." | **KEEP** (R1 from `mw.too_few_stocks`); "within 20% of the 52W high" → "within {gap}% of the 52-week high" (rule 9, glossary 14) | small groups; none |
| se.stk.1 | :688-690 | h2 "The {sector}’s ranked stocks, best rank first, in the Screener’s table." + note | "{S}'s {n:n} ranked stocks, best rank first." **REWRITE**: name the group picked (it is known once the picker is drawn; the h2 is drawn before it today, so the order moves) | - |
| se.group.1 | :53-56 | `GROUP_WORDS` meanings "ahead over six months and over the last month" … | **KEEP** as vocabulary, in figures ("6 months", "1 month") | - |
| se.dead.1 | :146-172 | `leadership_explainer` (the old map text) | **DROP**: only tests call it; `MAP_TEXT` is the live version (se.map.3). Delete with its tests | - |

## 6. Watchlist (`src/ui/views/watchlist_view.py`, `src/ui/watchlist_lines.py`)

| id | where | now | proposed | cases |
|---|---|---|---|---|
| wl.head.1 | `watchlist_lines.py:230-259` | h1: "Your 1 stock is **not in the book's top 20**" / "Both of your stocks are **outside …**" / "All {n} of your stocks are **in …**" / "{k} of your {n} stocks is/are **in the book's top 20**" + "; the one it holds is kept on {30 Nov}." / "; none of the {h} it holds is sold on {30 Nov}." / "; **{s} that it holds is/are sold** on {30 Nov}." | Head **KEEP**, with "the top {buy} qualified" for "the book's top 20" (the count is of qualified places, `group_of`). Tail as its own sentence, dash.brief.2's form: "The book holds {h:n} of them; none would be sold at the {check:day} check." / "The book holds it, and would keep it at the {check:day} check." / "The book holds {h:n} of them; **{s:n} would be sold** at the {check:day} check." **REWRITE**: "sold on 30 Nov" read as a trade on the 30th; they fill the next session (S193 B, dash.brief.2) | n = 1, 2, more; k = 0, k = n, between; plan missing (head only); h = 0; s = 0, 1, more |
| wl.head.2 | `watchlist_view.py:161-163`; `watchlist_lines.py:262-275` | "Ranked in the {Nifty 750} at the {20 Nov} close.[ {ranked_note}] If today's prices hold, on {Mon 30 Nov} the model book buys {A} and sells {B}; {C} is next in line." / "…neither buys nor sells any of your stocks" / "The model book's plan for the next rebalance is not available just now." | First **KEEP**. Plan: "If today's prices hold, the model book would buy {A} and sell {B} at the {check:day} check." "{C} is next in line." / "If today's prices hold, the model book would not trade any of your stocks at the {check:day} check." Missing **KEEP**. **REWRITE** (dash.brief.2's "would" and "check"; split) | buys only; sells only; both; neither; next in line 0, 1, more |
| wl.head.3 | `watchlist_view.py:165-167` | "Your watchlist is empty." + "Search a stock by name, type symbols and save, or press “Add to watchlist” on any stock's page. The list is kept in this browser only." | **KEEP** (R4) | - |
| wl.kept.1 | `watchlist_view.py:209-210` | "Kept in this browser only. Search a stock by name, or press “Add to watchlist” on its page, to add it; clear the box and save to empty the list." | **KEEP** | - |
| wl.lines.1 | `watchlist_view.py:237` | "None of your symbols is ranked in {the Nifty 750}." | **KEEP** | - |
| wl.lines.2 | `watchlist_lines.py:278-298` | "{A} is the one buy / {A and B} are the buys / None of your stocks is a buy; {S} is {k} place(s) short of the top 20." / "None of your stocks is qualified: each fails a filter." | "{A} is the one buy." / "{A} and {B} are the buys." / "None of your stocks is a buy." Then: "{S} is the nearest below the buy line, {k:n} places short of the top {buy}." **REWRITE**: split; "a place" → "1 place" (rule 8) | 0, 1, more buys; nearest below present; plan missing; none qualified |
| wl.lines.3 | `watchlist_view.py:246-247` | "Your stocks in rank order, grouped by where they sit against the book's lines: it buys the top {buy} qualified and keeps a holding while it is in the top {keep}." | **KEEP** | - |
| wl.lines.4 | `watchlist_view.py:254-265` | Keys: "Qualified: above the 50D EMA and within {gap}% of the 52W high. …"; "Rank before: the rank among the {n} ranked stocks {on 19 Aug and 19 Oct} …"; "{Plan head}: what the model book does at the next rebalance if today's prices hold, …" / "Plan: “–” on every row: the model book's plan could not be read just now."; "A click on a heading sorts …" | **KEEP**; "does" → "would do"; "the 52-week high" in a sentence (glossary 14). Shared with sc.key.1 (one function for both pages) | plan; no plan |
| wl.lines.5 | `watchlist_view.py:266-267` | "On a wider screen: rank among the {n} ranked stocks, the trail 3M and 1M ago, returns, filters and the 60-day line." | **KEEP** | - |
| wl.place.1 | `watchlist_lines.py:119-134` | Row notes "fails both filters / the 50D EMA filter / the 52W-high filter"; "the {20th}, the last place the book buys"; "{k} places inside the top {buy}[; not held]"; "the {40th}, the last place a holding is kept"; "{k} places short of the top {buy}"; "{k} places past the {40th}" | **KEEP** (row notes; they already use the lines) | each group; 1 place |
| wl.grp.1 | `watchlist_lines.py:109-116` | Group headings | **KEEP** (vocabulary) | - |
| wl.nr.1 | `watchlist_lines.py:352-422` | Why/where: "NSE changed the symbol to {NEW} ({Name})[ on {date}]."; "Not a member of the {uni}.[ It leaves out the Nifty 750’s stocks.]" + "Ranks {12th of 750 in the Nifty 750 and …}."; "In the {uni}, but too new to rank." + "It needs about three months of prices."; "Listed on NSE, but in none of the systems' lists."; "Not a symbol NSE lists today." | **KEEP**, except the too-new pair, which takes sc.sys.1's reason for the system (the 1000: "In the Nifty 1000, but not ranked yet: its history is being collected."), so one stock reads the same on Screener, Watchlist and its page; "about three months" from `MIN_OBSERVATIONS` (63 sessions) | each kind |
| wl.nr.2 | `watchlist_lines.py:317-328` | "{SYM} ranks {697th} of the {750} and {fails both filters / is {12th} among the qualified}." | **KEEP** | - |
| wl.nr.3 | `watchlist_lines.py:425-441` | "{n} of your symbols are not in {the Nifty 750}: {one} was renamed, {two} are in {> ₹2,000 Cr}, …." | **KEEP**, with figures for all counts ("1 was renamed", not "one", rule 8, as the head's "1 of your symbols") | 1; more; each kind |
| wl.fill.1 | `watchlist_lines.py:446-453` | "{k} meeting(s) or ex-date(s) before the {1 Dec} fill: {A and B}." / `mw.no_events("your stocks", fill)` | "{k:n} board meetings or ex-dates are announced before the {fill:day} fill, for {A} and {B}." **REWRITE**: a verb | 0 (R5); 1; more |
| wl.fill.2 | `watchlist_lines.py:456-468` | "{SYM} held its last results meeting on {day}." / "Every ranked stock on your list / {k} of the {n} ranked stocks on your list held its last results meeting {on {day} ({SYM}) / between {day} ({A}) and {day} ({B})}." | **KEEP**; "held their last results meetings" for the plural | n = 1; all; some; one date; a span |
| wl.fill.3 | `watchlist_view.py:322-325` | "**{SYM}** ({role}) {what}, {day}" | **KEEP** (ac.chg.3) | - |
| wl.foot.1 | `watchlist_view.py:335-350` | "{Data to …}. {k} of your {n} symbols ranked among the {N}; {each scored on all five horizons / j of the k …}, {none with a price gap / g with a price gap}." | "{Data to …}. {k:n} of your {n:n} symbols are ranked among the {N:n}; {scored}, {gaps}." **REWRITE** light (a verb) | empty list (date only); k = 0; all scored; gaps 0 |

## 7. Backtest (`src/ui/views/backtest_view.py`)

| id | where | now | proposed | cases |
|---|---|---|---|---|
| bt.tested.1 | :452-488 | "What was tested {Nifty 500 · Jan 2010 to Oct 2026 · 20 holdings · keep to rank 40 · …}" | **KEEP** (a list of settings, not a sentence) | - |
| bt.head.1 | :497-506 | h1: "Since {2010} this rule **made {+18.2%} a year** to the Nifty 500’s {12.1%}, before tax." / "Over {n} months this rule **returned {+5.0%}**, the Nifty 500 {+3.0%}." | "Since {first:mon} {first:year}, this rule **{made/lost} {a:r1} a year**, against {b_word} {b:r1} for the Nifty 500, before tax." Young: "Over {n:n} months, this rule **{returned/lost} {t:r1}**, against {b_word} {b:r1} for the Nifty 500." `{b_word}` "a gain of" / "a loss of". **REWRITE**: a signed figure after "made" (rule 2; a losing run read "made −3.0% a year"); the month named (the run starts at its first fill, not 1 Jan) | ahead; behind; level; loss on either side; under 12 months; benchmark missing (first clause only) |
| bt.head.2 | :507-509 | "{The record’s rules / These rules} replayed on the {index} as it stood each month, {first} to {last}, on NSE’s closes, after {30} bps a round trip. Price returns on both sides. A replay of the past, not a forecast." | **KEEP** | default; not |
| bt.head.3 | :260 | "{Index}'s point-in-time list begins {Mon yyyy}, so the test starts there." | **KEEP** | start moved |
| bt.head.4 | :515-516 | "**Warning:** These settings differ from the record’s. A setting chosen after seeing its result on this same history flatters the result; only months after a rule was fixed test it." | **KEEP** | not default |
| bt.head.5 | :1074-1075 | "The {system} system does not change these runs: each run picks its own index in the settings below." | **KEEP** | system ≠ 750 |
| bt.lead.1 | :522-527 | h2: "The lead over the Nifty 500 is **{x} points a year**; the rule was ahead in {k} of {n} months." (abs value; the sign in the colour only) / "Under a year, so no yearly figure: the rule is **{+5.0%}**, the Nifty 500 {+3.0%}." | "The rule is **{ahead/behind} of the Nifty 500 by {x:p1} points a year**; it was ahead in {k:n} of {n:n} months." Level: "The rule is level with the Nifty 500 over the run." Young: "Under 12 months, so no yearly figure: the rule is **{up/down} {t:r1}**, the Nifty 500 {up/down} {b:r1}." **REWRITE**: a negative lead read "the lead … is 2.3 points a year" in rust, so the colour alone carried the sign (S193 J: never colour alone); glossary 6 | ahead; behind; level; young; k = n |
| bt.lead.2 | :529-536 | Tile subs "Nifty 500 {x}" / "needs 12 months"; "a year" / "over the run"; "Nifty 500 ₹{x}"; "{p:.0%} · up in {u}" | **KEEP**; "up in {u}" → "up in {u:n} months" | young |
| bt.lead.3 | :546-552 | "**Price returns, both sides.** The rule’s figure includes a dividend only where …[. NSE’s own file puts the Nifty 500’s dividend yield at {dy}% a year on average since Feb 2012, against about 0.5% for the book (measured 2020–25 only, S125), so against the index with every dividend (its total-return version) the lead is about {dy − 0.5} points a year smaller than shown.]" | First two sentences **KEEP**. The yield clause as two sentences: "NSE's file puts the Nifty 500's dividend yield at {dy:.1f}% a year on average since {dy_from:my}; the book's was about 0.5%, measured 2020-25 only." "Against the index with every dividend, the lead is about {dy − 0.5:.1f} points a year smaller than shown." "0.5%" is a typed past measurement (Question 4); "Feb 2012" from the yield series' first date | yield missing (first sentence only) |
| bt.lead.4 | :554-555 | "**A year, compounded** is measured over calendar time, {y:.1f} years from the first fill. **pts**: {PTS_NOTE}" | **KEEP** | - |
| bt.lead.5 | :556-558 | "**Why the Nifty 500 and not Nifty Total Market.** Nifty Total Market starts on 14 Oct 2021 and this history in 2010 (owner, 21 Nov 2026). Nifty Total Market is beside it from 2022 in section 3 and from Nov 2021 in section 4.[ For this universe its own index, …]" | **KEEP**; the history's start year from `sm.first`; "14 Oct 2021" from the index file | own index; none |
| bt.lead.6 | :560-563 | "**The two halves.** The rule led by {a:.2f} pts a month on average to {my} and {b:.2f} after; the median month {+x pts}." | "**The two halves.** To {mid:my}, the rule was {ahead/behind} by {|a|:.2f} points a month on average; after it, {ahead/behind} by {|b|:.2f}." "The median month's lead was {m:signed} points." **REWRITE**: "led by −0.12" had no branch; pts in a sentence | each half ahead or behind |
| bt.lead.7 | :577-582 | chart how text | **KEEP** | - |
| bt.fall.1 | :588-595 | h2: "The rule is **{x}% below its {Month Year} peak**; its max drawdown since {2010} has not yet recovered." / "…; its max drawdown, {d}%, was back at its peak on {date}." / "The rule is at its peak[; its max drawdown was {d}%]." | "The rule is **{x:r1} below its {peak:mon} {peak:year} peak**." "Its max drawdown since {first:year}, {d:r1}, is not yet made back." / "Its max drawdown, {d:r1}, was made back by {rec:date}." / "The rule is at its peak. Its max drawdown was {d:r1}, made back by {rec:date}." **REWRITE**: one verb for one event ("made back", dash.mom.6); the open case gave no depth | below and open; below and recovered; at the peak |
| bt.fall.2 | :597-606 | Tile subs "Nifty 500 {x}"; "since {date}" / "at its peak"; "needs {+x}" | **KEEP** | - |
| bt.fall.3 | :620-621 | note | **KEEP** | - |
| bt.yr.1 | :664-672 | h2: "Ahead in **{k} of {n} whole years**[ ({2010} {Feb–Dec}: ahead)]; {2018} was the worst, **{8.3 pts}** behind." / "Ahead in **every whole year** of {n}[…]." | "The rule was ahead of the Nifty 500 in **{k:n} of {n:n} whole years**." "{worst_year} was the worst, **{x:p1} points behind**." Part years as their own sentence: "{2010}, from {Feb}, was {ahead/behind}." **REWRITE**: "pts" in a sentence; a parenthesis inside the headline | k = n; worst behind; no part year; two part years |
| bt.yr.2 | :676-681 | "A dark zero line; a lead left of it is a year behind. The first year starts at the first fill, {date}. Nifty Total Market is NSE’s index, live from 14 Oct 2021, so it starts in {2022}.[ {November} so far, to {date}, is not in the table: this rule {+x}, the Nifty 500 {+y}.]" | **KEEP**, with "this rule is {up/down} {x:r1}, the Nifty 500 {up/down} {y:r1}" for the month so far (rule 2) | month so far; none; benchmark missing |
| bt.yr.3 | :691-698, :723 | "Lead in pts. A year compounds its months; the first year from the first fill. – in a month: before {my}, the replay's first month; after {my}, the replay's last completed month (not published yet)." | "Lead in pts. …" **KEEP**. After the last month: a blank cell, not "– not published yet" **REWRITE** (owner's answer 8, pf.cal.2) | first month January (no clause); last December |
| bt.dep.1 | :735-745 | h2: "Tax costs the lead **{x} points a year**; costs matter more than the rebalance rule / the rebalance rule matters more than costs." / "What the result depends on, for the default run." | "Tax costs the lead **{x:p1} points a year**." "Costs matter more than the rebalance rule." / "The rebalance rule matters more than costs." Fallback: "The stored tests for the default run are not in yet." **REWRITE** (split; the fallback was a label) | each; equal ("Costs and the rebalance rule matter about as much."); tests missing |
| bt.dep.2 | :763-773 | "The rows other than “As tested” and “Nifty 500” are re-run once a week on the default settings only (run of {date}). After tax: {rates}, for an investor with no other gains; …[ These tests were run on the long file to {date}; this page reads the file to {date}, so they can differ slightly until the next weekly run.]" | **KEEP** (the stale clause is the S148 sentence for this page) | stale; current |
| bt.dep.3 | :775-777 | "Costs, the rebalance rule and tax are tested for the default run only." + note | **KEEP** | not default |
| bt.dep.4 | :789-790; :924 | "NSE’s Nifty200 Momentum 30 is the nearest index a fund tracks; it is a price index too. These windows are short and include this rule’s max drawdown." | **KEEP**; "include this rule's max drawdown" holds only when the window covers it: say it only when `big.peak ≥ window start` | covered; not |
| bt.tr.1 | :798-802 | "No sale used a price five or more sessions old." / "{k} sale(s) used a price {a} to {b} sessions old ({SYMs}…), {yyyy}–{yyyy}: stocks taken over or delisted, sold at their last price." | **KEEP**; a = b ("{a} sessions old"); one year ("in {yyyy}") | 0; 1; more |
| bt.tr.2 | :803-805 | "Every rebalance found enough stocks that passed the rules." / "{Month yyyy} found only {n} stocks that passed the rules; …; the rest of the book sat in cash at 0% until the next rebalance." | "At {month:mon} {year}'s rebalance only {n:n} stocks passed the rules." … **REWRITE** light (a month does not find) | none; 1-3 months shown, "and {k} more" past 3 |
| bt.tr.3 | :807-832 | The check rows: Survivorship "{p} of {p+c} rebalances picked from the {index} as it stood that day, leavers included; …"; Look-ahead; Stocks that stopped trading; Cash; Costs "{30} bps a round trip: about 22 statutory, …"; Tax; Rules chosen after looking "… came from a sweep of it (12 Oct 2026) …"; Sector cap; Index before Feb 2012 "… from the Kaggle dataset, not yet checked against NSE’s own file (S167)."; A second source | **KEEP**, with one change: "the Kaggle dataset" names a vendor (rule 7: the exchange only, never the vendor); "an outside dataset" | as listed |
| bt.tr.4 | :836-837 | h2, static: "Survivorship and look-ahead are handled; **costs, tax and the choice of rules** are the soft spots[; {k} check(s) is/are not made (below)]." | Built from the table's own statuses: "{checked} {is/are} handled; **{soft}** {is/are} the soft spots; {k:n} {check is/checks are} not made." **REWRITE**: when survivorship is a soft spot (`cur > 0`, :809-812) the headline still said "handled" over a table that says "Soft spot" | survivorship checked or soft; k = 0 (last clause dropped) |
| bt.trd.1 | :846 | "No trade closed in this run." | **KEEP** | - |
| bt.trd.2 | :848-849 | h2: "{n} trades closed; **fewer than half won**, and the winners paid for the rest." / "{n} trades closed; **{p} won**." | "{n:n} trades closed; **{p:s0} won**." Under half: "{n:n} trades closed; **fewer than half won ({p:s0})**." Then, only when the profit factor is above 1: "The winners paid for the losers: gains were {pf:.2f} times the losses." **REWRITE**: "the winners paid for the rest" was printed whatever the profit factor (**unsure**: true for the default run, not checked for every setting) | p ≥ 50%; under; pf ≤ 1 (no second sentence); pf missing |
| bt.trd.3 | :851-859 | Tile subs and the note "Every trade and the rebalance log are below; the live record’s trades are on Portfolio, which owns the record." | **KEEP** | - |
| bt.foot.1 | :863-866 | "{Data to {last} · NSE’s long price file}, the last completed month · prices to {date}[ · indices to {date}]." | **KEEP** | - |
| bt.err.1 | :225-226, :233-234, :252, :263-264, :279, :1009-1013, :1052-1053, :1110, :1115-1116, :1120 | Empty and failure notes ("No long price file yet." …, "Backtest running: request queued. …", "The download is not available for this run; …") | **KEEP** (R4 forms); "a 12M lookback" in the note at :1115 → "12 months of prices" (glossary 6, a sentence) | each |

## 8. The stock page (`src/ui/stock_lines.py`, `src/ui/views/stock_view.py`)

| id | where | now | proposed | cases |
|---|---|---|---|---|
| st.head.1 | sl:134-138 | h1: "{Name} is {12th} {of 750}, {passes both filters / fails both filters / passes one filter} and {is / is not} in the model book." | **KEEP**; "passes one filter" names which: "passes only the 50D EMA filter / only the 52-week-high filter" (the tiles already say which it fails) | 3 filter states × held; the list ("of the 1,912 in the > ₹2,000 Cr list") |
| st.head.2 | sl:141-157 | "{₹px} at the close on {date}[, a new 52-week closing high]. Up/Down {x}% in 12 months[, against {+y}% for Nifty Total Market]. Market cap {₹…}." | "{px} at the {as_of:date} close[, a new 52-week closing high]." "{Up/Down} {x:r1} over 12 months, against {up/down} {y:r1} for Nifty Total Market." "Market cap {cap:cr}." **REWRITE**: "against +0.8% for" a signed figure in a sentence (rule 2); "in 12 months" → "over 12 months" as Dashboard sentences; `market_cap` writes its own ₹ forms beside `cr()` (one helper). **Late**: when Nifty Total Market has no {as_of} close, the "against" clause reads "; Nifty Total Market's {as_of:day} close is not in yet." (st.ret.3) | new high; level ("unchanged over 12 months"); market missing; late; cap missing |
| st.head.3 | sv:268-269 | "Also {12th of 750 in the Nifty 750 and 17th of 1,000 in the Nifty 1000}. {links}" | "It also ranks {…}." **REWRITE** (a verb) | 1; 2 systems |
| st.head.4 | sl:167-186 | Tile subs "{+x}% in a month"; "{r3} three months ago" / "not ranked three months ago"; "the book buys the top {buy}"; "fails {…}"; "since {date}[, {w}% of the book]" / "since its first buy" | **KEEP** ("in a month" → "over 1M", the tile form) | - |
| st.rank.1 | sl:212-220 | h2: "{Twelfth} of the {290} that pass both filters, **inside the book’s buy line / between the book’s buy and keep lines / past the book’s keep line**" / "{Twelfth} of 750, but out of the {290} the book picks from: **it fails {…}**" | "{q:ord} of the {n_q:n} that pass both filters, **{where}**." / "{rank:ord} of {uni}, but **it fails {filters}**, so it is not among the {n_q:n} the book picks from." **REWRITE**: ordinals in figures, as the h1 (rule 8: "12th", not "Twelfth"); the missing stop; the second read "out of the 290 … : it fails" | inside; between; past; fails one or both; young (no 52-week high) |
| st.rank.2 | sl:223-232 | "A past rank is how today’s rule ranks the stock on that day, … the book buys the top {buy} of them and keeps a holding while it is in the top {keep}. Score {0.812}[, with all five horizons scored / with {k} of the five …]." | **KEEP**, "Its score is {s:.3f}, with …" (a verb) | hz 5; under; missing |
| st.rule.1 | sl:333-352 | h2: "**A holding would be sold** if this holds at {the 30 Nov check}: it is {why}." / "**Close to a sell rule**: it {why}." / "**Clear of all three sell rules**; a {x}% fall would reach the nearest, {its 50D EMA / the −20% line}." / "The sell rules cannot be read for this stock today." | Held: "**It would be sold** at the {check:day} check if today's price holds: it is {why}." Not held: "**It would be sold if held** …". WATCH: "**It is close to a sell rule**: it {why}." with cm.rule.3-5 written as verb phrases ("is 38th among …", "can fall …"). CLEAR **KEEP**; no cushion: "**Clear of all three sell rules.**". Unreadable: "No sell rule can be checked: the stock is not ranked today." **REWRITE**: "Close to a sell rule: it #38 · 2 places from the buffer" had no verb (cm.rule.4); "A holding would be sold" on a stock the book does not hold | sell held / not held; watch by rank, EMA, high, several; clear; unknown |
| st.rule.2 | sl:304-330 | Ladder rows "{x}% above / below"; "None before {126} sessions"; "At the high"; "{x}% from it"; "Not yet" | **KEEP** (cells) | - |
| st.rule.3 | sl:378-394 | "**The model book does not hold it.**" / "**The model book holds it:** {165 shares}, {5.4}% of the book, first bought on {date}[ at {₹}], {+x}% since." | **KEEP**; "{+x}% since" → "{up/down} {x:r1} since" (rule 2) | not held; held with each part missing |
| st.rule.4 | sl:397-410 | "The rules are checked at the month-end close, next on {30 Nov 2026}; board meetings and ex-dates announced before then: {Results on 3 Dec}." / "…; no board meeting is announced before then[ (its last results meeting was on {day})]." | "The sell rules are checked at each month-end close, next on {check:date}." Then `mw.no_events("it", check)` / "Announced before then: {what} on {day}." "Its last results meeting was on {day}." **REWRITE**: R5 (one sentence for the empty check on every page; today the stock page has its own); split | events; none; last results missing |
| st.rule.5 | sl:413-423 | "Highs and lows are closing prices over the last 12 months, … The all-time high is the same close, {₹}. / The all-time closing high is {₹}[, on {date}]." | **KEEP** | ATH = 52W high; other; date missing; no ATH |
| st.ret.1 | sl:533-544 | h2: "Up/Down {x}% in 12 months against **{+y}% for Nifty Total Market**; its max drawdown was {d}%." / "No return to show for this stock yet." | "{Up/Down} {x:r1} over {m} months, against **{up/down} {y:r1} for Nifty Total Market**." "Its max drawdown was {d:r1}." **REWRITE**: rule 2; split. It repeats st.head.2's 12-month figure (§2: a section heading may restate the page's lede only once; see Question 5) | 12M; a shorter window when 12M is missing ("over 6 months"); market missing; late (st.ret.3); max drawdown missing |
| st.ret.2 | sl:547-552 | returns note | **KEEP** | - |
| st.ret.3 | sv:551-553; `sl.market_return` | Nifty Total Market is cut at the page's session, then read with `value_at` (the last close on or before), so a late close silently ends a session early | **Late branch (new)**: when the index has no close for {as_of}, its column reads "–" and the section ends with cm.late.1. **Changes a number shown**: the market figure becomes "–" instead of a session-early figure, on late days only (the S148 rule; the Dashboard and Portfolio already do this) | late; on time |
| st.px.1 | sl:563-585 | h2: "Above its 50D EMA on {57} of the last {60} sessions; **against Nifty Total Market it has almost tripled / its relative strength rose {x}%** in 12 months." / "Too few sessions for a 50D EMA yet." | **KEEP** (S193 B wording); "in 12 months" → "over 12 months"; "has grown {r:.1f} times" kept | each verb; no RS |
| st.px.2 | sl:588-591 | `PRICE_NOTE` "… (none before 30 sessions) …" | **KEEP**; "30" from `EMA_MIN_PRINTS` (rule 9) | - |
| st.ind.1 | sl:612-620 | h2: "{Fourth} of {26} {Auto} stocks; {k} of them pass(es) both filters." | "{pos:ord} of the {n:n} {sector} stocks; {k:n} of them pass both filters." **REWRITE**: ordinal in figures (rule 8); "1 of them passes" agreement kept | pos missing; k = 0 ("none of them passes"); 1 |
| st.ind.2 | sv:131-143, :410-411 | "The {eight} best-ranked of the sector’s {26}, with this stock / and this stock ({14th}); returns in %. All {26} {Auto} stocks on the Screener →" | **KEEP**, the count in figures ("The 8 best-ranked …") | stock among them; below them |
| st.data.1 | sl:681-712 | Check items: "A close on every session of the last 12 months; none carried forward"; "{x}% of the last 12 months’ sessions carry the previous close"; "A data gap in the last 12 months"; "More than {126} sessions of prices, so the 52W high counts" / "Fewer than …"; "Ranked on all five horizons …" / "Ranked on {k} of the five horizons; …"; "The price is the {day} close, the ranking’s own day" / "…the last print, not the {day} close"; "No split, bonus, rights issue or demerger in NSE’s lists since {Month yyyy}"; "All-time closing high over Screener’s whole history, its weekly years filled with NSE’s daily closes" / "High from a two-year window, not all-time" | **KEEP**, with two changes: "the 52W high counts" → "the 52-week high counts" (a sentence, glossary 14); "Screener’s whole history" names a vendor (rule 7, owner 20-21 Nov: "Let's not show source"): "All-time closing high over the full price history we hold, its weekly years filled with NSE's daily closes" | each item |
| st.data.2 | sl:715-729 | h2: "Nothing to correct: a full year of prices with no gaps, and no split, bonus or rights issue to adjust for." / "{k} corporate action(s) in NSE’s lists since {Month yyyy}, the latest a {split} ex {date}; the prices before it are rescaled; {j} check(s) to read." | "Nothing to correct: …" **KEEP**. Second as two sentences: "{k:n} corporate actions in NSE's lists since {from:mon} {year}, the latest a {kind} ex {ex:date}; prices before it are rescaled." "{j:n} checks to read below." **REWRITE**: two semicolons | none; actions; checks; both |
| st.data.3 | sl:659-667 | "{Split}, ex {date}[: {terms}][; prices before it are scaled by {0.2}]" | **KEEP** (a list item) | - |
| st.nr.1 | sv:439-453 | h1: "{SYM} is not in the current ranking of {the 750}." + "{why} {where} {links / NEW’s page → / Back to the Screener for the stocks that are ranked.}" | **KEEP** (wl.nr.1's sentences); the last becomes a link ("Back to the Screener →"), as the others are | each kind |
| st.btn.1 | sv:248-256 | Button captions and helps | **KEEP** | - |

## 9. Guide (`src/ui/views/guide_view.py`)

The Guide is reference prose. Each paragraph that carries a number or a condition is a template; its numbers come
from `TRACK_RECORD_CONFIG` and the engine's constants, as most already do. The rows below list only the paragraphs
that change. **KEEP** covers the rest: the score formulas (:104-123), Filters (:127-138), the 52-week-high note
(:143-147), Acting on it, and the Questions (:207-237). They have no slot that the data could get wrong, or they fill
it from config already.

| id | where | now | proposed | cases |
|---|---|---|---|---|
| gd.head.1 | :245-248 | h1 "Guide" + "How the ranking, the filters, the book and the record work, and how to act on them" | See Question 1. Recommended: kicker "Guide"; h1 "How the ranking picks the book, and how to act on it."; lede "The ranking, the filters, the book and the record, step by step." | - |
| gd.step.1 | :87-90 | "**Universe.** About 750 stocks: the Nifty Total Market as NSE published it on each date, … The {Nifty 1000 and the > ₹2,000 Cr list} follow the same steps on their own lists." | "**Universe.** The {n_members:n} stocks of Nifty Total Market as NSE published it on each date, …" **REWRITE**: "the Nifty Total Market" (glossary 1 writes it without "the"); "About 750" from the list's count | - |
| gd.step.3 | :93 | "**Filters.** Above its 50D EMA and within 20% of its 52-week high." | "…within {gap}% of its 52-week high." **REWRITE**: 20% typed while the Filters section uses `high_pct` (rule 9) | - |
| gd.step.4 | :94-97 | "**Book.** … From the 30 Nov 2026 rebalance every holding goes back to 5% twice a year (March and September); …" | "From the {rule_from:date} rebalance every holding goes back to {stock_cap:s0} twice a year ({reset_months}); …" **REWRITE**: 30 Nov, 5%, March and September typed (they are in config; see ac.buy.3) | - |
| gd.sc.1 | :105-107 | "… its last close up to five sessions before stands in; …" | "…up to {ANCHOR_STALENESS_LIMIT:n} sessions before …" (from `calendar_momentum`) **REWRITE** (rule 9) | - |
| gd.fl.5 | :139-142 | h3 "A new listing waits about six months" + "No stock is ranked before {63} sessions of prices, and the 52-week high needs {126} closes … about six months of trading …" | h3 and text: "about {round(min_high / 21):n} months" **REWRITE**: "six" is typed beside a computed 126 | - |
| gd.bk.2 | :156-162 | "**Caps:** … From the 30 Nov 2026 rebalance a holding that is kept is trimmed only above 15%, …" | 30 Nov and 15% from config (`hold_cap`, the rule's start) **REWRITE** (rule 9) | - |
| gd.wt.2 | :173-186 | "**Six-monthly reset** (from the 30 Nov 2026 rebalance). … unless it is above 15%, when it is cut to 15%, and each new buy is 5% … No sector is above 40% after a rebalance. In the test behind the decision (8 Nov 2026, with an estimate of tax) the monthly reset earned 15.4% a year after tax and the six-monthly 15.3%, … 14 Oct 2021. …" | Config slots for 30 Nov, 15%, 5%, 40% (`sector_cap`); the test's figures stay as a dated quote, "In the test behind the decision (8 Nov 2026) …" (Question 4); paragraph split after "pay for them." **REWRITE** (rule 9; an 11-line paragraph) | - |
| gd.wt.3 | :187-191 | "…one over its volatility over the last 63 sessions." | "…the last {inv_vol_window:n} sessions." from the backtester's constant **REWRITE** (rule 9) | - |
| gd.faq.4 | :218-220 | "The header's "... % above its 200D EMA" (or below) compares …" | **KEEP** | - |

---

## 10. Counts

| | Rows found | Kept | Rewritten | Dropped whole |
|---|---|---|---|---|
| Shared (cm.) | 8 | 4 | 4 | 0 |
| Actions | 27 | 13 | 12 | 2 (ac.sell.1, ac.view.1) |
| Screener | 14 | 7 | 7 | 0 |
| Market | 22 | 13 | 8 | 1 (mk.dead.1) |
| Indices | 22 | 15 | 7 | 0 |
| Sectors | 24 | 13 | 10 | 1 (se.dead.1) |
| Watchlist | 18 | 13 | 5 | 0 |
| Backtest | 32 | 21 | 11 | 0 |
| Stock page | 23 | 14 | 9 | 0 |
| Guide | 10 | 1 | 9 | 0 |
| **All** | **200** | **114** | **82** | **4** |

"Kept" counts every row whose proposal starts with **KEEP**. That includes about 35 "KEEP, with …" rows, where the
sentence stays and only a slot, a unit word, a singular or a missing branch changes (for example "pts" to "points",
a typed 20 to `{buy}`, or a 0 case). A row is "rewritten" when its sentence changes. Sectors' `{uni}` change
(se.uni.1) is in the section's preamble, not a row.
A row is one reader-facing sentence pattern with its branches, as in the archive. A group of tile subs, check items or
row notes counts as one row. The Guide's unchanged paragraphs (about 25) are covered by its one KEEP line and are not
counted one by one.

**Faults the templates also fix (code, not wording):**
- Market: the title printed "Not enough data participation" when a score is missing (mk.head.1).
- Sectors:
  - "One sectors lead", "One of 20 sectors are", "no of the 30 are", "Breadth rose in no of 20", "the last one completed months" (`_words`, se.head.2, se.lead.1, se.ix.1, se.map.1, se.mo.1).
  - The Broad-or-narrow headline was all rust whatever the sign (se.broad.1).
  - The "the 750" regex pass (se.uni.1).
- Indices:
  - The P/E headline called the Nifty 50 "cheaper" and the Smallcap 250 "dearer" on every reading (ix.val.1).
  - The title covered one of four cases (ix.head.1).
  - A "{yyyy}–{yy}" span with no months (ix.lag.2).
- Backtest:
  - A negative lead was "the lead … is 2.3 points a year", with the sign in the colour only (bt.lead.1).
  - "made −3.0% a year" (bt.head.1).
  - The trust headline said "handled" over a "Soft spot" row (bt.tr.4).
  - "the winners paid for the rest" was printed whatever the profit factor (bt.trd.2).
  - A vendor was named (bt.tr.3).
- Stock page:
  - "Close to a sell rule: it #38 · 2 places from the buffer" (st.rule.1, cm.rule.4).
  - A vendor was named in the data checks (st.data.1).
  - The market figure was a session early on a late day with no note (st.ret.3, the S148 rule).
- Screener: the chip said "Fewer than 20" and fired under 15 (sc.chip.1).
- Watchlist: "sold on 30 Nov" (wl.head.1, dash.brief.2's fault). One stock reads "too new to rank" on the Watchlist and "history being collected" on the Screener for the 1000 (sc.sys.1, wl.nr.1).
- Actions: "beat … by −0.5 points" (ac.buy.4). The Hold note named a column the table does not have (ac.hold.3).
- Typed numbers that config or the data holds (rule 9):
  - Screener lede and key: 20, 40, 20%, 150, 1.5.
  - Actions: "30 Nov" and "20%".
  - Indices: "April 2021".
  - Guide: 20%, 5%, 15%, 40%, 30 Nov, March and September, six months, five sessions, 63, about 750.
  - Sectors examples: Healthcare and Financial Services.
- Dead code to delete instead of templating: `actions_view.rows_html`, `sells_html`, `buys_html`, `fill_due_note`; `qualified_view.correlation_note`; `market_questions_view.run_example`; `sector_view.leadership_explainer`.

**Rows that would change a number shown:**
- st.ret.3: on late days only, a session-early market figure becomes "–", by the S148 rule.
- sc.chip.1, if Question 3 is answered "tie it to the buy count". That changes when the chip shows, not a figure.

Otherwise only the half-up rounding moves (glossary 12, decided): a figure at exactly .x5 can change its last digit
where `:.1f` and `:.0f` sit today (Market chart heads, Sectors, Indices, the Actions after-table).

**Unsure:**
- mk.ch.5: points or %. The size lines are ratios, as on Indices.
- bt.trd.2: whether the claim holds for every setting.
- sc.chip.1: which threshold is meant.
- The typed past measurements in Question 4.

## 11. Rules added to the archive's (§4)

11. **A count in a sentence is a figure** ("7 of 20 sectors", "12th of 290"). A count is a word only in fixed phrases
    such as "both" and "none". This follows dash.sec.2 and rule 8, and removes `_words` and `ordinal_word` from
    sentences. Spelled-out counts printed "One sectors" and "no of the 30".
12. **The universe is a slot.** Every sentence that names the compared list takes `{uni}` (or `{system_name}`), not
    "750" rewritten afterwards.
13. **No vendor in a sentence.** Name the exchange only (rule 7). This covers "Screener's whole history" and "the
    Kaggle dataset".
14. **A number from a past test stays as a dated quote** ("In the test of 8 Nov 2026, …"). It is never written as if
    it were live. Anything the page computes is filled, never typed (see Question 4).

## 12. Questions for the owner

Answers (owner, 24 Nov 2026, one at a time): 1, the question title (recommended); 2, the subject named (recommended).

1. **The Guide's title (gd.head.1).** Every other page's h1 now answers a question (§2a); the Guide's is its name.
   I recommend "How the ranking picks the book, and how to act on it.", with "Guide" as the kicker. The alternative
   is to keep "Guide" as the one stated exception: a reference page has no finding.
2. **The Market title (mk.head.1).** Today it reads "About usual participation; no clear trend." I recommend
   "Participation is about usual; Nifty Total Market has no clear trend." It gives the trend a subject and covers the
   missing case. The alternative keeps today's two-noun form and adds only the missing-data branch. That is shorter,
   but the second half has no subject.
3. **The Screener's "Fewer than 20 pass both filters" chip (sc.chip.1).** The text says 20 and the code tests 15. I
   recommend tying both to the book's buy count ({buy}, 20 today), because the chip's point is that the book cannot
   fill. The chip would then show more often. The alternative keeps the 15 line and writes "Fewer than 15".
4. **Typed figures from past measurements**: Guide 15.4% and 15.3% (8 Nov 2026), Backtest "about 0.5% for the
   book (2020-25, S125)", Market "about 5 points broader", and the Sectors examples (Healthcare, Financial Services).
   I recommend:
   - Keep the first three as dated quotes, with the test's date in the sentence (rule 14).
   - Fill the Sectors examples from the table's top row.

   The alternative is to compute the Market's 5 points and the book's yield live each night. That is more correct,
   but it is new work with a job that someone must read (S195 §4).
5. **The stock page says its 12-month return twice**: in the lede (st.head.2) and in the Returns heading
   (st.ret.1). §2 says no figure twice. I recommend that the lede keep it, as the page's verdict, like the
   Dashboard's brief (answer 2). The Returns heading would then lead with the window the table cannot show at a
   glance: "Ahead of Nifty Total Market on {k} of 5 windows; its 12-month max drawdown was {d}." The alternative is
   to drop the figure from the lede.

**Not checked:**
- Wording was judged from the code, not from pages rendered on all three systems. The app on port 8542 was not
  touched.
- The case lists come from the branches in the code. Before the templates are built, each case needs a run on the
  system it names, for example:
  - a down year on the Backtest's headline (bt.head.1, bt.lead.1);
  - a late Nifty Total Market close on the stock page (st.ret.3);
  - the 1000 and the list on Sectors, for `{uni}`;
  - a Market score of None.
- Line numbers are from the working tree on 24 Nov 2026 and will move.
- The test for these pages should be built as `tests/test_s203_templates.py` is: one test per id, fake inputs, the
  `_clean` check on every branch, on the three systems.
