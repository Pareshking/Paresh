"""Bootstrap validated GitHub Release snapshots into the R2 archive.

This is a migration tool, not the daily writer. It publishes immutable
date-addressed objects and manifests and never deletes or replaces an existing
R2 object.
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


ASSETS = {
    "prices_full.parquet": {
        "dataset": "prices/yahoo/bootstrap",
        "source": "yahoo",
        "key_root": "archive/prices/yahoo/bootstrap",
    },
    "screener_prices.parquet": {
        "dataset": "prices/screener/bootstrap",
        "source": "screener",
        "key_root": "archive/prices/screener/bootstrap",
    },
    "prices.parquet": {
        "dataset": "snapshots/application",
        "source": "application",
        "key_root": "snapshots/application",
    },
    "rankings.parquet": {
        "dataset": "snapshots/rankings",
        "source": "system1",
        "key_root": "snapshots/rankings",
    },
}


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


def _describe(path: Path) -> dict[str, Any]:
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

    as_of = max_date
    if not as_of:
        raise RuntimeError(f"Cannot establish as_of for {path}")

    return {
        "as_of": as_of,
        "row_count": row_count,
        "symbol_count": symbol_count,
        "min_date": min_date,
        "max_date": max_date,
        "ranking_contract": contract,
    }


def _publish_file(archive: R2Archive, path: Path, key: str, *, content_type: str) -> None:
    try:
        archive.put_file(
            key, path, content_type=content_type, immutable=True, verify=True
        )
        print(f"PUBLISHED {key}")
    except R2ImmutableObjectExists:
        archive.verify_file(key, path)
        print(f"ALREADY PRESENT + VERIFIED {key}")


def _publish_manifest(archive: R2Archive, manifest: dict[str, Any], key: str) -> None:
    body = canonical_json(manifest)
    try:
        archive.put_bytes(key, body, content_type="application/json", immutable=True)
        print(f"MANIFEST PUBLISHED {key}")
    except R2ImmutableObjectExists:
        existing = json.loads(archive.get_bytes(key).decode("utf-8"))
        for field in (
            "dataset", "as_of", "source", "schema_version", "row_count",
            "symbol_count", "min_date", "max_date", "size_bytes", "sha256",
            "pipeline_version", "object_key",
        ):
            if existing.get(field) != manifest.get(field):
                raise RuntimeError(f"Existing manifest differs for {key}: {field}")
        print(f"MANIFEST ALREADY PRESENT + VERIFIED {key}")


def bootstrap(root: Path, release_tag: str, pipeline_version: str) -> None:
    archive = R2Archive(R2Config.from_env())

    for filename, spec in ASSETS.items():
        path = root / filename
        if not path.is_file():
            raise FileNotFoundError(
                f"Required release asset missing: {path}. "
                "Bootstrap is fail-closed; no partial migration is accepted."
            )

        description = _describe(path)
        as_of = description["as_of"]
        object_key = f"{spec['key_root']}/{as_of}/{filename}"
        manifest_key = f"archive/manifests/{spec['dataset']}/{as_of}.json"

        _publish_file(
            archive, path, object_key, content_type="application/octet-stream"
        )

        manifest = build_manifest(
            path,
            dataset=spec["dataset"],
            as_of=as_of,
            source=spec["source"],
            pipeline_version=pipeline_version,
            row_count=description["row_count"],
            symbol_count=description["symbol_count"],
            min_date=description["min_date"],
            max_date=description["max_date"],
            extra={
                "object_key": object_key,
                "release_tag": release_tag,
                "source_asset": filename,
                "source_asset_sha256": None,
            },
        )
        manifest["source_asset_sha256"] = manifest["sha256"]
        if description["ranking_contract"] is not None:
            manifest["ranking_contract"] = description["ranking_contract"]

        _publish_manifest(archive, manifest, manifest_key)

    print("R2 PHASE-2 BOOTSTRAP PASSED")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument("--release-tag", default="data-latest")
    parser.add_argument("--pipeline-version", default="r2-bootstrap-v1")
    args = parser.parse_args()
    bootstrap(args.root, args.release_tag, args.pipeline_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
