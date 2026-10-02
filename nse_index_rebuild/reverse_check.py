import csv, collections
cur = {}
for k in ["NIFTY_50","NIFTY_NEXT_50","NIFTY_MIDCAP_150","NIFTY_SMALLCAP_250","NIFTY_MICROCAP_250"]:
    cur[k] = {r["Symbol"].strip() for r in csv.DictReader(open(f"current/{k}.csv"))}
ev = list(csv.DictReader(open("events_raw.csv")))
groups = collections.defaultdict(list)
for r in ev: groups[(r["index"], r["effective"], r["file"])].append(r)
viol = []
state = {k: set(v) for k, v in cur.items()}
for k in state:
    for (idx, e, f), rows in sorted(((g, r) for g, r in groups.items() if g[0] == k), key=lambda x: (x[0][1], x[0][2]), reverse=True):
        ins = [r["symbol"] for r in rows if r["action"] == "IN"]; outs = [r["symbol"] for r in rows if r["action"] == "OUT"]
        bad_in = [s for s in ins if s not in state[k]]; bad_out = [s for s in outs if s in state[k]]
        for s in ins: state[k].discard(s)
        for s in outs: state[k].add(s)
        viol.append((k, e, f, len(ins), len(outs), len(state[k]), bad_in, bad_out))
bad = [v for v in viol if v[6] or v[7]]
print("events:", len(viol), "with violations:", len(bad))
for v in viol[:14]: print(v[0][6:], v[1], v[2][7:], f"in={v[3]} out={v[4]} size_after_undo={v[5]}", "BAD_IN" if v[6] else "", v[6][:4], "BAD_OUT" if v[7] else "", v[7][:4])
