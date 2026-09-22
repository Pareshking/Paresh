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

## Recovery

1. Enumerate archive/manifests/**/current.json.
2. Resolve each current pointer through R2DatasetReader.
3. Verify manifest schema and revision identity.
4. Verify object HEAD size and full object SHA/byte count.
5. For a pinned research run, resolve its exact dataset/as_of/revision SHA, never current.json.
6. If the current pointer is damaged but an immutable manifest exists, recover by explicitly selecting the verified immutable revision. Do not overwrite historical revisions.
7. Re-run the recovery and continuity audits after repair.

The recovery audit is read-only and therefore safe to schedule routinely.
