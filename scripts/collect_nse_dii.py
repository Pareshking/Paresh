#!/usr/bin/env python3
"""Domestic institutions' cash-market buying and selling on NSE, monthly from 2021 and daily (S153).

    python scripts/collect_nse_dii.py

NSE's archive publishes a "category-wise turnover" workbook for each session
(https://nsearchives.nseindia.com/archives/equities/cat/cat_turnover_DDMMYY.xls, about
two days after the session). Its "Daily" sheet has the day's buy and sell by client
category (banks, insurance companies, mutual funds, AIF, PMS, retail, others); its
"Historical" sheet has every month since January 2021 for domestic institutions: banks,
other financial institutions, insurance, mutual funds, the National Pension System, and
their total. Found 21 Nov 2026 (owner: "observations required to be cleared with right
data"): NSE's provisional FII/DII page keeps no history, so data/fii_dii_flows.csv starts
6 Nov 2026.

Writes data/nse_dii.csv: kind "month" (the Historical sheet's total DII, every month) and
kind "day" (banks + insurance + mutual funds from each Daily sheet, the categories it
lists). Refuses to write (exit 1) when, for a month the Historical sheet has and the daily
rows cover in full, banks + insurance + mutual funds disagree by more than Rs 1 crore:
checked 21 Nov 2026 on October 2026, 20 sessions, net +43,634 both ways.
Scope: NSE trades only (BSE and MSEI are not in these files).
"""
from __future__ import annotations

import io
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "nse_dii.csv"
URL = "https://nsearchives.nseindia.com/archives/equities/cat/cat_turnover_{d:%d%m%y}.xls"
DAILY_CATS = ("Bank", "Insurance Companies", "Mutual Funds")
FIELDS = ["kind", "period", "buy", "sell", "net", "scope"]
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                      "august", "september", "october", "november", "december"], 1)}


class Refused(Exception):
    pass


def _get(d: date) -> bytes | None:
    import requests
    r = requests.get(URL.format(d=d), headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    # A session not yet published (or a holiday) returns a short error page, not a workbook.
    return r.content if r.status_code == 200 and len(r.content) > 10_000 else None


def parse_daily(sheet: pd.DataFrame) -> tuple[pd.Timestamp, float, float]:
    """(trade date, buy, sell) for banks + insurance + mutual funds, Rs crore."""
    when = pd.Timestamp(sheet.iloc[2, 0])
    rows = sheet.iloc[1:12, 1:4].dropna(how="all")
    rows.columns = ["cat", "buy", "sell"]
    rows = rows[rows["cat"].astype(str).str.strip().isin(DAILY_CATS)].drop_duplicates("cat").set_index("cat")
    missing = set(DAILY_CATS) - set(rows.index)
    if missing:
        raise Refused(f"{when:%d %b %Y}: categories missing {sorted(missing)}")
    return when, float(pd.to_numeric(rows["buy"]).sum()), float(pd.to_numeric(rows["sell"]).sum())


def _month(label) -> pd.Period | None:
    m = re.match(r"\s*([A-Za-z]+)\s*'?\s*(\d{2})\s*$", str(label))
    # NSE spells months out, except "Aug'24": a name of three letters or more matches its month.
    hit = [n for name, n in MONTHS.items() if m and len(m.group(1)) >= 3 and name.startswith(m.group(1).lower())]
    if not hit:
        return None
    return pd.Period(year=2000 + int(m.group(2)), month=hit[0], freq="M")


def parse_history(sheet: pd.DataFrame) -> pd.DataFrame:
    """Every month: total DII buy, sell, net, and banks + insurance + mutual funds (for the check)."""
    out = []
    for _, r in sheet.iloc[3:].iterrows():
        p = _month(r.iloc[0])
        if p is None:
            continue
        v = pd.to_numeric(r.iloc[1:14], errors="coerce").fillna(0.0).to_numpy()
        # columns: bank b/s, DFI b/s, insurance b/s, MF b/s, NPS b/s, total b/s, net
        out.append({"period": str(p), "buy": v[10], "sell": v[11], "net": v[12],
                    "bim_net": (v[0] - v[1]) + (v[4] - v[5]) + (v[6] - v[7])})
    if not out:
        raise Refused("Historical sheet: no months read")
    frame = pd.DataFrame(out)
    want = pd.period_range(frame["period"].min(), frame["period"].max(), freq="M").astype(str)
    gaps = sorted(set(want) - set(frame["period"]))
    if gaps:
        raise Refused(f"Historical sheet: months not read {gaps}")
    return frame


def build(history: pd.DataFrame, days: pd.DataFrame, sessions: dict[str, int]) -> pd.DataFrame:
    """The file's rows, after the check that the daily rows and the history agree."""
    for _, h in history.iterrows():
        d = days[days["period"].str[:7] == h["period"]]
        if len(d) and len(d) == sessions.get(h["period"], -1):
            got = float((d["buy"] - d["sell"]).sum())
            if abs(got - h["bim_net"]) > 1.0:
                raise Refused(f"{h['period']}: daily banks+insurance+MF net {got:,.0f} against the month's {h['bim_net']:,.0f}")
    months = history.assign(kind="month", scope="NSE, total DII")[FIELDS]
    daily = days.assign(kind="day", net=days["buy"] - days["sell"], scope="NSE, banks + insurance + mutual funds")[FIELDS]
    return pd.concat([months, daily], ignore_index=True).round(2)


def main() -> int:
    today = datetime.now(timezone.utc).date()
    kept = pd.read_csv(OUT, dtype={"period": str}) if OUT.exists() else pd.DataFrame(columns=FIELDS)
    have = set(kept.loc[kept["kind"] == "day", "period"])
    start = date(today.year, today.month, 1) - timedelta(days=45)       # this month and last, for the check
    days, newest = [], None
    for d in pd.bdate_range(start, today):
        if d.strftime("%Y-%m-%d") in have:
            continue
        raw = _get(d.date())
        time.sleep(0.5)
        if raw is None:
            continue
        book = pd.read_excel(io.BytesIO(raw), header=None, sheet_name=None, engine="xlrd")
        when, buy, sell = parse_daily(book["Daily"])
        days.append({"period": f"{when:%Y-%m-%d}", "buy": buy, "sell": sell})
        newest = book
    if newest is None:
        print("No new session published; nothing written.")
        return 0
    old_days = kept[kept["kind"] == "day"][["period", "buy", "sell"]]
    all_days = pd.concat([old_days, pd.DataFrame(days)]).drop_duplicates("period", keep="last").sort_values("period")
    from src.loaders.nse_calendar import published_holidays
    cal = pd.offsets.CustomBusinessDay(holidays=published_holidays())
    sessions = {str(p): len(pd.date_range(p.start_time, p.end_time, freq=cal))
                for p in pd.PeriodIndex(all_days["period"].str[:7], freq="M").unique()}
    try:
        frame = build(parse_history(newest["Historical"]), all_days, sessions)
    except Refused as exc:
        print(f"::error::NSE DII: {exc}; nothing written")
        return 1
    frame.to_csv(OUT, index=False)
    print(f"Wrote {OUT.name}: {int((frame.kind == 'month').sum())} months, {int((frame.kind == 'day').sum())} days, "
          f"latest {frame.loc[frame.kind == 'day', 'period'].max()}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
