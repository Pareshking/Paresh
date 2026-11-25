"""Earnings growth for the broad indices, our calculation from companies' reported results (S171).

Owner, 25 Nov 2026: "We will use Screener data only"; weekly, on Saturday; past members from
data/membership_history.json. Each company's "Quarterly Results" table on its Screener.in page
(src/loaders/screener_quarters.py) is added up over each index's members at each quarter end.

    python -I scripts/screener_earnings.py fetch --cache DIR     # every member's page, >= 1.5 s apart
    python -I scripts/screener_earnings.py build --cache DIR     # the two files below, and the NSE check

Pages are read for every index member on those quarter ends and every stock the site lists (~1,250, NSE's lists only).

Keeps (owner, 25 Nov 2026: "storing in R2 so we can have own history getting build up, use correct R2 format to save
a space"): every quarter ever read, in R2 dataset fundamentals/screener_quarters (parquet, zstd), one immutable
revision a week; each run starts from it, so the history outlives the 13 quarters a page shows.

Writes (readers: the Indices page's Earnings section and the Stock page's results table, src/engine/earnings_review.py):
- data/reference/screener_quarters.csv: the pages' copy, one row per company and quarter (Rs crore)
  for the last 13 quarters. A quarter on this week's page replaces the stored one (Screener restates).
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
import re
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
PARTIAL_SHARE = 0.10      # the quarter still coming in shows "so far" from one in ten Nifty 500 companies (owner, 25 Nov 2026)
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


# Left out of every index sum, with the owner's reason; the company's own Stock page still shows what it reported.
LEFT_OUT = {
    "RAJESHEXPO": "owner, 25 Nov 2026: \"It's fraud company, leave it\"; its reported revenue (Rs 2.9 lakh crore in the "
                  "Sep 2026 quarter, above Reliance's) is ~31% of the Microcap 250's and alone adds 27-40 pts to its growth",
}


def members(key: str, qe: str) -> set[str]:
    out = (research.members_on(research.index_history(key), qe, canonical=True) or set()) - set(LEFT_OUT)
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


FIGURES = ["sales", "operating_profit", "pbt", "net_profit", "other_income", "tax_pct", "eps"]


def _differs(a: dict, b: dict) -> bool:
    for c in FIGURES:
        x, y = a.get(c), b.get(c)
        if (pd.isna(x) != pd.isna(y)) or (not pd.isna(x) and abs(float(x) - float(y)) > 1e-9):
            return True
    return str(a.get("basis")) != str(b.get("basis"))


def merge(stored: pd.DataFrame | None, new: list[dict], today: str | None = None) -> pd.DataFrame:
    """This week's page wins for every quarter it shows (owner, 25 Nov 2026: "Screener do restatement when companies
    does, so ensure we are saving updated one"). A quarter whose figures changed keeps its earlier reading as a row
    with `superseded_on` set to the day it was replaced, so no restatement is lost; current rows have none."""
    fresh = pd.DataFrame(new, columns=QUARTER_COLS)
    cols = QUARTER_COLS + ["superseded_on"]
    if stored is None or stored.empty:
        out = fresh.assign(superseded_on=None)
        return out.sort_values(["symbol", "quarter_end"]).reset_index(drop=True)[cols]
    stored = stored.reindex(columns=cols)
    sup = pd.to_datetime(stored["superseded_on"], errors="coerce")
    stored = stored.assign(superseded_on=sup.dt.strftime("%Y-%m-%d").where(sup.notna(), None),
                           quarter_end=pd.to_datetime(stored["quarter_end"]).dt.strftime("%Y-%m-%d"))
    old_rows = stored[stored["superseded_on"].notna()]
    current = stored[stored["superseded_on"].isna()]
    by_key = {(r["symbol"], r["quarter_end"]): r for r in current.to_dict("records")}
    replaced = []
    for r in fresh.to_dict("records"):
        before = by_key.get((r["symbol"], r["quarter_end"]))
        if before is not None and _differs(before, r):
            replaced.append({**before, "superseded_on": today or r["fetched"]})
    kept = pd.concat([current, fresh.assign(superseded_on=None)], ignore_index=True)
    kept = kept.drop_duplicates(["symbol", "quarter_end"], keep="last")
    out = pd.concat([kept, old_rows, pd.DataFrame(replaced, columns=cols)], ignore_index=True)
    return out.sort_values(["symbol", "quarter_end", "superseded_on"], na_position="first").reset_index(drop=True)[cols]


def current_rows(quarters: pd.DataFrame) -> pd.DataFrame:
    """The figures as the company reports them now: superseded readings left out."""
    if "superseded_on" not in quarters.columns:
        return quarters
    return quarters[quarters["superseded_on"].isna()].drop(columns="superseded_on")


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
            size = len(research.members_on(research.index_history(key), qe, canonical=True) or ())
            for field in FIELDS:
                g = growth(values, syms, qe, field)
                for stat in ("agg", "median"):
                    v = g[stat]
                    rows.append({"quarter": q, "quarter_end": qe, "index": label, "measure": f"{field}_{stat}_yoy",
                                 "value_pct": None if v is None else round(v, 2), "members": len(syms), "size": size,
                                 "used": g["used"], "complete": complete})
                theirs = nse.get((q, label, f"{'pat' if field != 'sales' else 'sales'}_agg_yoy"))
                if complete and label in research.GATED and theirs is not None and g["agg"] is not None \
                        and abs(g["agg"] - theirs) > GROSS_PTS:
                    notes.append(f"{q} {label} {field}: ours {g['agg']:.1f} NSE {theirs:.1f} | " +
                                 "; ".join(f"{s} {b:.0f}->{n:.0f} ({c:+.2f})" for s, n, b, c in g["top"]))
    return pd.DataFrame(rows), notes


R2_DATASET = "fundamentals/screener_quarters"   # the full history; the repo keeps the pages' copy only


def read_store(path: str | None, from_r2: bool, quarters_csv: str) -> pd.DataFrame | None:
    """Every quarter kept so far: R2's published store first (owner, 25 Nov 2026: "storing in R2 so we can have own
    history getting build up"), else a local store, else the repo's copy (the first run seeds R2 from it)."""
    if from_r2:
        try:
            from src.storage.r2 import R2Archive, R2Config
            from src.storage.reader import R2DatasetReader
            reader = R2DatasetReader(R2Archive(R2Config.from_env()))
            got = reader.read_parquet(reader.resolve_current(R2_DATASET))
            print(f"R2 {R2_DATASET}: {len(got)} rows, {got['symbol'].nunique()} companies")
            return got.drop(columns=["as_of"], errors="ignore")
        except FileNotFoundError:
            print(f"R2 {R2_DATASET}: nothing published yet; starting from the repo's copy")
    if path and os.path.exists(path):
        return pd.read_parquet(path).drop(columns=["as_of"], errors="ignore")
    return pd.read_csv(quarters_csv) if os.path.exists(quarters_csv) else None


def write_store(quarters: pd.DataFrame, path: str, as_of: str) -> None:
    """Parquet, zstd, text columns as categories: about a fifth of the CSV's size. `as_of` dates the R2 revision."""
    out = quarters.copy()
    for c in ("symbol", "basis", "sales_label", "fetched"):
        out[c] = out[c].astype("category")
    out["quarter_end"] = pd.to_datetime(out["quarter_end"])
    if "superseded_on" in out.columns:
        out["superseded_on"] = pd.to_datetime(out["superseded_on"])
    out["as_of"] = pd.Timestamp(as_of)
    out.to_parquet(path, index=False, compression="zstd")


def publishable(out: pd.DataFrame) -> pd.DataFrame:
    """Complete quarters, and the newest one after them while it comes in (owner, 25 Nov 2026: "Show partial one"),
    once one in ten Nifty 500 companies have reported it."""
    if out.empty:
        return out
    done_q = out[out["complete"]]["quarter_end"].max() if out["complete"].any() else ""
    later = out[(~out["complete"]) & (out["quarter_end"] > done_q)]
    if not len(later):
        return out[out["complete"]]
    newest = later["quarter_end"].max()
    n500 = later[(later["quarter_end"] == newest) & (later["index"] == "Nifty 500") & (later["measure"] == "sales_agg_yoy")]
    if len(n500) and n500["used"].iloc[0] >= PARTIAL_SHARE * n500["size"].iloc[0]:
        return out[out["complete"] | (out["quarter_end"] == newest)]
    return out[out["complete"]]


def build(cache: str, quarters_csv: str = QUARTERS_CSV, earnings_csv: str = EARNINGS_CSV, store: str | None = None,
          from_r2: bool = False) -> int:
    today = date.today().isoformat()
    stored = read_store(store, from_r2, quarters_csv)
    if stored is not None:
        stored = stored.assign(quarter_end=pd.to_datetime(stored["quarter_end"]).dt.strftime("%Y-%m-%d"))
    since = quarter_ends(date.today())[0]
    new = page_rows(cache, today, since=since)
    if research.universe.__name__ == "universe":         # widened: keep the stocks the site shows and index members
        keep = set(research.universe())
        new = [r for r in new if r["symbol"] in keep]
    if not new:
        print("no pages parsed; nothing written")
        return 1
    quarters = merge(stored, new, today)
    restated = quarters[quarters["superseded_on"].astype(str) == today]
    print(f"restated this run: {len(restated)} company-quarter(s)" + (" (" + ", ".join(
        f"{r.symbol} {r.quarter_end}" for r in restated.head(20).itertuples()) + ")" if len(restated) else ""))
    if store:
        write_store(quarters, store, today)
        print(f"wrote {store} ({os.path.getsize(store) / 1024:.0f} KB, every quarter kept)")
    # The pages' copy: the quarters the Stock page and the Indices build can use (13 back), not the whole history.
    now = current_rows(quarters)
    now[now["quarter_end"] >= since].to_csv(quarters_csv, index=False, quoting=csv.QUOTE_MINIMAL)
    out, notes = earnings(now)
    out = publishable(out)
    out["as_of"] = str(now["fetched"].max())
    out.to_csv(earnings_csv, index=False)
    print(f"wrote {quarters_csv} ({len(now)} rows, {now['symbol'].nunique()} companies) and "
          f"{earnings_csv} ({len(out)} rows)")
    done = out["quarter"].unique().tolist()
    print(f"complete quarters (>= {COMPLETE_SHARE:.0%} of the Nifty 500's members): {', '.join(done)}")
    print(f"NSE check: {len(notes)} reading(s) over {GROSS_PTS} points (a report, not a gate)")
    for n in notes:
        print("  " + n)
    return 0


# ── Which pages this week (owner, 25 Nov 2026: "keep our weekly run intelligent ... if it have latest Q results,
#    don't fetch it again and again every Saturday") ──────────────────────────────────────────────────────────────

CALENDAR_CSV = os.path.join(ROOT, "data", "results_calendar.csv")   # NSE's board meetings, nightly


def due_quarter(today: date) -> tuple[str, date]:
    """The latest quarter end before today, and its filing deadline: SEBI LODR Reg 33 gives 45 days after a quarter,
    60 after the March quarter (the year's audited results)."""
    qe = quarter_ends(today, years=1)[-1]
    end = date.fromisoformat(qe)
    return qe, end + pd.Timedelta(days=60 if end.month == 3 else 45)


def pages_to_read(candidates: list[str], stored: pd.DataFrame | None, calendar: pd.DataFrame | None,
                  today: date) -> tuple[list[str], dict[str, int]]:
    """A stock's page is read when:
    (1) we hold nothing for it;
    (2) it lacks the due quarter and NSE's calendar shows a results meeting since we last read it;
    (3) it lacks the due quarter, the calendar has no results meeting for it, and the filing window is open;
    (4) once a quarter, the first run after the filing deadline, if we last read it before then: restated quarters
        and late filers are caught.
    Otherwise it is skipped: it already has the due quarter, or it has no results to give yet."""
    qe, deadline = due_quarter(today)
    last, latest = {}, {}
    if stored is not None and len(stored):
        g = stored.groupby("symbol")
        last = g["fetched"].max().astype(str).to_dict()
        latest = g["quarter_end"].max().astype(str).str[:10].to_dict()
    meetings: dict[str, list[str]] = {}
    if calendar is not None and len(calendar):
        held = calendar[(calendar["results"] == 1) & (calendar["date"] <= today.isoformat())]
        for sym, d in zip(held["symbol"], held["date"]):
            meetings.setdefault(str(sym), []).append(str(d))
    out, why = [], {"new": 0, "results announced": 0, "window, no calendar": 0, "quarterly refresh": 0, "skipped": 0}
    for sym in candidates:
        seen = last.get(sym)
        if seen is None:
            reason = "new"
        elif today >= deadline and seen < deadline.isoformat():
            reason = "quarterly refresh"
        elif latest.get(sym, "") < qe and any(d >= seen for d in meetings.get(sym, [])):
            reason = "results announced"
        elif latest.get(sym, "") < qe and sym not in meetings and today <= deadline:
            reason = "window, no calendar"
        else:
            why["skipped"] += 1
            continue
        why[reason] += 1
        out.append(sym)
    return out, why


SERIES_SUFFIX = re.compile(r"\.[A-Z0-9]{1,3}$")     # ATLPP.E1, AARTISURF.P1, BIRET.RR: a partly-paid or unit line


def canonical_symbols(symbols, renames: dict[str, str], listed: set[str]) -> tuple[list[str], dict[str, str]]:
    """Each symbol as NSE lists it today, so every company has a page (owner, 25 Nov 2026: "check screener website with
    company names etc first"): a renamed ticker follows NSE's symbol-change file (AKZOINDIA -> JSWDULUX, BARBEQUE ->
    UFBL, ABCOTS -> ABCIND); a TradingView spelling takes NSE's (BAJAJ_AUTO -> BAJAJ-AUTO); a partly-paid or unit line
    (.P1, .E1, .RR) is the same company as its parent, whose page is read anyway. Returns the symbols and why each
    one changed or went."""
    out, why = set(), {}
    for sym in symbols:
        s = sym
        if SERIES_SUFFIX.search(s):
            why[sym] = "a partly-paid or unit line of " + SERIES_SUFFIX.sub("", s)
            continue
        if "_" in s and s.replace("_", "-") in listed:
            s = s.replace("_", "-")
        if s not in listed and renames.get(s) in listed:
            s = renames[s]
        if s != sym:
            why[sym] = f"read as {s}"
        out.add(s)
    return sorted(out), why


def site_lists() -> set[str]:
    """The stocks the site ranks and shows, from NSE's own index files (the 750, the Nifty 1000) and the Nano list
    built from NSE's: not TradingView's classification file, whose old tickers and spellings (AKZOINDIA, BAJAJ_AUTO,
    ATLPP.E1) were 315 of its 2,404 symbols (owner, 25 Nov 2026: "If you are using NSE CSV to build latest universe,
    this issue would not be there"). NSE's placeholder rows (DUMMYHEG) are not companies."""
    from scripts.nse_classification import LISTS
    out: set[str] = set()
    for path in LISTS.values():
        if os.path.exists(path):
            out |= set(pd.read_csv(path)["Symbol"].astype(str).str.strip().str.upper())
    return {s for s in out if s and s != "NAN" and not s.startswith("DUMMY")}


def widen_to_every_listed_stock() -> None:
    """Pages for every stock the site lists, not only the index members (owner, 25 Nov 2026: the Stock page's results
    table, "Go ahead"): the indices still add up their own members only. Each symbol is read as NSE lists it today
    (a past member renamed since, BARBEQUE -> UFBL), and names come from NSE's equity list for the name search."""
    from src.loaders import nse_identity as ni
    equity = pd.read_csv(ni.EQUITY_L)
    equity.columns = [c.strip() for c in equity.columns]
    nse_names = dict(zip(equity["SYMBOL"].str.strip(), equity["NAME OF COMPANY"].str.strip()))
    res = ni.resolve()
    renames = dict(zip(res["old"], res["new"]))
    members_only, names_only = research.universe, research.names
    shown = site_lists()

    def universe():
        syms, why = canonical_symbols(set(members_only()) | shown, renames, set(nse_names))
        if why:
            print(f"{len(why)} symbol(s) read another way: " + "; ".join(f"{k} {v}" for k, v in sorted(why.items())))
        return syms

    research.universe = universe
    research.names = lambda: {**nse_names, **names_only()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["fetch", "build"])
    ap.add_argument("--cache", required=True, help="a directory outside the repository for the raw pages")
    ap.add_argument("--pause", type=float, default=1.5)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--store", help="build: the full-history parquet to read and write (published to R2)")
    ap.add_argument("--from-r2", action="store_true", help="build: start from R2's published store")
    ap.add_argument("--all", action="store_true", help="fetch: every page, not only those due (pages_to_read)")
    args = ap.parse_args(argv)
    if os.path.abspath(args.cache).startswith(ROOT + os.sep):
        ap.error("--cache must be outside the repository")
    research.QUARTER_ENDS = quarter_ends(date.today())
    widen_to_every_listed_stock()
    if args.step == "fetch":
        if not args.all:
            stored = pd.read_csv(QUARTERS_CSV) if os.path.exists(QUARTERS_CSV) else None
            cal = pd.read_csv(CALENDAR_CSV) if os.path.exists(CALENDAR_CSV) else None
            every = research.universe()
            chosen, why = pages_to_read(every, stored, cal, date.today())
            print(f"due quarter {due_quarter(date.today())[0]}, deadline {due_quarter(date.today())[1]}: "
                  f"{len(chosen)} of {len(every)} pages to read; " + ", ".join(f"{k} {v}" for k, v in why.items()))
            research.universe = lambda: chosen
        research.fetch(args.cache, max(args.pause, 1.5), args.limit)
        if args.limit:
            return 0
        got = research._load_json(os.path.join(args.cache, "manifest.json"))
        ok = sum(1 for v in got.values() if v.get("status") == 200)
        want = len(research.universe())
        print(f"{ok} of {want} pages read")
        if want == 0:
            return 0
        # Screener stopped the run (403, or a 429 that did not clear): build nothing, show red.
        return 0 if ok >= COMPLETE_SHARE * want else 1
    return build(args.cache, store=args.store, from_r2=args.from_r2)  # widen_to_every_listed_stock() ran above


if __name__ == "__main__":
    sys.exit(main())
