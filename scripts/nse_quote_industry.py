"""Print NSE's own four-level classification for named stocks, read from NSE's quote API (owner, 26 Nov
2026: the one-off check for S189's four, CMPDI, SUDEEPPHRM, INA, BUILDPRO, whose Screener sector differs from
the Nifty 1000 list's). A report only: nothing is written.

    python scripts/nse_quote_industry.py CMPDI SUDEEPPHRM INA BUILDPRO
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.core import nse_web  # noqa: E402

LEVELS = (("macro", "Macro-economic sector"), ("sector", "Sector"), ("industry", "Industry"),
          ("basicIndustry", "Basic industry"))


def levels(payload: dict) -> dict[str, str]:
    """NSE's four levels from a quote-equity answer; a level NSE leaves out reads "not shown"."""
    info = (payload or {}).get("industryInfo") or {}
    return {label: str(info.get(key) or "not shown") for key, label in LEVELS}


def main(symbols: list[str]) -> int:
    missing = 0
    for sym in symbols:
        sym = sym.strip().upper()
        try:
            r, base = nse_web.get("/api/quote-equity", page=f"/get-quotes/equity?symbol={sym}",
                                  params={"symbol": sym})
            got = levels(r.json()) if r.status_code == 200 else {}
        except Exception as exc:  # noqa: BLE001  one stock's failure is reported, the rest still read
            print(f"{sym}: no answer ({type(exc).__name__}: {exc})")
            missing += 1
            continue
        if not got:
            print(f"{sym}: HTTP {r.status_code} from {base}")
            missing += 1
            continue
        print(f"{sym} ({base}): " + "; ".join(f"{k}: {v}" for k, v in got.items()))
    return 1 if missing == len(symbols) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["CMPDI", "SUDEEPPHRM", "INA", "BUILDPRO"]))
