"""Results kept on this machine's disk across cache clears (S233 (2); owner, 26 Nov 2026: "Ensure web pages
should now load faster, if required let's save calculated values").

Every pull of a new revision clears st.cache_data and st.cache_resource (app.py), so a result that took
seconds is rebuilt by the next reader even when nothing it was built from changed. `get` keeps such a
result in the temp directory under a key that the caller builds from every input (whole-value
fingerprints, not dates) and the code (code_fingerprint), so a changed input or a code
change is a different key and is rebuilt. Written and read by this process only, never fetched from
elsewhere, so pickle is safe here. Two keys per name are kept; older ones are removed. Never raises: a
memo that cannot be read or written only costs the rebuild it would have saved.
"""

from __future__ import annotations

import hashlib
import os
import pickle
import tempfile
import threading
from pathlib import Path
from typing import Any
from collections.abc import Callable

from src.core.logger import logger

KEEP = 2
ROOT = Path(__file__).resolve().parents[2]
_CODE: dict[str, str] = {}


def code_fingerprint(root: Path = ROOT) -> str:
    """Every .py file under src/, path and bytes, in path order. Once per module load: code_reload drops this
    module on a pull that changed src/, so a new revision is fingerprinted afresh."""
    if str(root) not in _CODE:
        h = hashlib.sha256()
        for p in sorted((root / "src").rglob("*.py")):
            h.update(p.relative_to(root).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
        _CODE[str(root)] = h.hexdigest()
    return _CODE[str(root)]


def _dir(name: str) -> Path:
    base = os.environ.get("APP_DISK_MEMO_DIR") or Path(tempfile.gettempdir()) / "app_disk_memo"
    return Path(base) / name


def digest(*parts: Any) -> str:
    return hashlib.sha256(repr(parts).encode()).hexdigest()


def get(name: str, key: str, build: Callable[[], Any]) -> Any:
    """`build()`'s result for `key`, from disk when this machine already built it."""
    d = _dir(name)
    path = d / f"{key[:40]}.pkl"
    try:
        if path.is_file():
            with path.open("rb") as fh:
                stored_key, value = pickle.load(fh)
            if stored_key == key:
                os.utime(path)
                logger.info("Disk memo %s: %s served.", name, key[:12])
                return value
    except Exception as exc:  # noqa: BLE001  an unreadable memo is rebuilt
        logger.info("Disk memo %s unreadable (%s); rebuilding.", name, type(exc).__name__)
    value = build()
    try:
        d.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.part")
        with tmp.open("wb") as fh:
            pickle.dump((key, value), fh, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(tmp, path)
        kept = sorted(d.glob("*.pkl"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in kept[KEEP:]:
            old.unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001
        logger.info("Disk memo %s not written (%s).", name, type(exc).__name__)
    return value
