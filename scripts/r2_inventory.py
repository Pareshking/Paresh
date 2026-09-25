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


def _mb(n: int) -> str:
    return f"{n / 1024**2:,.1f} MB"


# Datasets that a scheduled job republishes every trading day. If one of them
# stops moving, something upstream has stopped -- the historical evidence
# bootstrap sat at 2026-09-22 for days in September 2026 while every
# individual step still looked "fine" in isolation. Datasets published once
# (prices/yahoo/raw, parked by design) or whose as_of is fixed by the evidence
# itself (trading_sessions/*, market_caps/nse_snapshot, corporate_actions/*)
# are deliberately not listed.
DAILY_DATASETS = (
    "prices/screener",
    "prices/yahoo",
    "snapshots/rankings",
    "calculations/rankings",
    "market_caps/nse_history",
    "indices/prices/research",
    "indices/membership/nifty_total_market",
    "universes/point_in_time",
    "classifications/tv_history",
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
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else _summary(result))
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
