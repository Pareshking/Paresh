"""Audit one immutable R2 dataset/date publication.

The audit verifies the mutable current pointer, immutable manifest, and the
content-addressed object as one publication contract. It is intentionally
read-only and fails closed on any mismatch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

from src.storage.manifest import MANIFEST_SCHEMA_VERSION
from src.storage.r2 import R2Archive, R2Config


def _latest_as_of(archive: R2Archive, dataset: str) -> str:
    prefix = f"archive/manifests/{dataset}/"
    dates = set()
    for key in archive.list_keys(prefix):
        parts = key[len(prefix):].split("/")
        if len(parts) == 2 and parts[1] == "current.json":
            dates.add(parts[0])
    if not dates:
        raise RuntimeError(f"no current pointers found for {dataset}")
    return max(dates)


def audit(*, dataset: str, as_of: str | None = None) -> dict[str, Any]:
    archive = R2Archive(R2Config.from_env())
    as_of = as_of or _latest_as_of(archive, dataset)
    current_key = f"archive/manifests/{dataset}/{as_of}/current.json"
    current = json.loads(archive.get_bytes(current_key).decode("utf-8"))

    required_pointer = (
        "dataset", "as_of", "source", "revision_sha256",
        "object_key", "manifest_key",
    )
    for field in required_pointer:
        if field not in current or current[field] in (None, ""):
            raise RuntimeError(f"current pointer missing {field}: {current_key}")

    if current["dataset"] != dataset or current["as_of"] != as_of:
        raise RuntimeError(f"current pointer identity mismatch: {current_key}")

    manifest_key = str(current["manifest_key"])
    manifest = json.loads(archive.get_bytes(manifest_key).decode("utf-8"))

    for field in (
        "dataset", "as_of", "source", "schema_version", "size_bytes", "sha256",
        "object_key", "revision_sha256",
    ):
        if field not in manifest:
            raise RuntimeError(f"manifest missing {field}: {manifest_key}")

    if int(manifest["schema_version"]) != MANIFEST_SCHEMA_VERSION:
        raise RuntimeError("unsupported manifest schema version")

    for field in ("dataset", "as_of", "source", "revision_sha256", "object_key"):
        if current[field] != manifest[field]:
            raise RuntimeError(
                f"pointer/manifest mismatch {field}: {current_key} vs {manifest_key}"
            )

    object_key = str(manifest["object_key"])
    head = archive.head(object_key)
    head_size = int(head.get("ContentLength", -1))
    expected_size = int(manifest["size_bytes"])
    if head_size != expected_size:
        raise RuntimeError(
            f"object HEAD size mismatch: {object_key}: "
            f"manifest={expected_size}, head={head_size}"
        )

    remote = archive.get_bytes(object_key)
    digest = hashlib.sha256(remote).hexdigest()
    if digest != manifest["sha256"] or digest != manifest["revision_sha256"]:
        raise RuntimeError(f"object SHA mismatch: {object_key}")
    if len(remote) != expected_size:
        raise RuntimeError(f"object size mismatch: {object_key}")

    result = {
        "dataset": dataset,
        "as_of": as_of,
        "revision_sha256": manifest["revision_sha256"],
        "object_key": object_key,
        "manifest_key": manifest_key,
        "size_bytes": len(remote),
        "sha256": digest,
        "status": "PASS",
    }
    print(json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--as-of")
    args = parser.parse_args()
    audit(dataset=args.dataset, as_of=args.as_of)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
