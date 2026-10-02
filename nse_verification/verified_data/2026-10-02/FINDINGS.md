# 2026-10-02 official snapshot vs repo data

Source: niftyindices.com `IndexConstituent/*.csv`, fetched 2026-10-02T09:53Z (see MANIFEST.csv for URL and SHA-256).
These files carry no effective date; the fetch time is the only date evidence. Which NSE circular
produced this list is NOT yet established.

| Index | Official rows | Repo "2026-10-02" rows | Symbols only in official | Symbols only in repo |
|---|---|---|---|---|
| Nifty 50 | 50 | not in repo | - | - |
| Nifty Next 50 | 50 | not in repo | - | - |
| Midcap 150 | 150 | 150 | 13 | 13 |
| Smallcap 250 | 251 | 250 | 38 | 37 |
| Microcap 250 | 254 | 251 | 64 | 58 |

## Findings
1. The repo's latest snapshot does not match NSE's current files (about 9% of Midcap, 15% of Smallcap, 25% of Microcap differ). Either the repo snapshot is stale/mislabelled or the official files reflect a newer reconstitution. Not resolved.
2. Official Smallcap/Microcap files contain placeholder symbols (e.g. DUMMYHEG, DUMMYINGL1, DUMMYINGL2, DUMMYINXGN, DUMMYTRVN) and non-EQ series (BE, RR). These explain official row counts above 250 and are a candidate cause for some count "anomalies" in the repo data. Unconfirmed until the matching circulars are read.
3. Nothing here is verified against a circular yet. Status of every date remains PENDING.

## Next
Locate the NSE index-maintenance circulars for the Sep-2026 and Mar-2026 reconstitutions and tie each change to a circular, working backward by semi-annual rebalance date.
