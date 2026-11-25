"""S171 part (2), research only: can an aggregate of Screener.in's company "Quarters" tables
reproduce NSE's published earnings growth for the broad indices?

Nothing here writes to data/, feeds a page, or runs in a workflow. Pages are cached outside the
repo (the scratch directory) and treated as untrusted: run this script with ``python -I``.

    python -I scripts/screener_earnings_measure.py fetch   --cache DIR        # pages, >= 1.5 s apart
    python -I scripts/screener_earnings_measure.py measure --cache DIR --out FILE.csv

Members (owner, 25 Nov 2026): each index's point-in-time list on each quarter end, from
data/membership_history.json through src.engine.index_universe.index_history and
src.engine.membership.members_on(canonical=True) (the last recorded change on or before the
quarter end; ICICIPRULI is read as ICICILIFE, HEG as HEGAM). Indices: Nifty 50, Next 50,
Midcap 150, Smallcap 250, Microcap 250 and Nifty 500 (the Nifty 500's own timeline). Pages are
fetched for the union of every member on every quarter end measured.

Measures, per index and quarter q (NSE's definitions, "companies in the index as of the end of
the respective quarter"):
- aggregate growth = sum(x_q) / sum(x_{q-4}) - 1 over members with both quarters, for net
  profit and for sales (Screener's "Sales", or "Revenue" for banks and lenders);
- median growth = the median member's x_q / x_{q-4} - 1, leaving out members whose base
  quarter is zero or negative (counted and reported).
Q2 FY26 and Q3 FY26 leave out Tata Motors (TATAMOTORS / TMPV / TMCV), as NSE's issues do for
the Sep-25 and Dec-25 quarters (the demerger of 1 Oct 2025).

Basis: the /consolidated/ page. Screener fills a quarter with no consolidated figure with the
standalone one and marks it "(S)"; a company whose page mixes the two is read from its
standalone page for every quarter, so q and q-4 share a basis. A page with only "(S)" columns
is standalone. Each company's basis is recorded.

The check, FIXED BEFORE ANY RESULT WAS SEEN (owner, 25 Nov 2026: the comparison is a report,
not a gate; "ignore won't match NSE exactly"): a GROSS-ERROR check only. A quarter is FLAGGED
when our Nifty 50 or Nifty 500 aggregate profit growth or aggregate revenue growth differs from
NSE's figure in data/reference/nse_earnings_review.csv by more than 5.0 percentage points. Each
flagged gap is explained by its top 5 companies by absolute contribution to our growth
(contribution = (x_q - x_{q-4}) / sum(x_{q-4}), in points). Every other comparison (the other
indices, the medians, gaps under 5 points) is reported, not judged. Known reasons for small
gaps: NSE uses CMIE Prowess (adjusted PAT, its own revenue definition for banks), exceptional
items, minority interest (Screener's consolidated net profit is before it), consolidated vs
standalone, and companies whose results were not yet filed when NSE's issue went to press.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import time
from datetime import date
from urllib.parse import quote

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.nse_classification import (  # noqa: E402  (after the path insert)
    BASE,
    Blocked,
    _get,
    load_ids,
    pick_hit,
    search_text,
)
from src.engine.index_universe import index_history  # noqa: E402
from src.engine.membership import members_on  # noqa: E402
from src.loaders.screener_quarters import Quarters, parse_quarters  # noqa: E402

INDICES = {
    "nifty_50": "Nifty 50",
    "nifty_next_50": "Nifty Next 50",
    "nifty_midcap_150": "Nifty Midcap 150",
    "nifty_smallcap_250": "Nifty Smallcap 250",
    "nifty_microcap_250": "Nifty Microcap 250",
    "nifty_500": "Nifty 500",
}
# Quarter ends with a year-earlier quarter in Screener's 13 columns (Sep 2023 to Sep 2026).
QUARTER_ENDS = ["2024-09-30", "2024-12-31", "2025-03-31", "2025-06-30", "2025-09-30",
                "2025-12-31", "2026-03-31", "2026-06-30", "2026-09-30"]
EX_TATA = {"Q2FY26", "Q3FY26"}
TATA = {"TATAMOTORS", "TMPV", "TMCV"}
GROSS_PTS = 5.0
GATED = ("Nifty 50", "Nifty 500")
NSE_CSV = os.path.join(ROOT, "data", "reference", "nse_earnings_review.csv")
LIST_FILES = [os.path.join(ROOT, "data", "indices", f) for f in sorted(os.listdir(os.path.join(ROOT, "data", "indices")))]
MEASURE = {"net_profit": "pat", "sales": "sales"}


def quarter_label(qe: str) -> str:
    """"2026-06-30" -> "Q1FY27"."""
    y, m = int(qe[:4]), int(qe[5:7])
    n = {6: 1, 9: 2, 12: 3, 3: 4}[m]
    fy = y if m == 3 else y + 1
    return f"Q{n}FY{fy % 100:02d}"


def year_before(qe: str) -> str:
    return f"{int(qe[:4]) - 1}{qe[4:]}"


def members(key: str, qe: str) -> set[str]:
    out = members_on(index_history(key), qe, canonical=True) or set()
    return out - TATA if quarter_label(qe) in EX_TATA else out


def universe() -> list[str]:
    syms: set[str] = set()
    for key in INDICES:
        for qe in QUARTER_ENDS:
            syms |= members_on(index_history(key), qe, canonical=True) or set()
    return sorted(syms)


def names() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in LIST_FILES:
        if path.endswith(".csv"):
            with open(path, encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    if row.get("Symbol") and row.get("Company Name"):
                        out.setdefault(row["Symbol"].strip(), row["Company Name"].strip())
    return out


# ── Fetch ────────────────────────────────────────────────────────────────────


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _dump_json(obj: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)


def _save(cache: str, symbol: str, kind: str, text: str) -> None:
    with open(os.path.join(cache, f"{symbol}__{kind}.html"), "w", encoding="utf-8") as fh:
        fh.write(text)


def _consolidated_path(symbol: str, name: str, ids: dict[str, str], pause: float) -> tuple[str, requests.Response | None]:
    """The consolidated page, found by symbol, then the id map's other ticker, then a name search."""
    path = f"/company/{quote(symbol, safe='')}/consolidated/"
    resp = _get(BASE + path, requests.get, pause)
    if resp is not None and resp.status_code == 404:
        twins = sorted(s for s, i in ids.items() if ids.get(symbol) and i == ids[symbol] and s != symbol)
        found = None
        if twins:
            found = f"/company/{quote(twins[0], safe='')}/"
        elif name:
            time.sleep(pause)
            hit = _get(BASE + f"/api/company/search/?q={quote(search_text(name))}&v=3", requests.get, pause)
            try:
                hits = hit.json() if hit is not None and hit.status_code == 200 else []
            except ValueError:
                hits = []
            found = pick_hit(hits if isinstance(hits, list) else [], ids.get(symbol), name)
        if found:
            path = found.rstrip("/").removesuffix("/consolidated") + "/consolidated/"
            time.sleep(pause)
            resp = _get(BASE + path, requests.get, pause)
    return path, resp


def fetch(cache: str, pause: float, limit: int | None) -> None:
    os.makedirs(cache, exist_ok=True)
    manifest_path = os.path.join(cache, "manifest.json")
    manifest = _load_json(manifest_path) if os.path.exists(manifest_path) else {}
    ids, labels = load_ids(), names()
    todo = [s for s in universe() if s not in manifest]
    if limit:
        todo = todo[:limit]
    print(f"{len(todo)} to fetch, {len(manifest)} cached", flush=True)
    try:
        for n, sym in enumerate(todo, 1):
            path, resp = _consolidated_path(sym, labels.get(sym, ""), ids, pause)
            entry = {"consolidated_url": BASE + path, "status": resp.status_code if resp is not None else None}
            parsed = None
            if resp is not None and resp.status_code == 200:
                _save(cache, sym, "consolidated", resp.text)
                entry["consolidated_url"] = resp.url
                parsed = parse_quarters(resp.text)
            if resp is not None and resp.status_code == 200 and (parsed is None or parsed.mixed()):
                time.sleep(pause)
                url = resp.url.replace("/consolidated/", "/")
                alone = _get(url, requests.get, pause)
                entry["standalone_url"] = url
                entry["standalone_status"] = alone.status_code if alone is not None else None
                if alone is not None and alone.status_code == 200:
                    _save(cache, sym, "standalone", alone.text)
            manifest[sym] = entry
            if n % 25 == 0:
                print(f"{n}/{len(todo)} {sym}", flush=True)
                _dump_json(manifest, manifest_path)
            time.sleep(pause)
    except Blocked as err:
        print(f"stopped: {err}", flush=True)
    _dump_json(manifest, manifest_path)


# ── Measure ──────────────────────────────────────────────────────────────────


def _read(cache: str, sym: str, kind: str) -> Quarters | None:
    path = os.path.join(cache, f"{sym}__{kind}.html")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return parse_quarters(fh.read())


def company_data(cache: str, manifest: dict) -> tuple[dict[str, Quarters], dict[str, str]]:
    """symbol -> its quarters on one basis, and symbol -> basis or the reason it has none."""
    data, basis = {}, {}
    for sym in manifest:
        cons = _read(cache, sym, "consolidated")
        if cons is not None and not cons.mixed():
            data[sym], basis[sym] = cons, next(iter(cons.rows.values()))["basis"]
            continue
        alone = _read(cache, sym, "standalone")
        if alone is not None:
            data[sym], basis[sym] = alone, "standalone (consolidated page mixed)" if cons else "standalone (no consolidated table)"
        elif cons is not None:
            data[sym], basis[sym] = cons, "mixed (standalone page unreadable)"
        else:
            basis[sym] = f"no quarters table (HTTP {manifest[sym].get('status')})"
    return data, basis


def _value(q: Quarters | None, qe: str, field: str) -> float | None:
    return (q.rows.get(qe) or {}).get(field) if q else None


def measure(data: dict[str, Quarters], key: str, qe: str, field: str) -> dict:
    base_q = year_before(qe)
    pairs = []
    for sym in sorted(members(key, qe)):
        now, base = _value(data.get(sym), qe, field), _value(data.get(sym), base_q, field)
        if now is not None and base is not None:
            pairs.append((sym, now, base))
    total_base = sum(b for _, _, b in pairs)
    agg = (sum(n for _, n, _ in pairs) / total_base - 1) * 100 if pairs and total_base > 0 else None
    growths = [(n / b - 1) * 100 for _, n, b in pairs if b > 0]
    contrib = sorted(((s, n, b, (n - b) / total_base * 100) for s, n, b in pairs if total_base > 0),
                     key=lambda r: -abs(r[3]))
    return {"agg": agg, "median": statistics.median(growths) if growths else None,
            "members": len(members(key, qe)), "used": len(pairs),
            "nonpos_base": sum(1 for _, _, b in pairs if b <= 0), "top": contrib[:5]}


def nse_figures() -> dict[tuple[str, str, str], float]:
    with open(NSE_CSV, encoding="utf-8") as fh:
        return {(r["quarter"], r["index"], r["measure"]): float(r["value_pct"])
                for r in csv.DictReader(fh) if r["value_pct"] not in ("", None)}


def run_measure(cache: str, out: str) -> None:
    manifest = _load_json(os.path.join(cache, "manifest.json"))
    data, basis = company_data(cache, manifest)
    kinds: dict[str, int] = {}
    for b in basis.values():
        kinds[b] = kinds.get(b, 0) + 1
    print(f"pages: {len(manifest)} symbols; parsed {len(data)}; bases {json.dumps(kinds, sort_keys=True)}")
    print("no data:", sorted(s for s in manifest if s not in data))
    nse = nse_figures()
    rows, flagged = [], []
    for qe in QUARTER_ENDS:
        q = quarter_label(qe)
        for key, label in INDICES.items():
            for field, short in MEASURE.items():
                m = measure(data, key, qe, field)
                for stat in ("agg", "median"):
                    code = f"{short}_{stat}_yoy"
                    theirs = nse.get((q, label, code))
                    ours = m[stat]
                    gap = None if theirs is None or ours is None else round(ours - theirs, 2)
                    flag = stat == "agg" and label in GATED and gap is not None and abs(gap) > GROSS_PTS
                    rows.append({"quarter": q, "quarter_end": qe, "index": label, "measure": code,
                                 "ours_pct": None if ours is None else round(ours, 2), "nse_pct": theirs, "gap_pts": gap,
                                 "members": m["members"], "used": m["used"], "nonpos_base": m["nonpos_base"],
                                 "flagged": flag,
                                 "top5": "; ".join(f"{s} {b:.0f}->{n:.0f} ({c:+.2f})" for s, n, b, c in m["top"]) if stat == "agg" else ""})
                    if flag:
                        flagged.append(rows[-1])
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    _dump_json(basis, os.path.splitext(out)[0] + "_basis.json")
    print(f"wrote {out}; {len(flagged)} flagged (|gap| > {GROSS_PTS} pts, Nifty 50 / Nifty 500 aggregates)")
    for r in flagged:
        print(f"  {r['quarter']} {r['index']} {r['measure']}: ours {r['ours_pct']} NSE {r['nse_pct']} gap {r['gap_pts']} | {r['top5']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["fetch", "measure"])
    ap.add_argument("--cache", required=True, help="a directory outside the repo for the raw pages")
    ap.add_argument("--pause", type=float, default=1.5)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    if os.path.abspath(args.cache).startswith(ROOT + os.sep):
        ap.error("--cache must be outside the repository")
    if args.step == "fetch":
        fetch(args.cache, max(args.pause, 1.5), args.limit)
    else:
        run_measure(args.cache, args.out or os.path.join(args.cache, f"s171_screener_{date.today().isoformat()}.csv"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
