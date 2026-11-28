"""The track-record ledger's nightly R2 copy, and the check that it matches git (owner, 22 Nov 2026, S174 "1 a" D2).

The ledger stays in git (the record of truth). Each night, for every ledger file: if R2's current copy
(dataset record/ledger/<file stem>) already holds git's exact bytes, nothing is written; otherwise git's bytes
are published as a new revision dated today. Either way the copy is then read back from R2 and its SHA-256
compared with git's; a mismatch fails the run, which fires the scheduled-failure alert.

Read by: this check, and the app's backup path if git's copy is ever unavailable.

    python scripts/track_record_r2_copy.py            # copy where needed, then check
    python scripts/track_record_r2_copy.py --check    # check only, write nothing
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Every system's ledger (src/engine/systems.LEDGERS): the Nifty 1000's, first written at the 1-5 Dec 2026 freeze,
# was left out (S236, site audit 28 Nov); until then the run warns that it is not in the checkout.
LEDGER_FILES = ("data/track_record.json", "data/track_record_1000.json", "data/track_record_nano.json",
                "data/track_record_combined.json")
DATASET_ROOT = "record/ledger"


def dataset_of(path: str) -> str:
    return f"{DATASET_ROOT}/{Path(path).stem}"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def r2_sha(reader, dataset: str) -> str | None:
    """SHA-256 of R2's current copy, or None when R2 has none yet."""
    try:
        ref = reader.resolve_current(dataset)
    except FileNotFoundError:
        return None
    return sha(reader.read_bytes(ref))


def ist_today() -> str:
    return (datetime.now(UTC) + timedelta(hours=5, minutes=30)).date().isoformat()


def run(reader, publish, files=LEDGER_FILES, root: Path = ROOT, check_only: bool = False,
        today: str | None = None) -> list[str]:
    """The files whose R2 copy does not match git after the run ([] when every one matches)."""
    bad = []
    for rel in files:
        path = root / rel
        if not path.exists():
            print(f"::warning::{rel} is not in the checkout; nothing to copy.")
            continue
        want, ds = sha(path.read_bytes()), dataset_of(rel)
        have = r2_sha(reader, ds)
        if have != want and not check_only:
            publish(path, dataset=ds, source="git", key_root=ds, pipeline_version="track-record-r2-copy",
                    release_tag="none", as_of=today or ist_today())
            print(f"{rel}: R2 copy was {'missing' if have is None else have[:12]}; published {want[:12]}")
            have = r2_sha(reader, ds)
        if have == want:
            print(f"{rel}: R2 copy matches git ({want[:12]})")
        else:
            print(f"::error::{rel}: R2 copy {'missing' if have is None else have[:12]} does not match git {want[:12]}")
            bad.append(rel)
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="compare only; write nothing")
    args = ap.parse_args()
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "scripts"))
    from r2_publish import publish

    from src.loaders.app_source import r2_config
    from src.storage.r2 import R2Archive
    from src.storage.reader import R2DatasetReader

    config = r2_config()
    if config is None:
        print("::error::R2 keys are not configured.")
        return 2
    bad = run(R2DatasetReader(R2Archive(config)), publish, check_only=args.check)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
