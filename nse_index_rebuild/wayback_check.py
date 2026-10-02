import csv, io, json, os, subprocess, time, datetime
from reverse2 import run
FILES = {"NIFTY_50": "ind_nifty50list.csv", "NIFTY_NEXT_50": "ind_niftynext50list.csv", "NIFTY_MIDCAP_150": "ind_niftymidcap150list.csv",
         "NIFTY_SMALLCAP_250": "ind_niftysmallcap250list.csv", "NIFTY_MICROCAP_250": "ind_niftymicrocap250_list.csv"}
TARGETS = ["2019-07-15","2020-02-01","2020-08-01","2021-01-15","2021-07-15","2022-01-15","2022-07-15","2023-01-15","2023-07-15","2024-01-15","2024-07-15","2025-01-15","2025-07-15","2026-01-15"]
al = list(csv.DictReader(open("rules/aliases.csv")))
def canon(sym, date):
    ch = True
    while ch:
        ch = False
        for a in al:
            if sym == a["new_symbol"] and date < a["first_new_date"]: sym = a["old_symbol"]; ch = True
            elif sym == a["old_symbol"] and date >= a["first_new_date"]: sym = a["new_symbol"]; ch = True
    return sym
def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=90).stdout
def api(url, t):
    for wait in (0, 20, 60, 120):
        time.sleep(wait + 3)
        txt = sh(f'curl -sS -m 40 -A "Mozilla/5.0" "https://archive.org/wayback/available?url={url}&timestamp={t.replace("-","")}"')
        try: return json.loads(txt)
        except Exception: continue
    return None
def fetch(ts, fn):
    for wait in (0, 30, 90):
        time.sleep(wait + 3)
        raw = sh(f'curl -sS -m 60 -A "Mozilla/5.0" "https://web.archive.org/web/{ts}id_/https://www.niftyindices.com/IndexConstituent/{fn}"')
        if raw.lstrip().startswith(("Company", "\ufeffCompany")): return raw
    return ""
res, prob = run()
out = []
for k, fn in FILES.items():
    state, snaps = res[k]
    by_date = {}
    for e, f, s in snaps: by_date.setdefault(e, set(s))
    dates = sorted(by_date)
    for t in TARGETS:
        url = f"niftyindices.com/IndexConstituent/{fn}"
        j = api(url, t)
        if j is None: out.append([k, t, "", "", "api_error", "", "", ""]); continue
        c = (j.get("archived_snapshots") or {}).get("closest")
        if not c: out.append([k, t, "", "", "no_snapshot_confirmed", "", "", ""]); continue
        ts = c["timestamp"]; cap = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
        if abs((datetime.date.fromisoformat(cap) - datetime.date.fromisoformat(t)).days) > 120:
            out.append([k, t, ts, cap, "snapshot too far from target", "", "", ""]); continue
        raw = fetch(ts, fn)
        try: wb = {r["Symbol"].strip() for r in csv.DictReader(io.StringIO(raw)) if r.get("Symbol")}
        except Exception: wb = set()
        if len(wb) < 30: out.append([k, t, ts, cap, "fetch_failed_or_unparseable", len(wb), "", ""]); continue
        os.makedirs("reference/wayback", exist_ok=True)
        open(f"reference/wayback/{k}_{ts}.csv", "w").write(raw)
        eff = max((d for d in dates if d <= cap), default=None)
        mine = {canon(s, cap) for s in by_date[eff]} if eff else set()
        theirs = {canon(s, cap) for s in wb}
        # nearest effective dates (within 10 days of capture) make the comparison boundary-sensitive
        near = any(abs((datetime.date.fromisoformat(d) - datetime.date.fromisoformat(cap)).days) <= 10 for d in dates)
        out.append([k, t, ts, cap, "compared", len(theirs), len(mine), f"diff={len(theirs ^ mine)} only_archive={sorted(theirs - mine)[:5]} only_mine={sorted(mine - theirs)[:5]} eff_used={eff} near_boundary={near}"])
        print(out[-1][:4], out[-1][-1][:150], flush=True)
w = csv.writer(open("wayback_results.csv", "w", newline="")); w.writerow(["index","target","timestamp","capture_date","status","archive_size","reconstructed_size","detail"]); w.writerows(out)
