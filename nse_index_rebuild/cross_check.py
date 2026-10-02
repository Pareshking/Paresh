import csv, bisect
from reverse2 import run
res, prob = run()
al = list(csv.DictReader(open("rules/aliases.csv")))
def canon(sym, date):
    ch = True
    while ch:
        ch = False
        for a in al:
            if sym == a["new_symbol"] and date < a["first_new_date"]: sym = a["old_symbol"]; ch = True
            elif sym == a["old_symbol"] and date >= a["first_new_date"]: sym = a["new_symbol"]; ch = True
    return sym
steps = {}
for k, (st, sn) in res.items():
    seen = {}
    for e, f, s in sn: seen.setdefault(e, set(s))
    dates = sorted(seen)
    steps[k] = (dates, seen, set(st))
def state_at(k, d):
    dates, seen, oldest = steps[k]
    i = bisect.bisect_right(dates, d) - 1
    return seen[dates[i]] if i >= 0 else oldest
def check(name, whole, parts, start, label):
    ds = sorted({d for k in [whole] + parts for d in steps[k][0] if d >= start})
    bad = []; dvr = []
    for d in ds:
        a = {canon(s, d) for s in state_at(whole, d)}
        b = set()
        for p in parts: b |= {canon(s, d) for s in state_at(p, d)}
        if a ^ b == {"TATAMTRDVR"} and "2016-04-01" <= d < "2024-08-30" and "TATAMTRDVR" in a: dvr.append(d); continue
        if a != b: bad.append((d, len(a), len(b), sorted(a - b)[:4], sorted(b - a)[:4]))
    print(f"{label}: dates compared {len(ds)}, identical {len(ds) - len(bad) - len(dvr)}, explained only by the Tata Motors DVR additional security {len(dvr)}, mismatching {len(bad)}")
    for x in bad[:12]: print("  ", x)
    return bad
check("N500", "NIFTY_500", ["NIFTY_50", "NIFTY_NEXT_50", "NIFTY_MIDCAP_150", "NIFTY_SMALLCAP_250"], "2016-10-01", "Nifty 500 vs N50+Next50+Mid150+Small250 (from 2016-10)")
check("TM", "NIFTY_TOTAL_MARKET", ["NIFTY_500", "NIFTY_MICROCAP_250"], "2021-11-01", "Total Market vs Nifty 500 + Microcap 250")
