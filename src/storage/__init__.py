"""Durable archive storage primitives.

The storage package is deliberately independent from the quantitative engine.
R2 is infrastructure: callers publish and retrieve validated datasets without
knowing S3 signing, authentication, or object-store mechanics.
"""

from .manifest import build_manifest, sha256_file, sha256_bytes, verify_manifest
from .r2 import R2Archive, R2Config

__all__ = [
    "R2Archive",
    "R2Config",
    "build_manifest",
    "sha256_file",
    "sha256_bytes",
    "verify_manifest",
]
