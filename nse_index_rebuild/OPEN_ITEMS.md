# Open items (2026-10-02), in the order to close them

Each row: what is unproven, what would close it, and where it shows up (`caveats` in `data/membership_history.json`).

| # | Item | What closes it | State |
|---|---|---|---|
| 1 | ~~Two names with no symbol~~ closed: Micro Inks = MICRO, Vishal Retail = VISHALRET (now V2RETAIL), both from NSE's symbol-change file | - | closed |
| 2 | Four symbols from public listings, not NSE: SIRPAPER, SMARTLINK, PGIL (House of Pearl), ASIANHOTNR | NSE symbol-change record or a 2010-2012 NSE notice naming the symbol | `SYMBOL_WEB_SECONDARY`, 4 |
| 3 | Jindal Saw in / Provogue out of Nifty 500 on 2012-03-07 | The NSE notice `ind_prs02032012` (dead link) from any copy. Tried with no result (2026-10-02): NSE and niftyindices URLs (website shell), Wayback availability for 8 URL variants of the 2012-era paths (only a 2026 capture of the shell), two web searches. A relayed suggestion that it is a surveillance or trade-for-trade circular, and that 7 March was a corrigendum, is unverified and conflicts with the notice title seen in NSE's archive listing and with `ind_prs14032012` (7 March is the effective date). Untried: broker or fund-house circular archives, a printed copy. | `WEB_SECONDARY_2012-03-07`, 2 |
| 4 | Gayatri Projects / Gujarat Fluorochemicals swap in Smallcap 250 (and Nifty 500), effective 2020-03-27 or 2020-06-26. Evidence for 27 March: `ind_prs23032020` defers the rebalancing but says impact-cost compliance changes, which this swap is, apply w.e.f. 2020-03-27; `ind_prs13052020` voids only the releases of Feb 18, Mar 12 and Mar 19, not Mar 23. Evidence for 26 June: `ind_prs10062020` lists GAYAPROJ as excluded and FLUOROCHEM as included again (Nifty 500, Smallcap 250 and others), which would be incoherent if Gayatri had left on 27 March. The chain closes either way (the swap must count once). Currently applied as 26 June. Searched, no independent confirmation; Wayback has no constituent file inside the window (nearest 2019-02 and 2020-07-25, after the swap) | An NSE statement of the effective date, or a Smallcap 250 / Nifty 500 list or index-fund portfolio disclosure dated 2020-03-27 to 2020-06-25 | ambiguity, 1 |
| 5 | ~~PEL to PIRAMALFIN~~ closed: NSE notice `ind_prs15092025_1` removes PEL for the amalgamation (2025-09-23); PIRAMALFIN is a separate inclusion on 2026-03-30 | - | closed |
| 6 | G5 independent checkpoints: archived constituent files at 5+ dates per index | Wayback or fund-factsheet copies; first pass found none usable | not done |
| 7 | G7 blind second review of parsed events and the 8 OCR notices | A second reader, no sight of the output | not done |
| 8 | G4 anchor independence: today's lists against a second source on two days | NSE website view or factsheet, fetched twice | not done |
| 9 | G8 freeze and change log | Hash the released history; re-run G3 to G7 on any edit | not done |
| 10 | 10 dead announcement links | A copy of each; none is known to affect these indices | listed in `announcements/dead_links.txt` |
