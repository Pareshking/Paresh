"""History from 2010, precomputed: the default run of every index, written on GitHub, read by the app.

Owner, 2026-10-07: keep the app inside the free plan's memory. A History
backtest computed live peaked at ~870 MB. scripts/precompute_history.py runs
each index once, with the Backtest page's default settings, after every
long-file build, and publishes `history_backtests.zip` to the data-latest
release (one gzipped result per index, ~0.4 MB, and `meta.json`). The page
serves a stored result only when the index, the months, the floor and every
engine setting equal the stored run's, and the engine's code is the code
that produced it (engine_fingerprint); anything else is computed live.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import logging
import pickle
import zipfile
from pathlib import Path
from typing import Any

from src.loaders import nse_long

logger = logging.getLogger(__name__)

ASSET = "history_backtests.zip"
ROOT = Path(__file__).resolve().parents[2]
# The code a stored run depends on. A change to any of them makes the stored
# runs stale: the page computes live until the next precompute.
ENGINE_FILES = (
    "src/engine/backtester.py", "src/engine/history_run.py", "src/engine/calendar_momentum.py",
    "src/engine/momentum.py", "src/engine/portfolio.py", "src/engine/liquidity.py",
    "src/engine/index_universe.py", "src/engine/pipeline.py", "src/core/config.py",
    "data/membership_history.json",
)


def run_name(key: str, floor: float) -> str:
    """One stored run per index and liquidity floor: 'nifty_500__floor0', 'nifty_500__floor5'."""
    return f"{key}__floor{float(floor):g}"


def engine_fingerprint(root: Path = ROOT) -> str:
    """sha256 of the engine's code and the membership timeline (line endings normalised)."""
    h = hashlib.sha256()
    for rel in ENGINE_FILES:
        h.update(rel.encode())
        h.update((root / rel).read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:16]


def pack(runs: dict[str, dict[str, Any]], meta: dict[str, Any]) -> bytes:
    """The zip: {index}.pkl.gz per run and meta.json (meta[index] holds each run's key)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for key, res in runs.items():
            z.writestr(f"{key}.pkl.gz", gzip.compress(pickle.dumps(res, protocol=5)))
        z.writestr("meta.json", json.dumps(meta, indent=1, default=str))
    return buf.getvalue()


def read_meta(path: Path) -> dict[str, Any] | None:
    try:
        with zipfile.ZipFile(path) as z:
            return json.loads(z.read("meta.json"))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return None


def read_run(path: Path, key: str) -> dict[str, Any] | None:
    try:
        with zipfile.ZipFile(path) as z:
            return pickle.loads(gzip.decompress(z.read(f"{key}.pkl.gz")))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, pickle.UnpicklingError, EOFError):
        return None


def fetch(base: str = nse_long.NSE_LONG_BASE_URL, cache: Path | str = nse_long.DATA_DIR) -> Path | None:
    """The zip on disk (downloaded at most once a day), or None."""
    return nse_long._fetch(ASSET, base, Path(cache))


def lookup(meta: dict[str, Any] | None, key: str, wanted: dict[str, Any],
           fingerprint: str) -> bool:
    """True when the stored run of `key` is exactly the run `wanted` describes."""
    if not meta or meta.get("engine") != fingerprint:
        return False
    stored = (meta.get("runs") or {}).get(key)
    return bool(stored) and stored.get("request") == wanted
