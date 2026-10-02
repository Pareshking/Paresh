import csv, collections, re, sys
INDS = ["NIFTY_50","NIFTY_NEXT_50","NIFTY_MIDCAP_150","NIFTY_SMALLCAP_250","NIFTY_MICROCAP_250","NIFTY_TOTAL_MARKET","NIFTY_500"]
cur = {k: {r["Symbol"].strip().upper() for r in csv.DictReader(open(f"current/{k}.csv")) if r["Symbol"].strip() and not r["Symbol"].strip().upper().startswith("DUMMY")} for k in INDS}
TARGET = {"NIFTY_50": 50, "NIFTY_NEXT_50": 50, "NIFTY_MIDCAP_150": 150, "NIFTY_SMALLCAP_250": 250, "NIFTY_MICROCAP_250": 250, "NIFTY_TOTAL_MARKET": 750, "NIFTY_500": 500}
bad_snapshots = [(k, len(v), TARGET[k]) for k, v in cur.items() if len(v) != TARGET[k]]
if bad_snapshots:
    raise SystemExit(f"current snapshot cardinality failure: {bad_snapshots}")
def _pub(f):
    m = re.match(r"ind_prs(\d{2})(\d{2})(\d{4})", f)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""
ev = list(csv.DictReader(open("events_raw.csv")))
ov = list(csv.DictReader(open("rules/overrides.csv")))
al = list(csv.DictReader(open("rules/aliases.csv")))
cancel = {(o["file"], o["index"], o["action"], o["symbol"]) for o in ov if o["kind"] == "CANCEL"}
for o in ov:
    if o["kind"] == "ADD": ev.append({"published":_pub(o["file"]),"effective":o["effective"],"file":o["file"],"index":o["index"],"action":o["action"],"symbol":o["symbol"],"company":"(manual)"})
void = {(o["file"], o["index"]) for o in ov if o["kind"] == "VOID"}
for o in ov:
    if o["kind"] == "ADD_EFF":
        ev.append({"published":_pub(o["file"]),"effective":o["evidence"].split("|")[1],"file":o["file"],"index":o["index"],"action":o["action"],"symbol":o["symbol"],"company":"(manual)"})
ev = [r for r in ev if (r["file"], r["index"], r["action"], r["symbol"]) not in cancel and (r["file"], r["index"]) not in void]
# The same (effective date, index, action, symbol) announced twice is one event: keep the later-published copy.
_best = {}
for r in ev:
    k = (r["effective"], r["index"], r["action"], r["symbol"])
    if k not in _best or (r["published"], r["file"]) > (_best[k]["published"], _best[k]["file"]): _best[k] = r
ev = [r for r in ev if _best[(r["effective"], r["index"], r["action"], r["symbol"])] is r]
# The same (index, action, symbol) announced again within 45 days is a revision of the earlier notice: keep the later-published one.
import datetime as _dt
_grp = collections.defaultdict(list)
for r in ev: _grp[(r["index"], r["action"], r["symbol"])].append(r)
_drop = set()
for _k, _rows in _grp.items():
    _rows.sort(key=lambda x: (x["published"], x["file"]))
    for _a, _b in zip(_rows, _rows[1:]):
        if _a["file"] != _b["file"] and _a["published"] and _b["published"] and (_dt.date.fromisoformat(_b["published"]) - _dt.date.fromisoformat(_a["published"])).days <= 45 and _a["effective"] != _b["effective"]:
            _drop.add(id(_a))
ev = [r for r in ev if id(r) not in _drop]
def run(verbose=True):
    results = {}; problems = []
    for k in INDS:
        state = set(cur[k]); items = []
        g = collections.defaultdict(list)
        for r in ev:
            if r["index"] == k: g[(r["effective"], r["file"])].append(r)
        for (e, f), rows in g.items():
            published = max((r["published"] for r in rows), default="")
            items.append((e, published, 1, f, rows))
        for a in al:
            items.append((a["first_new_date"], "", 0, "ALIAS", a))
        # Rewind same-effective-date announcements in reverse publication order.
        # Filename ordering is not chronological (e.g. February vs August notices).
        items.sort(key=lambda x: (x[0], x[1], x[2], x[3]), reverse=True)
        snaps = []
        for e, published, kind, f, payload in items:
            if kind == 0:
                if payload["new_symbol"] in state:
                    state.discard(payload["new_symbol"]); state.add(payload["old_symbol"])
                continue
            ins = [r["symbol"] for r in payload if r["action"] == "IN"]; outs = [r["symbol"] for r in payload if r["action"] == "OUT"]
            bad_in = [s for s in ins if s not in state]; bad_out = [s for s in outs if s in state]
            snaps.append((e, f, sorted(state)))
            for s in ins: state.discard(s)
            for s in outs: state.add(s)
            n_after = len(state)
            if bad_in or bad_out: problems.append((k, e, f, bad_in, bad_out, n_after))
        results[k] = (state, snaps)
    return results, problems
if __name__ == "__main__":
    import csv
    res, prob = run()
    with open("open_issues.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["index", "effective_date", "announcement",
                    "symbols_in_announcement_but_not_in_reconstructed_state",
                    "symbols_excluded_but_still_in_state", "size_after_undo", "status"])
        for p in sorted(prob, key=lambda p: (p[1], p[0], p[2]), reverse=True):
            w.writerow([p[0], p[1], p[2], ";".join(p[3]), ";".join(p[4]), p[5], "OPEN"])
    print("problem events:", len(prob))
    for p in sorted(prob, key=lambda p: p[1], reverse=True)[:int(sys.argv[1]) if len(sys.argv) > 1 else 12]:
        print(p[0][6:], p[1], p[2][7:], "BAD_IN", p[3][:8], "BAD_OUT", p[4][:8], "size_after_undo", p[5])
    if prob:
        raise SystemExit(1)
