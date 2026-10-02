# NSE and Zerodha reference feeds: what was checked (2026-10-02)

All fetched without login through the agent proxy (NSE needs a browser User-Agent; no cookie was needed).

| feed | URL | content | use here |
|---|---|---|---|
| NSE symbol changes | `nsearchives.nseindia.com/content/equities/symbolchange.csv` | company, old symbol, new symbol, date (from 2019) | already the main source for `rules/aliases.csv` |
| NSE name changes | `.../content/equities/namechange.csv` | symbol, previous name, new name, date | adds company-name history; fetch failed once with an HTTP/2 error, retry works |
| NSE listed equities | `.../content/equities/EQUITY_L.csv` | symbol, name, listing date, ISIN, face value (today only) | ISIN per current ticker; a stable key across renames |
| NSE corporate actions | `www.nseindia.com/api/corporates-corporateActions?index=equities&from_date=DD-MM-YYYY&to_date=DD-MM-YYYY` | ex-date, record date, ISIN, subject (split, bonus, demerger, arrangement, dividend...) back to 2010: 35,489 rows | demerger/merger ex-dates, split/bonus for price adjustment |
| NSE index inclusion / exclusion workbook | `archives.nseindia.com/content/indices/IndexInclExcl.xls` | every inclusion and exclusion per index, one sheet per index (Nifty 50, Next 50, Nifty 500, sectoral and others), 1996 to 2020-09; NSE stopped updating it in 2020; no sheet for Midcap 150, Smallcap 250, Microcap 250 or Total Market | copy kept in `reference/IndexInclExcl.xls`; `crosscheck_inclexcl.py` compares it with the reconstruction |
| NSE index constituent lists | `www.niftyindices.com/IndexConstituent/ind_*list.csv` and `nsearchives.nseindia.com/content/indices/ind_*list.csv` | today's members of each index, from two hosts | `check_index_anchor.py` compares both with the history daily |
| Zerodha instruments | `api.kite.trade/instruments` | tradingsymbol, name, lot size, segment (today only, no ISIN) | liveness check that a ticker trades; no history |

## Findings

- Corporate actions are deep (2010 to date) but not complete: the Provogue demerger (ex-date 2012-03-07) is not in it, and
  it files Provogue under the ticker `PROVOGE`. That ticker corrected a wrong assumption in this rebuild (`PROVOGUE`).
- Jindal Saw's "Scheme Of Arrangement" ex-date of 2011-11-22 matches the date NSE removed it from Nifty 500.
- ISIN cross-check of the 105 ticker changes: 0 confirmed, 1 conflict, 104 not testable (the old ticker has no corporate
  action row, or the new one is missing from today's list). The conflict is PEL -> PIRAMALFIN: different ISINs
  (INE140A01024 vs INE202B01038), so it is a merger successor, not a rename, as `rules/aliases.csv` already labels it.
- Zerodha adds nothing for history. It is useful only to confirm a ticker is live today.

## Findings added 2026-10-02

- The inclusion / exclusion workbook is NSE's own table; comparing it with the reconstruction found a date fault in 54 events and 4 skipped events, and settled the 2012-03-07 and 2020 items (see `PROTOCOL.md`). Its ranges: Nifty 50 and Next 50 to 2020-07-31, Nifty 500 to 2020-09-14.
- NSE's live index API (`/api/equity-stockIndices`) answers 403 to this environment, so the two constituent-list hosts above are the second source for today's lists.
- `web.archive.org` is blocked by the build environment's network policy (the availability API works, captured pages do not), so no archived constituent file can be read from here.

## Daily sync (built)

`scripts/sync_nse_reference.py`, run by `.github/workflows/nse_reference_sync.yml` (daily, 02:45 UTC, also manual):
fetches `symbolchange.csv`, `namechange.csv`, `EQUITY_L.csv` and the last 45 days of corporate actions into
`data/reference/nse/` with `MANIFEST.json` (fetch time, rows, SHA-256) and `CHANGES.json` (new rows since the last run, and
those touching a name in the membership record, also printed as `::warning::` lines). It retries, refuses an empty or shrunken
feed, and fails the job on any fetch problem, which the scheduled-failure alert watches. It never edits
`data/membership_history.json`. The same workflow then runs `scripts/check_index_anchor.py` (today's lists on www.niftyindices.com and nsearchives.nseindia.com against the history, appended to `data/reference/nse/anchor_checks.jsonl`); the snapshot commits even if that step fails. Zerodha is not synced: it adds nothing beyond today's tickers.
