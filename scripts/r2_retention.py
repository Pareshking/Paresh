"""R2 retention for the two large daily datasets. Dry run unless told otherwise.

Owner-approved policy, 2026-09-25: for `prices/yahoo` and
`snapshots/application`, keep the last KEEP_DAILY as_of dates plus the last
as_of of every calendar month. Every other dataset keeps its full history and
is never touched here.

What goes, for each as_of date that is not kept:
    archive/manifests/<dataset>/<as_of>/current.json        (the pointer)
    archive/manifests/<dataset>/<as_of>/revisions/<sha>.json (each manifest)
    the object each manifest names                           (the payload)

Safety, in order:
- Only keys DIRECTLY under the dataset are considered. `prices/yahoo` is a
  prefix of `prices/yahoo/raw` and `prices/yahoo/bootstrap`, which are separate
  datasets and must never match (the same trap src/storage/reader.py documents).
- A payload is deleted only if its key sits under the dataset's own
  `<root>/<as_of>/revisions/` path, and no kept manifest names the same key.
- The newest as_of is always kept, so every reader that resolves "current"
  finds exactly what it found before.
- Nothing is deleted without --apply AND --expect-deletes N, where N is the
  count the dry run printed. If the archive changed in between, the counts
  differ and nothing happens.
- Pointer first, then manifests, then payloads: a reader can never resolve a
  date whose payload is already gone.

    python scripts/r2_retention.py                                   # dry run
    python scripts/r2_retention.py --apply --expect-deletes 57       # delete
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from typing import Any

from src.storage.r2 import R2Archive, R2Config

KEEP_DAILY = 7

# dataset -> the key root its payloads are published under (daily_sync.yml:
# `--key-root archive/prices/yahoo` and `--key-root snapshots/application`).
RETAINED_DATASETS: dict[str, str] = {
    "prices/yahoo": "archive/prices/yahoo",
    "snapshots/application": "snapshots/application",
}

_ENTRY = re.compile(
    r"^(?P<as_of>\d{4}-\d{2}-\d{2})/"
    r"(?:current\.json|revisions/(?P<sha>[0-9a-f]{64})\.json)$"
)


@dataclass
class DatasetPlan:
    dataset: str
    as_of_dates: list[str]
    keep: list[str]
    drop: list[str]
    delete_keys: list[str] = field(default_factory=list)  # in deletion order
    delete_bytes: int = 0
    kept_bytes: int = 0
    refused: list[str] = field(default_factory=list)


def keep_dates(as_of_dates: list[str], keep_daily: int = KEEP_DAILY) -> set[str]:
    """The last `keep_daily` dates plus the last date of every calendar month."""
    ordered = sorted(set(as_of_dates))
    keep = set(ordered[-keep_daily:]) if keep_daily > 0 else set()
    month_end: dict[str, str] = {}
    for d in ordered:
        month_end[d[:7]] = d  # sorted, so the last one per month wins
    keep.update(month_end.values())
    if ordered:
        keep.add(ordered[-1])
    return keep


def plan_dataset(archive: R2Archive, dataset: str, root: str,
                 sizes: dict[str, int]) -> DatasetPlan:
    prefix = f"archive/manifests/{dataset}/"
    pointers: dict[str, str] = {}
    manifests: dict[str, list[str]] = {}
    for key in archive.list_keys(prefix):
        m = _ENTRY.fullmatch(key[len(prefix):])
        if not m:
            continue  # a nested dataset (e.g. prices/yahoo/raw) or noise
        as_of = m["as_of"]
        if m["sha"]:
            manifests.setdefault(as_of, []).append(key)
        else:
            pointers[as_of] = key

    dates = sorted(set(pointers) | set(manifests))
    keep = keep_dates(dates)
    drop = [d for d in dates if d not in keep]
    plan = DatasetPlan(dataset, dates, sorted(keep), drop)

    def object_of(manifest_key: str) -> str:
        body = json.loads(archive.get_bytes(manifest_key).decode("utf-8"))
        return str(body.get("object_key", ""))

    kept_objects = {object_of(k) for d in keep for k in manifests.get(d, [])}
    plan.kept_bytes = sum(sizes.get(k, 0) for k in kept_objects)

    pointer_keys, manifest_keys, object_keys = [], [], []
    for d in drop:
        if d in pointers:
            pointer_keys.append(pointers[d])
        for mk in sorted(manifests.get(d, [])):
            obj = object_of(mk)
            if not obj.startswith(f"{root}/{d}/revisions/"):
                plan.refused.append(f"{mk}: object_key {obj!r} is outside {root}/{d}/")
                continue
            manifest_keys.append(mk)
            if obj in kept_objects:
                continue  # the same payload is still named by a kept date
            object_keys.append(obj)
    plan.delete_keys = pointer_keys + manifest_keys + object_keys
    plan.delete_bytes = sum(sizes.get(k, 0) for k in plan.delete_keys)
    return plan


def make_plan(archive: R2Archive,
              datasets: dict[str, str] = RETAINED_DATASETS) -> list[DatasetPlan]:
    sizes = dict(archive.list_objects(""))
    return [plan_dataset(archive, ds, root, sizes) for ds, root in datasets.items()]


def apply_plan(archive: R2Archive, plans: list[DatasetPlan]) -> int:
    deleted = 0
    for plan in plans:
        for key in plan.delete_keys:
            archive.delete(key)
            deleted += 1
    return deleted


def _mb(n: int) -> str:
    return f"{n / 1024**2:,.1f} MB"


def report(plans: list[DatasetPlan]) -> dict[str, Any]:
    return {
        "keep_daily": KEEP_DAILY,
        "delete_count": sum(len(p.delete_keys) for p in plans),
        "delete_bytes": sum(p.delete_bytes for p in plans),
        "datasets": {
            p.dataset: {
                "as_of_dates": len(p.as_of_dates),
                "keep": p.keep,
                "drop": p.drop,
                "delete_count": len(p.delete_keys),
                "delete_bytes": p.delete_bytes,
                "kept_payload_bytes": p.kept_bytes,
                "refused": p.refused,
            }
            for p in plans
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--expect-deletes", type=int, default=None,
                    help="the delete count the dry run printed; required with --apply")
    ap.add_argument("--list", action="store_true", help="print every key to delete")
    args = ap.parse_args()

    archive = R2Archive(R2Config.from_env())
    plans = make_plan(archive)
    rep = report(plans)
    for ds, row in rep["datasets"].items():
        print(f"RETENTION={ds} DATES={row['as_of_dates']} KEEP={len(row['keep'])} "
              f"DROP={len(row['drop'])} DELETE_KEYS={row['delete_count']} "
              f"FREES={_mb(row['delete_bytes'])} KEEPS={_mb(row['kept_payload_bytes'])}")
        print(f"  keep: {', '.join(row['keep'])}")
        if row["drop"]:
            print(f"  drop: {', '.join(row['drop'])}")
        for why in row["refused"]:
            print(f"  REFUSED {why}")
    if args.list:
        for p in plans:
            for key in p.delete_keys:
                print(f"  DELETE {key}")
    print(f"RETENTION_DELETE_COUNT={rep['delete_count']} "
          f"RETENTION_FREES={_mb(rep['delete_bytes'])}")

    if any(p.refused for p in plans):
        print("::error::some manifests point outside their dataset; nothing deleted")
        return 1
    if not args.apply:
        print("DRY RUN: nothing deleted. To apply: "
              f"--apply --expect-deletes {rep['delete_count']}")
        return 0
    if args.expect_deletes != rep["delete_count"]:
        print(f"::error::expected {args.expect_deletes} deletes, plan has "
              f"{rep['delete_count']}; the archive changed since the dry run. "
              "Nothing deleted.")
        return 1
    n = apply_plan(archive, plans)
    print(f"RETENTION_APPLIED deleted={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
