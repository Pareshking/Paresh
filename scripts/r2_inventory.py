"""Read-only inventory of the canonical R2 archive.

This is operational tooling only. It lists immutable manifests and current
pointers, reports revisions by dataset/date, and never downloads payloads or
changes R2 state.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = inventory(R2Archive(R2Config.from_env()))
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else _summary(result))
    return 0


def _summary(result: dict[str, Any]) -> str:
    lines = [
        f"R2_ARCHIVE_INVENTORY={result['status']}",
        f"MANIFEST_KEYS={result['manifest_keys']}",
        f"CURRENT_POINTERS={result['current_pointers']}",
        f"IMMUTABLE_REVISION_MANIFESTS={result['immutable_revision_manifests']}",
    ]
    for dataset, row in result["datasets"].items():
        lines.append(
            f"DATASET={dataset} AS_OF={row['first_as_of']}..{row['last_as_of']} "
            f"CURRENT={row['current_pointers']} REVISIONS={row['immutable_revisions']}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
