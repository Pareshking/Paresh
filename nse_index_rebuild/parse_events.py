import re, glob, os, csv
IDX = {"NIFTY_50": r"nifty\s*50(?:\s+index)?", "NIFTY_NEXT_50": r"nifty\s*next\s*50(?:\s+index)?",
       "NIFTY_MIDCAP_150": r"nifty\s*midcap\s*150(?:\s+index)?", "NIFTY_SMALLCAP_250": r"nifty\s*smallcap\s*250(?:\s+index)?",
       "NIFTY_MICROCAP_250": r"nifty\s*microcap\s*250(?:\s+index)?"}
HEAD = re.compile(r"^\s*(?:\(?\d+[\).]|[A-Za-z][\).])?\s*(nifty[^\n]{0,60}?)\s*(?:indices|index)?\s*:?\s*$", re.I)
ROW = re.compile(r"^\s*(\d+)\s+(.+?)\s{2,}([A-Z0-9&\-_]+)\s*$")
MON = "January February March April May June July August September October November December".split()
def eff(t):
    m = re.search(r"(?:effective from|with effect from|w\.e\.f\.?)\s+([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})", t)
    return f"{m.group(3)}-{MON.index(m.group(1))+1:02d}-{int(m.group(2)):02d}" if m and m.group(1) in MON else ""
def idx_of(h):
    h = re.sub(r"\s+", " ", h.strip().lower())
    for k, p in IDX.items():
        if re.fullmatch(p, h): return k
    return None
out = []
for f in sorted(glob.glob("announcements/txt/*.txt")):
    base = os.path.basename(f)[:-4]; raw = open(f, errors="ignore").read()
    raw = re.split(r"About NSE Indices", raw)[0]
    m = re.match(r"ind_prs(\d{2})(\d{2})(\d{4})", base); pub = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    if pub < "2019-01-01": continue
    e = eff(re.sub(r"\s+", " ", raw)); cur = None; mode = None
    lines = [l for l in raw.splitlines() if l.strip()]
    PFX = re.compile(r"^\s*\(?[0-9A-Za-z]{1,3}[\).]\s+\S")
    for i, line in enumerate(lines):
        s = line.strip()
        if re.search(r"being included|are included|is included|to be included", s, re.I) and not ROW.match(line): mode = "IN"; continue
        if re.search(r"being excluded|are excluded|is excluded|to be excluded", s, re.I) and not ROW.match(line): mode = "OUT"; continue
        h = HEAD.match(line)
        if h and not ROW.match(line):
            nxt = lines[i+1] if i+1 < len(lines) else ""
            ok = bool(PFX.match(line)) or bool(re.search(r"following|being (in|ex)cluded|replace", nxt, re.I))
            if ok:
                cur, mode = idx_of(h.group(1)), None
            continue
        r = ROW.match(line)
        if r and cur and mode:
            out.append([pub, e, base, cur, mode, r.group(3), r.group(2).strip()])
with open("events_raw.csv", "w", newline="") as o:
    w = csv.writer(o); w.writerow(["published","effective","file","index","action","symbol","company"]); w.writerows(out)
from collections import Counter
print(len(out), "event rows"); print(sorted(Counter((r[0][:4], r[3]) for r in out).items()))
print("missing effective:", len({r[2] for r in out if not r[1]}), "files")
