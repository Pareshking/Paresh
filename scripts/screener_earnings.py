"""Earnings growth for the broad indices, our calculation from companies' reported results (S171).

Owner, 25 Nov 2026: "We will use Screener data only"; weekly, on Saturday; past members from
data/membership_history.json. Each company's "Quarterly Results" table on its Screener.in page
(src/loaders/screener_quarters.py) is added up over each index's members at each quarter end.

    python -I scripts/screener_earnings.py fetch --cache DIR     # every member's page, >= 1.5 s apart
    python -I scripts/screener_earnings.py build --cache DIR     # the two files below, and the NSE check

Pages are read for every index member on those quarter ends and every stock the site lists (~2,400, ~2 h at ~3 s a page).

Writes (readers: the Indices page's Earnings section and the Stock page's results table, src/engine/earnings_review.py):
- data/reference/screener_quarters.csv: one row per company and quarter (Rs crore), merged into
  what earlier runs kept, so the history grows past the 13 quarters a page shows. A quarter on
  this week's page replaces the stored one (Screener restates).
- data/reference/screener_earnings.csv: per quarter, index and measure, the growth from a year
  earlier, with members, companies used and coverage.

Measures (as scripts/screener_earnings_measure.py, which measured them against NSE on 25 Nov):
aggregate growth = sum(x_q) / sum(x_{q-4}) - 1 over members with both quarters on the same basis;
median growth = the median member's growth, leaving out a zero or negative base. x is sales
(Screener's "Revenue" for banks and lenders), net profit as reported ("pat"), or net profit
without other income ("pat_xoi": for companies whose first row is "Sales", net profit minus other
income after tax at the quarter's Tax %, 25% when it is missing or outside 0-60%; banks and
lenders as reported, their other income being fees and treasury). Tata Motors (TATAMOTORS, TMPV,
TMCV) is left out of every quarter whose own or year-earlier quarter is Q2 or Q3 FY26: Q2 and Q3 FY26
as NSE's issues do (owner, 25 Nov 2026), and Q2 and Q3 FY27, whose base holds the demerger (1 Oct
2025; TMPV's Sep 2025 net profit is Rs 76,248 crore, 16 points of the Nifty 500's growth alone).
Q2 and Q3 FY27 are decided by rule, owner to confirm.

A quarter is complete when at least COMPLETE_SHARE of the Nifty 500's members have both
quarters; the page shows complete quarters only (decided by rule 25 Nov 2026, owner to confirm).

The NSE check (a report, not a gate; owner, 25 Nov: "won't match NSE exactly: ignore it"): each
quarter where our Nifty 50 or Nifty 500 aggregate is more than 5 points from NSE's published
figure (data/reference/nse_earnings_review.csv) is printed with its top five contributors, so a
parsing fault or a one-off is seen in the run log.
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
import sys
from datetime import date

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts import screener_earnings_measure as research  # noqa: E402

QUARTERS_CSV = os.path.join(ROOT, "data", "reference", "screener_quarters.csv")
EARNINGS_CSV = os.path.join(ROOT, "data", "reference", "screener_earnings.csv")
COMPLETE_SHARE = 0.90
GROSS_PTS = 5.0
FIELDS = ("sales", "pat", "pat_xoi")
QUARTER_COLS = ["symbol", "quarter_end", "basis", "sales_label", "sales", "operating_profit", "pbt", "net_profit",
                "other_income", "tax_pct", "eps", "fetched"]


def quarter_ends(today: date, years: int = 3) -> list[str]:
    """Quarter ends from `years` back to the last one before today, oldest first."""
    out = []
    for y in range(today.year - years, today.year + 1):
        for m, d in ((3, 31), (6, 30), (9, 30), (12, 31)):
            if date(y, m, d) < today:
                out.append(f"{y}-{m:02d}-{d:02d}")
    return out[-(4 * years + 1):]


EX_TATA = {"Q2FY26", "Q3FY26", "Q2FY27", "Q3FY27"}


def members(key: str, qe: str) -> set[str]:
    out = research.members_on(research.index_history(key), qe, canonical=True) or set()
    return out - research.TATA if research.quarter_label(qe) in EX_TATA else out


def pat_xoi(row: dict) -> float | None:
    """Net profit without other income, after tax; banks and lenders ("Revenue") as reported."""
    np_ = row.get("net_profit")
    if np_ is None or pd.isna(np_):
        return None
    oi = row.get("other_income")
    if str(row.get("sales_label", "")).lower().startswith("revenue") or oi is None or pd.isna(oi):
        return float(np_)
    t = row.get("tax_pct")
    rate = t / 100 if t is not None and not pd.isna(t) and 0 <= t <= 60 else 0.25
    return float(np_) - float(oi) * (1 - rate)


def page_rows(cache: str, fetched: str, since: str = "") -> list[dict]:
    """This week's rows on or after `since`, one basis per company (the research script's rule). A page
    whose company stopped reporting shows its last 13 quarters, years old; those are not kept."""
    manifest = research._load_json(os.path.join(cache, "manifest.json"))
    data, _ = research.company_data(cache, manifest)
    out = []
    for sym, q in data.items():
        for qe, r in q.rows.items():
            if qe < since:
                continue
            out.append({"symbol": sym, "quarter_end": qe, "basis": r["basis"], "sales_label": q.sales_label,
                        "sales": r["sales"], "net_profit": r["net_profit"], "other_income": r.get("other_income"),
                        "tax_pct": r.get("tax_pct"), "operating_profit": r.get("operating_profit"),
                        "pbt": r.get("pbt"), "eps": r.get("eps"), "fetched": fetched})
    return out


def merge(stored: pd.DataFrame | None, new: list[dict]) -> pd.DataFrame:
    fresh = pd.DataFrame(new, columns=QUARTER_COLS)
    if stored is None or stored.empty:
        both = fresh
    else:
        both = pd.concat([stored.reindex(columns=QUARTER_COLS), fresh], ignore_index=True)
    both = both.drop_duplicates(["symbol", "quarter_end"], keep="last")
    return both.sort_values(["symbol", "quarter_end"]).reset_index(drop=True)


def _values(quarters: pd.DataFrame) -> dict[tuple[str, str], dict]:
    out = {}
    for r in quarters.to_dict("records"):
        r["pat"] = None if pd.isna(r["net_profit"]) else float(r["net_profit"])
        r["pat_xoi"] = pat_xoi(r)
        r["sales"] = None if pd.isna(r["sales"]) else float(r["sales"])
        out[(r["symbol"], r["quarter_end"])] = r
    return out


def growth(values: dict, syms: set[str], qe: str, field: str) -> dict:
    base_q = research.year_before(qe)
    pairs = []
    for s in sorted(syms):
        now, base = values.get((s, qe)), values.get((s, base_q))
        if not now or not base or now["basis"] != base["basis"]:
            continue
        if now[field] is not None and base[field] is not None:
            pairs.append((s, now[field], base[field]))
    total = sum(b for _, _, b in pairs)
    agg = (sum(n for _, n, _ in pairs) / total - 1) * 100 if pairs and total > 0 else None
    gs = [(n / b - 1) * 100 for _, n, b in pairs if b > 0]
    top = sorted(((s, n, b, (n - b) / total * 100) for s, n, b in pairs if total > 0), key=lambda r: -abs(r[3]))[:5]
    return {"agg": agg, "median": statistics.median(gs) if gs else None, "used": len(pairs), "top": top}


def earnings(quarters: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    values = _values(quarters)
    have = set(quarters["quarter_end"])
    rows, notes = [], []
    nse = research.nse_figures() if os.path.exists(research.NSE_CSV) else {}
    for qe in sorted(q for q in have if research.year_before(q) in have):
        q = research.quarter_label(qe)
        n500 = members("nifty_500", qe)
        used500 = growth(values, n500, qe, "sales")["used"] if n500 else 0
        complete = bool(n500) and used500 >= COMPLETE_SHARE * len(n500)
        for key, label in research.INDICES.items():
            syms = members(key, qe)
            if not syms:
                continue
            for field in FIELDS:
                g = growth(values, syms, qe, field)
                for stat in ("agg", "median"):
                    v = g[stat]
                    rows.append({"quarter": q, "quarter_end": qe, "index": label, "measure": f"{field}_{stat}_yoy",
                                 "value_pct": None if v is None else round(v, 2), "members": len(syms),
                                 "used": g["used"], "complete": complete})
                theirs = nse.get((q, label, f"{'pat' if field != 'sales' else 'sales'}_agg_yoy"))
                if complete and label in research.GATED and theirs is not None and g["agg"] is not None \
                        and abs(g["agg"] - theirs) > GROSS_PTS:
                    notes.append(f"{q} {label} {field}: ours {g['agg']:.1f} NSE {theirs:.1f} | " +
                                 "; ".join(f"{s} {b:.0f}->{n:.0f} ({c:+.2f})" for s, n, b, c in g["top"]))
    return pd.DataFrame(rows), notes


def build(cache: str, quarters_csv: str = QUARTERS_CSV, earnings_csv: str = EARNINGS_CSV) -> int:
    stored = pd.read_csv(quarters_csv) if os.path.exists(quarters_csv) else None
    new = page_rows(cache, date.today().isoformat(), since=quarter_ends(date.today())[0])
    if not new:
        print("no pages parsed; nothing written")
        return 1
    quarters = merge(stored, new)
    quarters.to_csv(quarters_csv, index=False, quoting=csv.QUOTE_MINIMAL)
    out, notes = earnings(quarters)
    out = out[out["complete"]].drop(columns="complete")
    out["as_of"] = str(quarters["fetched"].max())
    out.to_csv(earnings_csv, index=False)
    print(f"wrote {quarters_csv} ({len(quarters)} rows, {quarters['symbol'].nunique()} companies) and "
          f"{earnings_csv} ({len(out)} rows)")
    done = out["quarter"].unique().tolist()
    print(f"complete quarters (>= {COMPLETE_SHARE:.0%} of the Nifty 500's members): {', '.join(done)}")
    print(f"NSE check: {len(notes)} reading(s) over {GROSS_PTS} points (a report, not a gate)")
    for n in notes:
        print("  " + n)
    return 0


def widen_to_every_listed_stock() -> None:
    """Pages for every stock the site lists, not only the index members (owner, 25 Nov 2026: the Stock page's results
    table, "Go ahead"): the indices still add up their own members only."""
    from scripts.nse_classification import universe as listed
    members_only, names_only = research.universe, research.names
    research.universe = lambda: sorted(set(members_only()) | set(listed()))
    research.names = lambda: {**{s: n for s, n in listed().items() if n}, **names_only()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["fetch", "build"])
    ap.add_argument("--cache", required=True, help="a directory outside the repository for the raw pages")
    ap.add_argument("--pause", type=float, default=1.5)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args(argv)
    if os.path.abspath(args.cache).startswith(ROOT + os.sep):
        ap.error("--cache must be outside the repository")
    research.QUARTER_ENDS = quarter_ends(date.today())
    widen_to_every_listed_stock()
    if args.step == "fetch":
        research.fetch(args.cache, max(args.pause, 1.5), args.limit)
        if args.limit:
            return 0
        got = research._load_json(os.path.join(args.cache, "manifest.json"))
        ok = sum(1 for v in got.values() if v.get("status") == 200)
        want = len(research.universe())
        print(f"{ok} of {want} pages read")
        # Screener stopped the run (403, or a 429 that did not clear): build nothing, show red.
        return 0 if ok >= COMPLETE_SHARE * want else 1
    return build(args.cache)


if __name__ == "__main__":
    sys.exit(main())
