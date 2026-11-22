"""Read-only inventory of the canonical R2 archive.

This is operational tooling only. It lists immutable manifests and current
pointers, reports revisions by dataset/date, and never downloads payloads or
changes R2 state.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any

from src.storage.r2 import R2Archive, R2Config


def inventory(archive: R2Archive) -> dict[str, Any]:
    prefix = "archive/manifests/"
    keys = sorted(archive.list_keys(prefix))
    current = [k for k in keys if k.endswith("/current.json")]
    revisions = [k for k in keys if "/revisions/" in k and k.endswith(".json")]

    by_dataset: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"as_of": set(), "current_pointers": 0, "immutable_revisions": 0}
    )
    for key in current:
        parts = key.split("/")
        if len(parts) < 5:
            continue
        dataset = "/".join(parts[2:-2])
        as_of = parts[-2]
        by_dataset[dataset]["as_of"].add(as_of)
        by_dataset[dataset]["current_pointers"] += 1
    for key in revisions:
        parts = key.split("/")
        if len(parts) < 7:
            continue
        dataset = "/".join(parts[2:-3])
        by_dataset[dataset]["immutable_revisions"] += 1

    datasets = {}
    for dataset, row in sorted(by_dataset.items()):
        datasets[dataset] = {
            "as_of_count": len(row["as_of"]),
            "first_as_of": min(row["as_of"]) if row["as_of"] else None,
            "last_as_of": max(row["as_of"]) if row["as_of"] else None,
            "current_pointers": row["current_pointers"],
            "immutable_revisions": row["immutable_revisions"],
        }

    return {
        "status": "PASS",
        "manifest_keys": len(keys),
        "current_pointers": len(current),
        "immutable_revision_manifests": len(revisions),
        "datasets": datasets,
    }


_DATE_SEGMENT = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RECENT_DAYS = 30


def storage_report(archive: R2Archive, today: date, recent_days: int = RECENT_DAYS) -> dict[str, Any]:
    """Bytes stored per dataset, split into the last ``recent_days`` and older.

    Read-only: one listing, no downloads. It answers "how much do the old
    versions actually cost?" before anyone decides to keep or delete them.
    A dataset is the key path up to its first YYYY-MM-DD segment; manifests are
    reported under their own prefix.
    """
    rows: dict[str, dict[str, int]] = defaultdict(
        lambda: {"objects": 0, "bytes": 0, "recent_bytes": 0, "old_bytes": 0,
                 "undated_bytes": 0}
    )
    for key, size in archive.list_objects(""):
        parts = key.split("/")
        pos = next((i for i, p in enumerate(parts) if _DATE_SEGMENT.match(p)), None)
        group = "/".join(parts[:pos]) if pos else "/".join(parts[:-1]) or key
        row = rows[group]
        row["objects"] += 1
        row["bytes"] += size
        if pos is None:
            row["undated_bytes"] += size
            continue
        age = (today - date.fromisoformat(parts[pos])).days
        row["recent_bytes" if age <= recent_days else "old_bytes"] += size
    total = {k: sum(r[k] for r in rows.values()) for k in
             ("objects", "bytes", "recent_bytes", "old_bytes", "undated_bytes")}
    return {"recent_days": recent_days, "total": total,
            "by_dataset": dict(sorted(rows.items(), key=lambda kv: -kv[1]["bytes"]))}


# Cloudflare R2's free allowance is 10 GB-month of Standard storage
# (docs/MARKET_DATA_ARCHIVE_R2_SPEC.md). Owner, 15 Nov 2026: "we need to keep it
# below 50% of Cloudflare limits". Counted in decimal GB, the smaller reading,
# so the guard errs early. A warning at 40% leaves time to act before 50% fails.
FREE_STORAGE_BYTES = 10 * 10**9
STORAGE_WARN_SHARE = 0.40
STORAGE_FAIL_SHARE = 0.50


def account_storage(client, own_bucket: str, own_bytes: int) -> dict[str, Any]:
    """Bytes in every R2 bucket of the Cloudflare account, as far as the key may see.

    The 10 GB free allowance is per ACCOUNT, all buckets together (owner, 15 Nov
    2026: "I think I am sharing this cloudflare with other account or website").
    This project's key may be scoped to its own bucket, in which case Cloudflare
    refuses ListBuckets or another bucket's listing; the result then says the
    account total is not known rather than passing off one bucket as the account.
    Read-only: listings only.
    """
    buckets: dict[str, int | None] = {own_bucket: own_bytes}
    try:
        names = [b["Name"] for b in client.list_buckets().get("Buckets", [])]
    except Exception as exc:                       # AccessDenied on a bucket-scoped key
        return {"buckets": buckets, "complete": False, "total": own_bytes,
                "reason": f"ListBuckets refused ({type(exc).__name__}): only this bucket is counted"}
    for name in names:
        if name == own_bucket:
            continue
        try:
            size = 0
            for page in client.get_paginator("list_objects_v2").paginate(Bucket=name):
                size += sum(int(o.get("Size", 0)) for o in page.get("Contents", []))
            buckets[name] = size
        except Exception:
            buckets[name] = None
    unread = [n for n, b in buckets.items() if b is None]
    return {"buckets": buckets, "complete": not unread,
            "total": sum(b for b in buckets.values() if b is not None),
            "reason": f"could not list: {', '.join(unread)}" if unread else ""}


def storage_limit(storage: dict[str, Any], account: dict[str, Any] | None = None) -> dict[str, Any]:
    """Where the ACCOUNT stands against half of Cloudflare's free storage.

    Judged on the account total when every bucket could be listed; otherwise on
    what could be counted, marked incomplete, with a warning that other buckets
    may hold more (they count against the same allowance).
    """
    total = (account or {}).get("total", storage.get("total", {}).get("bytes"))
    if total is None:
        return {"status": "UNKNOWN", "reason": storage.get("error", "no storage report")}
    share = total / FREE_STORAGE_BYTES
    status = "FAIL" if share >= STORAGE_FAIL_SHARE else ("WARN" if share >= STORAGE_WARN_SHARE else "PASS")
    complete = bool(account and account.get("complete"))
    return {"bytes": total, "free_bytes": FREE_STORAGE_BYTES, "share": round(share, 4),
            "warn_at": STORAGE_WARN_SHARE, "fail_at": STORAGE_FAIL_SHARE, "status": status,
            "account_complete": complete,
            "buckets": (account or {}).get("buckets", {}),
            "note": "" if complete else ((account or {}).get("reason")
                                         or "only this bucket is counted; other buckets in the account share the allowance")}


def _mb(n: int) -> str:
    return f"{n / 1024**2:,.1f} MB"


# Datasets that a scheduled job republishes every trading day. If one of them
# stops moving, something upstream has stopped -- the historical evidence
# bootstrap sat at 2026-09-22 for days in September 2026 while every
# individual step still looked "fine" in isolation. Datasets published once
# (prices/yahoo/raw, parked by design; prices/yahoo, no longer published since
# 2026-10-02) or whose as_of is fixed by the evidence
# itself (trading_sessions/*, market_caps/nse_snapshot, corporate_actions/*)
# are deliberately not listed. So is classifications/tv_history (S136, 15 Nov
# 2026): its as_of is the last day TradingView reclassified a stock, not the last
# day the job ran. The weekly refresh ran green on 13 Nov with "Refreshed 2404
# rows; 0 changed" while the as_of stayed at 4 Nov, which failed this check every
# day from 11 Nov (and 23-27 Oct). Its job's failures reach the alert on their own.
# calculations/rankings is retired (S141, 16 Nov 2026): r2_ranking_archive.yml
# republished the very release rankings.parquet daily_sync had just published as
# snapshots/rankings, and nothing read the copy. Its stored dates stay on R2.
DAILY_DATASETS = (
    "prices/screener",
    "snapshots/rankings",
    "market_caps/nse_history",
    "indices/prices/research",
    "indices/membership/nifty_total_market",
    "universes/point_in_time",
    # Every NSE index, daily (S168): backfilled 21 Nov 2026, extended each evening by nse_indices.yml.
    "indices/nse_close_all",
)

# Calendar days. A Friday session checked on the following Wednesday is five
# days old; that plus one exchange holiday and GitHub's hours-late schedule
# queue is the most a healthy pipeline should ever show.
DEFAULT_MAX_AGE_DAYS = 6


def freshness(
    result: dict[str, Any],
    today: date,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    required: tuple[str, ...] = DAILY_DATASETS,
) -> dict[str, Any]:
    """Flag every daily dataset that is missing or older than max_age_days."""
    stale: dict[str, Any] = {}
    for dataset in required:
        row = result["datasets"].get(dataset)
        last = row and row.get("last_as_of")
        if not last:
            stale[dataset] = {"last_as_of": None, "age_days": None}
            continue
        age = (today - date.fromisoformat(last)).days
        if age > max_age_days:
            stale[dataset] = {"last_as_of": last, "age_days": age}
    return {
        "checked_on": today.isoformat(),
        "max_age_days": max_age_days,
        "stale": stale,
        "status": "FAIL" if stale else "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    args = parser.parse_args()
    archive = R2Archive(R2Config.from_env())
    result = inventory(archive)
    today = datetime.now(timezone.utc).date()
    result["freshness"] = freshness(result, today, args.max_age_days)
    try:
        result["storage"] = storage_report(archive, today)
    except Exception as exc:  # a report, never a reason to fail the inventory
        result["storage"] = {"error": f"{type(exc).__name__}: {exc}"}
    if result["freshness"]["status"] != "PASS":
        result["status"] = "FAIL"
    account = None
    if "total" in result["storage"]:
        try:
            account = account_storage(archive.client, archive.config.bucket, result["storage"]["total"]["bytes"])
        except Exception as exc:  # a report, never a reason to fail the inventory
            account = {"complete": False, "reason": f"{type(exc).__name__}: {exc}",
                       "total": result["storage"]["total"]["bytes"], "buckets": {}}
    result["storage_limit"] = limit = storage_limit(result["storage"], account)
    if limit.get("note"):
        # A plain line, not a ::warning:: annotation: the project's key is scoped to
        # its bucket, so this holds on every run, and a warning on a green scheduled
        # run opens an alert issue (S116) -- one a day for a known fact. The owner's
        # dashboard (15 Nov 2026) shows the account holds this bucket alone.
        print(f"R2 account storage not fully counted: {limit['note']}. "
              "The owner's dashboard showed one bucket on 15 Nov 2026; check it there if that changes.")
    if limit["status"] in ("WARN", "FAIL"):
        print(f"::{'error' if limit['status'] == 'FAIL' else 'warning'}::R2 holds "
              f"{limit['bytes'] / 10**9:.2f} GB, {limit['share']:.0%} of Cloudflare's 10 GB free storage "
              f"(warn at {STORAGE_WARN_SHARE:.0%}, fail at {STORAGE_FAIL_SHARE:.0%}); see the STORAGE lines")
    if limit["status"] == "FAIL":
        result["status"] = "FAIL"
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else _summary(result))
    if args.json:
        # The size table too, from the same listing: the workflow ran the whole
        # inventory a second time just to print these lines (S141, 16 Nov 2026).
        print("\n".join(line for line in _summary(result).splitlines() if line.startswith("STORAGE")))
    return 0 if result["status"] == "PASS" else 1


def _summary(result: dict[str, Any]) -> str:
    lines = [
        f"R2_ARCHIVE_INVENTORY={result['status']}",
        f"MANIFEST_KEYS={result['manifest_keys']}",
        f"CURRENT_POINTERS={result['current_pointers']}",
        f"IMMUTABLE_REVISION_MANIFESTS={result['immutable_revision_manifests']}",
    ]
    for dataset, row in result.get("freshness", {}).get("stale", {}).items():
        lines.append(f"STALE={dataset} LAST_AS_OF={row['last_as_of']} AGE_DAYS={row['age_days']}")
    limit = result.get("storage_limit", {})
    if "share" in limit:
        lines.append(f"STORAGE_LIMIT={limit['status']} SHARE_OF_FREE={limit['share']:.1%} "
                     f"(warn {limit['warn_at']:.0%}, fail {limit['fail_at']:.0%} of 10 GB) "
                     f"ACCOUNT_COMPLETE={'yes' if limit.get('account_complete') else 'no'}")
        for name, size in (limit.get("buckets") or {}).items():
            lines.append(f"STORAGE_BUCKET={name} TOTAL={'unreadable' if size is None else _mb(size)}")
    storage = result.get("storage", {})
    if "total" in storage:
        t = storage["total"]
        lines.append(
            f"STORAGE_TOTAL={_mb(t['bytes'])} OBJECTS={t['objects']} "
            f"LAST_{storage['recent_days']}_DAYS={_mb(t['recent_bytes'])} "
            f"OLDER={_mb(t['old_bytes'])} UNDATED={_mb(t['undated_bytes'])}"
        )
        for group, row in storage["by_dataset"].items():
            lines.append(
                f"STORAGE={group} TOTAL={_mb(row['bytes'])} OBJECTS={row['objects']} "
                f"RECENT={_mb(row['recent_bytes'])} OLDER={_mb(row['old_bytes'])}"
            )
    for dataset, row in result["datasets"].items():
        lines.append(
            f"DATASET={dataset} AS_OF={row['first_as_of']}..{row['last_as_of']} "
            f"CURRENT={row['current_pointers']} REVISIONS={row['immutable_revisions']}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
