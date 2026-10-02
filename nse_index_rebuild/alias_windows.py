import csv, re, glob, os, subprocess
rows = list(csv.DictReader(open("rules/aliases.csv")))
def files_with(sym):
    out = subprocess.run(["grep","-lw","--",sym]+glob.glob("announcements/txt/*.txt"),capture_output=True,text=True).stdout.split()
    ds=[]
    for f in out:
        b=os.path.basename(f)[7:15]; ds.append(b[4:]+"-"+b[2:4]+"-"+b[:2])
    return sorted(ds)
for r in rows:
    o=files_with(r["old_symbol"]); n=files_with(r["new_symbol"])
    print(r["old_symbol"],"->",r["new_symbol"],"| old last:",o[-1] if o else None,"| new first:",n[0] if n else None, "| overlap" if o and n and n[0]<=o[-1] else "")
