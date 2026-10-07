"""BSE's daily bhavcopy, 2008 to today, as one table.

BSE is the second exchange for the same stocks, so it can say whether a day
NSE has no row for was a day the stock did not trade at all or only a day NSE
did not publish it (scripts/audit_gaps_against_bse.py).

    python scripts/bse_bhavcopy.py --mode download --out data_cache/bse_raw
    python scripts/bse_bhavcopy.py --mode build --raw data_cache/bse_raw --out data_cache/bse_daily.parquet

Two file formats, both public, both need a browser-like User-Agent and the
BhavCopy page as Referer (without them BSE answers with an HTML page):

  EQ<DDMMYY>_CSV.ZIP                              2008-01-01 to 2024-07-05
  BhavCopy_BSE_CM_0_0_0_<YYYYMMDD>_F_0000.CSV     2024-07-05 onward (UDiFF)

An HTML answer means the day has no file in that format. 20 sessions between
June 2008 and January 2010 have none in either (NSE traded normally on all of
them); the audit treats them as unknown, not as "BSE closed". The old format
carries no ISIN (the UDiFF one does, from 2024); the BSE scrip code (SC_CODE,
FinInstrmId) is the key that is stable throughout.

Columns of the table: date, code, name, group, open, high, low, close,
prev_close, trades, shares, value (rupees), isin (2024 onward only).
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import glob
import os
import subprocess
import time
import zipfile

import pandas as pd

HEADERS = ["-A", "Mozilla/5.0", "-e", "https://www.bseindia.com/markets/MarketInfo/BhavCopy.aspx"]
BASE = "https://www.bseindia.com/download/BhavCopy/Equity/"
LAST_LEGACY_DAY = pd.Timestamp("2024-07-05")


def _get(url: str, dest: str) -> bool | None:
    """True: saved. False: BSE has no file for the day. None: the request failed."""
    for attempt in range(3):
        r = subprocess.run(["curl", "-sS", "-m", "90", *HEADERS, "-o", dest + ".tmp", "-w", "%{http_code}", url],
                           capture_output=True, text=True)
        if r.stdout.strip() == "200" and os.path.exists(dest + ".tmp"):
            with open(dest + ".tmp", "rb") as f:
                head = f.read(5)
            is_file = head[:2] == b"PK" if dest.endswith(".zip") else head[:4] != b"<!DO" and head[:5] != b"<html"
            if is_file and os.path.getsize(dest + ".tmp") > 5000:
                os.replace(dest + ".tmp", dest)
                return True
            os.remove(dest + ".tmp")
            return False
        time.sleep(2 * (attempt + 1))
    return None


def fetch_day(day: pd.Timestamp, out: str) -> str:
    legacy = os.path.join(out, f"EQ{day:%d%m%y}.zip")
    udiff = os.path.join(out, f"U{day:%Y%m%d}.csv")
    if os.path.exists(legacy) or os.path.exists(udiff):
        return "cached"
    if day <= LAST_LEGACY_DAY and _get(f"{BASE}EQ{day:%d%m%y}_CSV.ZIP", legacy):
        return "legacy"
    got = _get(f"{BASE}BhavCopy_BSE_CM_0_0_0_{day:%Y%m%d}_F_0000.CSV", udiff)
    return "udiff" if got else ("none" if got is False else "error")


def sessions(start: str, end: str, calendar: str | None) -> list[pd.Timestamp]:
    """NSE's sessions when a long-price file is given (BSE's are the same but for a few days), else every weekday."""
    if calendar:
        idx = pd.read_parquet(calendar).index
        days = [d for d in idx if pd.Timestamp(start) <= d <= pd.Timestamp(end)]
    else:
        days = list(pd.bdate_range(start, end))
    return days


def download(args: argparse.Namespace) -> None:
    os.makedirs(args.out, exist_ok=True)
    days = sessions(args.start, args.end, args.calendar)
    with cf.ThreadPoolExecutor(args.workers) as ex:
        status = dict(zip(days, ex.map(lambda d: fetch_day(d, args.out), days)))
    s = pd.Series(status)
    s.to_csv(os.path.join(args.out, "status.csv"))
    print(s.value_counts().to_dict())
    print("days with no BSE file:", ", ".join(f"{d:%Y-%m-%d}" for d in s[s == "none"].index) or "none")


def read_file(path: str) -> pd.DataFrame:
    name = os.path.basename(path)
    if name.startswith("EQ"):
        day = pd.to_datetime(name[2:8], format="%d%m%y")
        z = zipfile.ZipFile(path)
        x = pd.read_csv(z.open(z.namelist()[0]), on_bad_lines="skip")   # EQ291221 has a malformed row
        x.columns = [c.strip() for c in x.columns]
        return pd.DataFrame({
            "date": day, "code": x.SC_CODE.astype("int64"), "name": x.SC_NAME.astype(str).str.strip(),
            "group": x.SC_GROUP.astype(str).str.strip(), "open": x.OPEN, "high": x.HIGH, "low": x.LOW,
            "close": x.CLOSE, "prev_close": x.PREVCLOSE, "trades": x.NO_TRADES, "shares": x.NO_OF_SHRS,
            "value": x.NET_TURNOV, "isin": None})
    day = pd.to_datetime(name[1:9], format="%Y%m%d")
    x = pd.read_csv(path)
    x.columns = [c.strip() for c in x.columns]
    return pd.DataFrame({
        "date": day, "code": x.FinInstrmId.astype("int64"), "name": x.FinInstrmNm.astype(str).str.strip(),
        "group": x.SctySrs.astype(str).str.strip(), "open": x.OpnPric, "high": x.HghPric, "low": x.LwPric,
        "close": x.ClsPric, "prev_close": x.PrvsClsgPric, "trades": x.TtlNbOfTxsExctd, "shares": x.TtlTradgVol,
        "value": x.TtlTrfVal, "isin": x.ISIN.astype(str).str.strip()})


def extend(base: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """The table `base` with `new`'s sessions added; a session in both takes `new`'s rows.

    The weekly refresh (bse_daily.yml) downloads only the sessions after the
    published table's last and extends it, so the table never has to be rebuilt
    from 4,600 files again. It never loses a session the base had.
    """
    if base is None or base.empty:
        return new.reset_index(drop=True)
    if new.empty:
        return base.reset_index(drop=True)
    base = base[~pd.to_datetime(base["date"]).isin(set(pd.to_datetime(new["date"])))].copy()
    new = new.copy()
    cols = list(dict.fromkeys([*base.columns, *new.columns]))
    for f in (base, new):                               # one dtype across the two parts
        f["date"] = pd.to_datetime(f["date"]).astype("datetime64[ns]")
        for c in ("group", "name", "isin"):
            if c in f:
                f[c] = f[c].astype(object)
    out = pd.concat([base.reindex(columns=cols), new.reindex(columns=cols)], ignore_index=True)
    return out.sort_values(["date", "code"], kind="stable").reset_index(drop=True)


def build(args: argparse.Namespace) -> None:
    frames, failed = [], []
    for path in sorted(glob.glob(os.path.join(args.raw, "*"))):
        if not os.path.basename(path).startswith(("EQ", "U")):
            continue
        try:
            frames.append(read_file(path))
        except Exception as exc:   # one bad day must not lose the other 4,600
            failed.append((os.path.basename(path), str(exc)[:80]))
    table = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if args.base:
        base = pd.read_parquet(args.base)
        before = base["date"].nunique()
        table = extend(base, table)
        print(f"extended {args.base}: {before} sessions -> {table['date'].nunique()}")
    table["group"] = table["group"].astype(str).astype("category")
    table.to_parquet(args.out, index=False, compression="zstd")
    print(f"{len(table):,} rows, {table.date.nunique()} days, {table.code.nunique()} codes, "
          f"{table.date.min():%Y-%m-%d} to {table.date.max():%Y-%m-%d}; failed to parse: {failed or 'none'}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mode", choices=["download", "build"], required=True)
    ap.add_argument("--out", required=True, help="download: the folder for the raw files; build: the parquet file")
    ap.add_argument("--raw", help="build: the folder the download wrote")
    ap.add_argument("--base", help="build: an earlier table to extend with the sessions in --raw")
    ap.add_argument("--start", default="2008-01-01")
    ap.add_argument("--end", default=str(pd.Timestamp.today().date()))
    ap.add_argument("--calendar", help="nse_long_close.parquet: use its sessions instead of every weekday")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    if args.mode == "build":
        if not args.raw:
            ap.error("--mode build needs --raw")
        build(args)
    else:
        download(args)


if __name__ == "__main__":
    main()
