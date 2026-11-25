"""S226: NSE's four levels for every filter and grouping, TradingView's only as the fallback; the
sector cap untouched and its switch measured (owner, 24 Nov 2026: "remove trading views sector or
Industry and use Screener 4 level for any filtering")."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from scripts import s226_measure as m
from src.engine import extra_universe as xu
from src.loaders import nse_classification as nc
from src.ui.views import ranking_view as rv
from src.ui.views import sector_view as sv

ROOT = Path(__file__).resolve().parents[1]


def _rank(n=10):
    return pd.DataFrame({"Symbol": [f"S{k}" for k in range(n)], "Rank": range(1, n + 1),
                         "Industry": ["Finance"] * n, "TV_Sector": ["Finance"] * n,
                         "TV_Industry": ["Regional Banks"] * n})


def _levels(syms):
    return {"NSE_Macro": {s: "Financial Services" for s in syms},
            "NSE_Industry": {s: "Banks" for s in syms},
            "NSE_Basic_Industry": {s: "Private Sector Bank" for s in syms}}


# ── The display copy ──────────────────────────────────────────────────────────


def test_levels_added_with_the_sector_and_the_missing_counted():
    rank = _rank()
    syms = list(rank["Symbol"][:9])                     # 9 of 10: 90%, at the guard
    out = nc.with_nse_levels(rank, xu.SYSTEM_NANO, {s: "Financial Services" for s in syms}, _levels(syms))
    assert out is not rank and out.attrs["nse_sectors"] is True
    assert out["Industry"].tolist() == ["Financial Services"] * 9 + ["Unclassified"]   # S9 not in the file: "Unclassified", never TradingView's
    assert out["NSE_Industry"].tolist() == ["Banks"] * 9 + [nc.UNCLASSIFIED]      # never TradingView's
    assert out.attrs["nse_unclassified"] == {"NSE_Macro": 1, "NSE_Industry": 1, "NSE_Basic_Industry": 1}
    # The ranking itself, whose Industry is the plan's sector cap, is unchanged.
    assert rank["Industry"].eq("Finance").all() and "NSE_Industry" not in rank


def test_a_level_short_of_90_percent_is_not_offered_and_the_sector_stays():
    rank = _rank()
    syms = list(rank["Symbol"][:5])
    out = nc.with_nse_levels(rank, xu.SYSTEM_NANO, {s: "Financial Services" for s in syms}, _levels(syms))
    assert nc.nse_levels_present(out) == [] and out.attrs["nse_sectors"] is False
    assert out["Industry"].eq("Finance").all()


def test_the_750_keeps_its_industry_and_gains_the_levels():
    rank = _rank().assign(Industry="Financial Services")
    out = nc.with_nse_levels(rank, xu.SYSTEM_750, {}, _levels(rank["Symbol"]))
    assert out.attrs["nse_sectors"] is True and out["Industry"].eq("Financial Services").all()
    assert nc.nse_levels_present(out) == ["NSE_Macro", "NSE_Industry", "NSE_Basic_Industry"]


def test_levels_map_reads_the_committed_file():
    got = nc.levels_map()
    assert set(got) == set(nc.LEVEL_COLUMNS) | {nc.FILE_SECTOR}
    assert got["NSE_Basic_Industry"]["ABSLAMC"] == "Asset Management Company"
    assert got["NSE_Industry"]["ABSLAMC"] == "Capital Markets"


# ── The Screener's search ─────────────────────────────────────────────────────


def test_search_offers_nse_levels_and_filters_by_them():
    rank = _rank().assign(NSE_Industry=["Banks"] * 5 + ["Capital Markets"] * 4 + [nc.UNCLASSIFIED],
                          NSE_Basic_Industry="Private Sector Bank", NSE_Macro="Financial Services")
    opts = rv.nse_search_options(rank)
    assert opts == ["[MACRO] Financial Services", "[NSE_INDUSTRY] Banks", "[NSE_INDUSTRY] Capital Markets",
                    "[BASIC_INDUSTRY] Private Sector Bank"]      # "Unclassified" is a count, not a choice
    assert rv.search_filter(rank, "[NSE_INDUSTRY] capital markets")["Symbol"].tolist() == ["S5", "S6", "S7", "S8"]
    assert len(rv.search_filter(rank, "[BASIC_INDUSTRY] Private Sector Bank")) == 10
    assert rv.search_filter(rank, "[INDUSTRY] Finance") is None             # handled by the old branch
    assert rv.search_label("[NSE_INDUSTRY] Banks") == "Banks · industry"
    assert rv.search_label("[BASIC_INDUSTRY] Private Sector Bank") == "Private Sector Bank · basic industry"
    assert rv.search_label("[MACRO] Financial Services") == "Financial Services · macro sector"


def test_search_falls_back_to_tradingview_only_without_nse_levels():
    assert rv.nse_search_options(_rank()) == []
    src = (ROOT / "src/ui/views/ranking_view.py").read_text()
    assert "sec_opts = [] if nse_opts else" in src and "tv_ind_opts = [] if nse_opts else" in src


# ── Sectors' grouping ─────────────────────────────────────────────────────────


def test_sectors_offers_nse_levels_when_the_copy_carries_them():
    rank = nc.with_nse_levels(_rank(), xu.SYSTEM_NANO, {s: "Financial Services" for s in _rank()["Symbol"]},
                              _levels(_rank()["Symbol"]))
    choices, nse = sv.groupings(rank, xu.SYSTEM_NANO)
    assert nse is True
    assert choices == {"NSE sector": "Industry", "NSE macro sector": "NSE_Macro", "NSE industry": "NSE_Industry",
                       "NSE basic industry": "NSE_Basic_Industry"}


def test_sectors_keeps_todays_groupings_without_the_levels():
    choices, nse = sv.groupings(_rank(), xu.SYSTEM_NANO)
    assert nse is False and list(choices) == ["TradingView sector", "TradingView industry"]
    choices, nse = sv.groupings(_rank(), xu.SYSTEM_750)
    assert nse is True and list(choices) == ["NSE sector", "TradingView sector", "TradingView industry"]


def test_sector_nouns():
    assert [sv.noun_for(c) for c in ("Industry", "NSE_Macro", "NSE_Industry", "NSE_Basic_Industry", "TV_Industry")] == [
        "sector", "sector", "industry", "industry", "industry"]


# ── The cap is not switched here ─────────────────────────────────────────────


def test_only_display_pages_get_the_nse_copy():
    app = (ROOT / "app.py").read_text()
    callers = [m_.group(1) for m_ in re.finditer(r"(render_\w+)\(\s*_nse_display\(\)", app)]
    assert sorted(callers) == ["render_market_view", "render_ranking_view", "render_sector_view"]
    # The plan's labels: rank_df's Industry, set from TradingView on Nano and Combined (S226 (B), measured).
    assert 'rank_df["Industry"] = rank_df["TV_Sector"]' in app


# ── The Dashboard and the Watchlist: labels from a copy, the plan from rank_df (S226 (A)) ─────────────


def _plan_rank():
    # Four names in one TradingView sector that NSE splits in two: with 2 slots a sector the cap binds on
    # TradingView's labels and not on NSE's, so a plan struck from the display copy would buy differently.
    n = 6
    rank = pd.DataFrame({"Symbol": [f"S{k}" for k in range(n)], "Rank": range(1, n + 1),
                         "Industry": ["T", "T", "T", "T", "U", "V"], "Above 50 EMA": True, "Near 52W High": True})
    nse = {"S0": "A", "S1": "A", "S2": "B", "S3": "B", "S4": "U", "S5": "V"}
    return rank, nse


def _plan(rank):
    from src.engine.actions import plan_rebalance
    p = plan_rebalance(rank, ["S0", "S4"], top_n=4, buffer_n=4, stock_cap=0.25, sector_cap=0.5)
    return p.sells, p.buys, p.holds, p.next_in_line, p.weights.round(10).to_dict()


def test_dashboard_labels_are_nses_and_the_plan_is_unchanged(monkeypatch):
    from src.ui.views import dashboard_home_view as dh
    rank, nse = _plan_rank()
    before = _plan(rank)
    monkeypatch.setattr(nc, "fetch_sector_map", lambda: nse)
    shown = dh.display_labels(rank, xu.SYSTEM_NANO)
    assert shown is not rank and shown["Industry"].tolist() == ["A", "A", "B", "B", "U", "V"]
    assert rank["Industry"].tolist() == ["T", "T", "T", "T", "U", "V"]          # the plan's input untouched
    assert _plan(rank) == before                                                 # same names, same weights
    assert _plan(shown) != before          # the test can tell: NSE's labels would have moved the book
    assert dh.display_labels(rank, xu.SYSTEM_750) is rank


def _function_source(path: str, name: str) -> str:
    import ast
    src = (ROOT / path).read_text()
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(src, fn)


def test_dashboard_and_watchlist_strike_the_plan_from_rank_df():
    import ast
    home = _function_source("src/ui/views/dashboard_home_view.py", "render_home_view")
    assert "model_plan(book, record, rank_df," in home and "shown = display_labels(rank_df, system)" in home
    assert "assess(shown," in home and 'industry = shown.set_index("Symbol")["Industry"]' in home
    wl = _function_source("src/ui/views/watchlist_view.py", "render_watchlist_view")
    assert "wl.book_plan(rank_df," in wl and "with_book_columns(with_nse_levels(rank_df, system)" in wl
    for body in (home, wl):     # rank_df is never rebound or written to in either function
        for node in ast.walk(ast.parse(body)):
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target] if isinstance(node, (ast.AugAssign, ast.AnnAssign)) else [])
            for t in targets:
                base = t
                while isinstance(base, (ast.Subscript, ast.Attribute)):
                    base = base.value
                assert not (isinstance(base, ast.Name) and base.id == "rank_df")


def test_configuration_lists_the_classification_file():
    assert '("NSE Classification", NSE_CLASSIFICATION_FILE, "Missing")' in (
        ROOT / "src/ui/views/config_view.py").read_text()


# ── The measurement (S226 (B)) ───────────────────────────────────────────────


def test_label_moves_and_group_counts():
    current = {"A": "Finance", "B": "Finance", "C": "Process Industries"}
    proposed = m.proposed_map(["A", "B", "C", "D"], current, {"A": "Financial Services", "C": "Chemicals"})
    assert proposed == {"A": "Financial Services", "B": "Finance", "C": "Chemicals", "D": "Other"}
    moves = m.label_moves(current, proposed)
    assert moves.to_dict("records") == [{"Symbol": "A", "Today": "Finance", "NSE": "Financial Services"},
                                        {"Symbol": "C", "Today": "Process Industries", "NSE": "Chemicals"}]
    g = m.group_counts(current, proposed).set_index("Group")
    assert g.loc["Finance", "Today"] == 2 and g.loc["Finance", "NSE"] == 1 and g.loc["Chemicals", "Change"] == 1


def test_plan_moves_names_the_buys_a_binding_cap_changes():
    # Four names in one TradingView sector; NSE splits them in two. With 2 slots a sector, the cap binds
    # today (S3 waits) and not under NSE's sectors (S3 is bought).
    n = 6
    rank = pd.DataFrame({"Symbol": [f"S{k}" for k in range(n)], "Rank": range(1, n + 1), "Industry": "x",
                         "Above 50 EMA": True, "Near 52W High": True})
    today = {"S0": "T", "S1": "T", "S2": "T", "S3": "T", "S4": "U", "S5": "V"}
    nse = {"S0": "A", "S1": "A", "S2": "B", "S3": "B", "S4": "U", "S5": "V"}
    cfg = {"top_n": 4, "buffer_n": 4, "stock_cap": 0.25, "sector_cap": 0.5}
    got = m.plan_moves(rank, [], today, nse, cfg)
    assert got["buys_only_nse"] == ["S2", "S3"] and got["buys_only_today"] == ["S4", "S5"]
    moved = {r["Symbol"]: r["Change"] for r in got["weights_moved"]}
    assert moved["S2"] > 0 and moved["S5"] < 0


def test_backtest_moves_reports_figures_and_held_names():
    def run(sector_map, **_):
        held = sorted(sector_map)[:2] if sector_map["A"] == "x" else sorted(sector_map)[1:3]
        tb = pd.DataFrame({"Period": ["2026-10"] * 2, "Symbol": held, "Weight %": [50.0, 50.0]})
        return {"stats": {"ann_return": 0.2 if sector_map["A"] == "x" else 0.25}, "tradebook": tb}

    got = m.backtest_moves(run, {}, {"A": "x", "B": "x", "C": "y"}, {"A": "z", "B": "x", "C": "y"})
    assert abs(got["figures"]["ann_return"]["change"] - 0.05) < 1e-12
    assert got["figures"]["sharpe"]["change"] is None
    assert got["periods_that_differ"] == [{"period": "2026-10", "only_today": ["A"], "only_nse": ["C"]}]


def test_live_plan_labels_are_tradingviews_on_nano():
    rank = pd.DataFrame({"Symbol": ["A", "B"], "Industry": ["Unclassified", "Finance"]})
    assert m.live_plan_labels(rank, xu.SYSTEM_NANO, {"A": "Producer Manufacturing"}) == {
        "A": "Producer Manufacturing", "B": "Finance"}
    assert m.live_plan_labels(rank, xu.SYSTEM_750, {"A": "Producer Manufacturing"}) == {
        "A": "Unclassified", "B": "Finance"}


def test_the_measure_refuses_below_the_guard(capsys, tmp_path):
    # With no classification file, NSE's own lists name a sector for under 90% of the > ₹2,000 Cr list.
    empty = tmp_path / "cls.csv"
    empty.write_text("Symbol,Macro,Sector,Industry,Basic_Industry,Source,Checked\n")
    assert m.main(["--system", xu.SYSTEM_NANO, "--classification", str(empty)]) == 2
    assert "run the full Screener sweep first" in capsys.readouterr().out


def test_a_former_member_falls_back_to_the_historical_file(tmp_path, monkeypatch):
    """S226 (B), 24 Nov 2026: 249 of the long file's 1,532 stocks are not on Screener any more (mostly
    delisted); historical_industries.csv (NSE's four levels, S18) names 217 of them. The sweep's file wins."""
    from src.loaders import nse_classification as nc
    hist = tmp_path / "hist.csv"
    hist.write_text("ISIN,NSE_SYMBOL,COMPANY_NAME,MACRO_SECTOR,SECTOR,INDUSTRY,BASIC_INDUSTRY,CONFIDENCE,SOURCE_URL,NOTES\n"
                    "X,ANDHRABANK,Andhra Bank,Financial Services,Financial Services,Banks,Public Sector Bank,high,u,\n"
                    "Y,SANSERA,Sansera,Old,Old Sector,Old,Old,high,u,\n", encoding="utf-8")
    cls = tmp_path / "cls.csv"
    cls.write_text("Symbol,Macro,Sector,Industry,Basic_Industry,Source,Checked\n"
                   "SANSERA,Consumer Discretionary,Automobile and Auto Components,Auto Components,"
                   "Auto Components & Equipments,SANSERA,2026-11-24\n", encoding="utf-8")
    monkeypatch.setattr(nc, "HISTORICAL_PATH", str(hist))
    monkeypatch.setattr(nc._historical, "__defaults__", (str(hist),))
    m = nc.sector_map(str(cls), str(tmp_path / "none.csv"), str(tmp_path / "none.csv"))
    assert m["ANDHRABANK"] == "Financial Services"
    assert m["SANSERA"] == "Automobile and Auto Components"


def test_a_row_whose_sector_and_levels_disagree_shows_no_levels():
    # S189: CMPDI's sector is "Services" in NSE's list, its file levels say Construction (24 Nov 2026).
    rank = _rank()
    syms = list(rank["Symbol"])
    levels = {**_levels(syms), nc.FILE_SECTOR: {s: "Financial Services" for s in syms} | {"S0": "Construction"}}
    out = nc.with_nse_levels(rank, xu.SYSTEM_NANO, {s: "Financial Services" for s in syms}, levels)
    assert out["Industry"].iloc[0] == "Financial Services"
    assert out.loc[0, ["NSE_Macro", "NSE_Industry", "NSE_Basic_Industry"]].eq(nc.UNCLASSIFIED).all()
    assert out["NSE_Industry"].iloc[1:].eq("Banks").all()
    assert out.attrs["nse_level_conflicts"] == ["S0"]


def test_the_committed_file_conflicts_only_where_found():
    rank = pd.DataFrame({"Symbol": ["CMPDI", "INA", "SUDEEPPHRM", "BUILDPRO", "RELIANCE"]})
    rank["Industry"] = rank["Symbol"].map(nc.sector_map())
    out = nc.with_nse_levels(rank, xu.SYSTEM_750, nc.sector_map(), nc.levels_map(), min_coverage=0.0)
    assert out.attrs["nse_level_conflicts"] == ["BUILDPRO", "CMPDI", "INA", "SUDEEPPHRM"]
    assert out.loc[4, "NSE_Industry"] != nc.UNCLASSIFIED
