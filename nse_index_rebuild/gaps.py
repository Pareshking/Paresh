import csv, glob, os, subprocess, sys, collections
from reverse2 import run
res, prob = run()
ev = list(csv.DictReader(open("events_raw.csv")))
parsed = collections.defaultdict(set)
for e in ev: parsed[e["symbol"]].add(e["file"])
def pub(f): b=os.path.basename(f)[7:15]; return b[4:]+"-"+b[2:4]+"-"+b[:2]
lim = int(sys.argv[1]) if len(sys.argv) > 1 else 12
for k, eff, f, bi, bo, n in sorted(prob, key=lambda p: p[1], reverse=True)[:lim]:
    for s in bi + bo:
        files = subprocess.run(["grep","-lw","--",s]+glob.glob("announcements/txt/*.txt"),capture_output=True,text=True).stdout.split()
        cand = sorted(os.path.basename(x)[:-4] for x in files if pub(x) > eff and os.path.basename(x)[:-4] not in parsed[s])
        print(f"{k[6:]:14s} {eff} {s:12s} later-unparsed-mentions: {[c[7:] for c in cand][:6]}")
