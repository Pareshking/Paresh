"""Figures for the Sectors mock-up (docs/mockups/sectors_v1.html), proposal stage only.

Computes every number the mock-up shows from the repository's own functions, so the
mock-up and a later build read the same construction:

- industry levels and leads: `src.engine.peer_index` (equal-weighted, daily rebalanced,
  S147) and `src.engine.market_questions` (groups, month by month, nearest switches);
- NSE's sector indices: `src.engine.indices_page` over the app's copy of NSE's daily
  index files (`data/nse_indices_history.parquet` + `data/nse_indices_recent.csv`);
- Nifty Total Market: `market_questions_view.total_market()` (`data/nse_total_market.csv`
  joined with `data/benchmark_indices.csv`);
- the ranking table and the Screener price store: passed in as files (the app reads them
  from R2, `snapshots/rankings` and `prices/screener`, falling back to the release files
  `rankings.parquet` and `screener_prices.parquet`).

The industry -> NSE sector index map below is PROPOSED (docs/SECTORS_INDEX_MAP_PROPOSAL.md)
and not approved; it lives here, not in data/reference, until the owner approves it.

    python scripts/sectors_mockup_figures.py --rankings rankings.parquet \
        --prices screener_prices.parquet --out figures.json [--html docs/mockups/sectors_v1.html]

With --html, the JSON is written into the mock-up between its DATA markers.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.engine import indices_page as ip  # noqa: E402
from src.engine import market_questions as mq  # noqa: E402
from src.engine import peer_index as pi  # noqa: E402
from src.loaders import nse_indices as ni  # noqa: E402

# PROPOSED map: NSE sector (the "Industry" column of NSE's index lists) -> the NSE sector
# index that stands for it (None: no index), and every other sector index under it.
HEADLINE = {
    "Capital Goods": "nifty_capital_goods",
    "Financial Services": "nifty_financial_services",
    "Healthcare": "nifty_healthcare_index",
    "Automobile and Auto Components": "nifty_auto",
    "Chemicals": "nifty_chemicals",
    "Fast Moving Consumer Goods": "nifty_fmcg",
    "Consumer Services": "nifty_consumer_services",          # owner, 21 Nov 2026 (MQ4): moved to Sector
    "Consumer Durables": "nifty_consumer_durables",
    "Information Technology": "nifty_it",
    "Metals & Mining": "nifty_metal",
    "Services": "nifty_commercial_transport_services",       # owner, 21 Nov 2026 (MQ4): moved to Sector
    "Construction": "nifty_construction",
    "Power": "nifty_power",
    "Realty": "nifty_realty",
    "Oil Gas & Consumable Fuels": "nifty_oil_gas",
    "Textiles": None,
    "Telecommunication": "nifty_telecommunications",
    "Construction Materials": "nifty_cement",
    "Media Entertainment & Publication": "nifty_media",
    "Utilities": None,
    "Diversified": None,
    "Forest Materials": None,
}
# Every other NSE sector index, under the NSE sector it belongs to.
FINER = {
    "Financial Services": ["nifty_bank", "nifty_private_bank", "nifty_psu_bank",
                           "nifty_financial_services_25_50", "nifty_financial_services_ex_bank",
                           "nifty_midsmall_financial_services", "nifty_nbfc", "nifty_housing_finance",
                           "nifty_capital_markets", "nifty_insurance",
                           "nifty_small_finance_banks_microfinance_institutions"],
    "Healthcare": ["nifty_pharma", "nifty500_healthcare", "nifty_midsmall_healthcare", "nifty_hospitals"],
    "Information Technology": ["nifty_midsmall_it_telecom"],
    "Oil Gas & Consumable Fuels": ["nifty_energy"],
    "Consumer Services": ["nifty_retail"],
    "Fast Moving Consumer Goods": ["nifty_sugar_ethanol"],
}
# Owner, 21 Nov 2026 (MQ4): these two leave Theme for Sector; nse_index_groups.csv changes in the build.
REGROUP = ("nifty_consumer_services", "nifty_commercial_transport_services")
MIN_STOCKS = 5          # "What is leading?" reads sectors with five or more ranked stocks
WINDOWS = (1, 3, 6, 9, 12)


def r2(v, nd=1):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return None
    return round(float(v), nd)


def on_or_before(idx: pd.DatetimeIndex, day: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(idx[idx.searchsorted(day, side="right") - 1])


def ew_return(level: pd.Series, months: int, end: pd.Timestamp) -> float | None:
    """The equal-weighted level's return in %, with the Indices page's date rule."""
    v = pi.window_return(level, end - pd.DateOffset(months=months), end)
    return None if v is None else v * 100


def from_high(s: pd.Series, end: pd.Timestamp) -> float | None:
    s = s.dropna()
    s = s[s.index <= end]
    year = s[s.index > end - pd.DateOffset(months=12)]
    if s.empty or s.index[0] > end - pd.DateOffset(months=12):
        return None
    return float(s.iloc[-1] / year.max() - 1) * 100


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rankings", required=True)
    ap.add_argument("--prices", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--html")
    a = ap.parse_args()

    rank = pd.read_parquet(a.rankings)
    store = pd.read_parquet(a.prices)
    close = store.xs("Close", axis=1, level=-1).sort_index()
    close.index = pd.DatetimeIndex(close.index).normalize()

    from src.ui.views.market_questions_view import total_market
    tm = total_market().dropna()
    f = ip.frames(ni.read_compact(), ni.groups())
    for k in REGROUP:
        f.groups[k] = "Sector"

    # One session for every figure (S148): the last one all three sources hold.
    as_of = min(close.index[-1], tm.index[-1], f.as_of)
    close = close[close.index <= as_of]
    tm = tm[tm.index <= as_of]
    f = f.until(as_of)

    syms = [s for s in rank["Symbol"] if s in close.columns]
    px = close[syms]
    industry = rank.drop_duplicates("Symbol").set_index("Symbol")["Industry"]
    levels, market, counts = pi.industry_levels(px, industry, min_stocks=MIN_STOCKS)
    all_counts = industry.value_counts().to_dict()

    d1 = on_or_before(px.index, as_of - pd.DateOffset(months=1))
    d3 = on_or_before(px.index, as_of - pd.DateOffset(months=3))

    def lead(level, months, end):
        return pi.relative_points(level, market, end - pd.DateOffset(months=months), end)

    # The repository's own answer, to check this script reads the same numbers.
    ld = mq.leaders_answer(px, industry, tm, {}, market_name="Nifty Total Market")
    check = ld.sectors.set_index("Industry")

    sectors = []
    for name, level in levels.items():
        row = {
            "name": name, "stocks": counts[name],
            "lead6_3m": r2(lead(level, 6, d3)), "lead6_1m": r2(lead(level, 6, d1)), "lead6": r2(lead(level, 6, as_of)),
            "lead1": r2(lead(level, 1, as_of)), "lead3": r2(lead(level, 3, as_of)),
        }
        assert abs(row["lead6"] - round(check.at[name, "rel_6m"], 1)) < 0.06, name
        assert abs(row["lead1"] - round(check.at[name, "rel_1m"], 1)) < 0.06, name
        row["group"] = check.at[name, "group"]
        row["ret"] = {m: r2(ew_return(level, m, as_of)) for m in WINDOWS}
        row["from_high"] = r2(from_high(level, as_of))
        sectors.append(row)
    sectors.sort(key=lambda r: -r["lead6"])

    # The 750 against Nifty Total Market (size leadership, the yardstick's own gap).
    gap = {m: r2(pi.size_gap(market, tm, as_of - pd.DateOffset(months=m), as_of)) for m in (1, 3, 6)}
    gap["6_3m"] = r2(pi.size_gap(market, tm, d3 - pd.DateOffset(months=6), d3))
    gap["6_1m"] = r2(pi.size_gap(market, tm, d1 - pd.DateOffset(months=6), d1))
    mkt_ret = {m: r2(ew_return(market, m, as_of)) for m in WINDOWS}
    tm_ret = {m: r2(ip.ret(tm, m, as_of)) for m in WINDOWS}

    # Size rows as the live page draws them (Nifty 50) and as the Dashboard means Large (Nifty 100).
    size = []
    for label, key in (("Nifty 50", "nifty_50"), ("Nifty 100", "nifty_100"), ("Midcap 150", "nifty_midcap_150"),
                       ("Smallcap 250", "nifty_smallcap_250"), ("Microcap 250", "nifty_microcap_250")):
        s = f.close[key].dropna()
        size.append({"name": label, **{f"m{m}": r2(ip.ret(s, m, as_of) - ip.ret(tm, m, as_of)) for m in (1, 3, 6)}})

    months = mq.industry_months(px, industry, tm)
    month_cols = [c for c in months.columns if c not in ("run", "total")]
    month_rows = [{"name": n, "cells": [r2(r[c]) for c in month_cols], "run": int(r["run"]), "total": r2(r["total"])}
                  for n, r in months.iterrows()]
    sw = mq.nearest_switches(ld.sectors)

    # NSE's sector indices, grouped under the NSE sector each belongs to.
    rows = {x.key: x for x in ip.every_index(f, families=("Sector",))["Sector"]}
    ew = {r["name"]: r for r in sectors}
    groups = []
    placed = set()
    for name in [r["name"] for r in sectors] + [n for n in HEADLINE if n not in ew]:
        keys = ([HEADLINE[name]] if HEADLINE.get(name) else []) + FINER.get(name, [])
        idx = []
        for k in keys:
            x = rows.get(k)
            if x is None:
                continue
            placed.add(k)
            idx.append({"key": k, "name": x.name if hasattr(x, "name") else k, "headline": k == HEADLINE.get(name),
                        "live": f"{x.live:%-d %b %Y}", "young": x.returns[12] is None,
                        "ret": {m: r2(x.returns[m]) for m in WINDOWS}, "from_high": r2(x.from_high), "pe": r2(x.pe)})
        if name not in ew and not idx:
            continue
        groups.append({"sector": name, "stocks": int(all_counts.get(name, 0)),
                       "ours": ({"ret": ew[name]["ret"], "from_high": ew[name]["from_high"]} if name in ew else None),
                       "indices": idx})
    unplaced = sorted(set(rows) - placed)
    assert not unplaced, unplaced

    # Broad or narrow: ours less the headline index, over 3M and 1M (every headline index has both).
    gaps = []
    for name, key in HEADLINE.items():
        if not key or name not in ew:
            continue
        x = rows[key]
        gaps.append({"sector": name, "index": x.name, "live": f"{x.live:%-d %b %Y}",
                     "ours3": ew[name]["ret"][3], "nse3": r2(x.returns[3]), "gap3": r2(ew[name]["ret"][3] - x.returns[3]),
                     "ours1": ew[name]["ret"][1], "nse1": r2(x.returns[1]), "gap1": r2(ew[name]["ret"][1] - x.returns[1])})
    gaps.sort(key=lambda g: g["gap3"])

    # One year of each pair, 100 at the first session both have inside the year.
    pairs = {}
    start = as_of - pd.DateOffset(months=12)
    for name, key in HEADLINE.items():
        if not key or name not in levels:
            continue
        nse = f.close[key].dropna()
        j = pd.concat([levels[name].rename("ours"), nse.rename("nse")], axis=1, join="inner").dropna()
        j = j[j.index >= start]
        j = 100 * j / j.iloc[0]
        pairs[name] = {"index": f.names.get(key, key), "dates": [f"{d:%Y-%m-%d}" for d in j.index],
                       "ours": [round(v, 2) for v in j["ours"]], "nse": [round(v, 2) for v in j["nse"]]}

    # Breadth: share of each sector's stocks above their 200-day EMA, 3M ago, 1M ago, now
    # (today's members; the EMA as Breadth and sector_breadth compute it).
    ema = px.ewm(span=200, min_periods=160).mean()
    breadth = []
    names = list(levels) + ["All ranked stocks"]
    for name in names:
        members = list(industry.index[industry == name].intersection(px.columns)) if name in levels else list(px.columns)
        row = {"name": name, "stocks": len(members)}
        for lab, d in (("b3", d3), ("b1", d1), ("now", as_of)):
            p, e = px.loc[d, members], ema.loc[d, members]
            obs = p.notna() & e.notna()
            row[lab] = r2(((p > e) & obs).sum() / max(int(obs.sum()), 1) * 100, 0)
            row[lab + "_n"] = int(obs.sum())
        breadth.append(row)

    # Inside each sector: the ranking table's own flags (sector_view.industry_board).
    from src.ui.views.sector_view import industry_board
    board, singles = industry_board(rank, "Industry")
    board = board.sort_values(["3M Return"], ascending=False)
    inside = [{"name": r.Industry, "stocks": int(r.Stocks), "med3": r2(r["3M Return"] * 100), "med6": r2(r["6M Return"] * 100),
               "ema50": r2(r["EMA %"] * 100, 0), "near": r2(r["Near %"] * 100, 0), "pass": int(r["Pass"]),
               "top50": int(r["Top 50"]), "leaders": list(r["Leaders"][:2])} for _, r in board.iterrows()]

    # Stocks in the sector the title leads with.
    from src.engine.exit_watch import qualified_ranks
    top = next((r["name"] for r in sectors if r["group"] == "ahead on both"), sectors[0]["name"])
    q = qualified_ranks(rank)
    mem = rank[rank["Industry"] == top].sort_values("Rank").head(10)
    stocks = [{"symbol": r.Symbol, "company": r["Company Name"], "rank": int(r.Rank),
               "qrank": (int(q[r.Symbol]) if r.Symbol in q.index else None),
               "r1": r2(r["1M Return"] * 100), "r3": r2(r["3M Return"] * 100), "r6": r2(r["6M Return"] * 100),
               "high": r2(r["% High"]),          # already in % (returns are fractions)
               "ema": bool(r["Above 50 EMA"]), "near": bool(r["Near 52W High"])} for _, r in mem.iterrows()]

    # The leadership map (kept, owner 21 Nov 2026): the live page's function, 200D EMA and 1M by default,
    # five or more stocks so the map counts the same 19 sectors as the rest of the page.
    from src.engine.sector_breadth import sector_leadership
    lmap = sector_leadership(px, industry, tm, 200, min_stocks=MIN_STOCKS, months=1)
    map_rows = [{"name": r.Sector, "stocks": int(r.Stocks), "x0": r2(r.x_then * 100), "x1": r2(r.x_now * 100),
                 "y0": r2(r.y_then * 100), "y1": r2(r.y_now * 100), "above0": int(r.above_then), "obs0": int(r.obs_then),
                 "above1": int(r.above_now), "obs1": int(r.obs_now), "ret": r2(r.ret_now * 100, 2),
                 "bench": r2(r.bench_now * 100, 2), "leaders": [[s, r2(v * 100)] for s, v in r.Leaders]}
                for r in lmap.itertuples()]
    lmap_dates = {"then": f"{pd.Timestamp(lmap['Then'].iloc[0]):%-d %b}", "now": f"{pd.Timestamp(lmap['Now'].iloc[0]):%-d %b}"}

    # The second state: a TradingView grouping chosen (the live page's choices; committed nse_tv_classification.csv).
    tv = pd.read_csv(ROOT / "data" / "nse_tv_classification.csv").drop_duplicates("Symbol").set_index("Symbol")["TV_Sector"]
    tv = tv.reindex(industry.index)
    tv_ld = mq.leaders_answer(px, tv, tm, {}, market_name="Nifty Total Market")
    tv_rows = [{"name": r.Industry, "stocks": int(r.Stocks), "lead6": r2(r.rel_6m), "lead1": r2(r.rel_1m), "group": r.group}
               for r in tv_ld.sectors.itertuples()]

    from src.ui.components import gap_count
    out = {
        "map": map_rows, "map_dates": lmap_dates, "tv": tv_rows, "tv_missing": int(tv.isna().sum()),
        "as_of": f"{as_of:%-d %b %Y}", "as_of_iso": f"{as_of:%Y-%m-%d}", "d1": f"{d1:%-d %b}", "d3": f"{d3:%-d %b}",
        "ranked": len(rank), "price_gaps": int(gap_count(rank)),
        "short_history": int((rank.get("Short History") == "Yes").sum()),
        "sectors_two_plus": int(sum(1 for v in all_counts.values() if v >= 2)),
        "sectors_five_plus": len(levels), "singles": singles,
        "sectors": sectors, "gap": gap, "mkt_ret": mkt_ret, "tm_ret": tm_ret, "size": size,
        "months": {"cols": month_cols, "rows": month_rows},
        "switches": {"entrants": [[n, r2(v)] for n, v in sw["entrants"]], "exits": [[n, r2(v)] for n, v in sw["exits"]]},
        "groups": groups, "gaps": gaps, "pairs": pairs, "breadth": breadth, "inside": inside,
        "top": top, "stocks": stocks, "sector_index_count": len(rows),
    }
    Path(a.out).write_text(json.dumps(out, indent=1, default=str))
    print(f"as of {out['as_of']}: {len(sectors)} sectors, {len(rows)} sector indices, {len(gaps)} pairs -> {a.out}")
    if a.html:
        page = Path(a.html).read_text()
        blob = json.dumps(out, separators=(",", ":"), default=str).replace("</", "<\\/")
        page, n = re.subn(r"(/\*DATA\*/).*?(/\*END\*/)", lambda m: m.group(1) + blob + m.group(2), page, flags=re.S)
        assert n == 1, "DATA markers not found"
        Path(a.html).write_text(page)
        print(f"wrote the figures into {a.html}")


if __name__ == "__main__":
    main()
