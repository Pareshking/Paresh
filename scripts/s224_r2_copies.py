#!/usr/bin/env python3
"""S224 (a)-(c): which git-only files have a copy on R2. Lists keys only; reads and writes nothing else.

TODO S224 (data audit part 1, 24 Nov 2026): (a) the track record
(`track_record*.json`, `book_exposure.csv`), (b) membership timelines other
than the Total Market and NSE's Nifty 1000 list, (c) `fii_dii_flows.csv` and
`results_calendar.csv` were found only in git. This walks the bucket's key
names (one listing per folder, never into a folder named by a date, so the
daily datasets cost a few requests) and reports every key or folder whose
name carries one of the files' stems. Run by s198_measure.yml beside S198 (a);
reader: TODO S224.

    PYTHONPATH=. python scripts/s224_r2_copies.py --out s224_r2_copies.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# What S224 asks about: item -> name stems looked for in R2's keys.
ITEMS = {
    "a_track_record": ["track_record", "book_exposure"],
    "b_membership": ["membership", "nifty_50", "nifty_next_50", "midcap_150", "smallcap_250", "microcap_250",
                     "nifty_500", "nanocap"],
    "c_flows_calendar": ["fii_dii", "results_calendar"],
}
# A folder named by a date (2026-11-24, date=2026-11-24, 20261124) or a content hash: not walked into.
_DATED = re.compile(r"^(\w+=)?\d{4}(-\d{2}(-\d{2})?)?$|^\d{8}$|^[0-9a-f]{32,64}$")
MAX_DEPTH = 5


def walk(list_level, prefix: str = "", depth: int = 0, out: list[str] | None = None) -> list[str]:
    """Every folder and key name under `prefix`, not descending into dated folders or below MAX_DEPTH.

    `list_level(prefix)` returns (sub-folders, keys) directly under `prefix`.
    """
    out = [] if out is None else out
    folders, keys = list_level(prefix)
    out.extend(keys)
    for f in folders:
        out.append(f)
        last = f.rstrip("/").rsplit("/", 1)[-1]
        if depth + 1 < MAX_DEPTH and not _DATED.match(last):
            walk(list_level, f, depth + 1, out)
    return out


def matches(names: list[str]) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    for item, stems in ITEMS.items():
        out[item] = {s: sorted(n for n in names if s in n.lower())[:50] for s in stems}
    return out


def _lister(archive):
    def list_level(prefix: str):
        folders, keys = [], []
        pages = archive.client.get_paginator("list_objects_v2").paginate(
            Bucket=archive.config.bucket, Prefix=prefix, Delimiter="/")
        for page in pages:
            folders += [p["Prefix"] for p in page.get("CommonPrefixes", [])]
            keys += [o["Key"] for o in page.get("Contents", [])]
        return folders, keys
    return list_level


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("s224_r2_copies.json"))
    a = ap.parse_args(argv)
    from src.storage.r2 import R2Archive, R2Config
    names = walk(_lister(R2Archive(R2Config.from_env())))
    found = matches(names)
    report = {"names_listed": len(names), "found": found,
              "summary": {item: {s: len(v) for s, v in d.items()} for item, d in found.items()}}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    for item, d in report["summary"].items():
        print(item, json.dumps(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
