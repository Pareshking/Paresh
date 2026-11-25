"""S171: the weekly Screener earnings build (scripts/screener_earnings.py)."""
from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _script():
    spec = importlib.util.spec_from_file_location("screener_earnings", ROOT / "scripts" / "screener_earnings.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_quarter_ends_are_the_13_before_today():
    m = _script()
    q = m.quarter_ends(date(2026, 11, 28))
    assert len(q) == 13 and q[0] == "2023-09-30" and q[-1] == "2026-09-30"


def test_profit_without_other_income():
    m = _script()
    # Vodafone Idea, Mar 2026 (screener.in/company/IDEA/consolidated/, read 25 Nov 2026): 51,970 profit, 57,595 other income, tax 0%
    assert m.pat_xoi({"net_profit": 51970, "other_income": 57595, "tax_pct": 0, "sales_label": "Sales"}) == -5625
    assert m.pat_xoi({"net_profit": 100, "other_income": 40, "tax_pct": 25, "sales_label": "Sales"}) == 70
    assert m.pat_xoi({"net_profit": 100, "other_income": 40, "tax_pct": None, "sales_label": "Sales"}) == 70   # 25% when missing
    assert m.pat_xoi({"net_profit": 100, "other_income": 40, "tax_pct": 25, "sales_label": "Revenue"}) == 100  # banks as reported
    assert m.pat_xoi({"net_profit": None, "other_income": 40, "tax_pct": 25, "sales_label": "Sales"}) is None


def test_merge_keeps_old_quarters_and_takes_this_weeks_restatement():
    m = _script()
    old = pd.DataFrame([{"symbol": "A", "quarter_end": "2023-06-30", "basis": "consolidated", "sales_label": "Sales",
                         "sales": 1, "net_profit": 1, "other_income": 0, "tax_pct": 25, "fetched": "2026-11-21"},
                        {"symbol": "A", "quarter_end": "2023-09-30", "basis": "consolidated", "sales_label": "Sales",
                         "sales": 2, "net_profit": 2, "other_income": 0, "tax_pct": 25, "fetched": "2026-11-21"}])
    new = [{"symbol": "A", "quarter_end": "2023-09-30", "basis": "consolidated", "sales_label": "Sales",
            "sales": 3, "net_profit": 3, "other_income": 0, "tax_pct": 25, "fetched": "2026-11-28"}]
    out = m.merge(old, new)
    assert list(out["quarter_end"]) == ["2023-06-30", "2023-09-30"] and list(out["sales"]) == [1, 3]


def test_growth_needs_the_same_basis_both_quarters():
    m = _script()
    v = {("A", "2026-06-30"): {"basis": "consolidated", "sales": 120.0},
         ("A", "2025-06-30"): {"basis": "consolidated", "sales": 100.0},
         ("B", "2026-06-30"): {"basis": "consolidated", "sales": 50.0},
         ("B", "2025-06-30"): {"basis": "standalone", "sales": 10.0}}
    g = m.growth(v, {"A", "B"}, "2026-06-30", "sales")
    assert g["used"] == 1 and round(g["agg"], 6) == 20.0


def test_tata_motors_out_of_the_demerger_quarters_and_their_year_after():
    m = _script()
    for qe in ("2025-09-30", "2025-12-31", "2026-09-30"):
        assert not ({"TMPV", "TMCV", "TATAMOTORS"} & m.members("nifty_500", qe))
    assert "TMPV" in m.members("nifty_50", "2026-06-30")


def test_the_built_file_holds_complete_quarters_for_six_indices():
    df = pd.read_csv(ROOT / "data" / "reference" / "screener_earnings.csv")
    assert set(df["index"]) == {"Nifty 50", "Nifty Next 50", "Nifty Midcap 150", "Nifty Smallcap 250",
                                "Nifty Microcap 250", "Nifty 500"}
    n500 = df[(df["index"] == "Nifty 500") & (df["measure"] == "sales_agg_yoy")]
    assert (n500["used"] >= 0.9 * n500["members"]).all()
    assert {"pat_agg_yoy", "pat_xoi_agg_yoy", "sales_median_yoy"} <= set(df["measure"])
