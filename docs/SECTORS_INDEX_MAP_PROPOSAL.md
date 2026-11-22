# Sector ↔ NSE sector index map: approved by the owner, 21 Nov 2026

**Owner, 21 Nov 2026:** every question answered as recommended below, and MQ4 yes: Nifty Consumer Services and Nifty
Commercial & Transport Services move to "Sector" and are the headlines for Consumer Services and Services, so 18
sectors have an index and 37 indices sit on the page (`SECTORS_REQUIREMENTS.md`, "Owner's decisions", items 1-6).
MQ7 waits (a TODO). Committing the map as `data/reference/nse_sector_index_map.csv` is part of the build.

Written 21 Nov 2026 for `SECTORS_REQUIREMENTS.md` row P3 (owner, 21 Nov 2026: NSE's sector indices move to
Sectors, beside each group's equal-weighted figure, "with an industry ↔ index map to show the owner first").
Nothing reads this map yet. Once approved it becomes `data/reference/nse_sector_index_map.csv` (a reference
table, so it stays in git under S172), with one line of reason per row, as `nse_index_aliases.csv` carries its
evidence.

Readings below are closes of **20 Nov 2026**: the ranking table (750 stocks) and the app's copy of NSE's daily
index files (`data/nse_indices_history.parquet` + `data/nse_indices_recent.csv`), computed by
`scripts/sectors_mockup_figures.py`. Index names are those in `data/reference/nse_index_groups.csv`.

## First, what the site calls an "industry"

The site's "Industry" column holds the 22 groups in the "Industry" column of NSE's index lists
(`data/indices/ind_niftytotalmarket_list.csv`): Capital Goods, Financial Services, Healthcare and so on. In NSE's
own four-level classification these 22 are the **Sector** level (Macro-economic sector, 12 → **Sector, 22** →
Industry, about 59 → Basic industry, about 197). `data/reference/historical_industries.csv` shows the same names
under its `SECTOR` column. So the site says "industry" where NSE says "sector", and the Sectors page itself says
both ("Sector leadership map" next to "Industry leaderboard"). Decision B in `SECTORS_REQUIREMENTS.md` asks
which word to use. This file says **sector**, NSE's word.

A consequence: the site knows each stock's sector only, not its NSE industry or basic industry. NSE's finer
indices (Bank, NBFC, Capital Markets, Insurance, Hospitals, Pharma) can be shown, but they cannot get an
equal-weighted figure of their own from the 750 without collecting each stock's basic industry (question MQ7).

## The map

Each of the 22 sectors gets at most one **headline** index, the one its equal-weighted figure is set beside.
Every other sector index sits under the sector it belongs to, so all 35 appear once.

| NSE sector | Ranked stocks | Headline NSE index | In NSE's daily file since | Why | Other NSE indices under it | Question |
|---|---|---|---|---|---|---|
| Capital Goods | 121 | Nifty Capital Goods | 15 Jun 2026 | Same name; the only sector index for it. Themes that overlap (Nifty India Manufacturing, Nifty India Defence) span several sectors and stay on Indices | — | MQ1 |
| Financial Services | 117 | Nifty Financial Services | 21 Feb 2012 | Same name, the index readers know, 14 years live. Banks are 35 of the 117 ranked names and about 52% of their market value, and the index is led by HDFC Bank and ICICI Bank: the gap to our equal-weighted figure is the point of row P2 | Nifty Bank, Nifty Private Bank, Nifty PSU Bank, Nifty Financial Services 25/50, Nifty Financial Services Ex-Bank, Nifty MidSmall Financial Services, Nifty NBFC, Nifty Housing Finance, Nifty Capital Markets, Nifty Insurance, Nifty Small Finance Banks & Microfinance Institutions | MQ2 |
| Healthcare | 67 | Nifty Healthcare Index | 19 Nov 2020 | Pharma, hospitals and diagnostics, as NSE's Healthcare sector; five years live | Nifty Pharma, Nifty500 Healthcare, Nifty MidSmall Healthcare, Nifty Hospitals | MQ3 |
| Automobile and Auto Components | 49 | Nifty Auto | 21 Feb 2012 | Same sector; holds component makers as well as vehicle makers (Bosch, Motherson are in the sector's top 8 by value) | — | — |
| Chemicals | 44 | Nifty Chemicals | 11 Mar 2025 | Same name, the only one | — | — |
| Fast Moving Consumer Goods | 43 | Nifty FMCG | 21 Feb 2012 | Same name | Nifty Sugar & Ethanol (sugar sits in NSE's FMCG sector) | MQ5 |
| Consumer Services | 43 | **none in the "Sector" group**; Nifty Consumer Services if re-grouped | 15 Jun 2026 | Retail, e-commerce, hotels, travel (Eternal, DMart, Trent, Indian Hotels, Nykaa, Swiggy). Nifty Retail covers only part. Nifty Consumer Services exists, but our groups file puts it under Theme | Nifty Retail | MQ4 |
| Consumer Durables | 40 | Nifty Consumer Durables | 27 Jan 2020 | Same name | — | — |
| Information Technology | 40 | Nifty IT | 21 Feb 2012 | Same sector; ten large IT services firms carry it (TCS, Infosys, HCL Tech lead the sector by value) | Nifty MidSmall IT & Telecom (spans IT and Telecom; listed under IT, its larger part) | — |
| Metals & Mining | 27 | Nifty Metal | 21 Feb 2012 | Same sector | — | — |
| Services | 24 | **none in the "Sector" group**; Nifty Commercial & Transport Services if re-grouped | 15 Jun 2026 | Ports, airlines, airports, logistics, distribution (Adani Ports, IndiGo, GMR Airports, Delhivery, Concor). Our groups file puts the matching index under Theme | — | MQ4 |
| Construction | 23 | Nifty Construction | 15 Jun 2026 | Same name. Nifty Infrastructure (a theme) spans power, telecom, cement and ports, so it is not this sector | — | MQ1 |
| Power | 23 | Nifty Power | 15 Jun 2026 | Same name. Nifty Energy mixes power with oil and gas and is listed under Oil & Gas | — | MQ1, MQ6 |
| Realty | 20 | Nifty Realty | 21 Feb 2012 | Same name. The 20 ranked names include two listed REITs (Embassy, Bagmane); whether Nifty Realty holds REITs was not checked | — | — |
| Oil Gas & Consumable Fuels | 19 | Nifty Oil & Gas | 27 Jan 2020 | Oil and gas producers, refiners, gas distributors (Reliance, ONGC, IOC, BPCL, GAIL). Coal India sits in this NSE sector; whether Nifty Oil & Gas holds it was not checked | Nifty Energy | MQ6 |
| Textiles | 12 | none | — | NSE publishes no textiles index | — | — |
| Telecommunication | 12 | Nifty Telecommunications | 15 Jun 2026 | Same name | (Nifty MidSmall IT & Telecom, under IT) | MQ1 |
| Construction Materials | 12 | Nifty Cement | 17 Feb 2026 | All 12 ranked names are cement makers (UltraTech, Grasim, Ambuja, Shree, JK Cement ... Birla Corp) | — | — |
| Media Entertainment & Publication | 8 | Nifty Media | 21 Feb 2012 | Same sector | — | — |
| Utilities | 4 | none | — | Water treatment and similar (Wabag, Ion Exchange, EIEL, Refex); fewer than five ranked stocks, so the page's sector sections leave it out | — | — |
| Diversified | 1 | none | — | One stock (Godrej Industries); a group of one is a stock, not a sector | — | — |
| Forest Materials | 1 | none | — | One stock (JK Paper) | — | — |

16 sectors get a headline index from the "Sector" group; 18 if MQ4 is answered yes. 19 sector indices sit under
a headline (all 35 placed once; the script fails if one is left over).

## Questions for the owner

- **MQ1. Indices launched on 15 Jun 2026.** Capital Goods (the largest sector, 121 stocks), Construction, Power
  and Telecommunications have five months of live history in NSE's file; Cement has nine. They can be compared
  over one and three months only, and get a 6M figure in Dec 2026 and a 1Y figure in Jun 2027. Recommended:
  map them now, show "—" with the launch date where a window is longer than their life (the Indices page's rule).
  Against: a sector compared on fewer windows than the others reads unevenly; the alternative is no headline index
  for them until each has a year.
- **MQ2. Financial Services: which headline?** Recommended: Nifty Financial Services, the index readers know,
  because row P2 exists to show where a few large companies carry a sector, and Financials is the clearest case
  (over three months the index +10.2%, the sector's 117 ranked stocks, equal-weighted, −1.5%). Against: Nifty
  MidSmall Financial Services (live Aug 2022) is closer to what the 750 holds and would show a smaller gap
  (−1.1% over three months) that is about membership, not weighting. Both are in the table either way.
- **MQ3. Healthcare: which headline?** Recommended: Nifty Healthcare Index (live Nov 2020). Against: Nifty500
  Healthcare is the closest in membership to the 750 but has been live only since 2 Jul 2025; Nifty Pharma has
  the longest history but leaves out hospitals and diagnostics.
- **MQ4. Two indices our groups file calls themes.** Nifty Consumer Services and Nifty Commercial & Transport
  Services entered NSE's daily file on 15 Jun 2026, the same day as Nifty Capital Goods, Construction, Hospitals,
  Housing Finance, Insurance, NBFC, Power, Retail and Telecommunications, which the file calls sectors. They match
  NSE's Consumer Services and Services sectors by name. Recommended: move both to "Sector" in
  `nse_index_groups.csv` (so they leave Indices for Sectors) and make them the headline for those two sectors.
  Against: the grouping is ours, written after NSE's four headings on niftyindices.com, which this machine cannot
  reach; if NSE lists them under thematic indices, moving them departs from NSE. Not checked against NSE's
  press release or methodology.
- **MQ5. Sugar & Ethanol under FMCG.** Recommended, as sugar sits in NSE's FMCG sector. Against: ethanol is a
  fuel; it could stand alone at the end of the table.
- **MQ6. Nifty Energy: under Oil & Gas or Power?** Recommended under Oil & Gas (Reliance and ONGC are its
  largest names). Against: it holds NTPC and Power Grid too; it could sit under both, which shows its figures
  twice.
- **MQ7. Finer matches later?** With each stock's NSE basic industry (from NSE's quote service, which the site
  does not store today) the page could set Nifty Bank beside the 750's banks, Nifty NBFC beside its NBFCs, and so
  on. Recommended: not in this makeover; a TODO once the map above is approved.

## Checks, and what was not checked

- Every one of the 35 sector indices is published for 20 Nov 2026, the session of the ranking table.
- The launch dates are the first day NSE's daily file lists each index (the S168 store's rule); not compared with
  NSE's press releases, except as noted on the Indices page.
- Not checked: any sector index's constituents or methodology (niftyindices.com refuses this machine), so how
  far each index's membership matches the sector's ranked stocks is unknown; no sector index against a second
  source (no ETF on a sector index is in the price store).
