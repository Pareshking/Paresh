# Blind second reading of the parsed events (protocol gate G7), 2026-10-02

**Method.** 22 notices were drawn at random (fixed seed 20261002) from the 87 notices that carry events for Midcap 150, Smallcap 250,
Microcap 250 or Total Market, the four indices NSE's IndexInclExcl.xls does not cover. They hold 1,126 events, 24.8% of all events for
those indices. A separate reader (an AI agent with its own context, not a person) was given only the notice texts and the task of
listing every inclusion and exclusion for those four indices with the date that governs each table. It was told not to open
`events_raw.csv`, the history, the rules or any other notice. Its output is `reviewer_events.csv`; its notes are `reviewer_notes.md`.

**Result.** The reviewer's 1,126 events equal the parser's 1,126 events exactly, symbol, action and effective date
(`python blind_review_compare.py`). It also noted the one notice with two dates inside these indices
(`ind_prs07092020`: Smallcap 250 section A 2020-09-14, section D 2020-09-25), which the parser reproduces.

**What this does and does not show.**
- It shows the parser reads these notices the way a second reader does. It does not show that the notices are complete, or that
  a notice was not revoked by another one; those rest on the chain closing at exact sizes and on the NSE workbook check.
- The reader is a second AI reading, not a human. A person re-deriving a sample would be stronger evidence; this does not
  replace compliance sign-off.
- Nifty 50, Next 50 and Nifty 500 are covered separately by the workbook check. Notices read by OCR were not in the sample.
