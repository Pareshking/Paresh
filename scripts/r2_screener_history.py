"""How the published Screener store's history has changed, revision by revision.

Read-only. For every immutable revision of `prices/screener` in R2 (and the
one-off `prices/screener/bootstrap`), report how many dates it holds, where
its daily history starts, and how many symbols it carries.

Why it exists: on 2026-09-21 the observed-session archive built from this
store held at least 1000 dates; on 2026-09-25 the same build found 720. The
store's merge never shortens history (merge_into_store refuses to write a
smaller frame), so either something replaced the store wholesale, or the
earlier count came from a differently built store. This answers which, from
the evidence R2 already keeps.

    python scripts/r2_screener_history.py            # table + JSON
"""

from __future__ import annotations

import io
import json
import re
from typing import Any

import pandas as pd

from src.storage.r2 import R2Archive, R2Config

DATASETS = ("prices/screener", "prices/screener/bootstrap")
_REVISION = re.compile(r"^(\d{4}-\d{2}-\d{2})/revisions/([0-9a-f]{64})\.json$")


def describe_store(frame: pd.DataFrame) -> dict[str, Any]:
    """Dates, the start of the daily history, and symbols in one store frame."""
    dates = pd.DatetimeIndex(frame.index).normalize().unique().sort_values()
    out: dict[str, Any] = {
        "rows": int(len(frame)),
        "distinct_dates": int(len(dates)),
        "first_date": str(dates[0].date()) if len(dates) else None,
        "last_date": str(dates[-1].date()) if len(dates) else None,
        "first_daily_date": None,
        "daily_dates": 0,
        "symbols": int(frame.columns.get_level_values(0).nunique())
        if isinstance(frame.columns, pd.MultiIndex) else int(frame.shape[1]),
    }
    if len(dates) > 1:
        gaps = pd.Series(dates[1:] - dates[:-1]).dt.days.to_numpy()
        # Daily history: the earliest date from which no gap exceeds 5 days
        # (a long weekend plus a holiday), running through to the end.
        start = len(dates) - 1
        while start > 0 and gaps[start - 1] <= 5:
            start -= 1
        out["first_daily_date"] = str(dates[start].date())
        out["daily_dates"] = int(len(dates) - start)
    return out


def history(archive: R2Archive) -> list[dict[str, Any]]:
    rows = []
    for dataset in DATASETS:
        prefix = f"archive/manifests/{dataset}/"
        for key in sorted(archive.list_keys(prefix)):
            m = _REVISION.fullmatch(key[len(prefix):])
            if not m:
                continue  # current.json, or a nested dataset's key
            manifest = json.loads(archive.get_bytes(key).decode("utf-8"))
            obj = str(manifest.get("object_key", ""))
            row: dict[str, Any] = {
                "dataset": dataset, "as_of": m[1], "revision": m[2][:12],
                "created_at": manifest.get("created_at"),
                "pipeline_version": manifest.get("pipeline_version"),
            }
            try:
                frame = pd.read_parquet(io.BytesIO(archive.get_bytes(obj)))
                row |= describe_store(frame)
            except Exception as exc:  # report, do not stop the whole survey
                row["error"] = f"{type(exc).__name__}: {exc}"
            rows.append(row)
    rows.sort(key=lambda r: (r["dataset"], str(r.get("created_at") or ""), r["as_of"]))
    return rows


def main() -> int:
    rows = history(R2Archive(R2Config.from_env()))
    for r in rows:
        if "error" in r:
            print(f"SCREENER_HISTORY {r['dataset']} as_of={r['as_of']} rev={r['revision']} ERROR {r['error']}")
            continue
        print(
            f"SCREENER_HISTORY {r['dataset']} as_of={r['as_of']} rev={r['revision']} "
            f"created={r['created_at']} dates={r['distinct_dates']} "
            f"span={r['first_date']}..{r['last_date']} daily_from={r['first_daily_date']} "
            f"daily_dates={r['daily_dates']} symbols={r['symbols']} "
            f"pipeline={r['pipeline_version']}"
        )
    print(json.dumps(rows, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
