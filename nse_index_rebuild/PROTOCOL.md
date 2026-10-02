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
| G4 Anchor independence | The current list matches a second source with zero diff: NSE's website view and the index factsheet. Fetched on two different days. | `scripts/check_index_anchor.py` compares www.niftyindices.com and nsearchives.nseindia.com with the history daily; first run 2026-10-02 agreed on all 7 indices; log in `data/reference/nse/anchor_checks.jsonl` |
| G5 Independent checkpoints | At least 5 historical dates per index are compared with a source outside the press releases (archived constituent files, factsheets, fund holdings disclosures). A single symbol mismatch fails that date and sends the range back to G3. | `crosscheck_inclexcl.py` against NSE's own IndexInclExcl.xls: every event 2010 to 2020 for Nifty 50, Next 50 and Nifty 500; not available for Midcap 150, Smallcap 250, Microcap 250, Total Market |
| G6 Corporate-action ledger | Renames, mergers, demergers, dummy placeholders, trading-segment shifts (BE/BZ/RR series), deferments and revocations each appear in the ledger with a document. | `rules/` |
| G7 Blind second review | A second reviewer re-derives at least 10% of events (random sample plus every manual override) from the PDFs without seeing the output. Zero discrepancies. | `reference/blind_review/`: an independent AI reader re-derived 22 random notices (1,126 events, 24.8% of the four indices the workbook does not cover) with zero discrepancies; manual overrides and a human reviewer not covered |
| G8 Freeze and change control | Released data carries a hash and a change log. Any edit re-runs G3 to G7 for the affected range. | `data/membership_history.freeze.json`, `freeze_history.py --check` in CI |

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
| Nifty Midcap 150 | 38 | 0 | 0 | none |
| Nifty Smallcap 250 | 61 | 0 | 0 | none |
| Nifty Microcap 250 | 32 | 0 | 0 | none |
| Nifty 500 | 133 | 0 | 0 | none |


Coverage: Nifty 50, Next 50 and Nifty 500 from 2010-01-01; Midcap 150 and Smallcap 250 from their launch, 2016-04-01; Microcap 250 from 2021-09-30; Total Market from 2021-10-29 (its first reconstructed snapshot). The history is `data/membership_history.json`; the open-item list is `OPEN_ITEMS.md`.

- **G3 chain closure.** Replaying every event backward from today's NSE lists leaves exactly the right number of members at every effective date (50 / 50 / 150 / 250 / 250 / 750 / 500) and no event adds a name already present or removes one that is absent; `reverse2.py` exits 0 with zero unresolved events and `validate_history.py` finds 0 differences between the history file and the reconstruction over 384 end-of-day states. Nifty 50 holds 51 securities from 2016-04-01 to 2017-05-26, and Nifty 500 and Total Market hold one extra while NSE counted the Tata Motors DVR as an additional security (stated in the 2016-02-22 notice); the size check allows for DVR shares.
- **G2 traceability.** Every event comes from a notice in `announcements/`. The 105 ticker changes in `rules/aliases.csv` each cite NSE's "Changes in Symbols" file or an NSE circular (PEL to PIRAMALFIN is not a rename: NSE's notice `ind_prs15092025_1` removes PEL for the amalgamation on 2025-09-23 and includes PIRAMALFIN separately on 2026-03-30, so there is no alias). All 14 name-only exits of 2010-2011 have symbols (`rules/name_symbol_map.csv`: 12 from NSE's corporate-action feed, 2 from NSE's symbol-change file). The 160 manual rules in `rules/overrides.csv` each cite a document. The 2012-03-07 swap (Jindal Saw in, Provogue out) and the 2020 swap (Gayatri out, Fluorochemicals in on 2020-06-26, not on 2020-03-27) are confirmed by NSE's own workbook, so the history's `caveats` list is empty. No `INFERRED_*` rows remain.
- **Cross-check against NSE's own workbook (G5, three indices).** `IndexInclExcl.xls` (NSE, last saved 2020-09-22) lists every inclusion and exclusion. `crosscheck_inclexcl.py` compares it with the reconstruction event by event: Nifty 50 76 of 76, Next 50 213 of 214, Nifty 500 1,078 agree with no date difference; 38 differences remain, all explained in `rules/inclexcl_known_differences.csv` (a company named differently in the two sources, one case where the press release and the workbook name different companies, two rows the workbook lists twice). It runs in CI. The comparison found and fixed two parser faults: a notice with several dates was given one date (54 events moved to the date stated for their section; the Nifty 50 change of September 2020 had been dated 14 instead of 25 September), and a table with an Effective Date column was skipped (4 Nifty 500 events, April 2012).
- **Union check.** `cross_check.py`: from October 2016 Nifty 500 equals Nifty 50 + Next 50 + Midcap 150 + Smallcap 250 on all compared dates apart from the DVR share; Total Market equals Nifty 500 + Microcap 250 since November 2021. These pairs come from separate event streams, so they validate each other and, through Nifty 500, tie Midcap 150 and Smallcap 250 to the workbook until September 2020.
- **G4 anchor.** `scripts/check_index_anchor.py` compares today's lists on www.niftyindices.com and nsearchives.nseindia.com with the history, daily (`nse_reference_sync.yml`), recording each run in `data/reference/nse/anchor_checks.jsonl`. First run 2026-10-02: all 7 indices agree on both hosts.
- **G7 second reading.** An independent AI reader re-derived 22 random notices (1,126 events, 24.8% of the events of Midcap 150, Smallcap 250, Microcap 250 and Total Market) from the notice texts alone: zero differences (`reference/blind_review/`). It is a second AI reading, not a person, and does not cover the manual rules or the notices read by OCR.
- **G8 freeze.** `data/membership_history.freeze.json` holds a SHA-256 of the history through 2026-09-30 and a continuous change log; `freeze_history.py --check` runs in the reconstruct CI job.
- **OCR.** Eight announcements were image-only and were read by OCR (`ocr_pdf.py`; 344 of 345 symbols matched on a text-layer control); one line (the effective date of `ind_prs23082021`) was transcribed by hand. They have not been read by a second person.
- **Source limits.** 10 announcement links on the NSE Indices site return the website shell instead of a PDF (`announcements/dead_links.txt`); none is known to affect these indices, but absence of a notice cannot be proven. `web.archive.org` is blocked from the build environment, so no archived constituent file could be read; a first pass found no usable capture.
- **Not met.** No outside constituent list is available for Midcap 150, Smallcap 250 (beyond the union check), Microcap 250 and Total Market before today; the G7 reading is by an AI reader and a person has not re-derived a sample; the notices' completeness rests on chain closure and the workbook, not on an NSE statement. Compliance sign-off is not something this repository can supply.
- **Adoption.** The repository owner adopted the history for production use on 2026-10-02. Nothing here certifies it for regulatory use.
