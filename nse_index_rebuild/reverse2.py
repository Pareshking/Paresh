import csv, collections, sys
INDS = ["NIFTY_50","NIFTY_NEXT_50","NIFTY_MIDCAP_150","NIFTY_SMALLCAP_250","NIFTY_MICROCAP_250"]
cur = {k: {r["Symbol"].strip() for r in csv.DictReader(open(f"current/{k}.csv"))} for k in INDS}
ev = list(csv.DictReader(open("events_raw.csv")))
ov = list(csv.DictReader(open("rules/overrides.csv")))
al = list(csv.DictReader(open("rules/aliases.csv")))
cancel = {(o["file"], o["index"], o["action"], o["symbol"]) for o in ov if o["kind"] == "CANCEL"}
for o in ov:
    if o["kind"] == "ADD": ev.append({"published":"","effective":o["effective"],"file":o["file"],"index":o["index"],"action":o["action"],"symbol":o["symbol"],"company":"(manual)"})
ev = [r for r in ev if (r["file"], r["index"], r["action"], r["symbol"]) not in cancel]
def run(verbose=True):
    results = {}; problems = []
    for k in INDS:
        state = set(cur[k]); items = []
        g = collections.defaultdict(list)
        for r in ev:
            if r["index"] == k: g[(r["effective"], r["file"])].append(r)
        for (e, f), rows in g.items(): items.append((e, 1, f, rows))
        for a in al: items.append((a["first_new_date"], 0, "ALIAS", a))
        items.sort(key=lambda x: (x[0], x[1]), reverse=True)
        snaps = []
        for e, kind, f, payload in items:
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
    res, prob = run()
    print("problem events:", len(prob))
    for p in sorted(prob, key=lambda p: p[1], reverse=True)[:int(sys.argv[1]) if len(sys.argv) > 1 else 12]:
        print(p[0][6:], p[1], p[2][7:], "BAD_IN", p[3][:8], "BAD_OUT", p[4][:8], "size_after_undo", p[5])
