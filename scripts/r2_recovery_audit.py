"""Read-only R2 recovery audit: re-resolve and fully read every current pointer."""

from __future__ import annotations

import argparse
import json
from typing import Any

from src.storage.r2 import R2Archive, R2Config
from src.storage.reader import R2DatasetReader


def audit_recovery(archive: R2Archive) -> dict[str, Any]:
    reader = R2DatasetReader(archive)
    pointers = sorted(
        key for key in archive.list_keys("archive/manifests/")
        if key.endswith("/current.json")
    )
    verified = []
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
    return {"status": "PASS", "current_pointers": len(pointers), "verified": verified}


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
