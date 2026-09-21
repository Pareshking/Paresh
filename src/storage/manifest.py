"""Dataset manifest and checksum primitives.

A manifest is the identity card of an archived dataset. It records the
minimum facts required to reproduce and audit a publication without treating a
mutable latest object as historical truth.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA_VERSION = 1


def sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def sha256_file(path: str | Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(
    path: str | Path,
    *,
    dataset: str,
    as_of: str,
    source: str,
    pipeline_version: str,
    row_count: int | None = None,
    symbol_count: int | None = None,
    min_date: str | None = None,
    max_date: str | None = None,
    schema_version: int = MANIFEST_SCHEMA_VERSION,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a manifest for a local candidate artifact."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(file_path)
    manifest: dict[str, Any] = {
        "dataset": dataset,
        "as_of": as_of,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "schema_version": int(schema_version),
        "row_count": row_count,
        "symbol_count": symbol_count,
        "min_date": min_date,
        "max_date": max_date,
        "size_bytes": file_path.stat().st_size,
        "sha256": sha256_file(file_path),
        "pipeline_version": pipeline_version,
    }
    if extra:
        manifest.update(extra)
    return manifest


def canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def verify_manifest(
    path: str | Path,
    manifest: dict[str, Any],
    *,
    require_size: bool = True,
) -> tuple[bool, str]:
    """Verify the local artifact against its recorded checksum/size."""
    file_path = Path(path)
    if not file_path.is_file():
        return False, "file missing"
    expected_sha = str(manifest.get("sha256", ""))
    if not expected_sha:
        return False, "manifest has no sha256"
    actual_sha = sha256_file(file_path)
    if actual_sha != expected_sha:
        return False, "sha256 differs"
    if require_size:
        expected_size = manifest.get("size_bytes")
        if expected_size is None:
            return False, "manifest has no size_bytes"
        if int(expected_size) != file_path.stat().st_size:
            return False, "size_bytes differs"
    return True, "ok"
