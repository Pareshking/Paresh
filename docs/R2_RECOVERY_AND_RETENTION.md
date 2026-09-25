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
