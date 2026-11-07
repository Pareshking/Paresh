"""Rights issues whose face value the S108 rule changes (read-only report).

Reads NSE's yearly corporate-action lists (a folder of y*.json, as on the
data-latest release in ref_nse_action_list_api_2008_2026.zip) and prints every
rights row where the face value the pipeline now uses differs from the one
NSE's row states: nse_adjusted._settled_face_value keeps the stock's earlier
face value when no split or consolidation lies between (TODO S108).

    python scripts/rights_face_values.py --actions refs/actions
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from src.loaders import nse_adjusted as na
from src.loaders import nse_backfill as nbf


def changed(actions: pd.DataFrame) -> pd.DataFrame:
    """Rights rows whose settled face value differs from the stated one."""
    a = actions[(actions["kind"] == "rights") & actions["ex_date"].notna()].copy()
    a["date"] = pd.to_datetime(a["ex_date"]).dt.normalize().astype("datetime64[ns]")
    fv = pd.to_numeric(actions["face_value"], errors="coerce")
    known = actions.assign(_fv=fv, _d=pd.to_datetime(actions["ex_date"], errors="coerce"))
    known = known[known["_fv"] > 0]
    a["stated"] = pd.to_numeric(a["face_value"], errors="coerce")
    a["settled"] = na._settled_face_value(a.assign(face_value=a["stated"]), known, actions)
    out = a[a["stated"].notna() & (a["stated"] != a["settled"])]
    return out[["symbol", "date", "purpose", "stated", "settled"]].sort_values("date")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--actions", type=Path, required=True, help="folder of NSE's yearly list JSON")
    args = ap.parse_args(argv)
    rows: list[dict] = []
    for f in sorted(args.actions.glob("*.json")):
        got = json.loads(f.read_text(encoding="utf-8"))
        rows += got if isinstance(got, list) else got.get("data", [])
    actions = nbf.api_actions(rows)
    rights = int((actions["kind"] == "rights").sum())
    out = changed(actions)
    pd.set_option("display.width", 220)
    print(f"{len(actions)} list rows, {rights} rights rows; the face value changes on {len(out)}:")
    print(out.to_string(index=False) if len(out) else "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
