"""Publish a validated production artifact to the canonical R2 archive.

Same-date source data can legitimately change (for example when a vendor
restates corporate-action-adjusted history). Therefore the archive is
content-addressed: every distinct byte-level source snapshot is immutable and
preserved as a revision. A mutable current pointer identifies the latest
validated revision for each dataset/date.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from src.storage.manifest import build_manifest, canonical_json
from src.storage.r2 import R2Archive, R2Config, R2ImmutableObjectExists


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ranking_contract(path: Path) -> dict[str, Any] | None:
    metadata = pq.read_schema(path).metadata or {}
    raw = metadata.get(b"umiya_ranking_contract")
    if not raw:
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def describe_parquet(path: Path) -> dict[str, Any]:
    frame = pd.read_parquet(path)
    row_count = int(len(frame))
    symbol_count: int | None = None

    if "Symbol" in frame.columns:
        symbol_count = int(frame["Symbol"].astype(str).str.strip().nunique())
    elif isinstance(frame.columns, pd.MultiIndex):
        symbol_count = int(
            pd.Index(frame.columns.get_level_values(0).astype(str)).nunique()
        )

    min_date = max_date = None
    if isinstance(frame.index, pd.DatetimeIndex) and len(frame.index):
        dates = pd.DatetimeIndex(frame.index).normalize()
        min_date = str(dates.min().date())
        max_date = str(dates.max().date())
    elif "date" in frame.columns:
        dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
        if not dates.empty:
            min_date = str(dates.min().date())
            max_date = str(dates.max().date())

    contract = _ranking_contract(path)
    if contract:
        symbol_count = symbol_count or len(contract.get("universe", []))
        max_date = max_date or str(contract.get("price_as_of") or "") or None

    if not max_date:
        raise RuntimeError(f"Cannot establish archive as_of for {path}")

    return {
        "as_of": max_date,
        "row_count": row_count,
        "symbol_count": symbol_count,
        "min_date": min_date,
        "max_date": max_date,
        "ranking_contract": contract,
    }


def _publish_manifest(
    archive: R2Archive,
    manifest: dict[str, Any],
    key: str,
) -> None:
    body = canonical_json(manifest)
    try:
        archive.put_bytes(key, body, content_type="application/json", immutable=True)
        print(f"MANIFEST PUBLISHED {key}")
    except R2ImmutableObjectExists:
        existing = json.loads(archive.get_bytes(key).decode("utf-8"))
        fields = (
            "dataset", "as_of", "source", "schema_version", "row_count",
            "symbol_count", "min_date", "max_date", "size_bytes", "sha256",
            "object_key", "release_tag", "source_asset", "source_asset_sha256",
            "revision_sha256",
        )
        for field in fields:
            if existing.get(field) != manifest.get(field):
                raise RuntimeError(
                    f"Existing R2 manifest differs for {key}: {field}"
                )
        print(f"MANIFEST ALREADY PRESENT + VERIFIED {key}")


def _publish_current(
    archive: R2Archive,
    *,
    dataset: str,
    as_of: str,
    revision_sha256: str,
    object_key: str,
    manifest_key: str,
    source: str,
    pipeline_version: str,
) -> None:
    key = f"archive/manifests/{dataset}/{as_of}/current.json"
    pointer = {
        "dataset": dataset,
        "as_of": as_of,
        "source": source,
        "revision_sha256": revision_sha256,
        "object_key": object_key,
        "manifest_key": manifest_key,
        "pipeline_version": pipeline_version,
    }
    # This pointer is intentionally mutable. The immutable revision and its
    # manifest are the historical evidence; current.json is only convenience
    # metadata identifying the latest accepted revision.
    archive.put_bytes(
        key,
        canonical_json(pointer),
        content_type="application/json",
        immutable=False,
    )
    print(f"CURRENT POINTER UPDATED {key} -> {revision_sha256}")


def publish(
    path: Path,
    *,
    dataset: str,
    source: str,
    key_root: str,
    pipeline_version: str,
    release_tag: str,
) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)

    description = describe_parquet(path)
    as_of = description["as_of"]
    revision_sha256 = _sha256_file(path)
    object_key = (
        f"{key_root}/{as_of}/revisions/{revision_sha256}/{path.name}"
    )
    manifest_key = (
        f"archive/manifests/{dataset}/{as_of}/revisions/{revision_sha256}.json"
    )

    archive = R2Archive(R2Config.from_env())

    try:
        archive.put_file(
            object_key,
            path,
            content_type="application/octet-stream",
            immutable=True,
            verify=True,
        )
        print(f"PUBLISHED {object_key}")
    except R2ImmutableObjectExists:
        archive.verify_file(object_key, path)
        print(f"REVISION ALREADY PRESENT + VERIFIED {object_key}")

    manifest = build_manifest(
        path,
        dataset=dataset,
        as_of=as_of,
        source=source,
        pipeline_version=pipeline_version,
        row_count=description["row_count"],
        symbol_count=description["symbol_count"],
        min_date=description["min_date"],
        max_date=description["max_date"],
        extra={
            "object_key": object_key,
            "release_tag": release_tag,
            "source_asset": path.name,
            "source_asset_sha256": revision_sha256,
            "revision_sha256": revision_sha256,
        },
    )
    if description["ranking_contract"] is not None:
        manifest["ranking_contract"] = description["ranking_contract"]

    _publish_manifest(archive, manifest, manifest_key)
    _publish_current(
        archive,
        dataset=dataset,
        as_of=as_of,
        revision_sha256=revision_sha256,
        object_key=object_key,
        manifest_key=manifest_key,
        source=source,
        pipeline_version=pipeline_version,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--key-root", required=True)
    parser.add_argument("--pipeline-version", required=True)
    parser.add_argument("--release-tag", default="data-latest")
    args = parser.parse_args()

    publish(
        args.path,
        dataset=args.dataset,
        source=args.source,
        key_root=args.key_root,
        pipeline_version=args.pipeline_version,
        release_tag=args.release_tag,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
