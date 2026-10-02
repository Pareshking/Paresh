import csv, datetime, re
def nm(n):
    n = n.lower().replace("&", " and ")
    n = re.sub(r"\b(ltd|limited|india|the|company|co|corporation|corp|industries|enterprises|inc)\b", " ", n)
    return re.sub(r"[^a-z0-9]+", " ", n).strip().split()
ev = list(csv.DictReader(open("events_raw.csv")))
company = {}
for e in ev: company.setdefault(e["symbol"], e["company"])
have = {(a["old_symbol"], a["new_symbol"]) for a in csv.DictReader(open("rules/aliases.csv"))}
rows = []
for l in csv.reader(open("reference/nse_symbolchange.csv")):
    if len(l) >= 4:
        d = datetime.datetime.strptime(l[3].strip().title(), "%d-%b-%Y").date()
        rows.append((l[0].strip(), l[1].strip(), l[2].strip(), d))
new = []
for name, old, nw, d in rows:
    if old in company and (old, nw) not in have and d >= datetime.date(2009, 1, 1):
        a, b = nm(company[old]), nm(name)
        if a and b and (a[0] == b[0] or set(a) & set(b)):
            new.append((old, nw, d, name, company[old]))
print(len(new), "candidate aliases")
for x in new: print(x[0], "->", x[1], x[2], "|", x[3][:35], "|", x[4][:30])
w = csv.writer(open("rules/aliases.csv", "a", newline=""))
for old, nw, d, name, c in new:
    w.writerow([old, nw, (d - datetime.timedelta(days=1)).isoformat(), d.isoformat(),
                f"NSE 'Changes in Symbols' file (reference/nse_symbolchange.csv; sha256 948ccc56...): {name}, {old} -> {nw}, effective {d.isoformat()}; added by name-match against announcement company '{c}'", "CONFIRMED_NSE_SYMBOLCHANGE_FILE"])
