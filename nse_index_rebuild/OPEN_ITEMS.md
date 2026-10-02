# Open items (2026-10-02), in the order to close them

Each row: what is unproven, what would close it, and where it shows up (`caveats` in `data/membership_history.json`).

| # | Item | What closes it | State |
|---|---|---|---|
| 1 | Two names with no symbol: Micro Inks Ltd (Nifty 500 exit 2010-04-06) and Vishal Retail Ltd (exit 2011-03-25) | NSE symbol as of that date, from any NSE or broker source | `UNMAPPED:` rows, 2 |
| 2 | Four symbols from public listings, not NSE: SIRPAPER, SMARTLINK, PGIL (House of Pearl), ASIANHOTNR | NSE symbol-change record or a 2010-2012 NSE notice naming the symbol | `SYMBOL_WEB_SECONDARY`, 4 |
| 3 | Jindal Saw in / Provogue out of Nifty 500 on 2012-03-07 | The NSE notice `ind_prs02032012` (dead link) from any copy | `WEB_SECONDARY_2012-03-07`, 2 |
| 4 | Gayatri Projects / Gujarat Fluorochemicals swap in Smallcap 250, 2020-03-27 vs 2020-06-26 | NSE statement of the effective date, or the Smallcap 250 list on a date inside the window | ambiguity, 1 |
| 5 | PEL to PIRAMALFIN treated as a rename; ISINs differ (INE140A01024 vs INE202B01038) | NSE notice for the merger: exit and entry, or substitution, and the date | `INFERRED_MERGER_SUCCESSOR`, 12 |
| 6 | G5 independent checkpoints: archived constituent files at 5+ dates per index | Wayback or fund-factsheet copies; first pass found none usable | not done |
| 7 | G7 blind second review of parsed events and the 8 OCR notices | A second reader, no sight of the output | not done |
| 8 | G4 anchor independence: today's lists against a second source on two days | NSE website view or factsheet, fetched twice | not done |
| 9 | G8 freeze and change log | Hash the released history; re-run G3 to G7 on any edit | not done |
| 10 | 10 dead announcement links | A copy of each; none is known to affect these indices | listed in `announcements/dead_links.txt` |
