import csv, sys, subprocess
syms = sys.argv[1:]
ev = list(csv.DictReader(open("events_raw.csv")))
cur = {k: {r["Symbol"] for r in csv.DictReader(open(f"current/{k}.csv"))} for k in ["NIFTY_50","NIFTY_NEXT_50","NIFTY_MIDCAP_150","NIFTY_SMALLCAP_250","NIFTY_MICROCAP_250"]}
for s in syms:
    print(f"== {s}  current in: {[k[6:] for k,v in cur.items() if s in v]}")
    for r in sorted((r for r in ev if r["symbol"] == s), key=lambda r: r["effective"], reverse=True)[:8]:
        print("  ", r["effective"], r["file"][7:], r["index"][6:], r["action"], r["company"][:40])
    files = subprocess.run(f"grep -l -w '{s}' announcements/txt/*.txt | sed 's#.*prs##;s#.txt##' | tr '\\n' ' '", shell=True, capture_output=True, text=True).stdout
    print("   files mentioning:", files[:200])
