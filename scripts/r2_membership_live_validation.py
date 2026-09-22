"""Live acceptance check for the manifest-pinned R2 membership consumer."""
from __future__ import annotations

import argparse
import json
from datetime import date

from r2.consumers.r2_historical import MEMBERSHIP_DATASET, membership_from_frame
from src.storage.r2 import R2Archive, R2Config
from src.storage.reader import R2DatasetIntegrityError, R2DatasetReader

def _resolve_membership_revision(reader: R2DatasetReader, *, as_of: str):
    """Resolve immutable PIT evidence without depending on a mutable pointer."""
    prefix = f"archive/manifests/{MEMBERSHIP_DATASET}/{as_of}/revisions/"
    revision_keys = sorted(
        key for key in reader.archive.list_keys(prefix)
        if key.endswith(".json")
    )
    if not revision_keys:
        raise FileNotFoundError(
            f"no immutable membership revisions for {MEMBERSHIP_DATASET} as_of={as_of}"
        )

    candidates = []
    for key in revision_keys:
        revision = key.rsplit("/", 1)[-1][:-5]
        if len(revision) != 64:
            raise R2DatasetIntegrityError(f"invalid membership revision key: {key}")
        ref = reader.resolve_revision(MEMBERSHIP_DATASET, as_of, revision)
        candidates.append(ref)

    # Prefer the latest manifest creation time; SHA is the deterministic tie-breaker.
    candidates.sort(
        key=lambda ref: (str(ref.manifest.get("created_at", "")), ref.revision_sha256)
    )
    return candidates[-1]

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", required=True)
    args = parser.parse_args()
    date.fromisoformat(args.as_of)

    archive = R2Archive(R2Config.from_env())
    reader = R2DatasetReader(archive)
    try:
        ref = _resolve_membership_revision(reader, as_of=args.as_of)
        frame = reader.read_parquet(ref)
        members = membership_from_frame(
            frame, index="nifty_total_market", as_of=args.as_of
        )
    except (R2DatasetIntegrityError, ValueError, KeyError, FileNotFoundError) as exc:
        raise SystemExit(f"R2 membership consumer acceptance failed: {exc}") from exc

    if members is None:
        raise SystemExit(f"R2 membership dataset has no PIT coverage for {args.as_of}")
    if not members:
        raise SystemExit(f"R2 membership reconstruction unexpectedly empty for {args.as_of}")

    print(
        json.dumps(
            {
                "dataset": MEMBERSHIP_DATASET,
                "as_of": args.as_of,
                "revision_sha256": ref.revision_sha256,
                "manifest_key": ref.manifest_key,
                "object_key": ref.object_key,
                "member_count": len(members),
                "consumer_acceptance": "PASS",
            },
            sort_keys=True,
        )
    )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
