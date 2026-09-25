"""Read-only R2 storage inventory and cost-observability report."""
from __future__ import annotations

import argparse
import json

from src.storage.r2 import R2Archive, R2Config


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", default=None)
    args = p.parse_args(argv)
    archive = R2Archive(R2Config.from_env())
    prefix = f"archive/manifests/{args.dataset}/" if args.dataset else "archive/manifests/"
    keys = list(archive.list_keys(prefix))
    current = [k for k in keys if k.endswith("/current.json")]
    revisions = [k for k in keys if "/revisions/" in k and k.endswith(".json")]
    bytes_total = 0
    object_count = 0
    for key in revisions:
        head = archive.head(key)
        bytes_total += int(head.get("ContentLength", 0))
        object_count += 1
    report = {
        "prefix": prefix,
        "manifest_revision_objects": object_count,
        "manifest_revision_bytes": bytes_total,
        "current_pointer_count": len(current),
        # ListObjectsV2 returns at most 1,000 keys a page, one request each.
        "list_operations": max(1, -(-len(keys) // 1000)),
        "head_operations": object_count,
        "billing_source": "inventory-derived; provider billing/API request logs are not exposed here",
    }
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
