import re, glob, os, csv
IDX = {"NIFTY_50": r"(?:s&p\s*)?(?:cnx\s*)?nifty(?:\s*50)?(?:\s+index)?", "NIFTY_NEXT_50": r"(?:cnx\s*)?nifty\s*(?:next\s*50|junior)(?:\s+index)?",
       "NIFTY_MIDCAP_150": r"nifty\s*midcap\s*150(?:\s+index)?", "NIFTY_SMALLCAP_250": r"nifty\s*smallcap\s*250(?:\s+index)?",
       "NIFTY_MICROCAP_250": r"nifty\s*microcap\s*250(?:\s+index)?", "NIFTY_TOTAL_MARKET": r"nifty\s*total\s*market(?:\s+index)?", "NIFTY_500": r"(?:s&p\s*)?(?:cnx|nifty)\s*500(?:\s+index)?"}
HEAD = re.compile(r"^\s*(?:\(?\d+[\).]|[A-Za-z][\).])?\s*((?:s&p\s*)?(?:cnx|nifty)[^\n()]{0,60}?)\s*(?:indices|index)?\s*:?\s*$", re.I)
_ROW_STRICT = re.compile(r"^\s*(\d+)\s+(.+?)\s{2,}([A-Z0-9&\-_]+)\s*$")
_ROW_RELAXED = re.compile(r"^\s*(\d+)\s+(.*[a-z].*?)\s+([A-Z][A-Z0-9&\-_]{1,19})\s*$")
class _Row:
    def match(self, line):
        return _ROW_STRICT.match(line) or _ROW_RELAXED.match(line)
ROW = _Row()
_ROW_DATED = re.compile(r"^\s*(\d+)\s+(.+?)\s{2,}([A-Z0-9&\-_]+)\s{2,}([A-Z][a-z]+)\s+(\d{1,2}),\s*(\d{4})\s*$")  # a table with an Effective Date column
MON = "January February March April May June July August September October November December".split()
_EFF = re.compile(r"(?:effective(?:\s+from)?|with effect from|w\.e\.f\.?)\s+([A-Z][a-z]+)\s*(\d{1,2})[,\s]*(?:\d{1,2}[,\s]+)?(\d{4})")
def _dates(t):
    """[(score, position, iso date)] for every date phrase in t; score 2 when the sentence it sits in makes an index change."""
    out = []
    for m in _EFF.finditer(t):
        if m.group(1) not in MON:
            continue
        before = t[max(0, m.start() - 160):m.start()]
        sentence = re.split(r"[.]\s", before)[-1]
        score = 2 if re.search(r"index|indices|replace|change|become|shall|decided", sentence, re.I) and not re.search(r"suspend|ex-date|ex date|trading|revok|null and void|cancel", sentence, re.I) else 0
        out.append((score, m.start(), f"{m.group(3)}-{MON.index(m.group(1))+1:02d}-{int(m.group(2)):02d}"))
    return out
def bind_dates(t):
    """{index: date} from the intro clauses of a notice: each date is bound to the indices named in the clause that
    ends with it ("The changes in CNX 200, CNX 500 ... shall be effective from February 2, 2015 and change in Nifty Midcap 50
    ... February 23, 2015"). Only text before the first include/exclude list is used."""
    cut = re.search(r"being\s+(?:in|ex)cluded|are\s+(?:in|ex)cluded|Sr\.?\s*No", t, re.I)
    intro = t[:cut.start()] if cut else t
    out, prev, last = {}, 0, ""
    for score, pos, day in sorted(_dates(intro), key=lambda d: d[1]):
        if score == 0:
            continue
        last = day
        end = next((m.end() for m in _EFF.finditer(intro) if m.start() == pos), pos)
        seg = intro[prev:end]
        for k, pat in SEARCH.items():
            if re.search(pat, seg, re.I):
                out.setdefault(k, day)
        prev = end
    out["_last"] = last  # the change date nearest the lists: governs an index no clause names
    return out
def eff(t):
    """The effective date of the index change. A notice can carry other dates (a trading suspension, an ex-date), so
    prefer a date in the sentence that makes the index change ('... changes ... will become effective from ...'), and
    fall back to the first date only when no sentence says so."""
    best = None
    for m in _EFF.finditer(t):
        if m.group(1) not in MON:
            continue
        before = t[max(0, m.start() - 160):m.start()]
        sentence = re.split(r"[.]\s", before)[-1]  # the sentence this date sits in
        score = 2 if re.search(r"index|indices|replace|change|become|shall|decided", sentence, re.I) and not re.search(r"suspend|ex-date|ex date|trading|revok|null and void|cancel", sentence, re.I) else 0
        cand = (score, -m.start(), f"{m.group(3)}-{MON.index(m.group(1))+1:02d}-{int(m.group(2)):02d}")
        if best is None or cand > best:
            best = cand
    return best[2] if best else ""
def idx_of(h):
    h = re.sub(r"\s+", " ", h.strip().lower())
    for k, p in IDX.items():
        if re.fullmatch(p, h): return k
    return None
def norm_name(n):
    n = n.lower().replace("&", " and ")
    n = re.sub(r"\b(ltd|limited|india|the|company|co|corporation|corp|industries|enterprises|inc)\b", " ", n)
    return re.sub(r"[^a-z0-9]+", " ", n).strip()
NAME2SYM = {}
for _f in sorted(glob.glob("announcements/txt/*.txt")):
    for _l in open(_f, errors="ignore").read().split("About NSE Indices")[0].splitlines():
        _m = ROW.match(_l)
        if _m: NAME2SYM[norm_name(_m.group(2))] = _m.group(3)
MANUAL_NAMES = {"sesa goa": "SESAGOA", "core projects and technologies": "COREPROTEC", "orissa mineral development": "ORISSAMINE", "pipavav shipyard": "PIPAVAVYD", "jindal southwest hold": "JINDALSWHL"}  # name-only 2010 tables; symbol from NSE symbol-change file (SESAGOA -> SSLT -> VEDL)
NAME2SYM.update(MANUAL_NAMES)
for _r in csv.DictReader(open("rules/name_symbol_map.csv")): NAME2SYM[norm_name(_r["name"])] = _r["symbol"]  # name-only tables; evidence per row
ROWN = re.compile(r"^\s*(\d+)\s+([A-Za-z].+?)\s*$")
NOSYM_HDR = re.compile(r"Sr\.?\s*No\.?\s+(?:Company|Scrip)\s+Name\s*$", re.I)
PAREN = re.compile(r"^\s*\(?\d{1,2}\)\s+[A-Za-z]")
SEC = re.compile(r"^\s*[A-Z]\.\s+\S")
SEARCH = {"NIFTY_50": r"(?:cnx\s*)?nifty\s*50\b(?!\s*(?:value|equal|shariah|alpha|low|high|arbitrage|\d))|s&p\s*cnx\s*nifty\s*index", "NIFTY_NEXT_50": r"nifty\s*(?:next\s*50\b(?!\s*equal)|junior)",
          "NIFTY_MIDCAP_150": r"nifty\s*midcap\s*150\b(?!\s*(?:quality|momentum))", "NIFTY_SMALLCAP_250": r"nifty\s*smallcap\s*250\b(?!\s*(?:quality|momentum))",
          "NIFTY_MICROCAP_250": r"nifty\s*microcap\s*250\b", "NIFTY_TOTAL_MARKET": r"nifty\s*total\s*market\b", "NIFTY_500": r"(?:cnx|nifty)\s*500\b(?!\s*(?:multicap|equal|shariah|ahimsa|value|low|quality|flexicap|largemidsmall))"}
def idx_in_heading(t):
    hits = [k for k, p in SEARCH.items() if re.search(p, t, re.I)]
    return hits[0] if len(hits) == 1 else None
out = []
for f in sorted(glob.glob("announcements/txt/*.txt")):
    base = os.path.basename(f)[:-4]; raw = open(f, errors="ignore").read()
    raw = re.split(r"About NSE Indices", raw)[0]
    m = re.match(r"ind_prs(\d{2})(\d{2})(\d{4})", base); pub = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    if pub < "2010-01-01": continue
    e0 = eff(re.sub(r"\s+", " ", raw)); bound = bind_dates(re.sub(r"\s+", " ", raw)); sec = None; seen_table = False; cur = None; mode = None; nosym = False
    lines = [l for l in raw.splitlines() if l.strip()]
    _merged = []
    for _l in lines:
        if _merged and re.match(r"^\s+[A-Za-z][^\n]*?\s{2,}[A-Z][A-Z0-9&\-_]+\s*$", _l) and re.match(r"^\s*\d+\s+[A-Za-z][^\n]*$", _merged[-1]) and not ROW.match(_merged[-1]):
            _merged[-1] = _merged[-1].rstrip() + " " + _l.strip()
        else:
            _merged.append(_l)
    lines = _merged
    has_headings = any(HEAD.match(_l) or PAREN.match(_l) or SEC.match(_l) for _l in lines)
    PFX = re.compile(r"^\s*\(?[0-9A-Za-z]{1,3}[\).]\s+\S")
    for i, line in enumerate(lines):
        s = line.strip()
        if not ROW.match(line) and not NOSYM_HDR.search(s):
            # a prose line that states the change date sets the date for the tables that follow (notices can carry several)
            _win = re.sub(r"\s+", " ", " ".join(lines[i:i + 2]))
            _hits = [d for d in _dates(_win) if d[0] > 0 and d[1] < len(re.sub(r"\s+", " ", line)) + 1]
            if _hits and seen_table:
                sec = _hits[0][2]
        if NOSYM_HDR.search(s): nosym = True; continue
        if re.search(r"Sr\.?\s*No\.?.*Symbol", s, re.I): nosym = False; continue
        if cur is None and not has_headings and i < 25 and re.search(r"being (?:in|ex)cluded|are (?:in|ex)cluded|is (?:in|ex)cluded", s, re.I) and not ROW.match(line):
            _ctx = " ".join(lines[max(0, i - 8):i])
            cur = idx_in_heading(_ctx)
        if re.search(r"being included|are included|is included|to be included", s, re.I) and not ROW.match(line): mode = "IN"; seen_table = True; continue
        if re.search(r"being excluded|are excluded|is excluded|to be excluded", s, re.I) and not ROW.match(line): mode = "OUT"; seen_table = True; continue
        h = HEAD.match(line)
        if PAREN.match(line) and not h and not ROW.match(line):
            cur, mode = None, None
            continue
        if SEC.match(line) and not ROW.match(line) and not h:
            cur, mode = idx_in_heading(line), None
            continue
        if h and not ROW.match(line):
            nxt = lines[i+1] if i+1 < len(lines) else ""
            ok = bool(PFX.match(line)) or bool(re.search(r"following|being (in|ex)cluded|replace", nxt, re.I))
            if ok:
                cur, mode = idx_of(h.group(1)), None
            continue
        dm = _ROW_DATED.match(line)
        if dm and cur and mode and dm.group(4) in ("January February March April May June July August September October November December".split()):
            day = f"{dm.group(6)}-{('January February March April May June July August September October November December'.split()).index(dm.group(4)) + 1:02d}-{int(dm.group(5)):02d}"
            out.append([pub, day, base, cur, mode, dm.group(3), dm.group(2).strip()])
            continue
        r = ROW.match(line)
        if r and cur and mode:
            out.append([pub, sec or bound.get(cur) or bound.get("_last") or e0, base, cur, mode, r.group(3), r.group(2).strip()])
        elif nosym and cur and mode:
            rn = ROWN.match(line)
            if rn and not re.search(r"page|iisl", rn.group(2), re.I):
                nm = rn.group(2).strip(); out.append([pub, sec or bound.get(cur) or bound.get("_last") or e0, base, cur, mode, NAME2SYM.get(norm_name(nm), "UNMAPPED:" + nm), nm])
with open("events_raw.csv", "w", newline="") as o:
    w = csv.writer(o); w.writerow(["published","effective","file","index","action","symbol","company"]); w.writerows(out)
from collections import Counter
print(len(out), "event rows"); print(sorted(Counter((r[0][:4], r[3]) for r in out).items()))
print("missing effective:", len({r[2] for r in out if not r[1]}), "files")
