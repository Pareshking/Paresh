"""R2 retention for the two large daily datasets. Dry run unless told otherwise.

Owner-approved policy, 2026-09-25: for `prices/yahoo`,
`snapshots/application` and (added the same day) `prices/screener`, keep the
last KEEP_DAILY as_of dates plus the last as_of of every calendar month. Every other dataset keeps its full history and
is never touched here.

What goes, for each as_of date that is not kept:
    archive/manifests/<dataset>/<as_of>/current.json        (the pointer)
    archive/manifests/<dataset>/<as_of>/revisions/<sha>.json (each manifest)
    the object each manifest names                           (the payload)

And within each KEPT date (owner, 2026-09-25: "keep only the newest revision
per kept date"): every revision except the one current.json names and the one
resolve_latest_revision() picks (newest created_at). Those two are nearly
always the same revision; keeping both means no reader changes its answer. A
kept date whose pointer or created_at values cannot be read is left whole and
reported as SKIPPED.

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
from datetime import datetime
from typing import Any

from src.storage.r2 import R2Archive, R2Config

KEEP_DAILY = 7

# dataset -> the key root its payloads are published under (daily_sync.yml:
# `--key-root archive/prices/yahoo` and `--key-root snapshots/application`;
# screener_sync.yml: `--key-root archive/prices/screener`). Each nightly
# Screener store is the whole history (~5 MB), so older copies add nothing the
# newest does not hold. prices/screener/bootstrap is a separate dataset and,
# like every nested one, is never matched here.
RETAINED_DATASETS: dict[str, str] = {
    "prices/yahoo": "archive/prices/yahoo",
    "snapshots/application": "snapshots/application",
    "prices/screener": "archive/prices/screener",
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
    superseded: list[str] = field(default_factory=list)  # manifests pruned on kept dates
    skipped: list[str] = field(default_factory=list)     # kept dates left whole, and why


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

    def load(key: str) -> dict[str, Any]:
        body = json.loads(archive.get_bytes(key).decode("utf-8"))
        return body if isinstance(body, dict) else {}

    bodies = {mk: load(mk) for d in dates for mk in manifests.get(d, [])}

    def object_of(manifest_key: str) -> str:
        return str(bodies[manifest_key].get("object_key", ""))

    # Manifests that stay: every one on a kept date, minus the superseded.
    kept_manifests: set[str] = set()
    for d in keep:
        mks = manifests.get(d, [])
        survivors = _survivors(archive, pointers.get(d), mks, bodies)
        if isinstance(survivors, str):
            if len(mks) > 1:
                plan.skipped.append(f"{d}: {survivors}")
            kept_manifests.update(mks)
            continue
        kept_manifests.update(survivors)
        plan.superseded.extend(sorted(set(mks) - survivors))

    kept_objects = {object_of(k) for k in kept_manifests}
    plan.kept_bytes = sum(sizes.get(k, 0) for k in kept_objects)

    pointer_keys, manifest_keys, object_keys = [], [], []
    by_date = {mk: d for d in dates for mk in manifests.get(d, [])}
    doomed = [mk for d in drop for mk in sorted(manifests.get(d, []))] + plan.superseded
    for d in drop:
        if d in pointers:
            pointer_keys.append(pointers[d])
    for mk in doomed:
        d = by_date[mk]
        obj = object_of(mk)
        if not obj.startswith(f"{root}/{d}/revisions/"):
            plan.refused.append(f"{mk}: object_key {obj!r} is outside {root}/{d}/")
            continue
        manifest_keys.append(mk)
        if obj in kept_objects or obj in object_keys:
            continue  # the same payload is still named by a kept revision
        object_keys.append(obj)
    plan.delete_keys = pointer_keys + manifest_keys + object_keys
    plan.delete_bytes = sum(sizes.get(k, 0) for k in plan.delete_keys)
    return plan


def _created_at(body: dict[str, Any]) -> datetime | None:
    value = body.get("created_at")
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _survivors(archive: R2Archive, pointer_key: str | None, mks: list[str],
               bodies: dict[str, dict[str, Any]]) -> set[str] | str:
    """The manifests of a kept date that must stay, or why the date is left whole.

    Two readers pick a revision: resolve_current() follows current.json, and
    resolve_latest_revision() takes the newest created_at (sha breaks ties),
    exactly as src/storage/reader.py orders them.
    """
    if len(mks) <= 1:
        return set(mks)
    if pointer_key is None:
        return "no current.json"
    try:
        pointed = json.loads(archive.get_bytes(pointer_key).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return "current.json is not valid JSON"
    if not isinstance(pointed, dict):
        return "current.json is not a JSON object"
    named = str(pointed.get("manifest_key") or "")
    if not named and pointed.get("revision_sha256"):
        named = f"{pointer_key.rsplit('/', 1)[0]}/revisions/{pointed['revision_sha256']}.json"
    if named not in mks:
        return f"current.json names {named!r}, not one of this date's manifests"
    stamped = []
    for mk in mks:
        when = _created_at(bodies[mk])
        if when is None:
            return f"{mk} has no usable created_at"
        stamped.append((when, mk.rsplit("/", 1)[-1], mk))
    newest = max(stamped)[2]
    return {named, newest}


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
                "superseded_revisions": len(p.superseded),
                "skipped": p.skipped,
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
              f"SUPERSEDED={row['superseded_revisions']} "
              f"FREES={_mb(row['delete_bytes'])} KEEPS={_mb(row['kept_payload_bytes'])}")
        print(f"  keep: {', '.join(row['keep'])}")
        if row["drop"]:
            print(f"  drop: {', '.join(row['drop'])}")
        for why in row["refused"]:
            print(f"  REFUSED {why}")
        for why in row["skipped"]:
            print(f"  SKIPPED {why}")
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
