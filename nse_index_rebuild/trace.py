import csv, glob, sys
# No shell (audit O-L7): the symbols come from argv, and interpolating
# them into a shell string let an odd argument run as a command.
syms = sys.argv[1:]
ev = list(csv.DictReader(open("events_raw.csv")))
cur = {k: {r["Symbol"] for r in csv.DictReader(open(f"current/{k}.csv"))} for k in ["NIFTY_50","NIFTY_NEXT_50","NIFTY_MIDCAP_150","NIFTY_SMALLCAP_250","NIFTY_MICROCAP_250","NIFTY_TOTAL_MARKET"]}
for s in syms:
    print(f"== {s}  current in: {[k[6:] for k,v in cur.items() if s in v]}")
    for r in sorted((r for r in ev if r["symbol"] == s), key=lambda r: r["effective"], reverse=True)[:8]:
        print("  ", r["effective"], r["file"][7:], r["index"][6:], r["action"], r["company"][:40])
    hits = []
    for path in sorted(glob.glob("announcements/txt/*.txt")):
        try:
            with open(path, encoding="utf-8", errors="ignore") as fh:
                if any(s == word for line in fh for word in line.split()):
                    hits.append(path.split("prs")[-1].removesuffix(".txt"))
        except OSError:
            continue
    files = " ".join(hits)
    print("   files mentioning:", files[:200])
