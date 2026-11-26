"""Publish the app pack to R2 and check it (S172 (b), owner 26 Nov 2026: "Stop commit and save everything in R2").

Step 1: the pack is built from the checkout's committed files, published as a new revision of
`app/pack` only when its bytes differ from R2's current one, read back and checked file by file
against the checkout. A mismatch fails the run, which fires the scheduled-failure alert.

Read by: the app (src/loaders/app_pack.py), every page.

    python scripts/app_pack.py            # publish when changed, then check
    python scripts/app_pack.py --check    # check only, write nothing
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.loaders import app_pack as ap  # noqa: E402

KEY_ROOT = "archive/app/pack"


def ist_today() -> str:
    return (datetime.now(UTC) + timedelta(hours=5, minutes=30)).date().isoformat()


def current(reader) -> bytes | None:
    try:
        ref = reader.resolve_current(ap.DATASET)
    except FileNotFoundError:
        return None
    return reader.read_bytes(ref)


def differences(pack: dict[str, bytes], root: Path, files=ap.FILES) -> list[str]:
    """Files whose pack copy is not the checkout's bytes (or is missing from one side)."""
    out = []
    for rel in files:
        p = root / rel
        mine = p.read_bytes() if p.is_file() else None
        if pack.get(rel) != mine:
            out.append(rel)
    return out


def run(reader, publish, root: Path = ROOT, check_only: bool = False, today: str | None = None) -> list[str]:
    body = ap.build(root)
    have = current(reader)
    if have != body and not check_only:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app_pack.zip"
            path.write_bytes(body)
            publish(path, dataset=ap.DATASET, source="git", key_root=KEY_ROOT, pipeline_version="app-pack",
                    release_tag="none", as_of=today or ist_today())
        print(f"Published app pack {ap.sha256(body)[:12]} ({len(body):,} bytes, {len(ap.unpack(body))} files).")
        have = current(reader)
    elif have == body:
        print(f"R2's app pack already holds the checkout's bytes ({ap.sha256(body)[:12]}).")
    if have is None:
        print("::error::R2 has no app pack.")
        return list(ap.FILES)
    bad = differences(ap.unpack(have), root)
    for rel in bad:
        print(f"::error::{rel}: R2's app pack does not hold the checkout's bytes")
    if not bad:
        print(f"All {len(ap.FILES)} files in R2's app pack match the checkout.")
    return bad


def main() -> int:
    ap_ = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap_.add_argument("--check", action="store_true", help="compare only; write nothing")
    args = ap_.parse_args()
    from r2_publish import publish

    from src.loaders.app_source import r2_config
    from src.storage.r2 import R2Archive
    from src.storage.reader import R2DatasetReader

    config = r2_config()
    if config is None:
        print("::error::R2 keys are not configured.")
        return 2
    return 1 if run(R2DatasetReader(R2Archive(config)), publish, check_only=args.check) else 0


if __name__ == "__main__":
    raise SystemExit(main())
