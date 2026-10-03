"""Put the BSE bhavcopy work on R2, under one prefix that is meant to be deleted.

    python scripts/bse_to_r2.py --raw data_cache/bse_raw --table data_cache/bse_daily.parquet \
        --audit audit/ --prefix scratch/bse_bhavcopy_2026-10-03

Owner, 3 Oct 2026: "upload everything to R2, we will delete it after all the data
is aligned, including the raw data downloaded from BSE". So this is scratch, not a
dataset: the prefix is outside every dataset scripts/r2_retention.py lists, and
nothing reads it. Delete the whole prefix once NSE and BSE are reconciled.

What goes there:
  raw_<year>.tar        BSE's files as downloaded, one tar per year (about 250 files each)
  bse_daily.parquet     the table scripts/bse_bhavcopy.py build makes
  status.csv            what each session's download returned (none = BSE has no file)
  bse_gap_verify.csv    scripts/audit_gaps_against_bse.py output
  MANIFEST.json         sizes, SHA-256, row and day counts, source, how to rebuild, when to delete

Objects are immutable (a key that exists is left alone and reported), and every
upload is read back and checked against its SHA-256 (R2Archive.put_file).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.storage.r2 import R2Archive, R2Config, R2ImmutableObjectExists


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def year_of(name: str) -> int | None:
    m = re.match(r"EQ\d{4}(\d\d)\.zip$", name)         # EQ<DDMMYY>.zip
    if m:
        yy = int(m.group(1))
        return 2000 + yy
    m = re.match(r"U(\d{4})\d{4}\.csv$", name)          # U<YYYYMMDD>.csv
    return int(m.group(1)) if m else None


def pack_raw(raw: Path, workdir: Path) -> list[Path]:
    by_year: dict[int, list[Path]] = {}
    for f in sorted(raw.iterdir()):
        y = year_of(f.name)
        if y:
            by_year.setdefault(y, []).append(f)
    tars = []
    for y, files in sorted(by_year.items()):
        tar = workdir / f"raw_{y}.tar"
        with tarfile.open(tar, "w") as t:      # the files are already zip or small csv: no second compression
            for f in files:
                t.add(f, arcname=f.name)
        tars.append(tar)
    return tars


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raw", required=True)
    ap.add_argument("--table", required=True)
    ap.add_argument("--audit", required=True, help="directory holding bse_gap_verify.csv")
    ap.add_argument("--prefix", required=True, help="e.g. scratch/bse_bhavcopy_2026-10-03")
    ap.add_argument("--dry-run", action="store_true", help="pack and describe, upload nothing")
    args = ap.parse_args()
    prefix = args.prefix.strip("/")
    if not prefix.startswith("scratch/"):
        raise SystemExit("the prefix must start with scratch/: this is data to be deleted, not a dataset")

    raw, table, audit = Path(args.raw), Path(args.table), Path(args.audit)
    frame = pd.read_parquet(table, columns=["date", "code"])
    status = raw / "status.csv"
    work = Path(tempfile.mkdtemp(prefix="bse_r2_"))
    files = [*pack_raw(raw, work), table, audit / "bse_gap_verify.csv"]
    if status.exists():
        files.append(status)

    manifest = {
        "what": "BSE bhavcopy 2008 to date, raw as downloaded plus the built table and the gap audit",
        "purpose": "check NSE price gaps and prices against a second exchange (docs/DATA_CORRECTNESS.md)",
        "delete_when": "NSE and BSE data are aligned (owner, 2026-10-03); delete the whole prefix",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "https://www.bseindia.com/download/BhavCopy/Equity/ (EQ<DDMMYY>_CSV.ZIP to 2024-07-05, "
                  "BhavCopy_BSE_CM_0_0_0_<YYYYMMDD>_F_0000.CSV after)",
        "rebuild": "python scripts/bse_bhavcopy.py --mode download / build; python scripts/audit_gaps_against_bse.py",
        "table": {"rows": int(len(frame)), "days": int(frame.date.nunique()), "codes": int(frame.code.nunique()),
                  "first": str(frame.date.min().date()), "last": str(frame.date.max().date())},
        "files": {p.name: {"bytes": p.stat().st_size, "sha256": sha256(p)} for p in files},
    }
    manifest_path = work / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=1))
    print(json.dumps({k: v for k, v in manifest.items() if k != "files"}, indent=1))
    for name, meta in manifest["files"].items():
        print(f"  {name:24} {meta['bytes']:>12,} bytes")
    if args.dry_run:
        return 0

    r2 = R2Archive(R2Config.from_env())
    for p in [*files, manifest_path]:
        key = f"{prefix}/{p.name}"
        try:
            r2.put_file(key, p, content_type="application/octet-stream")
            print("uploaded", key)
        except R2ImmutableObjectExists:
            r2.verify_file(key, p)
            print("already there, checksum matches:", key)
    print("done:", len(files) + 1, "objects under", prefix)
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
