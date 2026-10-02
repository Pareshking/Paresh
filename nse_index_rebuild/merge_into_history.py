"""Merge the reconstructed history into ../data/membership_history.json.

Every index gets baseline = its earliest reconstructed state and one change per effective
date up to today. Where the file already holds a history (Total Market from 2025-12-31, the
other five from 2026-09-29) the existing baseline and changes are kept untouched and the
reconstruction is prepended, after checking that it lands exactly on that existing baseline.
Nifty 500 is a new index entry. Symbols use today's ticker (rules/aliases.csv), except a
rename the file already records as an explicit change (HEG -> HEGAM).
The flat top-level baseline/changes (Total Market) stay identical to indices.nifty_total_market.
Unproven rows are listed under the top-level "caveats" key.
"""
import csv, json, os, sys
import reverse2
import export_pit

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "membership_history.json")
KEY = {"NIFTY_50": "nifty_50", "NIFTY_NEXT_50": "nifty_next_50", "NIFTY_MIDCAP_150": "nifty_midcap_150",
       "NIFTY_SMALLCAP_250": "nifty_smallcap_250", "NIFTY_MICROCAP_250": "nifty_microcap_250",
       "NIFTY_TOTAL_MARKET": "nifty_total_market", "NIFTY_500": "nifty_500"}
TITLE = {"nifty_500": "NIFTY 500"}

def main(write=True):
    base = next((a.split("=",1)[1] for a in sys.argv if a.startswith("--base=")), PATH)
    hist = json.load(open(base))  # pass --base=<pre-merge file> to regenerate from the original history
    res, problems = reverse2.run()
    if problems: sys.exit("unresolved chain problems; refusing to merge")
    explicit = {}  # per index: old tickers the file already uses, kept as they are so the junction matches
    for key, ix in hist["indices"].items():
        named = set(ix["baseline"]["symbols"])
        for c in ix["changes"]: named |= set(c["added"]) | set(c["removed"])
        explicit[key] = {o for o in export_pit.aliases if o in named}
    def cur(s, key):
        out = s
        seen = set()
        while out in export_pit.aliases and out not in seen and out not in explicit.get(key, ()):
            seen.add(out); out = export_pit.aliases[out]["new_symbol"]
        return out
    report = {}
    for idx, (initial, snaps, timeline) in export_all(res).items():
        key = KEY[idx]
        states = [(d, {cur(s, key) for s in m}, f) for d, m, f in timeline]
        old = hist["indices"].get(key)
        if old:
            bdate = old["baseline"]["date"]
            states = [x for x in states if x[0] <= bdate]
            if not states or states[-1][1] != set(old["baseline"]["symbols"]):
                diff = sorted(states[-1][1] ^ set(old["baseline"]["symbols"])) if states else "no overlap"
                sys.exit(f"{key}: reconstruction does not land on the existing baseline {bdate}: {diff}")
            states[-1] = (bdate, states[-1][1], states[-1][2])
        base_d, base, _ = states[0]
        changes = []
        for (d0, s0, _f0), (d1, s1, f1) in zip(states, states[1:]):
            added, removed = sorted(s1 - s0), sorted(s0 - s1)
            if added or removed: changes.append({"date": d1, "added": added, "removed": removed, "notice": f1 + ".pdf"})
        if old:
            # the junction date may carry a change of its own; the existing baseline is the state after it
            new = {"baseline": {"date": base_d, "symbols": sorted(base)}, "changes": changes + old["changes"]}
        else:
            new = {"baseline": {"date": base_d, "symbols": sorted(base)}, "changes": changes}
        hist["indices"][key] = new
        report[key] = (base_d, len(base), len(new["changes"]))
    tm = hist["indices"]["nifty_total_market"]
    hist["baseline"], hist["changes"] = tm["baseline"], tm["changes"]
    if hist.get("index") is None: hist["index"] = "NIFTY TOTAL MARKET"
    rows = list(csv.DictReader(open(export_pit.OUT)))
    hist["caveats"] = {"note": "Reconstruction from NSE press releases; these intervals rest on open items. See docs/INDEX_MEMBERSHIP_PIT.md.",
                       "intervals": [{"index": KEY[r["index"]], "symbol": r["current_symbol"], "from": r["from_date"],
                                      "to": r["to_date"] or None, "caveat": r["caveat"]} for r in rows if r["caveat"]]}
    named = set()
    for ix in hist["indices"].values():
        named |= set(ix["baseline"]["symbols"])
        for c in ix["changes"]: named |= set(c["added"]) | set(c["removed"])
    companies = {}
    for r in csv.reader(open("reference/nse_symbolchange.csv")):
        if len(r) >= 4: companies[(r[1].strip().upper(), r[2].strip().upper())] = r[0].strip()
    changes_ledger = []
    for old, a in sorted(export_pit.aliases.items(), key=lambda kv: kv[1]["first_new_date"]):
        changes_ledger.append({"old_symbol": old, "new_symbol": a["new_symbol"], "company": companies.get((old, a["new_symbol"])),
                               "last_old_date": a["last_old_date"], "first_new_date": a["first_new_date"], "status": a["status"],
                               "evidence": a["evidence"]})
    hist["symbol_changes"] = {"note": "Ticker/name changes found while rebuilding 2010-to-date. A rename is never an index entry or exit; "
                              "membership above uses today's ticker except the old names listed under 'aliases'.", "changes": changes_ledger}
    # `aliases` is left as the repo had it: the price stores are keyed by the tickers they were built with, and a
    # new alias there silently unprices a name (GUJGASLTD -> GUJENERGY did). Full renames live in symbol_changes.
    hist["adjustments_applied"] = {"note": "Hand-made rules that corrected or completed the parsed NSE notices (revocations, deferments, manual events). Each cites its document.",
                                   "rules": [{k: r[k] for k in ("kind", "file", "index", "action", "symbol", "evidence")} for r in csv.DictReader(open("rules/overrides.csv"))]}
    for k, v in report.items(): print(k, v)
    if write:
        with open(PATH, "w") as fh: json.dump(hist, fh, indent=2); fh.write("\n")

def export_all(res):
    out = {}
    for idx, (initial, snaps) in res.items():
        timeline = []
        if export_pit.START[idx]: timeline.append((export_pit.START[idx], set(initial), "initial"))
        for d, f, m in sorted(reversed(snaps), key=lambda x: x[0]): timeline.append((d, set(m), f))
        eod = {}
        for t in timeline: eod[t[0]] = t
        out[idx] = (initial, snaps, sorted(eod.values(), key=lambda t: t[0]))
    return out

if __name__ == "__main__":
    main(write="--dry-run" not in sys.argv)
