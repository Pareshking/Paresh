#!/usr/bin/env python3
"""S198 (a): measure Ultra Nano Cap and backtest the three January 2027 systems against today's.

Owner, 22 Nov 2026 (TODO S198): from the January 2027 book the systems are the
Nifty 750, the Nifty 1000 and Ultra Nano Cap (₹1,000 Cr or more outside the
Nifty 1000; buyable from ₹1,000 Cr, tracked to ₹500 Cr, prices from ₹800 Cr,
a holding below ₹1,000 Cr sold at the rebalance; src/engine/ultra_nano.py).
Owner, 24 Nov 2026: "we should do it". This script measures it from the data,
read only:

  1. every month-end of NSE's market-cap file on R2 (nse/market_caps, the
     source of today's list, scripts/build_extra_universe.py): the new list's
     size, its cap bands, how many are eligible / tracked / priced, how many it
     buys and sells against today's "> ₹2,000 Cr outside the 750", and the
     list's own turnover from the ₹1,000 Cr buy line and the sell rule;
  2. price coverage: of the stocks ≥ ₹800 Cr outside the Nifty 1000, how many
     have a full year of closes on the long NSE file or on closes adjusted here
     from NSE's raw bhavcopy (the long file's own build, run on the extra names);
  3. median daily traded value of the eligible names (NSE's TOTTRDVAL);
  4. a backtest of the three systems and today's two others (> ₹2,000 Cr and
     Combined) with the repository's engine (src/engine/backtester.run_backtest,
     the record's rules, the January 2027 book's rules applied throughout), over
     the longest window the market-cap history allows, at the record's cost and
     at 60 and 100 bps a round trip for the small-cap lists.

Writes s198_measure.json (the figures) and s198_measure.md (the write-up) to
--out. Nothing is written to R2 or to the repository; the workflow
s198_measure.yml uploads the two files as an artifact. Reader: the S198 (a)
write-up in docs/archive/, and the owner through it.

The Nifty 1000 before NSE's first list (30 Oct 2026, nifty1000_backfill.START)
is a PROXY: the Total Market of that date plus the 250 largest others by the
month-end cap (ultra_nano.nifty_1000_proxy). Every figure built on it says so.

    PYTHONPATH=. python scripts/s198_measure.py --long nse_long_close.parquet \
        [--value nse_long_value.parquet] [--pack nse_raw_pack.parquet \
         --actions-pack nse_actions_pack.parquet --bse bse_daily.parquet] \
        [--caps-dir DIR] --out out/s198
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import src.engine.pipeline  # noqa: E402,F401  (import order: avoids a circular import)
from src.core.market_time import ist_today  # noqa: E402
from src.engine import backtest_page as bp  # noqa: E402
from src.engine import extra_universe as xu  # noqa: E402
from src.engine import index_universe as iu  # noqa: E402
from src.engine import ultra_nano as un  # noqa: E402
from src.engine.membership import members_on, record_snapshot  # noqa: E402
from src.engine.metrics import max_drawdown  # noqa: E402
from src.engine.track_record import TRACK_RECORD_CONFIG as CFG  # noqa: E402
from src.engine.track_record import run_backtest_kwargs  # noqa: E402

CAPS_DATASET = "nse/market_caps"
OUT_JSON, OUT_MD = "s198_measure.json", "s198_measure.md"

# The systems run, each with the record's sector key and its costs (bps a round trip).
# The record's cost is 30 bps; 60 and 100 are the small-cap lists' "costs for this
# size band" (S198 (a)), the Backtest page's own cost tests.
NEW = ("750", "1000", "ultra_nano")
TODAY = ("750", "1000", "nano_today", "combined_today")
SYSTEMS = {
    "750": {"name": "Nifty 750", "sector_key": "750", "costs": (30.0,)},
    "1000": {"name": "Nifty 1000", "sector_key": "1000", "costs": (30.0,)},
    "ultra_nano": {"name": "Ultra Nano Cap (≥ ₹1,000 Cr outside the Nifty 1000)", "sector_key": "nano",
                   "costs": (30.0, 60.0, 100.0)},
    "nano_today": {"name": "> ₹2,000 Cr outside the 750 (today)", "sector_key": "nano",
                   "costs": (30.0, 60.0, 100.0)},
    "combined_today": {"name": "Combined (today; retired from Jan 2027)", "sector_key": "combined",
                       "costs": (30.0,)},
}

# Fixed before any result (S198 (a): "a backtest with the pass rule fixed before
# results"). Decided by rule, owner to confirm (docs/TODO.md S198). At 60 bps a
# round trip, Ultra Nano Cap passes when it compounds faster than Nifty Total
# Market over the window AND its deepest fall is no more than 5 points deeper
# than today's > ₹2,000 Cr system's at the same cost.
PASS_RULE = {"cost_bps": 60.0, "beats": "nifty_total_market", "max_dd_vs": "nano_today",
             "max_dd_slack_pts": 5.0}

FULL_HISTORY_SESSIONS = 0.95      # a close on 95% of the sessions of the year before
CONTEXT_INDICES = ("nifty_total_market", "nifty_500", "nifty_1000", "nifty_microcap_250")


# ── Market caps ─────────────────────────────────────────────────────────────

class R2Caps:
    """NSE's market-cap file per session, from R2 (read only)."""

    def __init__(self):
        from src.storage.r2 import R2Archive, R2Config
        from src.storage.reader import R2DatasetReader
        self.archive = R2Archive(R2Config.from_env())
        self.reader = R2DatasetReader(self.archive)

    def dates(self) -> set[date]:
        from scripts.nse_collect import present_dates
        return present_dates(self.archive, CAPS_DATASET)

    def read(self, day: date) -> pd.DataFrame:
        return self.reader.read_parquet(self.reader.resolve_current(CAPS_DATASET, as_of=day.isoformat()))


class DirCaps:
    """The same files from a folder of <YYYY-MM-DD>.parquet (tests, a local copy)."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)

    def dates(self) -> set[date]:
        out = set()
        for p in self.folder.glob("*.parquet"):
            try:
                out.add(date.fromisoformat(p.stem))
            except ValueError:
                continue
        return out

    def read(self, day: date) -> pd.DataFrame:
        return pd.read_parquet(self.folder / f"{day.isoformat()}.parquet")


def month_ends(held: set[date], today: date) -> list[date]:
    """The last held session of every month, the current month only once it is complete.

    The same rule as today's list (extra_universe.membership_day): a month's
    list is built on its last session, the close that signals the next book.
    """
    by_month: dict[tuple[int, int], date] = {}
    for d in held:
        k = (d.year, d.month)
        by_month[k] = max(by_month.get(k, d), d)
    current = xu.membership_day(held, today)
    out = []
    for _k, d in sorted(by_month.items()):
        if d == max(held) and d != current:
            continue
        out.append(d)
    return out


def canonical(symbols, succ: dict[str, str]) -> set[str]:
    """Symbols under the ticker their prices are filed under (renames followed, three hops)."""
    out = set()
    for s in symbols:
        for _ in range(3):
            if s in succ and succ[s] != s:
                s = succ[s]
            else:
                break
        out.add(s)
    return out


def measure_lists(source, days: list[date], h750: dict, h1000: dict | None,
                  succ: dict[str, str] | None = None) -> tuple[list[dict], dict[str, dict], dict[str, pd.Series]]:
    """(one record per month-end, a membership timeline per system, the caps of each day).

    Timelines are month-end snapshots (in force from the session each list was
    built on, as systems.nano_history), under the ticker prices are filed under.
    """
    succ = succ or {}
    recorded_from = (h1000 or {}).get("baseline", {}).get("date")
    rows: list[dict] = []
    timelines: dict[str, dict] = {k: {"schema_version": 1, "index": k, "baseline": None, "changes": []}
                                  for k in ("1000", "ultra_nano", "nano_today", "combined_today")}
    caps_by_day: dict[str, pd.Series] = {}
    prev_states: dict[str, str] = {}
    prev_today: set[str] | None = None
    for day in days:
        all_caps = un.screened_caps(source.read(day), floor_cr=0.0)
        caps = all_caps[all_caps >= un.TRACK_FLOOR_CR]
        tm = members_on(h750, day)
        if tm is None:
            rows.append({"date": day.isoformat(), "skipped": "before the 750's recorded history"})
            continue
        if recorded_from and day.isoformat() >= recorded_from:
            n1000, n1000_src = members_on(h1000, day) or set(), "recorded"
        else:
            n1000, n1000_src = un.nifty_1000_proxy(all_caps, tm), "proxy"
        states = un.classify(caps, n1000, prev_states)
        today = un.today_list(caps, tm)
        proxy_check = None
        if n1000_src == "recorded":
            # How good the proxy is where NSE's own list exists: same date, both ways.
            proxy = un.nifty_1000_proxy(all_caps, tm)
            proxy_check = {"recorded": len(n1000), "proxy": len(proxy), "in_both": len(proxy & n1000),
                           "eligible_with_proxy": len(un.eligible(un.classify(caps, proxy, prev_states)))}
        elig = un.eligible(states)
        row: dict[str, Any] = {
            "date": day.isoformat(),
            "effective_from": xu.effective_from(day).isoformat(),
            "nifty_1000": n1000_src,
            "nifty_1000_size": len(n1000),
            "eligible": len(elig),
            "tracked": sum(v == un.TRACKED for v in states.values()),
            "priced_only": sum(v == un.PRICED for v in states.values()),
            "price_set": len(un.price_set(states)),
            "band_500_1000_outside_1000": int(((caps < un.BUY_FLOOR_CR) & ~caps.index.isin(n1000)).sum()),
            "band_800_1000_outside_1000": int(((caps >= un.PRICE_FLOOR_CR) & (caps < un.BUY_FLOOR_CR)
                                                & ~caps.index.isin(n1000)).sum()),
            "cap_bands_eligible": un.cap_buckets(caps, elig),
            "cap_quantiles_cr": ({q: round(float(caps.reindex(sorted(elig)).quantile(q)), 0)
                                  for q in (0.1, 0.25, 0.5, 0.75, 0.9)} if elig else {}),
            "today_list": len(today),
            "vs_today": {"in_both": len(elig & today), "new_only": len(elig - today),
                         "today_only": len(today - elig),
                         "today_only_inside_1000": len((today - elig) & n1000)},
        }
        if proxy_check:
            row["proxy_check"] = proxy_check
        if prev_states:
            row["turnover"] = un.turnover(prev_states, states, all_caps, n1000).as_dict()
            held = un.eligible(prev_states)
            row["sold_by_rule"] = _count(un.sell_at_rebalance(held, states, n1000, all_caps))
        if prev_today is not None:
            left = prev_today - today
            row["today_turnover"] = {"before": len(prev_today), "joined": len(today - prev_today),
                                     "left": len(left),
                                     "rate": round(len(left) / len(prev_today), 4) if prev_today else None}
        rows.append(row)
        caps_by_day[day.isoformat()] = all_caps
        for key, syms in (("1000", n1000), ("ultra_nano", elig), ("nano_today", today),
                          ("combined_today", tm | today)):
            if syms:
                timelines[key], _ = record_snapshot(timelines[key], day, canonical(syms, succ))
        prev_states, prev_today = states, today
    return rows, timelines, caps_by_day


def _count(why: dict[str, str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in why.values():
        out[r] = out.get(r, 0) + 1
    return out


def committed_check(rows_caps: dict[str, pd.Series], h750: dict) -> list[dict]:
    """Today's list as recomputed here against data/nanocap_membership.json, where both exist.

    A reproduction of our own list from the same file (a lead, not evidence):
    the committed list excluded the 750 file of its build day, this one the
    750 recorded on the date.
    """
    path = ROOT / "data" / "nanocap_membership.json"
    try:
        months = json.loads(path.read_text(encoding="utf-8"))["months"]
    except (OSError, ValueError, KeyError):
        return []
    out = []
    for day, entry in sorted(months.items()):
        caps = rows_caps.get(day)
        tm = members_on(h750, day)
        if caps is None or tm is None:
            continue
        ours, theirs = un.today_list(caps, tm), set(entry.get("symbols") or [])
        out.append({"date": day, "committed": len(theirs), "recomputed": len(ours),
                    "only_committed": sorted(theirs - ours)[:20], "only_recomputed": sorted(ours - theirs)[:20]})
    return out


# ── Prices ──────────────────────────────────────────────────────────────────

def build_extra_prices(pack: Path, actions_pack: Path | None, bse: Path | None, symbols: set[str],
                       since: date) -> tuple[pd.DataFrame, pd.DataFrame, dict, dict[str, str]]:
    """(adjusted closes, traded value ₹ Cr, report, renames) for `symbols` from NSE's raw rows.

    The long file's own build (scripts/build_nse_long_prices.build: splits,
    bonuses, consolidations, demergers, rights, large dividends, renames
    joined, NSE-only gaps from BSE) on the raw-history pack, for names the
    long file does not keep. Corporate actions are read from R2 (read only).
    """
    from scripts import build_nse_long_prices as bl
    from scripts.nse_history_audit import read_actions, read_bc_rows
    from src.loaders import nse_prices as npx
    from src.loaders.nse_identity import auto_renames
    from src.storage.r2 import R2Archive, R2Config
    from src.storage.reader import R2DatasetReader

    archive = R2Archive(R2Config.from_env())
    reader = R2DatasetReader(archive)
    until = date.today() - timedelta(days=1)
    notes = json.loads((npx.DIR / "notes.json").read_text(encoding="utf-8"))
    prices = pd.read_parquet(pack)
    prices["date"] = pd.to_datetime(prices["date"])
    prices = prices[prices["date"].dt.date >= since]
    renames = {**auto_renames(set(prices["symbol"].dropna().unique())), **(notes.get("renames") or {})}
    keep, raw = bl.with_renames(symbols, renames)
    prices = prices[prices["symbol"].isin(raw)]
    old_bc = pd.read_parquet(actions_pack) if actions_pack and actions_pack.exists() else None
    bc_rows = read_bc_rows(reader, archive, since, until, pack=old_bc)
    actions, _ = bl.with_tejhq(read_actions(reader, archive, since, until, bc_rows=bc_rows))
    actions = actions[actions["symbol"].isin(raw)] if len(actions) else actions
    bse_t = isin_hist = current = None
    if bse is not None and bse.exists():
        from src.loaders.nse_identity import current_isins, isin_history
        bse_t = pd.read_parquet(bse, columns=["date", "code", "name", "close", "shares", "isin"])
        isin_hist = isin_history()
        current = {sym: isin for isin, sym in current_isins().items()}
    print(f"extra prices: {len(keep)} symbols ({len(raw)} raw tickers), {len(prices):,} rows, "
          f"{len(actions):,} actions", flush=True)
    close, value, report = bl.build(prices, actions, notes, renames, keep, bse=bse_t,
                                    isin_history=isin_hist, current_isins=current, fill_log={})
    succ = {old: (a["new_symbol"] if isinstance(a, dict) else str(a)) for old, a in renames.items()}
    small = {k: report.get(k) for k in ("first_session", "last_session", "bse_fill")}
    small["unpriced"] = len(report.get("unpriced") or [])
    return close, value, small, succ


def coverage(close: pd.DataFrame, long_cols: set[str], names: set[str], day: pd.Timestamp) -> dict:
    """Of `names`, how many have a close on `day` and on 95% of the year's sessions before it, by source."""
    idx = close.index[(close.index <= day) & (close.index > day - pd.Timedelta(days=365))]
    out = {"names": len(names), "full": 0, "short": 0, "none": 0,
           "full_long_file": 0, "full_built_here": 0, "none_names": []}
    if not len(idx):
        out["none"] = len(names)
        return out
    window = close.reindex(columns=sorted(names)).loc[idx]
    on_day = window.iloc[-1] if idx[-1] == day else pd.Series(float("nan"), index=window.columns)
    share = window.notna().mean()
    for s in window.columns:
        if pd.isna(on_day.get(s)):
            out["none"] += 1
            out["none_names"].append(s)
        elif share[s] >= FULL_HISTORY_SESSIONS:
            out["full"] += 1
            out["full_long_file" if s in long_cols else "full_built_here"] += 1
        else:
            out["short"] += 1
    out["none_names"] = out["none_names"][:30]
    return out


def traded_value(value: pd.DataFrame | None, names: set[str], day: pd.Timestamp) -> dict | None:
    """Median daily traded value (₹ Cr) of each name over the 21 sessions to `day`; the spread of those medians."""
    if value is None or value.empty or not names:
        return None
    w = value.reindex(columns=sorted(names)).loc[:day].tail(21)
    med = w.median().dropna()
    if med.empty:
        return None
    return {"names": int(len(med)), "median_cr": round(float(med.median()), 2),
            "p10_cr": round(float(med.quantile(0.1)), 2),
            "below_1_cr": int((med < 1).sum()), "below_0_5_cr": int((med < 0.5).sum())}


# ── Backtest ────────────────────────────────────────────────────────────────

def index_series(key: str) -> pd.Series:
    from src.loaders import nse_indices as ni
    store = ni.read_compact()
    s = store[store["key"] == key].set_index("date")["close"].sort_index()
    s.index = pd.DatetimeIndex(s.index)
    return pd.to_numeric(s, errors="coerce").dropna()


def run_one(system: str, timeline: dict, close: pd.DataFrame, bench: pd.Series, start: pd.Period,
            end: pd.Period, cost: float, first_signal: str) -> dict:
    """One run of the record's engine on a system's timeline; the January 2027 book's rules throughout."""
    from src.engine.backtester import run_backtest
    from src.engine.model_record import record_sector_map

    frame = bp.frame_for(close, iu.ever_members(timeline), end, to_latest=True)
    frame = frame.loc[start.start_time - pd.DateOffset(years=3):]
    sectors, unlabelled = bp.industry_map(frame.columns, record_sector_map(frame.columns, SYSTEMS[system]["sector_key"]))
    kwargs = run_backtest_kwargs(CFG) | {
        "cost_bps": cost, "hold_cap_from": None,
        # Forward-dated rules (30 Nov 2026 signal) govern the whole window: this
        # measures the system the January 2027 book runs, not the frozen months.
        "members_only_scoring_from": first_signal, "ema_warmup_from": first_signal,
        "high_rule_from": first_signal,
    }
    res = run_backtest(f"s198_{system}_{cost}_{start}_{end}", frame, **kwargs, sector_map=sectors,
                       _benchmark_close=bench, backtest_months=(end - start).n + 1, _membership=timeline,
                       stateful_history=True, history_start=start.start_time, _actions=[])
    if not res:
        return {"system": system, "cost_bps": cost, "error": "no result (insufficient history?)"}
    eq = pd.Series(res["equity_curve"]).dropna()
    eq.index = pd.DatetimeIndex(eq.index)
    s = bp.summary(eq, bench)
    stats = res.get("stats") or {}
    out = {"system": system, "cost_bps": cost, "from": f"{s.first:%Y-%m-%d}", "to": f"{s.last:%Y-%m-%d}",
           "years": round(s.years, 2), "a_year": _r(s.a_year), "total": _r(s.total),
           "bench_a_year": _r(s.bench_a_year), "lead_pts": _r(None if s.lead is None else s.lead * 100, 2),
           "months": s.months, "months_ahead": s.ahead, "max_drawdown": _r(max_drawdown(eq)),
           "avg_turnover_pct": _r(stats.get("avg_turnover"), 2), "sharpe": _r(stats.get("sharpe"), 2),
           "pit_periods": stats.get("pit_periods"), "current_universe_periods": stats.get("current_universe_periods"),
           "frame_symbols": int(frame.shape[1]), "unlabelled_industry": int(unlabelled),
           "context": {}}
    for key in CONTEXT_INDICES:
        ser = index_series(key)
        if len(ser) and ser.index[0] <= eq.index[0]:
            out["context"][key] = _r(bp.a_year(bp.on_calendar(ser, eq.index)))
    monthly = res.get("monthly")
    if monthly is not None and len(monthly) and "Holdings" in monthly:
        out["median_holdings"] = float(pd.to_numeric(monthly["Holdings"], errors="coerce").median())
    return out


def _r(v, d=4):
    return None if v is None or pd.isna(v) else round(float(v), d)


def verdict(runs: list[dict]) -> dict:
    """The pass rule (PASS_RULE), applied to the runs as fixed before them."""
    c = PASS_RULE["cost_bps"]
    pick = {(r["system"], r["cost_bps"]): r for r in runs if "error" not in r}
    un_r, today_r = pick.get(("ultra_nano", c)), pick.get((PASS_RULE["max_dd_vs"], c))
    if not un_r or not today_r or un_r.get("a_year") is None:
        return {"rule": PASS_RULE, "result": "not decided: a run is missing or under a year"}
    tm = un_r["context"].get(PASS_RULE["beats"])
    beats = tm is not None and un_r["a_year"] > tm
    dd_ok = un_r["max_drawdown"] >= today_r["max_drawdown"] - PASS_RULE["max_dd_slack_pts"] / 100
    return {"rule": PASS_RULE, "beats_total_market": beats, "drawdown_within_slack": dd_ok,
            "ultra_nano_a_year": un_r["a_year"], "total_market_a_year": tm,
            "ultra_nano_max_dd": un_r["max_drawdown"], "nano_today_max_dd": today_r["max_drawdown"],
            "result": "pass" if beats and dd_ok else "fail"}


# ── Write-up ────────────────────────────────────────────────────────────────

def _pct(v, d=1):
    return "–" if v is None else f"{v * 100:+.{d}f}%"


def write_md(out: dict) -> str:
    L = [f"# S198 (a): Ultra Nano Cap measured, {out['built']}", "",
         "Read only (R2 `nse/market_caps`, the long NSE file, NSE's raw bhavcopy pack). "
         "Built by `scripts/s198_measure.py` (workflow `s198_measure.yml`); the figures are in "
         f"`{OUT_JSON}` beside this file. Reader: the S198 (a) write-up in `docs/archive/`.", "",
         "## The rule measured", "",
         "Ultra Nano Cap: main-board stocks (EQ/BE, listed, not a fund) of ₹1,000 Cr or more outside "
         "the Nifty 1000 on each month-end date; tracked (not buyable) from ₹500 to ₹1,000 Cr once a "
         "member; prices from ₹800 Cr; a holding below ₹1,000 Cr sold at the rebalance. Today's "
         "system for comparison: ₹2,000 Cr or more outside the 750 on the same date.", "",
         f"Market-cap history: {out['caps']['first']} to {out['caps']['last']}, "
         f"{out['caps']['month_ends']} month-ends. Nifty 1000: NSE's recorded list from "
         f"{out['caps']['nifty_1000_recorded_from'] or '–'}; before it a **proxy** (the 750 plus the "
         "250 largest others by the month-end cap; NSE uses six-month average full caps).", "",
         "## The list, month by month", "",
         "| Month-end | N1000 | Eligible | Tracked | ₹800-1,000 Cr priced | Today's list | Both | New only | "
         "Today only | Left (rate) | Sold: below ₹1,000 Cr / into N1000 / no cap |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in out["months"]:
        if "skipped" in r:
            continue
        t, sold = r.get("turnover") or {}, r.get("sold_by_rule") or {}
        left = f"{t['left']} ({t['rate']:.0%})" if t and t.get("rate") is not None else "–"
        sold_s = (f"{sold.get(un.SOLD_BELOW_FLOOR, 0)} / {sold.get(un.SOLD_INTO_1000, 0)} / "
                  f"{sold.get(un.SOLD_NO_CAP, 0)}") if t else "–"
        v = r["vs_today"]
        L.append(f"| {r['date']} | {r['nifty_1000']} | {r['eligible']} | {r['tracked']} | {r['priced_only']} | "
                 f"{r['today_list']} | {v['in_both']} | {v['new_only']} | {v['today_only']} | {left} | {sold_s} |")
    last = next((r for r in reversed(out["months"]) if "skipped" not in r), None)
    if last:
        L += ["", f"Latest ({last['date']}): eligible by cap band (₹ Cr) {last['cap_bands_eligible']}; "
              f"quantiles {last['cap_quantiles_cr']}. Today's list names not in the new one "
              f"({last['vs_today']['today_only']}): {last['vs_today']['today_only_inside_1000']} of them "
              "are inside the Nifty 1000 (they move to that system)."]
    pc = next((r for r in out["months"] if r.get("proxy_check")), None)
    if pc:
        c = pc["proxy_check"]
        L.append(f"Proxy against NSE's list on {pc['date']}: {c['in_both']} of {c['recorded']} names agree; "
                 f"eligible {pc['eligible']} with NSE's list, {c['eligible_with_proxy']} with the proxy. The "
                 "first recorded month's turnover includes the change from proxy to NSE's list.")
    tov = [r["turnover"]["rate"] for r in out["months"] if r.get("turnover", {}).get("rate") is not None]
    tt = [r["today_turnover"]["rate"] for r in out["months"] if (r.get("today_turnover") or {}).get("rate") is not None]
    if tov:
        L.append(f"Median monthly one-way list turnover: new {pd.Series(tov).median():.1%}, "
                 f"today's {pd.Series(tt).median():.1%}." if tt else
                 f"Median monthly one-way list turnover: new {pd.Series(tov).median():.1%}.")
    L += ["", "## Prices and liquidity", ""]
    for k, c in (out.get("coverage") or {}).items():
        L.append(f"- {k}: {c['names']} names ≥ ₹800 Cr outside the Nifty 1000; full year of closes "
                 f"{c['full']} (long file {c['full_long_file']}, adjusted here {c['full_built_here']}), "
                 f"short {c['short']}, no close on the day {c['none']}.")
    for k, v in (out.get("traded_value") or {}).items():
        if v:
            L.append(f"- {k}: eligible names' median daily traded value ₹{v['median_cr']} Cr "
                     f"(10th percentile ₹{v['p10_cr']} Cr; {v['below_1_cr']} below ₹1 Cr, "
                     f"{v['below_0_5_cr']} below ₹0.5 Cr).")
    L.append(f"- Extra prices: {out['extra_prices']}.")
    L += ["", "## Backtest", "",
          "Engine: `src/engine/backtester.run_backtest`, the record's rules (`TRACK_RECORD_CONFIG`), the "
          "rules of the 30 Nov 2026 signal applied throughout (members-only scoring, 30-print EMA, "
          "calendar-year high, six-monthly reset with 15% cap and 5% buys). Benchmark: Nifty Total Market.", "",
          "| System | Cost bps | From | To | A year | Nifty TM a year | Lead pts | Max DD | Months ahead | "
          "Avg turnover % |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in out["backtest"]:
        if "error" in r:
            L.append(f"| {SYSTEMS[r['system']]['name']} | {r['cost_bps']:.0f} | {r['error']} |||||||| ")
            continue
        L.append(f"| {SYSTEMS[r['system']]['name']} | {r['cost_bps']:.0f} | {r['from']} | {r['to']} | "
                 f"{_pct(r['a_year'])} | {_pct(r['context'].get('nifty_total_market'))} | "
                 f"{'–' if r['lead_pts'] is None else format(r['lead_pts'], '+.1f')} | {_pct(r['max_drawdown'])} | "
                 f"{r['months_ahead']} of {r['months']} | "
                 f"{'–' if r['avg_turnover_pct'] is None else r['avg_turnover_pct']} |")
    v = out.get("verdict") or {}
    L += ["", f"Pass rule (fixed before the results; decided by rule, owner to confirm): {json.dumps(PASS_RULE)}. "
          f"Result: **{v.get('result', '–')}**.", "",
          "## Not measured here", "",
          "- ASM/GSM lists and 5% / 2% price bands: no dataset in the repository or on R2 holds them.",
          "- Screener and SS closes for the new names (the live ranking reads Screener first); the backtest "
          "reads NSE's closes adjusted by the long file's own rules.",
          "- The Nifty 1000 before NSE's first list is a proxy (above).",
          "- A cross-check against an independent source: this is our own data, run through our own engine.", ""]
    if out.get("committed_check"):
        L += ["## Today's list recomputed against `data/nanocap_membership.json` (a lead, not evidence)", ""]
        for c in out["committed_check"]:
            L.append(f"- {c['date']}: committed {c['committed']}, recomputed {c['recomputed']}; "
                     f"only committed {c['only_committed']}, only recomputed {c['only_recomputed']}")
        L.append("")
    return "\n".join(L) + "\n"


# ── Main ────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--long", type=Path, required=True, help="nse_long_close.parquet")
    ap.add_argument("--value", type=Path, default=None, help="nse_long_value.parquet (traded value)")
    ap.add_argument("--pack", type=Path, default=None, help="nse_raw_pack.parquet: adjust the extra names here")
    ap.add_argument("--actions-pack", type=Path, default=None, help="nse_actions_pack.parquet")
    ap.add_argument("--bse", type=Path, default=None, help="bse_daily.parquet")
    ap.add_argument("--caps-dir", type=Path, default=None, help="read market caps from here instead of R2")
    ap.add_argument("--since", type=lambda s: date.fromisoformat(s) if s.strip() else None, default=None,
                    help="first month-end to use (blank: all)")
    ap.add_argument("--no-backtest", action="store_true")
    ap.add_argument("--out", type=Path, default=Path("out/s198"))
    a = ap.parse_args(argv)

    source = DirCaps(a.caps_dir) if a.caps_dir else R2Caps()
    held = source.dates()
    days = [d for d in month_ends(held, ist_today()) if a.since is None or d >= a.since]
    if not days:
        print("::error::no month-end market caps found")
        return 1
    print(f"market caps: {len(held)} sessions, {len(days)} month-ends {days[0]} to {days[-1]}", flush=True)

    h750 = iu.index_history("nifty_total_market")
    h1000 = iu.index_history("nifty_1000", None)
    close = pd.read_parquet(a.long)
    if "date" in close.columns:
        close = close.set_index("date")
    close.index = pd.DatetimeIndex(close.index)
    long_cols = set(close.columns)
    value = pd.read_parquet(a.value) if a.value and a.value.exists() else None
    if value is not None:
        if "date" in value.columns:
            value = value.set_index("date")
        value.index = pd.DatetimeIndex(value.index)
    succ = {old: a_["new_symbol"] for old, a_ in (h750.get("aliases") or {}).items()}

    rows, timelines, caps_by_day = measure_lists(source, days, h750, h1000, succ)
    used = [r for r in rows if "skipped" not in r]
    print(f"lists: {len(used)} month-ends measured", flush=True)

    # Every name that is ever in the price set or today's list, outside the long file.
    wanted: set[str] = set()
    for t in timelines.values():
        wanted |= iu.ever_members(t)
    for caps in caps_by_day.values():
        wanted |=set(caps[caps >= un.PRICE_FLOOR_CR].index)
    extra_info: Any = "not built (no raw pack): only names on the long file are priced"
    if a.pack and a.pack.exists():
        since = date(days[0].year - 4, 1, 1)
        ex_close, ex_value, extra_info, more = build_extra_prices(
            a.pack, a.actions_pack, a.bse, wanted - long_cols, since)
        succ.update(more)
        add = [c for c in ex_close.columns if c not in long_cols]
        close = close.join(ex_close[add].reindex(close.index), how="left")
        if value is not None and len(add):
            value = value.join(ex_value.reindex(columns=add).reindex(value.index), how="left")
        extra_info = {**extra_info, "symbols_added": len(add)}
        # Timelines under the tickers the build joined renames to.
        rows, timelines, caps_by_day = measure_lists(source, days, h750, h1000, succ)
        used = [r for r in rows if "skipped" not in r]

    cov, tv = {}, {}
    for r in used:
        day = pd.Timestamp(r["date"])
        caps = caps_by_day[r["date"]]
        n1000 = members_on(timelines["1000"], day.date()) or set()
        band = canonical({s for s, c in caps.items() if c >= un.PRICE_FLOOR_CR}, succ) - n1000
        cov[r["date"]] = coverage(close, long_cols, band, day)
        tv[r["date"]] = traded_value(value, members_on(timelines["ultra_nano"], day.date()) or set(), day)
    # The coverage table in the write-up: the first, middle and latest month-ends.
    keys = sorted(cov)
    shown = {k: cov[k] for k in sorted({keys[0], keys[len(keys) // 2], keys[-1]})} if keys else {}

    out: dict[str, Any] = {
        "built": f"{datetime.now(UTC):%Y-%m-%d}",
        "rule": {"buy_floor_cr": un.BUY_FLOOR_CR, "track_floor_cr": un.TRACK_FLOOR_CR,
                 "price_floor_cr": un.PRICE_FLOOR_CR, "today_floor_cr": un.TODAY_FLOOR_CR},
        "caps": {"sessions": len(held), "first": days[0].isoformat(), "last": days[-1].isoformat(),
                 "month_ends": len(days),
                 "nifty_1000_recorded_from": (h1000 or {}).get("baseline", {}).get("date")},
        "months": rows, "coverage": shown, "coverage_all": cov,
        "traded_value": {k: tv[k] for k in shown}, "traded_value_all": tv,
        "extra_prices": extra_info, "long_last_session": f"{close.index[-1]:%Y-%m-%d}",
        "committed_check": committed_check(caps_by_day, h750), "backtest": [],
    }

    if not a.no_backtest and used:
        bench = index_series("nifty_total_market")
        timelines["750"] = h750
        start = pd.Period(used[0]["date"], "M") + 1
        end = pd.Period(close.index[-1], "M") - 1
        first_signal = used[0]["date"]
        out["window"] = {"start": str(start), "end": str(end), "months": (end - start).n + 1}
        print(f"backtest {start} to {end}", flush=True)
        if end < start:
            out["backtest"].append({"system": "ultra_nano", "cost_bps": 30.0, "error": "window under a month"})
        else:
            for system, spec in SYSTEMS.items():
                for cost in spec["costs"]:
                    r = run_one(system, timelines[system], close, bench, start, end, cost, first_signal)
                    print(json.dumps({k: r.get(k) for k in ("system", "cost_bps", "a_year", "max_drawdown",
                                                             "lead_pts", "error")}), flush=True)
                    out["backtest"].append(r)
        out["verdict"] = verdict(out["backtest"])

    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / OUT_JSON).write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8")
    (a.out / OUT_MD).write_text(write_md(out), encoding="utf-8")
    print(f"wrote {a.out / OUT_JSON} and {a.out / OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
