"""Publish a validated production artifact to the canonical R2 archive.

This is the Phase-3 dual-publication boundary. It does not fetch market data,
rank symbols, or transform source values. The caller supplies the exact file
that was already validated/published by the existing pipeline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from src.storage.manifest import build_manifest, canonical_json
from src.storage.r2 import R2Archive, R2Config, R2ImmutableObjectExists


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


def _verify_existing(
    archive: R2Archive,
    path: Path,
    key: str,
) -> None:
    archive.verify_file(key, path)
    print(f"ALREADY PRESENT + VERIFIED {key}")


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
            "dataset",
            "as_of",
            "source",
            "schema_version",
            "row_count",
            "symbol_count",
            "min_date",
            "max_date",
            "size_bytes",
            "sha256",
            "object_key",
            "release_tag",
            "source_asset",
            "source_asset_sha256",
        )
        for field in fields:
            if existing.get(field) != manifest.get(field):
                raise RuntimeError(
                    f"Existing R2 manifest differs for {key}: {field}"
                )
        print(f"MANIFEST ALREADY PRESENT + VERIFIED {key}")


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
    object_key = f"{key_root}/{as_of}/{path.name}"
    manifest_key = f"archive/manifests/{dataset}/{as_of}.json"

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
        _verify_existing(archive, path, object_key)

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
            "source_asset_sha256": None,
        },
    )
    manifest["source_asset_sha256"] = manifest["sha256"]
    if description["ranking_contract"] is not None:
        manifest["ranking_contract"] = description["ranking_contract"]

    _publish_manifest(archive, manifest, manifest_key)


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
