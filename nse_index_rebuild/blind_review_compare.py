"""Compare an independent reviewer's events with the parser's, for the notices in reference/blind_review/.

    python blind_review_compare.py            # exits 1 on any difference

The reviewer worked only from the notice texts listed in sample_files.txt (no access to events_raw.csv, the history or the
rules) and wrote reviewer_events.csv: file,index,action,symbol,effective.
"""
import collections, csv, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(HERE, "reference", "blind_review")
INDICES = {"NIFTY_MIDCAP_150", "NIFTY_SMALLCAP_250", "NIFTY_MICROCAP_250", "NIFTY_TOTAL_MARKET"}


def key(r):
    return (r["file"], r["index"], r["action"], r["symbol"], r["effective"])


def main():
    rev = list(csv.DictReader(open(os.path.join(DIR, "reviewer_events.csv"))))
    files = {r["file"] for r in rev}
    mine = [r for r in csv.DictReader(open(os.path.join(HERE, "events_raw.csv"))) if r["file"] in files and r["index"] in INDICES]
    R, M = collections.Counter(map(key, rev)), collections.Counter(map(key, mine))
    only_rev, only_mine = R - M, M - R
    print(f"{len(files)} notices, reviewer {len(rev)} events, parser {len(mine)} events, identical {sum((R & M).values())}")
    for k in sorted(only_rev):
        print("ONLY REVIEWER", k)
    for k in sorted(only_mine):
        print("ONLY PARSER", k)
    return 1 if only_rev or only_mine else 0


if __name__ == "__main__":
    sys.exit(main())
