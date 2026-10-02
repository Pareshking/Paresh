"""Export every reconstructed index into ONE point-in-time CSV for backtests.

Output: pit_export.csv (intermediate, git-ignored; merge_into_history.py folds it into data/membership_history.json)  (one row per index/symbol membership interval)
  index, symbol, current_symbol, from_date, to_date, caveat
from_date = first day the symbol is a member; to_date = last day (blank = member today).
Membership on day d: from_date <= d and (to_date == "" or d <= to_date).
`caveat` is blank for rows with no open item; otherwise ';'-joined codes (see docs).
Verifies the export by replaying it against every reconstructed snapshot and against today's lists.
"""
import csv, datetime as dt, os, sys
import reverse2

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pit_export.csv")
# Coverage start per index. None = start at the first reconstructed snapshot (launch state not documented).
START = {"NIFTY_50": "2010-01-01", "NIFTY_NEXT_50": "2010-01-01", "NIFTY_500": "2010-01-01",
         "NIFTY_MIDCAP_150": "2016-04-01", "NIFTY_SMALLCAP_250": "2016-04-01",
         "NIFTY_MICROCAP_250": None, "NIFTY_TOTAL_MARKET": None}
aliases = {r["old_symbol"]: r for r in csv.DictReader(open("rules/aliases.csv"))}
web_symbols = {r["symbol"] for r in csv.DictReader(open("rules/name_symbol_map.csv")) if r["status"] == "WEB_SECONDARY"}

def current_symbol(s):
    seen = set()
    while s in aliases and s not in seen:
        seen.add(s); s = aliases[s]["new_symbol"]
    return s

def caveats(index, sym, a, b):
    """a, b = from_date, to_date ('' = open). Return caveat codes touching this interval."""
    out = []
    if sym.startswith("UNMAPPED:"): out.append("UNMAPPED_NAME_ONLY_NOTICE")
    if sym in web_symbols: out.append("SYMBOL_WEB_SECONDARY")
    if sym in aliases and aliases[sym]["status"] not in ("CONFIRMED_NSE_CIRCULAR", "CONFIRMED_NSE_CLEARING_CIRCULAR",
            "CONFIRMED_NSE_CIRCULAR_BROKER_COPY", "CONFIRMED_NSE_SYMBOLCHANGE_FILE"):
        out.append("ALIAS_" + aliases[sym]["status"])
    return ";".join(sorted(set(out)))

def day_before(d):
    return (dt.date.fromisoformat(d) - dt.timedelta(days=1)).isoformat()

def main():
    res, problems = reverse2.run(verbose=False) if "verbose" in reverse2.run.__code__.co_varnames else reverse2.run()
    if problems: sys.exit(f"refusing to export: {len(problems)} unresolved chain problems")
    rows = []
    for idx, (initial, snaps) in res.items():
        timeline = []  # (from_date, set) oldest first
        if START[idx]: timeline.append((START[idx], set(initial), "initial"))
        # snaps are newest-first; several can share an effective date, and the last one processed is the end-of-date state.
        for d, f, m in sorted(reversed(snaps), key=lambda x: x[0]): timeline.append((d, set(m), f))
        eod = {}
        for t in timeline: eod[t[0]] = t  # later entry for the same date wins
        timeline = sorted(eod.values(), key=lambda t: t[0])
        open_ = {}
        for i, (d, members, _) in enumerate(timeline):
            for s in list(open_):
                if s not in members:
                    rows.append((idx, s, open_.pop(s), day_before(d)))
            for s in members:
                open_.setdefault(s, d)
        for s, a in open_.items(): rows.append((idx, s, a, ""))
        res[idx] = (initial, snaps, timeline)
    out = [(i, s, current_symbol(s), a, b, caveats(i, s, a, b)) for i, s, a, b in rows]
    out.sort(key=lambda r: (r[0], r[3], r[1]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["index", "symbol", "current_symbol", "from_date", "to_date", "caveat"]); w.writerows(out)
    verify(out, res)
    print(f"wrote {len(out)} rows -> {os.path.normpath(OUT)}")

def members_on(rows, idx, d):
    return {r[1] for r in rows if r[0] == idx and r[3] <= d and (not r[4] or d <= r[4])}

def verify(rows, res):
    n = 0
    for idx, (initial, snaps, timeline) in res.items():
        for d, members, _ in timeline:
            got = members_on(rows, idx, d)
            if got != members: sys.exit(f"replay mismatch {idx} {d}: {sorted(got ^ members)[:5]}")
            n += 1
        if members_on(rows, idx, dt.date.today().isoformat()) != reverse2.cur[idx]:
            sys.exit(f"{idx}: export does not equal today's NSE list")
    print(f"verified {n} snapshots + today's lists")

if __name__ == "__main__":
    main()
