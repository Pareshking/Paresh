"""NSE's four-level classification for every stock the site lists, from Screener.in.

Owner, 24 Nov 2026: get NSE's classification (Macro-economic sector / Sector / Industry /
Basic industry) for all stocks. NSE's index lists carry the Sector level only, and only for
their own members; Screener.in's company page carries all four levels, as NSE writes them,
in its peer-comparison breadcrumb:

    <a href="/market/IN02/" title="Broad Sector">Consumer Discretionary</a>
    <a href="/market/IN02/IN0201/" title="Sector">Automobile and Auto Components</a>
    <a href="/market/IN02/IN0201/IN020102/" title="Broad Industry">Auto Components</a>
    <a href="/market/.../IN020102001/" title="Industry">Auto Components &amp; Equipments</a>

Screener's "Broad Sector" is NSE's macro-economic sector, its "Sector" NSE's sector (the 22
groups in the "Industry" column of NSE's index lists), its "Broad Industry" NSE's industry and
its "Industry" NSE's basic industry.

Who is asked: the Nifty Total Market (750), the Nifty 1000, the > ₹2,000 Cr list
(data/indices/ind_nanocap_list.csv) and every symbol in data/nse_tv_classification.csv.
Writes data/reference/nse_classification.csv (Symbol, Macro, Sector, Industry,
Basic_Industry, Source, Checked), sorted by symbol. Read by the Screener's Sector column on
Nano, Combined and the Nifty 1000 (src/loaders/nse_classification.py).

    python scripts/nse_classification.py                 # missing or older than 90 days
    python scripts/nse_classification.py --limit 900     # the same, at most 900 (the monthly run)
    python scripts/nse_classification.py --all           # every symbol
    python scripts/nse_classification.py --symbols A B   # these only
    python scripts/nse_classification.py --validate      # compare with NSE's own lists, no fetch

A symbol Screener does not know (404) is looked up by company name with Screener's search,
and a hit is taken only when its company id is the one data/screener_company_ids.json holds
for the symbol, or, with no id on file, when its name is the company's name. A symbol found
nowhere gets no row, so the next run asks again. An honest user agent, a pause between
requests, and a backoff on 429 / 5xx; a 403 or a 429 that does not clear stops the run and
keeps what was fetched.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
from datetime import date, timedelta
from urllib.parse import quote

import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "data", "reference", "nse_classification.csv")
COLUMNS = ["Symbol", "Macro", "Sector", "Industry", "Basic_Industry", "Source", "Checked"]
LISTS = {
    "750": os.path.join(ROOT, "data", "indices", "ind_niftytotalmarket_list.csv"),
    "1000": os.path.join(ROOT, "data", "indices", "ind_nifty1000_list.csv"),
    "nano": os.path.join(ROOT, "data", "indices", "ind_nanocap_list.csv"),
}
TV_FILE = os.path.join(ROOT, "data", "nse_tv_classification.csv")
IDS_FILE = os.path.join(ROOT, "data", "screener_company_ids.json")

UA = {"User-Agent": "Mozilla/5.0 (compatible; umiya-classify/1.0)"}
BASE = "https://www.screener.in"
PAGE = BASE + "/company/{}/"
SEARCH = BASE + "/api/company/search/?q={}&v=3"
MAX_AGE_DAYS = 90

# Screener's title attribute -> NSE's level.
LEVELS = {"Broad Sector": "Macro", "Sector": "Sector", "Broad Industry": "Industry", "Industry": "Basic_Industry"}
_LINK = re.compile(r'<a href="/market/[^"]+"[^>]*title="([^"]+)"[^>]*>\s*([^<]+?)\s*</a>')


class Blocked(RuntimeError):
    """Screener asked us to stop (403, or a 429 that did not clear)."""


def parse(page: str) -> dict[str, str] | None:
    """NSE's four levels from a Screener.in company page; None without a Sector."""
    out: dict[str, str] = {}
    for title, name in _LINK.findall(page):
        level = LEVELS.get(html.unescape(title).strip())
        if level and level not in out:
            out[level] = " ".join(html.unescape(name).split())
    if not out.get("Sector"):
        return None
    return {level: out.get(level, "") for level in LEVELS.values()}


# ── Who is asked ─────────────────────────────────────────────────────────────


def universe(lists: dict[str, str] = LISTS, tv_file: str = TV_FILE) -> dict[str, str]:
    """{symbol: company name} for every stock the site lists ("" where no list names it)."""
    names: dict[str, str] = {}
    for path in lists.values():
        if not os.path.exists(path):
            continue
        frame = pd.read_csv(path)
        frame.columns = [str(c).strip() for c in frame.columns]
        for sym, name in zip(frame["Symbol"], frame.get("Company Name", pd.Series("", index=frame.index))):
            sym = str(sym).strip().upper()
            if sym and sym != "NAN" and not names.get(sym):
                names[sym] = "" if pd.isna(name) else str(name).strip()
    if os.path.exists(tv_file):
        for sym in pd.read_csv(tv_file)["Symbol"].astype(str):
            names.setdefault(sym.strip().upper(), "")
    return names


def load(path: str = OUT) -> pd.DataFrame:
    if not os.path.exists(path):
        return pd.DataFrame(columns=COLUMNS)
    return pd.read_csv(path, dtype=str, keep_default_na=False).reindex(columns=COLUMNS, fill_value="")


def due(existing: pd.DataFrame, symbols, today: date, max_age_days: int = MAX_AGE_DAYS,
        everything: bool = False, limit: int = 0) -> list[str]:
    """The symbols to ask, at most `limit` (0: no cap).

    All with `everything`; else those with no row first, then rows older than max_age_days,
    oldest first, so a capped monthly run spreads the refresh over the months.
    """
    symbols = sorted(set(symbols))
    if everything:
        return symbols[:limit] if limit else symbols
    checked = dict(zip(existing["Symbol"], pd.to_datetime(existing["Checked"], errors="coerce")))
    cutoff = pd.Timestamp(today - timedelta(days=max_age_days))
    missing = [s for s in symbols if pd.isna(checked.get(s, pd.NaT))]
    stale = sorted((s for s in symbols if s not in set(missing) and checked[s] < cutoff),
                   key=lambda s: (checked[s], s))
    out = missing + stale
    return out[:limit] if limit else out


def merge(existing: pd.DataFrame, rows: list[dict]) -> pd.DataFrame:
    """Existing rows with `rows` written over them by symbol; sorted, one row per symbol."""
    new = pd.DataFrame(rows, columns=COLUMNS)
    keep = existing[~existing["Symbol"].isin(set(new["Symbol"]))]
    out = pd.concat([keep, new], ignore_index=True) if len(keep) else new
    return out.reindex(columns=COLUMNS).fillna("").sort_values("Symbol").reset_index(drop=True)


def write(frame: pd.DataFrame, path: str = OUT) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    frame.to_csv(tmp, index=False, lineterminator="\n")
    os.replace(tmp, path)


# ── Fetching ─────────────────────────────────────────────────────────────────


def _get(url: str, get, pause: float, tries: int = 4):
    """A response, retried with backoff on 429, 5xx and dropped connections; Blocked on 403 or a 429 that stays."""
    for attempt in range(tries):
        try:
            resp = get(url, timeout=30, headers=UA)
        except requests.RequestException:
            resp = None
        if resp is not None and resp.status_code == 403:
            raise Blocked(f"HTTP 403 on {url}")
        if resp is not None and resp.status_code < 500 and resp.status_code != 429:
            return resp
        if attempt == tries - 1:
            if resp is not None and resp.status_code == 429:
                raise Blocked(f"HTTP 429 on {url} after {tries} tries")
            return resp
        time.sleep(max(pause, 1.0) * 2 ** (attempt + 1))
    return None


def _name_key(name: str) -> str:
    text = re.sub(r"[^a-z0-9]", "", str(name).lower().replace("&", "and"))
    return re.sub(r"(limited|ltd)$", "", text)


def search_text(name: str) -> str:
    """The company name as Screener's search finds it: no "Ltd." / "Limited", no punctuation."""
    text = re.sub(r"[^A-Za-z0-9& ]", " ", str(name))
    text = re.sub(r"\b(limited|ltd)\b\s*$", "", " ".join(text.split()), flags=re.I)
    return text.strip()


def pick_hit(hits: list[dict], company_id: str | None, name: str) -> str | None:
    """The page path of the search hit that is this company, or None when none surely is."""
    for hit in hits or []:
        if company_id and str(hit.get("id")) == str(company_id):
            return hit.get("url")
    if not company_id and name:
        same = [h for h in hits or [] if _name_key(h.get("name", "")) == _name_key(name)]
        if len(same) == 1:
            return same[0].get("url")
    return None


def fetch_one(symbol: str, name: str, ids: dict[str, str], get=requests.get, pause: float = 1.0,
              today: date | None = None) -> dict | None:
    """One stock's row, or None when Screener has no classification for it."""
    url = PAGE.format(quote(symbol, safe=""))
    resp = _get(url, get, pause)
    if resp is not None and resp.status_code == 404:
        path = None
        if name:
            time.sleep(pause)
            found = _get(SEARCH.format(quote(search_text(name))), get, pause)
            try:
                hits = found.json() if found is not None and found.status_code == 200 else []
            except ValueError:
                hits = []
            path = pick_hit(hits if isinstance(hits, list) else [], ids.get(symbol), name)
        if not path and ids.get(symbol):
            # A renamed symbol whose other ticker the id map also holds (an "id twin").
            twins = sorted(s for s, i in ids.items() if i == ids[symbol] and s != symbol)
            path = f"/company/{quote(twins[0], safe='')}/" if twins else None
        if path:
            time.sleep(pause)
            url = BASE + path
            resp = _get(url, get, pause)
    if resp is None or resp.status_code != 200:
        return None
    levels = parse(resp.text)
    if not levels:
        return None
    source = url.replace("https://www.", "").replace("/consolidated/", "/")
    return {"Symbol": symbol, **levels, "Source": source, "Checked": (today or date.today()).isoformat()}


def load_ids(path: str = IDS_FILE) -> dict[str, str]:
    try:
        with open(path, encoding="utf-8") as fh:
            return {str(k): str(v) for k, v in (json.load(fh).get("ids") or {}).items()}
    except (OSError, ValueError, AttributeError):
        return {}


# ── Validation against NSE's own lists ───────────────────────────────────────


def _key(label) -> str:
    return re.sub(r"[^a-z0-9]", "", str(label).lower().replace("&", "and"))


def compare(classification: pd.DataFrame, lists: dict[str, str] | None = None) -> dict[str, dict]:
    """{list: {"checked", "agree", "missing", "mismatches": [(symbol, NSE's list, Screener)]}}."""
    lists = lists or {k: v for k, v in LISTS.items() if k in ("750", "1000")}
    ours = dict(zip(classification["Symbol"], classification["Sector"]))
    out = {}
    for label, path in lists.items():
        frame = pd.read_csv(path)
        frame.columns = [str(c).strip() for c in frame.columns]
        checked = agree = missing = 0
        mismatches = []
        for sym, nse in zip(frame["Symbol"].astype(str).str.strip(), frame["Industry"].astype(str)):
            if sym not in ours:
                missing += 1
                continue
            checked += 1
            if _key(nse) == _key(ours[sym]):
                agree += 1
            else:
                mismatches.append((sym, nse, ours[sym]))
        out[label] = {"checked": checked, "agree": agree, "missing": missing, "mismatches": mismatches}
    return out


def print_comparison(result: dict[str, dict]) -> None:
    for label, r in result.items():
        share = f"{r['agree'] / r['checked']:.1%}" if r["checked"] else "–"
        print(f"{label}: Sector agrees with NSE's list for {r['agree']} of {r['checked']} ({share}); "
              f"{r['missing']} of the list not in the file yet.")
        for sym, nse, ours in r["mismatches"]:
            print(f"  {sym}: NSE's list {nse!r}, Screener {ours!r}")


# ── Run ──────────────────────────────────────────────────────────────────────


def run(symbols: list[str], names: dict[str, str], existing: pd.DataFrame, get=requests.get,
        pause: float = 1.0, today: date | None = None, path: str = OUT, save_every: int = 100,
        ids: dict[str, str] | None = None) -> tuple[pd.DataFrame, int, list[str], bool]:
    """(file, rows found, symbols not found, blocked). Saves every `save_every` stocks, so a stop keeps the work."""
    ids = load_ids() if ids is None else ids
    rows, missed, blocked = [], [], False
    frame = existing
    for i, sym in enumerate(symbols, 1):
        try:
            row = fetch_one(sym, names.get(sym, ""), ids, get=get, pause=pause, today=today)
        except Blocked as exc:
            print(f"::warning::Screener stopped the run at {sym} ({exc}); keeping {len(rows)} fetched.")
            blocked = True
            break
        if row:
            rows.append(row)
        else:
            missed.append(sym)
        if i % save_every == 0:
            frame = merge(existing, rows)
            write(frame, path)
            print(f"{i} of {len(symbols)} asked, {len(rows)} found.", flush=True)
        time.sleep(pause)
    frame = merge(existing, rows)
    write(frame, path)
    return frame, len(rows), missed, blocked


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--all", action="store_true", help="ask about every symbol")
    ap.add_argument("--symbols", nargs="+", help="ask about these symbols only")
    ap.add_argument("--max-age-days", type=int, default=MAX_AGE_DAYS)
    ap.add_argument("--limit", type=int, default=0, help="ask at most this many (missing first, then oldest)")
    ap.add_argument("--pause", type=float, default=1.0)
    ap.add_argument("--validate", action="store_true", help="compare the file with NSE's lists; no fetch")
    args = ap.parse_args(argv)

    existing = load()
    if args.validate:
        print_comparison(compare(existing))
        return 0
    names = universe()
    if args.symbols:
        todo = sorted({s.strip().upper() for s in args.symbols})
    else:
        todo = due(existing, names, date.today(), args.max_age_days, everything=args.all, limit=args.limit)
    print(f"{len(names)} symbols listed, {len(existing)} on file, {len(todo)} to ask.")
    frame, found, missed, blocked = run(todo, names, existing, pause=args.pause)
    print(f"{found} found, {len(missed)} not found; {len(frame)} rows on file.")
    if missed:
        print("Not found: " + ", ".join(missed))
    print_comparison(compare(frame))
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
