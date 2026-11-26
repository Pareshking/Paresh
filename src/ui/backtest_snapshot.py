"""The Backtest page's default run, kept as its finished parts (S233 (1); owner, 26 Nov 2026: "Ensure web
pages should now load faster, if required let's save calculated values on defulat website").

The page opens on one run (backtest_view.is_default). Cold, that run and the figures cut from it cost ~23 s
(13.6 s the run, 8 s the figures, measured 26 Nov 2026), and every pull of a new revision drops the caches
that held them (app.py), so most readers paid it. Here the page's parts (HTML strings and chart specs, both
plain JSON) are written once the default run has been computed, under a key that names everything they were
cut from:

  - the settings and every run input (the price frame, the membership, the industry map, the file's dates);
  - the benchmark, the index store's closes and dividend yields, the stored tests' file;
  - the code: every file under src/, so a code change never serves parts an older page drew.

A later visit with the same key draws the stored parts instead of running again; any other key runs live,
as before. Nothing here moves a figure: the stored parts are the page's own, byte for byte (tests).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from pathlib import Path

import pandas as pd

from src.core.disk_memo import code_fingerprint  # noqa: F401  (monkeypatched in tests)
from src.core.disk_memo import value_fingerprint as fingerprint
from src.core.logger import logger

ROOT = Path(__file__).resolve().parents[2]
VERSION = 1          # the parts' JSON layout; a change writes under a new key


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def key(settings: dict, inputs: dict, caps: tuple, bench: pd.Series, store, reference_bytes: bytes | None) -> str:
    """Everything the default page is cut from: the settings, every run input (the price frame, the membership,
    the industry map, the file's dates), the caps, the benchmark, the index store, the stored tests, the code."""
    parts = (VERSION, fingerprint(settings), fingerprint(inputs), repr(caps), fingerprint(bench),
             fingerprint(getattr(store, "close", None)), fingerprint(getattr(store, "dy", None)),
             repr(getattr(store, "as_of", None)), _sha(reference_bytes or b""), code_fingerprint())
    return _sha(repr(parts).encode())


# ── The parts as JSON ─────────────────────────────────────────────────────────


def encode(parts: list) -> list:
    from src.ui.views.dashboard_home_view import Chart, Cols

    out = []
    for p in parts:
        if isinstance(p, str):
            out.append(p)
        elif isinstance(p, Chart):
            out.append({"chart": p.kind, "spec": p.spec, "fill": p.fill})
        elif isinstance(p, Cols):
            out.append({"cols": [encode(p.left), encode(p.right)], "ratio": list(p.ratio)})
        else:
            raise TypeError(f"not a page part: {type(p).__name__}")
    return out


def decode(parts: list) -> list:
    from src.ui.views.dashboard_home_view import Chart, Cols

    out = []
    for p in parts:
        if isinstance(p, str):
            out.append(p)
        elif "chart" in p:
            out.append(Chart(p["chart"], p["spec"], p["fill"]))
        else:
            out.append(Cols(decode(p["cols"][0]), decode(p["cols"][1]), tuple(p["ratio"])))
    return out


def dumps(snapshot: dict) -> bytes:
    sections = {name: encode(parts) for name, parts in snapshot["sections"].items()}
    body = {"version": VERSION, "key": snapshot["key"], "sections": sections, "meta": snapshot.get("meta") or {}}
    return json.dumps(body, separators=(",", ":"), allow_nan=False).encode()


def loads(raw: bytes, want_key: str) -> dict | None:
    """The snapshot in `raw` when it is this layout and this key; else None."""
    try:
        body = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(body, dict) or body.get("version") != VERSION or body.get("key") != want_key:
        return None
    try:
        return {"key": body["key"], "meta": body.get("meta") or {},
                "sections": {name: decode(parts) for name, parts in body["sections"].items()}}
    except (KeyError, TypeError, IndexError):
        return None


# ── Where it is kept ──────────────────────────────────────────────────────────


def _dir() -> Path:
    return Path(os.environ.get("BACKTEST_SNAPSHOT_DIR") or Path(tempfile.gettempdir()) / "backtest_default")


def _path(k: str) -> Path:
    return _dir() / f"{k[:32]}.json"


def load(k: str) -> dict | None:
    """The stored parts for key `k`, or None. Never raises."""
    try:
        p = _path(k)
        return loads(p.read_bytes(), k) if p.is_file() else None
    except OSError:
        return None


def save(snapshot: dict) -> bool:
    """Write the snapshot (a temp file, then a rename, so a reader never sees half of one); older keys go.
    Never raises: the page has already drawn, so a failure here only costs the next reader the run."""
    try:
        raw = dumps(snapshot)
        d = _dir()
        d.mkdir(parents=True, exist_ok=True)
        target = _path(snapshot["key"])
        tmp = target.with_suffix(f".{os.getpid()}.{threading.get_ident()}.part")   # one per writer
        tmp.write_bytes(raw)
        os.replace(tmp, target)
        for old in d.glob("*.json"):
            if old != target:
                old.unlink(missing_ok=True)
        logger.info("Backtest default kept: %s (%d bytes).", snapshot["key"][:12], len(raw))
        return True
    except (OSError, TypeError, ValueError) as exc:
        logger.info("Backtest default not kept (%s: %s).", type(exc).__name__, exc)
        return False
