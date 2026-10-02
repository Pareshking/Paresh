"""Check data/membership_history.json against the reconstruction, end of day, at every effective date.

Fails on any difference. This is the guard against the class of bug where a change lands on the wrong date
(membership right at the baseline, wrong between a change's real date and the baseline). Run by the reconstruct CI job.
"""
import json, os, sys
import reverse2, export_pit

KEY = {"NIFTY_50": "nifty_50", "NIFTY_NEXT_50": "nifty_next_50", "NIFTY_MIDCAP_150": "nifty_midcap_150",
       "NIFTY_SMALLCAP_250": "nifty_smallcap_250", "NIFTY_MICROCAP_250": "nifty_microcap_250",
       "NIFTY_TOTAL_MARKET": "nifty_total_market", "NIFTY_500": "nifty_500"}
PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "membership_history.json")

def main():
    res, problems = reverse2.run()
    if problems: sys.exit("unresolved chain problems")
    hist = json.load(open(PATH))
    bad = checked = 0
    for idx, (_, snaps) in res.items():
        ix = hist["indices"][KEY[idx]]
        dates = [c["date"] for c in ix["changes"]]
        if dates != sorted(dates): sys.exit(f"{idx}: changes not in date order")
        named = set(ix["baseline"]["symbols"])
        for c in ix["changes"]: named |= set(c["added"]) | set(c["removed"])
        keep_old = {o for o in export_pit.aliases if o in named}  # tickers the file records under their old name
        def cur(s):
            seen = set()
            while s in export_pit.aliases and s not in seen and s not in keep_old:
                seen.add(s); s = export_pit.aliases[s]["new_symbol"]
            return s
        eod = {}
        for dt, _f, m in sorted(reversed(snaps), key=lambda x: x[0]): eod[dt] = m
        for dt, m in sorted(eod.items()):
            if dt < ix["baseline"]["date"]: continue
            state = set(ix["baseline"]["symbols"])
            for c in ix["changes"]:
                if c["date"] <= dt: state = (state - set(c["removed"])) | set(c["added"])
            checked += 1
            want = {cur(s) for s in m}
            if state != want:
                bad += 1; print(f"MISMATCH {idx} {dt}: {sorted(state ^ want)[:6]}")
    print(f"{checked} end-of-day states checked, {bad} mismatches")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
