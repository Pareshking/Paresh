"""Cross-check the reconstruction against NSE's own IndexInclExcl.xls, event by event.

NSE publishes every inclusion and exclusion per index in one workbook (https://archives.nseindia.com/content/indices/IndexInclExcl.xls;
the copy used here is reference/IndexInclExcl.xls, last saved by NSE 2020-09-22). Its sheets cover Nifty 50, Next 50 and Nifty 500,
so this is a check of the reconstruction against a source that is not the press-release PDFs. Events match on (effective date,
action, company name); names are normalised, then matched by token similarity when a company was renamed between the two sources.

    python crosscheck_inclexcl.py [path/to/IndexInclExcl.xls]            # report
    python crosscheck_inclexcl.py --assert                                # CI: fail on any difference not in rules/inclexcl_known_differences.csv
    python crosscheck_inclexcl.py --write-known                           # regenerate the known-differences list (then review it)
"""
import collections, csv, datetime as dt, difflib, io, os, sys, contextlib
import pandas as pd

with contextlib.redirect_stdout(io.StringIO()):  # parse_events prints its tally on import
    import reverse2
    import parse_events as pe

HERE = os.path.dirname(os.path.abspath(__file__))
SHEETS = {"NIFTY_50": ("Nifty 50", "2010-01-01", "2020-07-31"), "NIFTY_NEXT_50": ("Nifty Next 50", "2010-01-01", "2020-07-31"),
          "NIFTY_500": ("Nifty 500", "2010-01-01", "2020-09-14")}


def parse_date(v):
    if isinstance(v, (dt.datetime, pd.Timestamp)):
        return v.date().isoformat()
    s = str(v).strip()
    for fmt in ("%d-%m-%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def nse_events(path, sheet, lo, hi):
    d = pd.ExcelFile(path).parse(sheet, header=0)
    d.columns = ["index", "date", "name", "desc"]
    out = []
    for _, r in d.iterrows():
        day = parse_date(r["date"])
        if day and lo <= day <= hi:
            out.append((day, "IN" if str(r["desc"]).strip().lower().startswith("inclusion") else "OUT", str(r["name"]).strip()))
    return out


def my_events(index, lo, hi):
    names = {r["symbol"]: r["company"] for r in reverse2.ev if r["company"] and r["company"] != "(manual)"}
    return [(r["effective"], r["action"], names.get(r["symbol"], r["symbol"]), r["symbol"])
            for r in reverse2.ev if r["index"] == index and lo <= r["effective"] <= hi]


def similar(a, b):
    na, nb = pe.norm_name(a), pe.norm_name(b)
    if na == nb:
        return 1.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def compare(nse, mine, threshold=0.8):
    """Greedy match within (date, action); returns matched, only_nse, only_mine."""
    by = collections.defaultdict(list)
    for e in mine:
        by[(e[0], e[1])].append(e)
    matched, only_nse = [], []
    for day, act, name in nse:
        pool = by[(day, act)]
        best = max(pool, key=lambda e: similar(name, e[2]), default=None)
        if best is not None and similar(name, best[2]) >= threshold:
            pool.remove(best)
            matched.append(((day, act, name), best))
        else:
            only_nse.append((day, act, name))
    only_mine = [e for pool in by.values() for e in pool]
    return matched, only_nse, only_mine


def pair_leftovers(nse_left, mine_left, name_min=0.6, days=45):
    """Pair leftover events of the same action by name similarity and date proximity.
    Returns (renamed_same_date, date_differs, only_nse, only_mine)."""
    def gap(a, b):
        return abs((dt.date.fromisoformat(a) - dt.date.fromisoformat(b)).days)
    cands = sorted(((similar(n[2], m[2]), -gap(n[0], m[0]), i, j) for i, n in enumerate(nse_left) for j, m in enumerate(mine_left)
                    if n[1] == m[1] and gap(n[0], m[0]) <= days and similar(n[2], m[2]) >= name_min), reverse=True)
    used_n, used_m, renamed, moved = set(), set(), [], []
    for sim, _g, i, j in cands:
        if i in used_n or j in used_m:
            continue
        used_n.add(i); used_m.add(j)
        (renamed if nse_left[i][0] == mine_left[j][0] else moved).append((nse_left[i], mine_left[j]))
    return (renamed, moved, [n for i, n in enumerate(nse_left) if i not in used_n],
            [m for j, m in enumerate(mine_left) if j not in used_m])


KNOWN = os.path.join(HERE, "rules", "inclexcl_known_differences.csv")
REASONS = {  # events where the two sources really disagree, beyond a company being named differently
    ("NIFTY_500", "2011-01-20", "OUT", "nse"): "NSE's workbook names Next Mediaworks; the press release ind_prs18012011 (ex-date 2011-01-20, scheme of arrangement) names Mid-Day Multimedia. The press release is followed.",
    ("NIFTY_500", "2017-09-05", "OUT", "nse"): "the workbook lists this event twice on 2017-09-05; the reconstruction has it once (ind_prs29082017 rescheduled it from 2017-09-29)",
    ("NIFTY_500", "2017-09-05", "IN", "nse"): "the workbook lists this event twice on 2017-09-05; the reconstruction has it once (ind_prs29082017 rescheduled it from 2017-09-29)",
}


def load_known():
    if not os.path.exists(KNOWN):
        return set()
    return {(r["index"], r["date"], r["action"], r["side"], r["name"]) for r in csv.DictReader(open(KNOWN))}


def main(path, mode="report"):
    rows = []
    unexplained = []
    for index, (sheet, lo, hi) in SHEETS.items():
        m, on, om = compare(nse_events(path, sheet, lo, hi), my_events(index, lo, hi))
        renamed, moved, on, om = pair_leftovers(on, om)
        print(f"{index} [{lo} to {hi}]: {len(m)} exact + {len(renamed)} under another company name = {len(m) + len(renamed)} agree; "
              f"{len(moved)} same event, date differs; {len(on)} only in NSE's file; {len(om)} only in the reconstruction")
        for e, o in moved:
            print(f"   DATE  {e[1]} {e[2]!r}: NSE {e[0]}, reconstruction {o[0]} ({o[3]}, {(dt.date.fromisoformat(o[0]) - dt.date.fromisoformat(e[0])).days:+d} days)")
        for e in on:
            print(f"   ONLY NSE   {e[0]} {e[1]} {e[2]!r}")
        for o in om:
            print(f"   ONLY MINE  {o[0]} {o[1]} {o[2]!r} ({o[3]})")
        if mode != "report":
            known = load_known()
            unexplained += [("date", index, e) for e, o in moved]
            unexplained += [("only_nse", index, e) for e in on if (index, e[0], e[1], "nse", e[2]) not in known]
            unexplained += [("only_mine", index, o) for o in om if (index, o[0], o[1], "mine", o[2]) not in known]
            if mode == "write-known":
                with open(KNOWN, "a", newline="") as fh:
                    w = csv.writer(fh)
                    for e in on:
                        same = any(o[0] == e[0] and o[1] == e[1] for o in om)
                        w.writerow([index, e[0], e[1], "nse", e[2], REASONS.get((index, e[0], e[1], "nse")) or ("same event, company named differently in the two sources" if same else "UNEXPLAINED")])
                    for o in om:
                        same = any(e[0] == o[0] and e[1] == o[1] for e in on)
                        w.writerow([index, o[0], o[1], "mine", o[2], "same event, company named differently in the two sources" if same else "UNEXPLAINED"])
        rows += [(index, "match", e[0], e[1], e[2], o[0], o[3]) for e, o in m]
        rows += [(index, "match_renamed", e[0], e[1], e[2], o[0], o[3]) for e, o in renamed]
        rows += [(index, "date_differs", e[0], e[1], e[2], o[0], o[3]) for e, o in moved]
        rows += [(index, "only_nse", e[0], e[1], e[2], "", "") for e in on]
        rows += [(index, "only_reconstruction", "", o[1], o[2], o[0], o[3]) for o in om]
    with open(os.path.join(HERE, "reference", "inclexcl_crosscheck.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["index", "result", "nse_date", "action", "nse_name", "reconstruction_date", "symbol"])
        w.writerows(rows)
    if mode == "assert":
        if unexplained:
            for kind, index, e in unexplained:
                print("UNEXPLAINED", kind, index, e)
            sys.exit(f"{len(unexplained)} difference(s) from NSE's workbook not in rules/inclexcl_known_differences.csv")
        print("every difference from NSE's workbook is explained")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    main(args[0] if args else os.path.join(HERE, "reference", "IndexInclExcl.xls"),
         "assert" if "--assert" in flags else "write-known" if "--write-known" in flags else "report")
