"""Read-only R2 recovery audit: re-resolve and fully read every current pointer."""

from __future__ import annotations

import argparse
import json
from typing import Any

from src.storage.r2 import R2Archive, R2Config
from src.storage.reader import R2DatasetReader


def audit_recovery(archive: R2Archive) -> dict[str, Any]:
    reader = R2DatasetReader(archive)
    manifest_keys = sorted(
        key for key in archive.list_keys("archive/manifests/")
        if "/revisions/" in key and key.endswith(".json")
    )
    pointers = sorted(
        key for key in archive.list_keys("archive/manifests/")
        if key.endswith("/current.json")
    )
    verified = []
    immutable_verified = []
    for key in manifest_keys:
        parts = key.split("/")
        if len(parts) < 7:
            continue
        dataset = "/".join(parts[2:-3])
        as_of = parts[-3]
        revision_sha256 = parts[-1][:-5]
        if len(revision_sha256) != 64:
            raise RuntimeError(f"Invalid immutable manifest revision key: {key}")
        ref = reader.resolve_revision(dataset, as_of, revision_sha256)
        body = reader.read_bytes(ref)
        immutable_verified.append({
            "dataset": dataset,
            "as_of": as_of,
            "revision_sha256": ref.revision_sha256,
            "size_bytes": len(body),
        })

    for key in pointers:
        parts = key.split("/")
        if len(parts) < 5 or parts[-1] != "current.json":
            continue
        dataset = "/".join(parts[2:-2])
        as_of = parts[-2]
        ref = reader.resolve_current(dataset, as_of=as_of)
        body = reader.read_bytes(ref)
        verified.append({
            "dataset": dataset,
            "as_of": as_of,
            "revision_sha256": ref.revision_sha256,
            "size_bytes": len(body),
        })
    return {
        "status": "PASS",
        "current_pointers": len(pointers),
        "immutable_revisions": len(manifest_keys),
        "verified": verified,
        "immutable_verified": immutable_verified,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = audit_recovery(R2Archive(R2Config.from_env()))
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("R2_RECOVERY_AUDIT={}".format(result["status"]))
        print("CURRENT_POINTERS={}".format(result["current_pointers"]))
        print("VERIFIED_OBJECTS={}".format(len(result["verified"])))
        print("IMMUTABLE_REVISIONS={}".format(result["immutable_revisions"]))
        print("IMMUTABLE_VERIFIED={}".format(len(result["immutable_verified"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
