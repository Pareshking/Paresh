"""Cloudflare R2 archive adapter.

R2 is the durable archive, not an application cache. This module contains
only storage mechanics; it deliberately knows nothing about rankings,
universes, or source-specific data semantics.

The adapter supports:
- bucket-scoped S3 credentials from environment variables;
- immutable-by-default publication with PutObject If-None-Match;
- explicit overwrite for mutable convenience objects;
- head/get/list operations;
- upload verification by size and SHA-256;
- no credential logging.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import boto3
from botocore.exceptions import ClientError


class R2ConfigurationError(RuntimeError):
    """Required R2 configuration is missing or invalid."""


class R2VerificationError(RuntimeError):
    """An uploaded object did not match the local source."""


class R2ImmutableObjectExists(RuntimeError):
    """An immutable archive key already exists."""


@dataclass(frozen=True)
class R2Config:
    account_id: str
    access_key_id: str
    secret_access_key: str
    endpoint: str
    bucket: str

    @classmethod
    def from_env(cls) -> "R2Config":
        values = {
            "account_id": os.getenv("R2_ACCOUNT_ID", "").strip(),
            "access_key_id": os.getenv("R2_ACCESS_KEY_ID", "").strip(),
            "secret_access_key": os.getenv("R2_SECRET_ACCESS_KEY", "").strip(),
            "endpoint": os.getenv("R2_ENDPOINT", "").strip().rstrip("/"),
            "bucket": os.getenv("R2_BUCKET", "").strip(),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise R2ConfigurationError(
                "Missing R2 configuration: " + ", ".join(missing)
            )
        if not values["endpoint"].startswith("https://"):
            raise R2ConfigurationError("R2_ENDPOINT must use https://")
        if ".r2.cloudflarestorage.com" not in values["endpoint"]:
            raise R2ConfigurationError(
                "R2_ENDPOINT is not a Cloudflare R2 S3 endpoint"
            )
        return cls(**values)

    def redacted(self) -> dict[str, str]:
        """Safe diagnostic representation; never returns secret material."""
        return {
            "account_id": self.account_id,
            "access_key_id": self.access_key_id[:4] + "..." if self.access_key_id else "",
            "endpoint": self.endpoint,
            "bucket": self.bucket,
        }


class R2Archive:
    """Small S3-compatible adapter for the canonical R2 archive."""

    def __init__(self, config: R2Config, client=None):
        self.config = config
        self.client = client or boto3.client(
            "s3",
            endpoint_url=config.endpoint,
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
            region_name="auto",
        )

    def head(self, key: str) -> dict:
        return self.client.head_object(Bucket=self.config.bucket, Key=_key(key))

    def exists(self, key: str) -> bool:
        try:
            self.head(key)
            return True
        except ClientError as exc:
            if _status(exc) == 404:
                return False
            raise

    def put_bytes(
        self,
        key: str,
        body: bytes,
        *,
        content_type: str | None = None,
        immutable: bool = True,
    ) -> dict:
        """Publish bytes; immutable publication cannot replace an existing key."""
        params = {
            "Bucket": self.config.bucket,
            "Key": _key(key),
            "Body": body,
        }
        if content_type:
            params["ContentType"] = content_type
        if immutable:
            params["IfNoneMatch"] = "*"
        try:
            return self.client.put_object(**params)
        except ClientError as exc:
            if immutable and _status(exc) == 412:
                raise R2ImmutableObjectExists(
                    f"Immutable R2 object already exists: {key}"
                ) from exc
            raise

    def put_file(
        self,
        key: str,
        path: str | os.PathLike[str],
        *,
        content_type: str | None = None,
        immutable: bool = True,
        verify: bool = True,
    ) -> dict:
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(source)
        with source.open("rb") as fh:
            params = {
                "Bucket": self.config.bucket,
                "Key": _key(key),
                "Body": fh,
            }
            if content_type:
                params["ContentType"] = content_type
            if immutable:
                params["IfNoneMatch"] = "*"
            try:
                response = self.client.put_object(**params)
            except ClientError as exc:
                if immutable and _status(exc) == 412:
                    raise R2ImmutableObjectExists(
                        f"Immutable R2 object already exists: {key}"
                    ) from exc
                raise
        if verify:
            self.verify_file(key, source)
        return response

    def get_bytes(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.config.bucket, Key=_key(key))
        return response["Body"].read()

    def get_file(self, key: str, path: str | os.PathLike[str]) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        response = self.client.get_object(Bucket=self.config.bucket, Key=_key(key))
        with target.open("wb") as fh:
            for chunk in response["Body"].iter_chunks(chunk_size=1 << 20):
                fh.write(chunk)
        return target

    def list_keys(self, prefix: str = "") -> Iterator[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=self.config.bucket, Prefix=_key(prefix) if prefix else ""
        ):
            for obj in page.get("Contents", []):
                yield str(obj["Key"])

    def list_objects(self, prefix: str = "") -> Iterator[tuple[str, int]]:
        """(key, size in bytes) for every object under ``prefix``."""
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=self.config.bucket, Prefix=_key(prefix) if prefix else ""
        ):
            for obj in page.get("Contents", []):
                yield str(obj["Key"]), int(obj.get("Size", 0))

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.config.bucket, Key=_key(key))

    def verify_file(self, key: str, source: str | os.PathLike[str]) -> None:
        path = Path(source)
        local_size = path.stat().st_size
        remote = self.head(key)
        remote_size = int(remote.get("ContentLength", -1))
        if remote_size != local_size:
            raise R2VerificationError(
                f"R2 size mismatch for {key}: local={local_size}, remote={remote_size}"
            )

        local_sha = _sha256_file(path)
        # Streamed: the ten-year price archive is verified on every daily
        # publish, and reading it whole doubled the runner's peak memory.
        response = self.client.get_object(Bucket=self.config.bucket, Key=_key(key))
        digest = hashlib.sha256()
        for chunk in response["Body"].iter_chunks(chunk_size=1 << 20):
            digest.update(chunk)
        remote_sha = digest.hexdigest()
        if local_sha != remote_sha:
            raise R2VerificationError(
                f"R2 SHA-256 mismatch for {key}: local={local_sha}, remote={remote_sha}"
            )


def _key(value: str) -> str:
    key = str(value).strip().lstrip("/")
    if not key or "\x00" in key:
        raise ValueError("R2 object key must be non-empty and contain no NUL")
    return key


def _status(exc: ClientError) -> int | None:
    try:
        return int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode"))
    except (TypeError, ValueError):
        return None


def _sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()
