"""Manifest-pinned R2 dataset reader.

This module is storage infrastructure only. It resolves immutable R2 revisions
through current pointers or explicit revision identities and validates manifest,
object size, and object SHA before returning bytes/dataframes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import pandas as pd

from .manifest import MANIFEST_SCHEMA_VERSION, sha256_bytes
from .r2 import R2Archive


class R2DatasetIntegrityError(RuntimeError):
    """The R2 pointer, manifest, or object failed an integrity check."""


@dataclass(frozen=True)
class R2DatasetRef:
    dataset: str
    as_of: str
    revision_sha256: str
    manifest_key: str
    object_key: str
    manifest: dict[str, Any]


def _json(body: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise R2DatasetIntegrityError(f"invalid JSON in {label}") from exc
    if not isinstance(value, dict):
        raise R2DatasetIntegrityError(f"{label} must contain a JSON object")
    return value


class R2DatasetReader:
    """Read canonical R2 datasets without bypassing their manifest contract."""

    def __init__(self, archive: R2Archive):
        self.archive = archive

    def resolve_current(self, dataset: str, *, as_of: str | None = None) -> R2DatasetRef:
        if as_of:
            key = f"archive/manifests/{dataset}/{as_of}/current.json"
            return self._resolve_pointer(key, expected_dataset=dataset, expected_as_of=as_of)

        prefix = f"archive/manifests/{dataset}/"
        candidates = sorted(
            key for key in self.archive.list_keys(prefix)
            if key.endswith("/current.json")
        )
        if not candidates:
            raise FileNotFoundError(f"no current R2 pointer for dataset {dataset}")
        key = candidates[-1]
        return self._resolve_pointer(key, expected_dataset=dataset)

    def resolve_latest_revision(self, dataset: str, as_of: str) -> R2DatasetRef:
        """Resolve the newest immutable revision for an exact dataset/date.

        This deliberately does not consult current.json. Immutable evidence is
        the source of truth for historical consumers; a mutable pointer is only
        a convenience index and must never be required for PIT research.
        """
        try:
            normalized_as_of = date.fromisoformat(as_of).isoformat()
        except (TypeError, ValueError) as exc:
            raise R2DatasetIntegrityError(f"invalid as_of date: {as_of!r}") from exc
        if normalized_as_of != as_of:
            raise R2DatasetIntegrityError(f"as_of must be ISO YYYY-MM-DD: {as_of!r}")

        prefix = f"archive/manifests/{dataset}/{as_of}/revisions/"
        keys = sorted(
            key for key in self.archive.list_keys(prefix) if key.endswith(".json")
        )
        if not keys:
            raise FileNotFoundError(
                f"no immutable R2 revisions for dataset {dataset} as_of={as_of}"
            )
        candidates = []
        for key in keys:
            revision = key.rsplit("/", 1)[-1][:-5]
            if len(revision) != 64 or any(c not in "0123456789abcdef" for c in revision):
                raise R2DatasetIntegrityError(f"invalid revision key: {key}")
            candidates.append(self.resolve_revision(dataset, as_of, revision))
        def _created_at(ref: R2DatasetRef) -> str:
            value = ref.manifest.get("created_at")
            if not isinstance(value, str) or not value.strip():
                raise R2DatasetIntegrityError(
                    f"immutable manifest missing created_at: {ref.manifest_key}"
                )
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise R2DatasetIntegrityError(
                    f"invalid manifest created_at: {ref.manifest_key}"
                ) from exc
            if parsed.tzinfo is None:
                raise R2DatasetIntegrityError(
                    f"manifest created_at must include timezone: {ref.manifest_key}"
                )
            return parsed.astimezone().isoformat()

        candidates.sort(key=lambda ref: (_created_at(ref), ref.revision_sha256))
        return candidates[-1]

    def resolve_revision(
        self,
        dataset: str,
        as_of: str,
        revision_sha256: str,
    ) -> R2DatasetRef:
        if len(revision_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in revision_sha256
        ):
            raise ValueError("revision_sha256 must be a lowercase 64-character SHA-256")

        manifest_key = (
            f"archive/manifests/{dataset}/{as_of}/revisions/"
            f"{revision_sha256}.json"
        )
        manifest = self._load_manifest(manifest_key)
        self._validate_manifest(
            manifest,
            dataset=dataset,
            as_of=as_of,
            revision_sha256=revision_sha256,
        )
        object_key = str(manifest.get("object_key", ""))
        if not object_key:
            raise R2DatasetIntegrityError("manifest has no object_key")
        self._validate_object(object_key, manifest)
        return R2DatasetRef(
            dataset=dataset,
            as_of=as_of,
            revision_sha256=revision_sha256,
            manifest_key=manifest_key,
            object_key=object_key,
            manifest=manifest,
        )

    def read_bytes(self, ref: R2DatasetRef) -> bytes:
        body = self.archive.get_bytes(ref.object_key)
        actual_sha = sha256_bytes(body)
        expected_sha = str(ref.manifest.get("sha256", ""))
        if actual_sha != expected_sha or actual_sha != ref.revision_sha256:
            raise R2DatasetIntegrityError(
                f"R2 object SHA mismatch for {ref.object_key}: "
                f"expected={ref.revision_sha256}, actual={actual_sha}"
            )
        expected_size = int(ref.manifest.get("size_bytes", -1))
        if len(body) != expected_size:
            raise R2DatasetIntegrityError(
                f"R2 object size mismatch for {ref.object_key}: "
                f"expected={expected_size}, actual={len(body)}"
            )
        return body

    def read_parquet(self, ref: R2DatasetRef) -> pd.DataFrame:
        from io import BytesIO

        return pd.read_parquet(BytesIO(self.read_bytes(ref)))

    def read_current_parquet(
        self, dataset: str, *, as_of: str | None = None
    ) -> tuple[R2DatasetRef, pd.DataFrame]:
        ref = self.resolve_current(dataset, as_of=as_of)
        return ref, self.read_parquet(ref)

    def _resolve_pointer(
        self,
        pointer_key: str,
        *,
        expected_dataset: str,
        expected_as_of: str | None = None,
    ) -> R2DatasetRef:
        pointer = _json(self.archive.get_bytes(pointer_key), pointer_key)
        dataset = str(pointer.get("dataset", ""))
        as_of = str(pointer.get("as_of", ""))
        revision = str(pointer.get("revision_sha256", ""))
        manifest_key = str(pointer.get("manifest_key", ""))
        object_key = str(pointer.get("object_key", ""))

        if dataset != expected_dataset:
            raise R2DatasetIntegrityError(
                f"pointer dataset mismatch: expected={expected_dataset}, actual={dataset}"
            )
        if expected_as_of is not None and as_of != expected_as_of:
            raise R2DatasetIntegrityError(
                f"pointer as_of mismatch: expected={expected_as_of}, actual={as_of}"
            )
        if not revision or not manifest_key or not object_key:
            raise R2DatasetIntegrityError(f"incomplete current pointer: {pointer_key}")

        manifest = self._load_manifest(manifest_key)
        self._validate_manifest(
            manifest,
            dataset=dataset,
            as_of=as_of,
            revision_sha256=revision,
        )

        if str(manifest_key) != str(pointer.get("manifest_key", "")):
            raise R2DatasetIntegrityError("pointer manifest_key mismatch")
        if str(object_key) != str(pointer.get("object_key", "")):
            raise R2DatasetIntegrityError("pointer object_key mismatch")

        self._validate_object(object_key, manifest)
        return R2DatasetRef(
            dataset=dataset,
            as_of=as_of,
            revision_sha256=revision,
            manifest_key=manifest_key,
            object_key=object_key,
            manifest=manifest,
        )

    def _load_manifest(self, key: str) -> dict[str, Any]:
        return _json(self.archive.get_bytes(key), key)

    @staticmethod
    def _validate_manifest(
        manifest: dict[str, Any],
        *,
        dataset: str,
        as_of: str,
        revision_sha256: str,
    ) -> None:
        try:
            schema_version = int(manifest.get("schema_version", -1))
        except (TypeError, ValueError) as exc:
            raise R2DatasetIntegrityError("manifest has invalid schema_version") from exc
        if schema_version != MANIFEST_SCHEMA_VERSION:
            raise R2DatasetIntegrityError("unsupported R2 manifest schema version")
        if str(manifest.get("dataset", "")) != dataset:
            raise R2DatasetIntegrityError("manifest dataset mismatch")
        manifest_as_of = str(manifest.get("as_of", ""))
        try:
            normalized_as_of = date.fromisoformat(manifest_as_of).isoformat()
        except (TypeError, ValueError) as exc:
            raise R2DatasetIntegrityError("manifest has invalid as_of") from exc
        if normalized_as_of != manifest_as_of or manifest_as_of != as_of:
            raise R2DatasetIntegrityError("manifest as_of mismatch")
        if str(manifest.get("sha256", "")) != revision_sha256:
            raise R2DatasetIntegrityError("manifest SHA does not match revision identity")
        if str(manifest.get("revision_sha256", "")) != revision_sha256:
            raise R2DatasetIntegrityError("manifest revision SHA does not match revision identity")
        try:
            size_bytes = int(manifest.get("size_bytes", -1))
        except (TypeError, ValueError) as exc:
            raise R2DatasetIntegrityError("manifest has invalid size_bytes") from exc
        if size_bytes < 0:
            raise R2DatasetIntegrityError("manifest has invalid size_bytes")
        created_at = manifest.get("created_at")
        if not isinstance(created_at, str) or not created_at.strip():
            raise R2DatasetIntegrityError("manifest has no created_at")
        try:
            parsed_created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise R2DatasetIntegrityError("manifest has invalid created_at") from exc
        if parsed_created_at.tzinfo is None:
            raise R2DatasetIntegrityError("manifest created_at must include timezone")

    def _validate_object(self, object_key: str, manifest: dict[str, Any]) -> None:
        head = self.archive.head(object_key)
        remote_size = int(head.get("ContentLength", -1))
        expected_size = int(manifest.get("size_bytes", -1))
        if remote_size != expected_size:
            raise R2DatasetIntegrityError(
                f"R2 HEAD size mismatch for {object_key}: "
                f"expected={expected_size}, actual={remote_size}"
            )
