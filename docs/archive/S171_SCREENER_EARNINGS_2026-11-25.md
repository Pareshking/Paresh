# S171 (2): our Screener aggregate against NSE's earnings growth, 25 Nov 2026

Research only. Nothing went on a page, into `data/` or into a workflow.

## What was measured

- **Members:** each index's point-in-time list on each quarter end, from `data/membership_history.json`
  (`index_universe.index_history` + `membership.members_on(canonical=True)`) (owner, 25 Nov 2026).
  We measured six indices: Nifty 50, Next 50, Midcap 150, Smallcap 250, Microcap 250 and Nifty 500.
- **Figures:** the "Quarterly Results" table on each company's Screener page, read with
  `src/loaders/screener_quarters.py`: "Sales" (or "Revenue" for lenders) and "Net Profit", in Rs crore.
  We read the /consolidated/ page. A company whose page mixes consolidated and "(S)" standalone
  quarters was read from its standalone page.
- **Growth:** aggregate = sum(x_q) / sum(x_{q-4}) - 1 over members with both quarters. Median = the median
  member's growth, leaving out members with a base of zero or less. Q2 and Q3 FY26 leave out Tata
  Motors (TMPV/TMCV), as NSE does.
- **Script:** `scripts/screener_earnings_measure.py` (`fetch`, then `measure`, both run with `python -I`).
- **Pages:** 933 companies fetched on 25 Nov 2026 (the union of all members on the 9 quarter ends Sep 2024 to
  Sep 2026), 1.5 s apart, with the honest user agent. All 933 returned HTTP 200, plus 15 standalone pages.
  All 933 were parsed. Basis: 830 consolidated, 88 standalone (no consolidated figures on Screener),
  9 standalone because the consolidated page was mixed, 6 standalone because the consolidated page had
  no table. Raw pages and the per-quarter CSV are in the session scratch directory only.

## The check (fixed in the script's docstring before any result was seen, commit bd0a25b)

The owner's rule of 25 Nov 2026 is a gross-error check, and the comparison is a report, not a gate.
A quarter is **flagged** when our Nifty 50 or Nifty 500 aggregate profit growth or aggregate
revenue growth differs from NSE's (`data/reference/nse_earnings_review.csv`) by more than 5.0
points. Each flagged gap is explained by its top 5 companies, ranked by the absolute size of
their contribution to our growth.

## Result: revenue reproduces NSE; profit does not (8 quarters flagged, all profit)

Figures are % YoY. The gap is ours minus NSE's, in points. Coverage is the members with both
quarters out of all members (Nifty 50 / Nifty 500).

| Quarter | N50 revenue: NSE / ours / gap | N500 revenue: NSE / ours / gap | N50 profit: NSE / ours / gap | N500 profit: NSE / ours / gap | Coverage |
|---|---|---|---|---|---|
| Q2 FY25 | 6.6 / 5.9 / -0.8 | 8.3 / 8.2 / -0.1 | 0.8 / 4.3 / +3.5 | -4.1 / 1.2 / **+5.3** | 50/50, 486/500 |
| Q3 FY25 | 4.5 / 3.7 / -0.8 | 4.6 / 4.4 / -0.3 | 9.5 / 14.4 / +4.9 | 11.1 / 15.4 / +4.3 | 50/50, 488/500 |
| Q4 FY25 | 6.4 / 4.7 / -1.7 | 5.7 / 4.9 / -0.8 | 0.8 / 11.3 / **+10.5** | 9.5 / 15.5 / **+6.0** | 50/50, 488/500 |
| Q1 FY26 | 6.2 / 5.4 / -0.8 | 5.9 / 5.2 / -0.7 | 14.8 / 9.3 / **-5.5** | 13.2 / 8.7 / -4.6 | 50/50, 486/500 |
| Q2 FY26 (ex-TM) | 7.0 / 7.2 / +0.2 | 6.6 / 6.6 / -0.0 | 7.9 / 10.8 / +2.9 | 18.0 / 17.4 / -0.6 | 49/49, 485/499 |
| Q3 FY26 (ex-TM) | 12.5 / 12.4 / -0.2 | 11.1 / 11.8 / +0.7 | 12.8 / 4.7 / **-8.1** | 18.2 / 10.8 / **-7.4** | 49/49, 486/499 |
| Q4 FY26 | 11.2 / 10.0 / -1.3 | 11.2 / 10.3 / -0.9 | 8.2 / 3.5 / -4.7 | 15.3 / 25.1 / **+9.8** | 50/50, 488/500 |
| Q1 FY27 | 18.4 / 18.0 / -0.4 | 18.9 / 19.1 / +0.2 | 11.8 / 4.8 / **-7.0** | 11.1 / 8.6 / -2.5 | 50/50, 488/500 |

- **Revenue:** no quarter is flagged. Every gap is within 1.7 points; the Nifty 500 gaps are within 0.9.
  Ours is slightly low in most quarters.
- **Profit:** 8 flags in 8 quarters (Nifty 50: 4, Nifty 500: 4). Even the unflagged quarters are off by up to 4.9 points.

## What drives the flagged profit gaps (top contributors, points of our growth)

Each flagged gap is led by one or two companies with a large one-off item in Screener's "Net Profit".
NSE's PAT (CMIE Prowess, "adjusted") appears to leave those items out.

- **Q4 FY25 N50 +10.5, N500 +6.0:** ITC 5,191 -> 19,808 (+6.5; the Mar-25 quarter includes the ITC Hotels
  demerger gain), Bharti Airtel 2,068 -> 12,476 (+4.6), TMPV 17,528 -> 8,556 (-4.0), IndusInd Bank
  2,349 -> -2,329 (-2.1), Adani Enterprises 352 -> 4,015 (+1.6).
- **Q3 FY26 N50 -8.1, N500 -7.4:** Bharti Airtel 16,135 -> 8,503 (-3.5 N50; its Dec-24 base is the
  quarter Indus Towers was consolidated), Adani Enterprises 229 -> 5,727 (+2.5), HUL 2,989 -> 6,603 (+1.7),
  SBI (+1.2), Tata Steel (+1.1). For the N500, IOC 2,147 -> 13,502 (+2.8) and IRB Infra 6,026 -> 211 (-1.4) also count.
- **Q4 FY26 N500 +9.8:** Vodafone Idea -7,167 -> 51,970 (+12.7 alone), JSW Steel 1,501 -> 19,243 (+3.8),
  ITC 19,808 -> 5,470 (-3.1, the base effect of Q4 FY25), Sammaan Capital 324 -> -8,101 (-1.8), IOC (+1.5).
- **Q1 FY27 N50 -7.0:** Reliance 30,783 -> 23,196 (-3.3; its Jun-25 base includes the Asian Paints stake
  sale), ONGC 11,554 -> 6,554 (-2.2), HDFC Bank (+1.4), TMPV 4,003 -> 859 (-1.4), Hindalco (+1.3).
- **Q1 FY26 N50 -5.5:** Reliance 17,445 -> 30,783 (+6.3), TMPV 10,587 -> 4,003 (-3.1), Kotak Bank
  7,448 -> 4,472 (-1.4; its Jun-24 base includes a stake-sale gain), Bharti (+1.3), Coal India (-1.0).
  Our growth is lower than NSE's even though Reliance's one-off raises it, so this gap is not explained by exceptional items alone.
- **Q2 FY25 N500 +5.3:** IOC 13,713 -> -449 (-4.0), Tata Steel -6,511 -> 759 (+2.0), Vedanta -915 -> 5,603 (+1.8),
  ONGC (-1.8), BPCL (-1.7). These are operating swings, not one-offs. This gap is the closest to the
  5-point line and is not explained.

Known reasons for the smaller gaps:

- NSE uses CMIE Prowess adjusted PAT and Prowess's own revenue definition for banks.
- Screener's consolidated "Net Profit" is before minority interest.
- Consolidated vs standalone: NSE does not say which basis it uses.
- 12 to 14 Nifty 500 members are missing from ours each quarter (no year-earlier quarter on Screener,
  mostly recent listings), and NSE may cover a different set.
- Results not yet filed when NSE's issue went to press.

## Not judged, reported

- **Medians:** they are close where NSE publishes them, except Q3 FY26: Nifty 500 PAT median 10.7 vs 18.4,
  Midcap 12.4 vs 19.1, Smallcap 9.8 vs 21.8, while the sales medians agree (12.2 vs 12.2). This is not explained.
- **Microcap 250 revenue:** +41% (Q4 FY25), +30% (Q1 FY26) and +48% (Q2 FY26). Rajesh Exports alone
  (91,445 -> 199,190 crore in Q4 FY25) adds 37 points, which looks like a fault in Screener's figures.
  NSE publishes no Microcap figure to compare with.
- **Q2 FY27 (ours only, NSE not out):** Nifty 50 profit -11.7%, of which TMPV's Sep-25 base of 76,248
  (the demerger gain) contributes -28 points.

## Conclusion

- **Revenue:** our Screener aggregate reproduces NSE's revenue growth for the Nifty 50 and Nifty 500.
- **Profit:** it does not reproduce NSE's profit growth, because Screener's "Net Profit" carries
  exceptional items that NSE's adjusted PAT leaves out.
- **Next step, if the owner wants one:** strip exceptional items per company. The other choice is a
  version that excludes outliers, such as "ex the top 2 contributors". Either would need a new rule
  and the owner's decision. Nothing goes in `data/` until then.

## Not checked

- The 5 spot-check rows against Screener by hand.
- Each one-off item named above against the company's own filing. Those attributions are leads,
  not evidence.
- NSE's member set for each quarter against ours.
- Whether Screener's quarterly figures have been restated since NSE's issue.
- The six tickers with "&" (M&M, M&MFIN, J&KBANK, ARE&M, GMRP&UI, GVT&D): we did not check by hand that each page is the right company. All six returned HTTP 200 on their own URL.
