#!/usr/bin/env python3
"""Daily copy of NSE's reference feeds: ticker changes, name changes, listed equities, corporate actions.

    python scripts/sync_nse_reference.py            # fetch, write, report
    python scripts/sync_nse_reference.py --dry-run  # fetch and report, write nothing

Writes data/reference/nse/ (latest copy of each feed + MANIFEST.json with fetch time, rows and SHA-256) and
data/reference/nse/CHANGES.json (what is new since the previous run, and which of it touches a name in the
membership record). It never edits membership_history.json: a rename or a demerger is a decision, not a diff.
It refuses to replace a feed with an empty or shrunken one and exits non-zero, so a blocked or broken fetch is
loud instead of silently overwriting good data. See nse_index_rebuild/FEEDS.md.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reference" / "nse"
ARCHIVE = "https://nsearchives.nseindia.com/content/equities/"
FEEDS = {
    "symbolchange.csv": ARCHIVE + "symbolchange.csv",
    "namechange.csv": ARCHIVE + "namechange.csv",
    "equity_l.csv": ARCHIVE + "EQUITY_L.csv",
}
CA_URL = "https://www.nseindia.com/api/corporates-corporateActions"
CA_DAYS = 45
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
# A feed that loses more than this share of its rows is a broken download, not a real change.
SHRINK_LIMIT = 0.10


class SyncError(RuntimeError):
    pass


def _get(url: str, params: dict | None = None, tries: int = 5, session=requests) -> bytes:
    last = None
    for attempt in range(1, tries + 1):
        try:
            r = session.get(url, params=params, headers=UA, timeout=60)
            if r.status_code == 200 and r.content:
                return r.content
            last = f"HTTP {r.status_code}, {len(r.content)} bytes"
        except requests.RequestException as exc:
            last = repr(exc)
        time.sleep(attempt * 3)
    raise SyncError(f"{url}: {last}")


# symbolchange.csv has no header row; its columns are fixed by NSE.
HEADERLESS = {"symbolchange.csv": ["company", "old_symbol", "new_symbol", "date"]}


def parse_csv(raw: bytes, fieldnames: list[str] | None = None) -> list[dict]:
    text = raw.decode("utf-8", errors="replace").lstrip("\ufeff")
    return [{(k or "").strip(): (v or "").strip() for k, v in row.items() if k is not None}
            for row in csv.DictReader(io.StringIO(text), fieldnames=fieldnames)]


def guard(name: str, new_rows: int, old_rows: int | None) -> None:
    """Refuse an empty feed, or one that shrank by more than SHRINK_LIMIT."""
    if new_rows == 0:
        raise SyncError(f"{name}: no rows")
    if old_rows and new_rows < old_rows * (1 - SHRINK_LIMIT):
        raise SyncError(f"{name}: {new_rows} rows against {old_rows} before; refusing to overwrite")


def fetch_corporate_actions(today: datetime, days: int = CA_DAYS, fetch=_get) -> list[dict]:
    params = {"index": "equities", "from_date": (today - timedelta(days=days)).strftime("%d-%m-%Y"),
              "to_date": today.strftime("%d-%m-%Y")}
    rows = json.loads(fetch(CA_URL, params))
    if not isinstance(rows, list):
        raise SyncError("corporate actions: unexpected response shape")
    return rows


def _key(row: dict, fields: tuple[str, ...]) -> tuple:
    return tuple(row.get(f, "") for f in fields)


def diff_new(old: list[dict], new: list[dict], fields: tuple[str, ...]) -> list[dict]:
    seen = {_key(r, fields) for r in old}
    return [r for r in new if _key(r, fields) not in seen]


def membership_symbols(path: Path | None = None) -> set[str]:
    """Every symbol the membership record has named in the last two years of changes plus today's lists."""
    path = path or ROOT / "data" / "membership_history.json"
    try:
        hist = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    names: set[str] = set()
    for ix in (hist.get("indices") or {}).values():
        names |= set(ix.get("baseline", {}).get("symbols", []))
        for c in ix.get("changes", [])[-12:]:
            names |= set(c.get("added", [])) | set(c.get("removed", []))
    return names


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "MANIFEST.json"
    old_manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"files": {}}
    now = datetime.now(timezone.utc)
    manifest = {"fetched_at_utc": now.isoformat(timespec="seconds"), "files": {}}
    changes: dict = {"fetched_at_utc": manifest["fetched_at_utc"], "new": {}, "touching_members": {}}
    members = membership_symbols()
    pending: dict[str, bytes] = {}
    try:
        for name, url in FEEDS.items():
            raw = _get(url)
            rows = parse_csv(raw, HEADERLESS.get(name))
            guard(name, len(rows), old_manifest["files"].get(name, {}).get("rows"))
            old_path = OUT / name
            old_rows = parse_csv(old_path.read_bytes(), HEADERLESS.get(name)) if old_path.exists() else []
            fields = {"symbolchange.csv": ("old_symbol", "new_symbol", "date"),
                      "namechange.csv": ("NCH_SYMBOL", "NCH_NEW_NAME", "NCH_DT"), "equity_l.csv": ("SYMBOL",)}[name]
            new = diff_new(old_rows, rows, fields) if old_rows else []
            changes["new"][name] = new
            hits = [r for r in new if any(v.strip().upper() in members for v in r.values())]
            if hits:
                changes["touching_members"][name] = hits
            manifest["files"][name] = {"url": url, "rows": len(rows), "sha256": hashlib.sha256(raw).hexdigest()}
            pending[name] = raw
        ca = fetch_corporate_actions(now)
        guard("corporate_actions_recent.json", len(ca), None)
        old_ca_path = OUT / "corporate_actions_recent.json"
        old_ca = json.loads(old_ca_path.read_text()) if old_ca_path.exists() else []
        ca_fields = ("symbol", "exDate", "subject")
        new_ca = diff_new(old_ca, ca, ca_fields) if old_ca else []
        changes["new"]["corporate_actions"] = new_ca
        hits = [r for r in new_ca if r.get("symbol", "").upper() in members]
        if hits:
            changes["touching_members"]["corporate_actions"] = hits
        ca_bytes = (json.dumps(ca, indent=1, sort_keys=True) + "\n").encode()
        manifest["files"]["corporate_actions_recent.json"] = {
            "url": CA_URL, "window_days": CA_DAYS, "rows": len(ca), "sha256": hashlib.sha256(ca_bytes).hexdigest()}
        pending["corporate_actions_recent.json"] = ca_bytes
    except SyncError as exc:
        print(f"::error::NSE reference sync failed, nothing was written: {exc}")
        return 1
    for name, n in ((k, len(v)) for k, v in changes["new"].items()):
        print(f"{name}: {n} new row(s)")
    for name, rows in changes["touching_members"].items():
        for r in rows:
            print(f"::warning::{name} touches an index member: {json.dumps(r)[:200]}")
    if args.dry_run:
        return 0
    for name, raw in pending.items():
        (OUT / name).write_bytes(raw)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    (OUT / "CHANGES.json").write_text(json.dumps(changes, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
