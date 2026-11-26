"""The app pack: the job outputs the pages read, as one R2 dataset (S172 (b), owner 26 Nov 2026).

Owner, 26 Nov 2026: "Stop commit and save everything in R2". The 37 files below are written by
the nightly jobs and read by the pages. They travel to R2 as one zip, `app/pack`, with each
file's SHA-256 in `pack.json` inside it. The app reads the pack once, checks every file against
that list, and serves the files from it; a file the pack lacks, or a pack that cannot be read,
falls back to the committed copy. The reference tables (`data/reference/`, the price notes) and
the track-record ledgers (D2) are not in the pack: they stay in git.

Step 1 (now): the jobs still commit, and `scripts/app_pack.py` publishes the pack from the
commit, so the two hold the same bytes and the pages can be checked against git. Step 2: each
job publishes into the pack and stops committing its files.

    resolve("data/benchmarks.csv")  ->  the pack's copy if it has one, else the path given
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import threading
import time
import zipfile
from pathlib import Path

from src.core import code_reload
from src.core.logger import logger

DATASET = "app/pack"
LABEL = "app_pack"
MANIFEST = "pack.json"
ROOT = Path(__file__).resolve().parents[2]

# Repository-relative paths. Measured 26 Nov 2026: every page in three systems, an audit hook on
# open() (docs/archive/S172_INVENTORY_2026-11-26.md, group C).
FILES: tuple[str, ...] = (
    "data/backtest_reference.json",
    "data/benchmark_indices.csv",
    "data/benchmarks.csv",
    "data/book_exposure.csv",
    "data/breadth_history.csv",
    "data/corporate_actions_log.json",
    "data/fii_dii_flows.csv",
    "data/indices/ind_nanocap_list.csv",
    "data/indices/ind_nifty1000_list.csv",
    "data/indices/ind_nifty50list.csv",
    "data/indices/ind_niftymicrocap250_list.csv",
    "data/indices/ind_niftymidcap150list.csv",
    "data/indices/ind_niftynext50list.csv",
    "data/indices/ind_niftysmallcap250list.csv",
    "data/indices/ind_niftytotalmarket_list.csv",
    "data/indices_sync_meta.json",
    "data/membership_history.json",
    "data/momentum_health.csv",
    "data/momentum_health_750.csv",
    "data/momentum_health_latest.json",
    "data/momentum_health_nano.csv",
    "data/nanocap_membership.json",
    "data/nsdl_fpi_daily.csv",
    "data/nse_all_time_highs.csv",
    "data/nse_dii.csv",
    "data/nse_fo_symbols.json",
    "data/nse_indices_recent.csv",
    "data/nse_market_caps.csv",
    "data/nse_total_market.csv",
    "data/nse_trading_days.json",
    "data/nse_tv_classification.csv",
    "data/qualified_now.json",
    "data/reference/screener_earnings.csv",
    "data/results_calendar.csv",
    "data/results_calendar_meta.json",
    "data/screener_pending_history.json",
    "data/signal_tests.json",
)
_SET = frozenset(FILES)

# How often a running process asks R2 whether a newer pack was published.
REFRESH_S = 15 * 60

# Kept across code reloads (code_reload drops this module on a pull; the extracted pack need not
# be fetched again for that).
_STATE: dict = code_reload.__dict__.setdefault("PERSISTENT", {}).setdefault(
    "app_pack", {"dir": None, "revision": None, "checked": 0.0, "files": {}})
_LOCK = threading.Lock()


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def build(root: Path, files=FILES, base: dict[str, bytes] | None = None) -> bytes:
    """A deterministic zip of `files` read under `root` (missing ones taken from `base`), with
    `pack.json` listing each file's SHA-256 and size. Same contents, same bytes."""
    contents: dict[str, bytes] = dict(base or {})
    for rel in files:
        p = root / rel
        if p.is_file():
            contents[rel] = p.read_bytes()
    manifest = {"files": {rel: {"sha256": sha256(b), "bytes": len(b)} for rel, b in sorted(contents.items())}}
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in sorted(contents):
            info = zipfile.ZipInfo(rel, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, contents[rel])
        info = zipfile.ZipInfo(MANIFEST, date_time=(2026, 1, 1, 0, 0, 0))
        z.writestr(info, json.dumps(manifest, sort_keys=True, indent=1))
    return out.getvalue()


class PackError(ValueError):
    pass


def unpack(body: bytes) -> dict[str, bytes]:
    """The files of a pack, each checked against its listed SHA-256 and size; raises PackError."""
    try:
        z = zipfile.ZipFile(io.BytesIO(body))
        manifest = json.loads(z.read(MANIFEST))["files"]
    except Exception as exc:  # noqa: BLE001
        raise PackError(f"unreadable pack: {type(exc).__name__}") from exc
    out: dict[str, bytes] = {}
    for rel, meta in manifest.items():
        if rel.startswith("/") or ".." in Path(rel).parts:
            raise PackError(f"unsafe path in pack: {rel}")
        data = z.read(rel)
        if len(data) != meta["bytes"] or sha256(data) != meta["sha256"]:
            raise PackError(f"{rel}: bytes do not match the pack's list")
        out[rel] = data
    return out


def _fetch(reader):
    """(revision, files) of R2's current pack; (None, {}) when none is published yet."""
    try:
        ref = reader.resolve_current(DATASET)
    except FileNotFoundError:
        return None, {}
    if ref.revision_sha256 == _STATE["revision"]:
        return ref.revision_sha256, None
    return ref.revision_sha256, unpack(reader.read_bytes(ref))


def _extract(revision: str, files: dict[str, bytes]) -> Path:
    base = Path(os.environ.get("APP_PACK_DIR") or Path(tempfile.gettempdir()) / "app_pack") / revision[:16]
    for rel, data in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.is_file() or p.stat().st_size != len(data):
            tmp = p.with_suffix(p.suffix + ".part")
            tmp.write_bytes(data)
            os.replace(tmp, p)
    return base


def refresh(reader=None, *, force: bool = False) -> str | None:
    """Ask R2 for the current pack at most every REFRESH_S; returns the revision in use or None.

    Never raises. No keys, or no pack published yet: the committed files serve, with no note. R2
    configured but failing, or a pack that fails its check: the committed files serve and the
    pages' foot line names the backup copy (app_source.UNREACHED, S174 D3)."""
    from src.loaders import app_source

    with _LOCK:
        now = time.monotonic()
        if not force and _STATE["checked"] and now - _STATE["checked"] < REFRESH_S:
            return _STATE["revision"]
        _STATE["checked"] = now
        try:
            if reader is None:
                config = app_source.r2_config()
                if config is None:
                    return _STATE["revision"]
                from src.storage.r2 import R2Archive
                from src.storage.reader import R2DatasetReader

                reader = R2DatasetReader(R2Archive(config))
            revision, files = _fetch(reader)
            if revision is None:
                return _STATE["revision"]
            if files is not None:
                _STATE["dir"] = _extract(revision, files)
                _STATE["files"] = {rel: True for rel in files}
                _STATE["revision"] = revision
                app_source.record(LABEL, "r2")
                logger.info("App pack %s from R2: %d files.", revision[:16], len(files))
            app_source.UNREACHED.discard(LABEL)
            return _STATE["revision"]
        except Exception as exc:  # noqa: BLE001 - a page must never fail on the pack
            logger.info("App pack unavailable (%s: %s); using the committed files.", type(exc).__name__, exc)
            app_source.UNREACHED.add(LABEL)
            app_source.record(LABEL, "release")
            return _STATE["revision"]


def _rel(path) -> str | None:
    try:
        p = Path(path)
        p = p if p.is_absolute() else Path.cwd() / p
        return p.resolve().relative_to(ROOT).as_posix()
    except (ValueError, OSError, TypeError):
        return None


def resolve(path):
    """The pack's copy of `path` when it is one of FILES and the pack holds it; else `path` as given.

    Returns the same type it was given (str or Path) so callers need no other change."""
    rel = _rel(path)
    if rel is None or rel not in _SET:
        return path
    refresh()
    base = _STATE["dir"]
    if base is None or rel not in _STATE["files"]:
        return path
    p = Path(base) / rel
    if not p.is_file():
        return path
    return str(p) if isinstance(path, str) else p
