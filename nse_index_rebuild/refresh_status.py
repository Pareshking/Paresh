import csv, json, re
from reverse2 import run
res, prob = run()
with open("open_issues.csv", "w", newline="") as o:
    w = csv.writer(o); w.writerow(["index","effective_date","announcement","in_but_not_in_state","out_but_still_in_state","size_after_undo","status"])
    for p in sorted(prob, key=lambda p: (p[0], p[1]), reverse=True): w.writerow([p[0], p[1], p[2], ";".join(p[3]), ";".join(p[4]), p[5], "OPEN"])
import subprocess; subprocess.run(["python3", "gate_check.py"], capture_output=True)
g = json.load(open("gate_status.json"))
names = {"NIFTY_50":"Nifty 50","NIFTY_NEXT_50":"Nifty Next 50","NIFTY_MIDCAP_150":"Nifty Midcap 150","NIFTY_SMALLCAP_250":"Nifty Smallcap 250","NIFTY_MICROCAP_250":"Nifty Microcap 250","NIFTY_500":"Nifty 500"}
rows = "\n".join(f"| {names[k]} | {v['snapshots']} | {v['snapshots_wrong_size']} | {v['chain_breaks']} | {v['latest_chain_break'] or 'none'} |" for k, v in g.items())
n = len(list(csv.DictReader(open("rules/aliases.csv"))))
p = open("PROTOCOL.md").read()
p = re.sub(r"(\| Index \| Snapshots reconstructed.*?\|---\|---\|---\|---\|---\|\n).*?\n\n", lambda m: m.group(1) + rows + "\n\n", p, flags=re.S)
p = re.sub(r"- The \d+ symbol changes in `rules/aliases.csv`", f"- The {n} symbol changes in `rules/aliases.csv`", p)
open("PROTOCOL.md", "w").write(p); print(rows)
