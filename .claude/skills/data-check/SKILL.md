---
name: data-check
description: Check, fix or explain a figure, price, return, market cap, index level, breadth reading or dataset of the NSE Momentum Terminal. Use before saying a number is right or wrong, before changing how data is built, and before showing held data on a page.
---

# Checking data

The prices are the product: data correctness comes before features (CLAUDE.md). The full rules are in `docs/DATA_CORRECTNESS.md`. Read it first. It says which source is trusted for what, and lists the findings already explained, so they are not investigated twice.

## Steps

1. **Find where the figure comes from.**
   - `docs/DATA_CATALOGUE.md` (each dataset, its writer and its readers);
   - `docs/PRICE_PIPELINE.md` (prices and corporate actions);
   - `docs/THREE_SYSTEMS.md` (the 750, the Nifty 1000, > ₹2,000 Cr, Combined);
   - `docs/MEMBERSHIP_FROM_NOTICES.md` (index membership).

   Name the file, the function and the line.
2. **Check against an independent source, dated and quoted.** A check that reproduces our own numbers, or text pasted from another tool, is a lead, not evidence.
   - **Closes:** BSE's bhavcopy (`scripts/bse_bhavcopy.py`; `SttlmPric`, not the last trade).
   - **Adjusted returns over a split or bonus, and market cap:** Screener.in's daily chart (`/api/company/<id>/chart/?q=Price&days=400`, ids in `data/screener_company_ids.json`) and its company page.
   - **FPI flows:** NSDL's own table.

   Plain requests only. If a source blocks us (NSE, BSE), report it; do not work around it: no browser user agent, no disguise.
3. **A gap in NSE's files is not yet a halt.** NSE does not list a security on days it did not deal in it. BSE's bhavcopy says whether it traded. Check both before calling a gap a halt or a download fault.
4. **Never change a price by hand.**
   - Fix the rule, or add a `data/nse_prices/notes.json` correction with its evidence.
   - Then rebuild the long file and run the audits.
   - Files the nightly sync writes (`data/`) are not edited by hand.
5. **Say what was not checked.** Every finding ends with its "not checked" list.
6. **Held data shown for the first time:**
   - record its trust note from `docs/DATA_CORRECTNESS.md`;
   - mark known breaks on the chart, for example NSE's P/E basis change of 31 Mar 2021 and its P/B basis changes of 29 Sep 2023 and 23 Sep 2024;
   - name who reads it (nothing is written that nothing reads, S195 §4).

## Write it down

- A finding goes in `docs/DATA_CORRECTNESS.md` (explained findings) or `docs/TODO.md` (open work) the same day, with how we will know it is done.
- A one-off audit goes in `docs/archive/`, for example `docs/SITE_AUDIT_2026-11-28.md`, whose §1 is the model for an outside-source table.
