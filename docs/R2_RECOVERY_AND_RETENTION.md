# R2 Retention and Recovery Procedure

## Retention policy

R2 revisions are content-addressed and immutable. No automated deletion is authorized by this procedure.

A future retention policy must be approved only after confirming:
- every current pointer has at least one recoverable immutable revision;
- research runs retain their explicit dataset/as_of/revision SHA pins;
- same-date revisions needed for reproducibility remain available;
- an export or archival strategy exists before deletion;
- recovery audit passes before and after any approved retention action.

Until those conditions are implemented, retention is **retain indefinitely**.

### Approved policy (owner, 2026-09-25)

The 30-day size report (`r2_archive_inventory.yml`, `STORAGE=` lines) showed
723 MB, growing about 35 MB a day (~9 GB a year). Nearly all of it comes from
two datasets that are republished in full every day: `prices/yahoo`
(~25 MB/day) and `snapshots/application`.

- **`prices/yahoo` and `snapshots/application`:** keep the last **7** as_of dates
  plus the last as_of of **every calendar month**. This keeps the archive under
  about 1 GB.
- **Every other dataset:** full history, never touched.

How it is applied (`scripts/r2_retention.py`, workflow `R2 retention`):

1. **Dry run by default.** A push to the script, and any dispatch without
   `apply`, only prints the plan: the dates kept and dropped, every key to be
   deleted, and `RETENTION_DELETE_COUNT`.
2. **Deleting needs `apply=true` and `expect_deletes`** equal to that count. If
   the archive changed since the dry run, the counts differ and nothing is
   deleted.
3. **The newest date is always kept,** so every "current" reader resolves
   exactly as before. Research pins are made from current, so they survive too.
4. **Only keys directly under each dataset are considered.** `prices/yahoo/raw`
   and `prices/yahoo/bootstrap` never match.
   - A payload is deleted only if it sits under its own dataset/date path and no
     kept manifest names it.
   - A manifest pointing anywhere else makes the whole run refuse.
5. **Order:** the pointer first, then the manifests, then the payloads.
6. **The recovery audit runs after every apply.**
7. **Newest revision per kept date** (owner, item 7). A date can be
   republished several times a day, which is about 5 revisions per date today.
   On each kept date, every revision goes except two:
   - the one `current.json` names;
   - the one `resolve_latest_revision()` picks (newest `created_at`).

   These two are nearly always the same. Keeping both means neither reader
   changes its answer.
   - If a date's pointer or `created_at` values cannot be read, that date is
     left whole and printed as `SKIPPED`.
   - Superseded revisions count toward `SUPERSEDED=`.
8. **Weekly dry run:** Sunday at 03:17 UTC. It is watched by the scheduled-failure
   alert, so a refused plan raises an issue.

The month-end copies are the archival strategy that the conditions above ask
for.

**No deletion has been run.** The first one needs the owner to confirm the
dry-run list.

## Recovery

1. Enumerate archive/manifests/**/current.json.
2. Resolve each current pointer through R2DatasetReader.
3. Verify manifest schema and revision identity.
4. Verify object HEAD size and full object SHA/byte count.
5. For a pinned research run, resolve its exact dataset/as_of/revision SHA, never current.json.
6. If the current pointer is damaged but an immutable manifest exists, recover by explicitly selecting the verified immutable revision. Do not overwrite historical revisions.
7. Re-run the recovery and continuity audits after repair.

The recovery audit is read-only and therefore safe to schedule routinely.

### `snapshots/application` is no longer published (owner, 2026-09-25)

`prices.parquet` is a 2-year cut of `prices_full.parquet`, which is already
archived as `prices/yahoo`. The app reads `prices.parquet` from the release
asset, and nothing ever read it from R2. So the daily sync stops sending it to
R2. Its 14 existing copies (137 MB) stay in place until the owner deletes them.
Until then, retention still trims their superseded revisions.
