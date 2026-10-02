import csv, json
from reverse2 import run, INDS, cur
EXP = {"NIFTY_50":50,"NIFTY_NEXT_50":50,"NIFTY_MIDCAP_150":150,"NIFTY_SMALLCAP_250":250,"NIFTY_MICROCAP_250":250}
res, prob = run()
al = list(csv.DictReader(open("rules/aliases.csv"))); ov = list(csv.DictReader(open("rules/overrides.csv")))
out = {}
for k in [i for i in INDS if i in EXP]:
    state, snaps_all = res[k]
    seen = set(); snaps = []
    for e, f, s_ in snaps_all:
        if e not in seen: seen.add(e); snaps.append((e, f, s_))
    dummies = sum(1 for s in cur[k] if s.startswith("DUMMY"))
    exp = EXP[k] + dummies
    bad_sizes = [(e, f, len(s_)) for e, f, s_ in snaps if len(s_) != exp + sum(1 for x in s_ if x.endswith('DVR'))]
    first_bad = max((e for e, f, n in bad_sizes), default=None)
    chain_breaks = [p for p in prob if p[0] == k]
    first_break = max((p[1] for p in chain_breaks), default=None)
    clean_from = first_break  # reconstructions strictly after this date have passed every check
    out[k] = {"expected_size_incl_dummies": exp, "snapshots": len(snaps), "snapshots_wrong_size": len(bad_sizes),
              "chain_breaks": len(chain_breaks), "latest_chain_break": first_break,
              "oldest_snapshot": snaps[-1][0] if snaps else None}
print(json.dumps(out, indent=1))
print("aliases:", len(al), "all inferred:", all(a["status"].startswith("INFERRED") for a in al), "| manual overrides:", len(ov))
json.dump(out, open("gate_status.json", "w"), indent=1)
