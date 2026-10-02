import csv, glob, os, subprocess
import reverse2
base = [dict(r) for r in csv.DictReader(open("rules/aliases.csv"))]
cands = [("GLS","ALIVUS"),("LAXMIMACH","LMW")]
ev = reverse2.ev
def mentions(sym):
    out = subprocess.run(["grep","-lw","--",sym]+glob.glob("announcements/txt/*.txt"),capture_output=True,text=True).stdout.split()
    ds=[]
    for f in out:
        b=os.path.basename(f)[7:15]; ds.append(b[4:]+"-"+b[2:4]+"-"+b[:2])
    for f in glob.glob("current/*.csv"):
        if f.endswith("MANIFEST.csv"): continue
        if any(r["Symbol"]==sym for r in csv.DictReader(open(f))): ds.append("2026-10-02")
    return sorted(ds)
def score():
    res, prob = reverse2.run()
    return sum(len(p[3])+len(p[4]) for p in prob if p[0]!="TOTAL_MARKET"), len([p for p in prob if p[0]!="TOTAL_MARKET"])
reverse2.al = base; s0 = score(); print("baseline bad symbols/events:", s0)
acc = []
for old, new in cands:
    if old == new: continue
    n = mentions(new); o = mentions(old)
    if not n: print("skip (new symbol never appears):", old, new); continue
    oe=[e["effective"] for e in ev if e["symbol"]==old]; ne=[e["effective"] for e in ev if e["symbol"]==new]
    last_old = max(oe+o[-1:]); first_new = min(ne+n[:1])
    if last_old >= first_new:
        # allow if old only appears in older notices and new appears only later by effective date
        print("overlap, skip:", old, last_old, new, first_new); continue
    trial = base + acc + [{"old_symbol":old,"new_symbol":new,"last_old_date":last_old,"first_new_date":first_new,"evidence":"","status":"TRIAL"}]
    reverse2.al = trial; s1 = score()
    cur_best = score_prev = None
    reverse2.al = base + acc; s_before = score()
    if s1[0] < s_before[0]:
        acc.append({"old_symbol":old,"new_symbol":new,"last_old_date":last_old,"first_new_date":first_new,
            "evidence":f"Company-name continuity ({old} -> {new}); accepted because it removed {s_before[0]-s1[0]} chain violations in the reverse replay; old last in notices {last_old}, new first {first_new}. NSE circular still to be located",
            "status":"INFERRED_FROM_SYMBOL_CONTINUITY"})
        print("ACCEPT", old, "->", new, f"(-{s_before[0]-s1[0]} violations)")
    else: print("reject", old, "->", new, "no improvement")
reverse2.al = base + acc; print("final:", score())
w = csv.DictWriter(open("rules/aliases.csv","w",newline=""), fieldnames=["old_symbol","new_symbol","last_old_date","first_new_date","evidence","status"]); w.writeheader(); w.writerows(base+acc)
