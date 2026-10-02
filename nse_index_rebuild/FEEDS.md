# NSE and Zerodha reference feeds: what was checked (2026-10-02)

All fetched without login through the agent proxy (NSE needs a browser User-Agent; no cookie was needed).

| feed | URL | content | use here |
|---|---|---|---|
| NSE symbol changes | `nsearchives.nseindia.com/content/equities/symbolchange.csv` | company, old symbol, new symbol, date (from 2019) | already the main source for `rules/aliases.csv` |
| NSE name changes | `.../content/equities/namechange.csv` | symbol, previous name, new name, date | adds company-name history; fetch failed once with an HTTP/2 error, retry works |
| NSE listed equities | `.../content/equities/EQUITY_L.csv` | symbol, name, listing date, ISIN, face value (today only) | ISIN per current ticker; a stable key across renames |
| NSE corporate actions | `www.nseindia.com/api/corporates-corporateActions?index=equities&from_date=DD-MM-YYYY&to_date=DD-MM-YYYY` | ex-date, record date, ISIN, subject (split, bonus, demerger, arrangement, dividend...) back to 2010: 35,489 rows | demerger/merger ex-dates, split/bonus for price adjustment |
| Zerodha instruments | `api.kite.trade/instruments` | tradingsymbol, name, lot size, segment (today only, no ISIN) | liveness check that a ticker trades; no history |

## Findings

- Corporate actions are deep (2010 to date) but not complete: the Provogue demerger (ex-date 2012-03-07) is not in it, and
  it files Provogue under the ticker `PROVOGE`. That ticker corrected a wrong assumption in this rebuild (`PROVOGUE`).
- Jindal Saw's "Scheme Of Arrangement" ex-date of 2011-11-22 matches the date NSE removed it from Nifty 500.
- ISIN cross-check of the 105 ticker changes: 0 confirmed, 1 conflict, 104 not testable (the old ticker has no corporate
  action row, or the new one is missing from today's list). The conflict is PEL -> PIRAMALFIN: different ISINs
  (INE140A01024 vs INE202B01038), so it is a merger successor, not a rename, as `rules/aliases.csv` already labels it.
- Zerodha adds nothing for history. It is useful only to confirm a ticker is live today.

## Daily sync (built)

`scripts/sync_nse_reference.py`, run by `.github/workflows/nse_reference_sync.yml` (daily, 02:45 UTC, also manual):
fetches `symbolchange.csv`, `namechange.csv`, `EQUITY_L.csv` and the last 45 days of corporate actions into
`data/reference/nse/` with `MANIFEST.json` (fetch time, rows, SHA-256) and `CHANGES.json` (new rows since the last run, and
those touching a name in the membership record, also printed as `::warning::` lines). It retries, refuses an empty or shrunken
feed, and fails the job on any fetch problem, which the scheduled-failure alert watches. It never edits
`data/membership_history.json`. Zerodha is not synced: it adds nothing beyond today's tickers.
