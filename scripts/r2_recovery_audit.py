"""Read-only R2 recovery audit: re-resolve and fully read every current pointer."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from typing import Any

from src.storage.r2 import R2Archive, R2Config
from src.storage.reader import R2DatasetReader


def _in_scope(key: str, datasets: tuple[str, ...] | None) -> bool:
    """Whether a manifest key belongs DIRECTLY to one of the datasets.

    prices/yahoo is a prefix of prices/yahoo/raw, a separate dataset, so the
    next path part after the dataset must be the as_of date.
    """
    if datasets is None:
        return True
    rest = key.removeprefix("archive/manifests/")
    for ds in datasets:
        if rest.startswith(ds + "/"):
            nxt = rest[len(ds) + 1:].split("/", 1)[0]
            if len(nxt) == 10 and nxt[4] == "-" and nxt[7] == "-":
                return True
    return False


FULL_READ_DAYS = 14   # A3, owner 15 Nov 2026: bound what the weekly run downloads


def _key_parts(key: str) -> tuple[str, str] | None:
    """(dataset, as_of) of a manifest key, or None."""
    rest = key.removeprefix("archive/manifests/").split("/")
    for i, part in enumerate(rest):
        if len(part) == 10 and part[4] == "-" and part[7] == "-":
            return "/".join(rest[:i]), part
    return None


def full_read_set(keys: list[str], today: date, days: int | None) -> set[tuple[str, str]]:
    """The (dataset, as_of) pairs to download in full: the last `days` days and each
    dataset's newest date. None means every pair (the complete audit)."""
    pairs = {p for p in (_key_parts(k) for k in keys) if p}
    if days is None:
        return pairs
    cutoff = (today - timedelta(days=days)).isoformat()
    newest: dict[str, str] = {}
    for ds, as_of in pairs:
        newest[ds] = max(newest.get(ds, as_of), as_of)
    return {(ds, a) for ds, a in pairs if a >= cutoff or newest[ds] == a}


def audit_recovery(archive: R2Archive,
                   datasets: tuple[str, ...] | None = None,
                   workers: int = 10,
                   full_days: int | None = None,
                   today: date | None = None) -> dict[str, Any]:
    """Every pointer and revision, or only those of `datasets` when given.

    The retention job passes the datasets it may delete from: the whole
    bucket (the NSE archive holds thousands of days) outgrew its time limit.

    Every revision and pointer is resolved: its manifest is read and
    validated, and the object's size is checked by HEAD. With `full_days`,
    only the last `full_days` days and each dataset's newest date are also
    downloaded and checked against their SHA-256; older ones are immutable
    and were downloaded in full when they were recent (A3: 7 min on 28 Sep,
    43 on 9 Nov, 34 on 16 Nov after the storage was cut by a third, because
    the cost is the number of objects, not their size). `full_days=None`
    downloads everything, as before.
    """
    reader = R2DatasetReader(archive)
    keys = [k for k in archive.list_keys("archive/manifests/") if _in_scope(k, datasets)]
    full = full_read_set(keys, today or datetime.now(timezone.utc).date(), full_days)
    manifest_keys = sorted(
        key for key in keys
        if "/revisions/" in key and key.endswith(".json")
    )
    pointers = sorted(key for key in keys if key.endswith("/current.json"))
    def check_revision(key: str) -> dict[str, Any] | None:
        parts = key.split("/")
        if len(parts) < 7:
            return None
        dataset = "/".join(parts[2:-3])
        as_of = parts[-3]
        revision_sha256 = parts[-1][:-5]
        if len(revision_sha256) != 64:
            raise RuntimeError(f"Invalid immutable manifest revision key: {key}")
        ref = reader.resolve_revision(dataset, as_of, revision_sha256)
        if (dataset, as_of) not in full:
            return {"dataset": dataset, "as_of": as_of, "revision_sha256": ref.revision_sha256,
                    "size_bytes": int(ref.manifest.get("size_bytes", -1)), "checked": "manifest+size"}
        body = reader.read_bytes(ref)
        return {"dataset": dataset, "as_of": as_of, "revision_sha256": ref.revision_sha256,
                "size_bytes": len(body), "checked": "sha256"}

    def check_pointer(key: str) -> dict[str, Any] | None:
        parts = key.split("/")
        if len(parts) < 5 or parts[-1] != "current.json":
            return None
        dataset = "/".join(parts[2:-2])
        as_of = parts[-2]
        ref = reader.resolve_current(dataset, as_of=as_of)
        if (dataset, as_of) not in full:
            return {"dataset": dataset, "as_of": as_of, "revision_sha256": ref.revision_sha256,
                    "size_bytes": int(getattr(ref, "manifest", {}).get("size_bytes", -1)),
                    "checked": "manifest+size"}
        body = reader.read_bytes(ref)
        return {"dataset": dataset, "as_of": as_of, "revision_sha256": ref.revision_sha256,
                "size_bytes": len(body), "checked": "sha256"}

    # Many small reads, each a network round trip: in parallel (10, the size
    # of the boto3 client's connection pool), so the whole
    # bucket (the NSE archive adds thousands of days) fits the job's time
    # limit (2026-09-27: one at a time, it ran out at 15 minutes). The first
    # failure still raises, as before.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        immutable_verified = [r for r in pool.map(check_revision, manifest_keys) if r]
        verified = [r for r in pool.map(check_pointer, pointers) if r]
    return {
        "status": "PASS",
        "current_pointers": len(pointers),
        "immutable_revisions": len(manifest_keys),
        "verified": verified,
        "immutable_verified": immutable_verified,
        "full_read_days": full_days,
        "downloaded_in_full": sum(r.get("checked") == "sha256" for r in verified + immutable_verified),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dataset", action="append",
                        help="limit to this dataset (repeatable); default: all")
    parser.add_argument("--full", action="store_true",
                        help="download every revision (the complete audit); default: the last "
                             f"{FULL_READ_DAYS} days and each dataset's newest date")
    parser.add_argument("--retention-scope", action="store_true",
                        help="limit to the datasets scripts/r2_retention.py deletes from")
    args = parser.parse_args()
    datasets = tuple(args.dataset) if args.dataset else None
    if args.retention_scope:
        from scripts.r2_retention import RETAINED_DATASETS
        datasets = tuple(RETAINED_DATASETS) + (datasets or ())
    result = audit_recovery(R2Archive(R2Config.from_env()), datasets,
                            full_days=None if args.full else FULL_READ_DAYS)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("R2_RECOVERY_AUDIT={}".format(result["status"]))
        print("CURRENT_POINTERS={}".format(result["current_pointers"]))
        print("VERIFIED_OBJECTS={}".format(len(result["verified"])))
        print("IMMUTABLE_REVISIONS={}".format(result["immutable_revisions"]))
        print("IMMUTABLE_VERIFIED={}".format(len(result["immutable_verified"])))
        print("DOWNLOADED_IN_FULL={}".format(result["downloaded_in_full"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
