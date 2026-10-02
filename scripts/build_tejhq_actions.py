"""Copy TejHQ's NSE splits, bonuses, consolidations and demergers into the repo.

    python scripts/build_tejhq_actions.py          # writes data/reference/tejhq_actions.csv

TejHQ (huggingface.co/datasets/tejhq/indian-markets, MIT) publishes NSE's
corporate-action feed from 2010 as parquet, one file a year. Its rows come from
the same exchange source as ours, but it holds some our yearly list lacks
(SUPRAJIT's 2010 "Bon 1:1/Fv Spl Rs.5tore.1"). The long price file
(scripts/build_nse_long_prices.py) uses these only to fill gaps: a row is added
where NSE's own list has no price-changing action for that stock within five
days, and like every action it is applied only when the price confirms it.

The factor is TejHQ's own structured fields: face value to / from for a split
or consolidation, times held / (new + held) for a bonus named with it.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "reference" / "tejhq_actions.csv"
BASE = "https://huggingface.co/datasets/tejhq/indian-markets/resolve/main/actions/nse_{year}.parquet"
KINDS = ("split", "bonus", "consolidation", "demerger")


def factor(row) -> float:
    f = 1.0
    fv_from, fv_to = row["face_value_from"], row["face_value_to"]
    if row["type"] in ("split", "consolidation"):
        if not (fv_from > 0 and fv_to > 0):
            return np.nan
        f = fv_to / fv_from
    new, held = row["ratio_num"], row["ratio_den"]
    if row["type"] == "bonus" or (row["type"] == "split" and "BON" in str(row["raw_subject"]).upper()):
        if new > 0 and held > 0:
            f *= held / (new + held)
        elif row["type"] == "bonus":
            return np.nan
    return f if row["type"] != "demerger" else np.nan


def main(argv=None) -> int:
    frames = []
    for year in range(2010, pd.Timestamp.today().year + 1):
        r = requests.get(BASE.format(year=year), timeout=120)
        r.raise_for_status()
        frames.append(pd.read_parquet(io.BytesIO(r.content)))
    a = pd.concat(frames, ignore_index=True)
    a = a[a["exchange"].eq("NSE") & a["type"].isin(KINDS) & a["ex_date"].notna()].copy()
    a["price_factor"] = a.apply(factor, axis=1)
    a["ex_date"] = pd.to_datetime(a["ex_date"]).dt.date
    out = (a[["symbol", "isin", "ex_date", "type", "price_factor", "raw_subject"]]
           .rename(columns={"type": "kind", "raw_subject": "purpose"})
           .drop_duplicates(["symbol", "ex_date", "kind", "purpose"])
           .sort_values(["ex_date", "symbol"]))
    out.to_csv(OUT, index=False)
    print(f"{len(out)} actions to {OUT.relative_to(ROOT).as_posix()}: "
          + ", ".join(f"{k} {n}" for k, n in out["kind"].value_counts().items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
