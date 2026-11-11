# Deletions waiting on the owner

Owner, 11 Nov 2026: *"Record items which required delete as I am on mobile and
can't do it, whatever possible please delete it."*

Nothing on this page could be deleted from the cloud session. Both items are
outside what it can reach, for two different reasons, both verified on 11 Nov:

- **R2** — no credentials at all. `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`,
  `R2_ACCOUNT_ID`, `R2_BUCKET` and `R2_ENDPOINT` are all unset in the
  container, so no object can be listed, let alone removed.
- **GitHub release assets** — refused by the platform, not by a missing
  permission we could grant:
  `HTTP 403: Creating, editing, or deleting releases is not permitted for this
  session type.`

Each item below states what it is, why it is safe to remove, **what to check
before removing it**, and the exact command. Check first in every case: a
deletion that turns out to be wrong cannot be undone, and two of the three
candidates originally on this list did not survive their own check.

---

## 1. The BSE scratch prefix on R2 — 1,221.8 MiB, 39% of the bucket

`scratch/bse_bhavcopy_2026-10-03/` — 23 objects: 19 raw tar files, the built
table, the gap CSV, `status.csv` and `MANIFEST.json`.

**Why it is safe.** The alignment work it was created for has shipped: the BSE
fill of NSE-only gaps (S38), the ISIN-first `bse_fill.map_code` the gap audit
now shares with the fill (S52/S53), and `bse_daily.yml` keeping both the
release asset and `archive/bse/daily` current. Nothing under the prefix is a
live source — the table is superseded, the gap CSV is rebuilt on every
long-file build, and the raw tars are re-downloadable with
`scripts/bse_bhavcopy.py --mode download`. It sits outside every dataset
`scripts/r2_retention.py` knows, so nothing prunes it and nothing reads it.

**The one thing that used to block it is already fixed.**
`.github/workflows/bse_daily.yml` seeded from
`scratch/bse_bhavcopy_2026-10-03/bse_daily.parquet` as its third fallback;
since commit `b4f7111` it exits with an instruction to re-run with `full=yes`
instead, so deleting the prefix cannot cause a silent eighteen-year
re-download.

**Still true and worth knowing**: `.github/workflows/bse_bhavcopy_r2.yml`
carries this prefix as its *default input*. That is the dispatch-only job which
*wrote* the scratch. It never runs on its own and it writes rather than reads,
so it does not block deletion — but dispatching it would recreate the prefix.

**Check, then delete** (needs the R2 credentials):

```sh
# 1. Confirm what is there: expect 23 objects, 1,221.8 MiB
aws s3 ls --recursive "s3://$R2_BUCKET/scratch/bse_bhavcopy_2026-10-03/" \
  --endpoint-url "$R2_ENDPOINT"

# 2. The same command as a removal, without removing anything
aws s3 rm --recursive "s3://$R2_BUCKET/scratch/bse_bhavcopy_2026-10-03/" \
  --endpoint-url "$R2_ENDPOINT" --dryrun

# 3. For real, once step 2 listed exactly what step 1 did
aws s3 rm --recursive "s3://$R2_BUCKET/scratch/bse_bhavcopy_2026-10-03/" \
  --endpoint-url "$R2_ENDPOINT"
```

---

## 2. One dead release asset — 10.85 MB

`tmp_session_2026-10-03.zip` on the `data-latest` release: **10,851,823 bytes,
0 downloads**, untouched since 2026-10-03. `docs/AUDIT_PLAN.md` mentions it
only as an observation that it is waste; nothing reads it, and no workflow
names it.

```sh
gh release delete-asset data-latest tmp_session_2026-10-03.zip \
  --repo Pareshking/Paresh
```

---

## What came off this list, and why

**`ref_long_price_audit_2026-10-03.zip` is NOT dead — do not delete it.** It
was on this list as the second "dead asset" (330,498 bytes, 0 downloads,
superseded by `long_price_audit_latest.zip`). Reading
`docs/R2_RECOVERY_AND_RETENTION.md` before deleting showed otherwise: it is
named there as part of the deliberately retained 3 October reference set,
beside `ref_nse_action_list_api_2008_2026.zip` and `ref_marketlens_sectors.csv`,
mirrored in the owner's local backup. The `ref_` prefix is the convention for
reference evidence. `long_price_audit_latest.zip` is the rolling current audit,
which does not replace a dated snapshot. Zero downloads is what you expect of
an archive.

So the figure of "two dead release assets, 11.18 MB" was wrong: it is **one
asset, 10.85 MB**.

**`nse_index_rebuild/` stays** (owner, 11 Nov 2026). 12,101 KB of the
repository's 25,689 KB, 1,314 of its files NSE announcement text. It is live —
read by `src/engine/index_universe.py`, two scripts, two workflows and a test —
and it is what makes the membership history defensible. The 20%-less-space
target was dropped rather than paid for out of this.

**Two empty files were deleted** (`nse_index_rebuild/announcements/dl.log` and
`dl_old.log`, 0 bytes each, referenced by nothing; `*.log` now ignored). Across
2,046 tracked files a reachability audit found nothing else worth removing:
0 of 105 `src` modules are unimported, and every script with no caller is
either a documented hand-run tool or named by description in a spec.
