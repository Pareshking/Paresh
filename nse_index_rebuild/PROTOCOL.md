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
| Nifty 50 | 14 | 0 | 0 | none |
| Nifty Next 50 | 20 | 15 | 6 | 2021-03-31 |
| Nifty Midcap 150 | 23 | 0 | 0 | none |
| Nifty Smallcap 250 | 44 | 0 | 0 | none |
| Nifty Microcap 250 | 32 | 0 | 0 | none |

- G3 holds for Nifty 50 back to 2019-03-29. G4, G5, G7 and G8 have not been done, so nothing is `PRODUCTION` yet.
- The 45 symbol changes in `rules/aliases.csv` are all `INFERRED_FROM_SYMBOL_CONTINUITY`: each was accepted because it removed a chain violation, not because an NSE circular was found. They fail G2 for production use until each circular is located.
- Every other range is `RESEARCH_ONLY` until its open items are closed.
