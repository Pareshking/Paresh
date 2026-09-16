"""Publish and consume a precomputed ranking table.

Thirty of the eighty-nine seconds of a production cold start went into
``build_engine`` -- five calendar-period passes and every signal column, over
750 symbols, on one shared Streamlit Cloud core, while a reader watched a
spinner. Nothing about that work needs a reader present. It is the same
arithmetic on the same frame every time, and the nightly sync job already
fetches that frame on a runner where nobody is waiting.

So the job ranks it once and publishes the answer. This module is the contract
between the two.

IT IS AN ACCELERATOR, NOT A DEPENDENCY. Every failure path returns None and the
app computes the ranking itself, exactly as before. A missing asset, an
unreachable release, a corrupt file, a stale fingerprint -- all of them cost a
slow cold start, never a wrong number and never an outage.

WHAT MAKES IT SAFE IS THE FINGERPRINT, NOT THE FRESHNESS. A precomputed table
is a cache of a pure function, so it is valid only if every input matches:
the price frame it was ranked from, the universe, the weights, and the pipeline
version. All four are written into the parquet's own metadata and all four are
re-checked before a single row is used. Serving a ranking that does not match
the reader's configuration would be a wrong answer delivered fast, which is
worse than the spinner it replaces -- so the check is exact, and anything it
cannot verify is discarded.

The published price snapshot is what makes the fingerprint match in practice.
Production seeds from it and, now that requests are gated on DOWNLOAD_SETTLES,
leaves it untouched until the vendor's bar settles at 22:30 IST -- so for the
whole trading day production's frame IS the frame the job ranked.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from typing import Any

import pandas as pd
import requests

from src.core import startup_metrics as metrics
from src.core.config import RANKINGS_SNAPSHOT_URL
from src.core.logger import logger

DOWNLOAD_TIMEOUT_S: int = int(os.getenv("UMIYA_RANKINGS_TIMEOUT_S", "30"))
# An HTML error page is small; a real ranking table for 750 symbols is not.
MIN_PLAUSIBLE_BYTES: int = 10_000
# The parquet key-value metadata slot the contract is written into.
META_KEY: bytes = b"umiya_ranking_contract"


def actions_digest(applied: list[dict[str, Any]] | None) -> str:
    """Fingerprint the corporate actions that were neutralised before ranking.

    THE PRICE FINGERPRINT CANNOT SEE THESE, and that is not obvious. A
    corporate action rewrites history BEFORE its own date and deliberately
    leaves the current price alone -- neutralising ABFRL's 1:3 split rewrites
    168 rows of the shipped snapshot and changes the last row not at all. So
    the frame's last row, its shape and its last date are all identical with
    and without the adjustment, and price_fingerprint returns the same string
    either way.

    Which means the event set is an input to the ranking that every other
    field in the contract is blind to. Without this, a table built under one
    set of events would be served against a different set, with the contract
    passing: exactly the hit-that-should-have-been-a-miss the rest of this
    module exists to prevent.

    Not hypothetical. The daily sync publishes the ranking at step 5d and
    re-scans for corporate actions afterwards, so the run of 2026-09-16
    precomputed with 12 applied events and then appended a thirteenth (PGIL,
    2026-08-03) to the log the app reads. One run, two event sets, one
    fingerprint.

    Only APPLIED events count. An event the vendor has since restated is
    skipped by adjust_prices on both sides, so it must not enter the digest --
    otherwise the log growing an entry nobody acts on would force a miss.
    """
    if not applied:
        return "none"
    parts = sorted(
        f"{e.get('symbol')}|{e.get('date')}|{round(float(e.get('ratio', 0) or 0), 6)}"
        for e in applied
    )
    return hashlib.md5("~".join(parts).encode()).hexdigest()[:12]


def contract(
    *,
    price_fingerprint: str,
    symbols_fingerprint: str,
    weights,
    pipeline_version: str,
    universe: list[str] | None = None,
    price_as_of: str | None = None,
    applied_actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Everything that must match before a precomputed table may be used."""
    return {
        "actions_digest": actions_digest(applied_actions),
        "price_fingerprint": price_fingerprint,
        "symbols_fingerprint": symbols_fingerprint,
        # Rounded, because a float round-trip through JSON must not be the
        # reason a valid table is rejected. Six places is far finer than any
        # weight a slider can express.
        "weights": [round(float(w), 6) for w in weights],
        "pipeline_version": pipeline_version,
        "universe": sorted(universe or []),
        "price_as_of": price_as_of or "",
    }


def matches(published: dict[str, Any] | None, expected: dict[str, Any]) -> tuple[bool, str]:
    """Does a published contract satisfy the one the caller needs?

    Returns (ok, reason). The reason is logged on a miss, because "the
    precompute did not hit" is otherwise indistinguishable from "the precompute
    does not exist", and those need very different fixes.
    """
    if not published:
        return False, "no contract recorded"
    for field in ("pipeline_version", "symbols_fingerprint", "price_fingerprint",
                  "actions_digest"):
        if str(published.get(field, "")) != str(expected[field]):
            return False, f"{field} differs"
    if [round(float(w), 6) for w in published.get("weights", [])] != expected["weights"]:
        return False, "weights differ"
    if list(published.get("universe", [])) != expected["universe"]:
        return False, "universe differs"
    return True, "ok"


def write_snapshot(path: str, rank_df: pd.DataFrame, contract_: dict[str, Any]) -> str:
    """Write the ranking plus its contract as one self-describing file.

    The contract travels INSIDE the parquet rather than beside it. A sidecar
    JSON is one more asset to upload, one more to download, and one more way
    for the two to arrive out of step -- at which point the app would check a
    contract that does not describe the table it is holding.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pandas(rank_df, preserve_index=False)
    meta = dict(table.schema.metadata or {})
    meta[META_KEY] = json.dumps(contract_).encode("utf-8")
    table = table.replace_schema_metadata(meta)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    pq.write_table(table, path, compression="zstd")
    return path


def read_snapshot(path: str) -> tuple[pd.DataFrame | None, dict[str, Any] | None]:
    """Read a ranking snapshot and its contract. Never raises."""
    try:
        import pyarrow.parquet as pq

        table = pq.read_table(path)
        raw = (table.schema.metadata or {}).get(META_KEY)
        published = json.loads(raw.decode("utf-8")) if raw else None
        return table.to_pandas(), published
    except Exception as exc:
        logger.warning(
            "Ranking snapshot unreadable (%s: %s); ranking will be computed.",
            type(exc).__name__, exc,
        )
        return None, None


def fetch_snapshot(url: str | None = None) -> tuple[pd.DataFrame | None, dict[str, Any] | None]:
    """Download the published ranking table, or return (None, None).

    Never raises and never blocks indefinitely. The caller's fallback is to
    compute the ranking, which is what it did before this existed.
    """
    target = url or RANKINGS_SNAPSHOT_URL
    started = time.perf_counter()
    tmp_path = None
    try:
        resp = requests.get(target, timeout=DOWNLOAD_TIMEOUT_S, stream=True)
        if resp.status_code != 200:
            logger.info(
                "Ranking snapshot unavailable (HTTP %s); computing instead.",
                resp.status_code,
            )
            metrics.note("ranking_snapshot", f"http_{resp.status_code}")
            return None, None

        fd, tmp_path = tempfile.mkstemp(suffix=".parquet")
        size = 0
        with os.fdopen(fd, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 18):
                if chunk:
                    fh.write(chunk)
                    size += len(chunk)

        if size < MIN_PLAUSIBLE_BYTES:
            logger.warning("Ranking snapshot was only %d bytes; ignoring it.", size)
            metrics.note("ranking_snapshot", "too_small")
            return None, None

        frame, published = read_snapshot(tmp_path)
        if frame is None or frame.empty:
            metrics.note("ranking_snapshot", "empty")
            return None, None

        elapsed = time.perf_counter() - started
        metrics.note("ranking_snapshot_seconds", round(elapsed, 2))
        metrics.note("ranking_snapshot_mb", round(size / 1024**2, 2))
        logger.info(
            "Ranking snapshot fetched: %d rows, %.2f MB in %.1fs",
            len(frame), size / 1024**2, elapsed,
        )
        return frame, published

    except Exception as exc:
        logger.info(
            "Ranking snapshot could not be used (%s: %s); computing instead.",
            type(exc).__name__, exc,
        )
        metrics.note("ranking_snapshot", f"error_{type(exc).__name__}")
        return None, None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
