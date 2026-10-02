import csv, difflib, re, collections
from reverse2 import run, cur
res, prob = run()
ev = list(csv.DictReader(open("events_raw.csv")))
name_of = {}
for e in ev: name_of.setdefault(e["symbol"], e["company"])
cur_names = {}
for k in cur:
    try:
        for r in csv.DictReader(open(f"current/{k}.csv")): cur_names[r["Symbol"]] = r["Company Name"]
    except Exception: pass
def norm(s): return re.sub(r"\b(ltd|limited|india|the|company|co|corporation|corp|industries|enterprises)\b|[^a-z0-9 ]", "", s.lower()).split()
syms = sorted({s for p in prob for s in p[3] + p[4] if p[0] != "TOTAL_MARKET"})
first_later = collections.defaultdict(list)
for s in syms:
    nm = name_of.get(s) or cur_names.get(s, "")
    pool = {**{k: v for k, v in name_of.items() if k != s}, **{k: v for k, v in cur_names.items() if k != s}}
    t = norm(nm)
    scored = []
    for k, v in pool.items():
        u = norm(v)
        if not t or not u: continue
        r = difflib.SequenceMatcher(None, " ".join(t), " ".join(u)).ratio()
        if t[0] == u[0]: r += 0.25
        scored.append((r, k, v))
    scored.sort(reverse=True)
    best = [(round(r, 2), k, v[:34]) for r, k, v in scored[:2] if r > 0.8]
    if best: print(f"{s:12s} {nm[:34]:34s} -> {best}")
