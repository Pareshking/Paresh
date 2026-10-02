# Verification protocol for production use

Use case: production trading, regulatory reporting, fund strategy.
Scope: Nifty 50, Nifty Next 50, Nifty Midcap 150, Nifty Smallcap 250, Nifty Microcap 250.

## Principles

1. **No self-assigned confidence numbers.** A snapshot is either `PRODUCTION`, `RESEARCH_ONLY` or `REJECTED`. Status is computed from the gates below, not asserted.
2. **Unit of release = (index, effective-date range).** A range is released only if every gate passes for that range. One failing event downgrades every earlier date for that index, because the reconstruction runs backward from today's list.
3. **Zero tolerance for known discrepancies.** "99%+" is met only when there are no unresolved discrepancies. A known open item is a failure, not a rounding error.
4. **Why not sampling alone.** If k independent spot-checks all match, the 95% upper bound on the share of bad snapshots is about 3/k (rule of three). Showing a bad-snapshot rate under 1% needs about 300 independent matches, which no source offers. Assurance therefore comes from deterministic chain closure (G3) for every date, with sampling (G5) as a check on it.
5. **Humans sign off.** This protocol does not certify regulatory compliance. Compliance, risk and legal sign-off are required and are not something this repo can supply.

## Gates (all must pass per release unit)

| Gate | Requirement | Evidence |
|---|---|---|
| G1 Source integrity | Every document used is archived with URL, fetch time (UTC) and SHA-256. A second fetch on a different day returns identical bytes for historical PDFs. | `current/MANIFEST.csv`, `announcements/` |
| G2 Event traceability | Every membership change cites a document and section. Parsed rows come from `events_raw.csv`. Every hand-made rule in `rules/overrides.csv` cites a document. Rows marked `INFERRED_*` are not allowed in a production range. | `rules/*.csv` evidence column |
| G3 Chain closure | Replaying all events backward from the anchor gives exactly N members (plus dummy placeholders, listed) at every effective date. No event adds a symbol already present or removes one that is absent. | `reverse2.py`, `open_issues.csv` empty for the range |
| G4 Anchor independence | The current list matches a second source with zero diff: NSE's website view and the index factsheet. Fetched on two different days. | to do |
| G5 Independent checkpoints | At least 5 historical dates per index are compared with a source outside the press releases (archived constituent files, factsheets, fund holdings disclosures). A single symbol mismatch fails that date and sends the range back to G3. | to do |
| G6 Corporate-action ledger | Renames, mergers, demergers, dummy placeholders, trading-segment shifts (BE/BZ/RR series), deferments and revocations each appear in the ledger with a document. | `rules/` |
| G7 Blind second review | A second reviewer re-derives at least 10% of events (random sample plus every manual override) from the PDFs without seeing the output. Zero discrepancies. | to do |
| G8 Freeze and change control | Released data carries a hash and a change log. Any edit re-runs G3 to G7 for the affected range. | to do |

## Event types that must be handled explicitly

- Replacement tables (include/exclude) and their effective date (close of the previous trading day)
- Revocations ("Inclusion revoked" / "Exclusion revoked") and deferments, for example the March 2020 deferral voided by `ind_prs13052020`
- Accelerated removals, for example Yes Bank on 2020-03-19
- Symbol or name changes (aliases), with a last-old and first-new date
- Mergers, demergers and delistings, including "DUMMY" placeholder symbols that appear in the official files
- Shifts between index tiers that appear only as an inclusion in one index and an exclusion in another

## Release rule

A date range is `PRODUCTION` only if G1 to G8 all pass. A range with open items is `RESEARCH_ONLY`. A range contradicted by an independent source is `REJECTED`.

## Status as of 2026-10-02 (computed by `gate_check.py`)

| Index | Snapshots reconstructed | Sizes wrong | Open chain breaks | Latest break |
|---|---|---|---|---|
| Nifty 50 | 33 | 0 | 0 | none |
| Nifty Next 50 | 47 | 0 | 0 | none |
| Nifty Midcap 150 | 37 | 0 | 0 | none |
| Nifty Smallcap 250 | 59 | 0 | 0 | none |
| Nifty Microcap 250 | 32 | 0 | 0 | none |

- G3 (chain closure) holds for every index over its whole reconstructed range, and the gate script (`reverse2.py`) exits 0 with zero unresolved events: Nifty 50 and Next 50 from 2010-04-08, Smallcap 250 from 2016-04-29, Midcap 150 from 2016-09-30 and Microcap 250 from 2021-09-30 (its launch). Midcap 150 and Smallcap 250 only came into existence on 2016-04-01 (NSE restructuring notice of 2016-02-22), so nothing earlier is reconstructed for them. For all five, the earliest snapshot is the state implied before the first parsed event; the announcement archive downloaded here starts in January 2010, so membership before that is not claimed.
- Nifty 50 correctly holds 51 securities from 2016-04-01 to 2017-05-26 because Tata Motors DVR was an additional security (stated in the 2016-02-22 notice); the size check allows for DVR shares.
- G2 (traceability): 46 of the 47 symbol changes in `rules/aliases.csv` are confirmed by NSE documents: 36 by NSE's "Changes in Symbols" file (`reference/nse_symbolchange.csv`, hashed and dated), 10 by individual NSE circulars (one read from a broker-hosted copy, one via an NSE Clearing circular). The remaining one, PEL to PIRAMALFIN, is a merger successor and is `INFERRED_MERGER_SUCCESSOR`, so it still fails G2 for production use. Ranges that involve it are `RESEARCH_ONLY`.
- Known ambiguity: Smallcap 250 membership of GAYAPROJ and FLUOROCHEM between 2020-03-27 and 2020-06-25 is unresolved (`rules/ambiguities.csv`); ranges overlapping that window are not production-grade.
- Eight announcements were image-only and were read by OCR (`ocr_pdf.py`; 344 of 345 symbols matched on a text-layer control). One line (the effective date of `ind_prs23082021`) was transcribed by hand. OCR output has not been blind-reviewed (G7).
- Known source limits: 10 announcement links on the NSE Indices site return the website shell instead of a PDF (`announcements/dead_links.txt`); none is known to affect these indices, but absence of a notice cannot be proven. Releases before 2012 list companies without symbols, so symbols were resolved by company name from later releases (`parse_events.py`, one manual mapping for Sesa Goa). The same change announced in two releases for one effective date is counted once (the later-published copy), which is an assumption the gate cannot independently test.
- G4, G5, G7 and G8 have not been done, so nothing is `PRODUCTION` yet. Chain closure shows the announcements are internally consistent and agree with today's NSE lists; it does not prove each announcement was complete.
