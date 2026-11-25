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


def test_the_r2_store_keeps_every_quarter_and_round_trips(tmp_path):
    m = _script()
    q = pd.DataFrame([{"symbol": "A", "quarter_end": qe, "basis": "consolidated", "sales_label": "Sales", "sales": 1.0,
                       "operating_profit": 1.0, "pbt": 1.0, "net_profit": 1.0, "other_income": 0.0, "tax_pct": 25.0,
                       "eps": 1.0, "fetched": "2026-11-28"} for qe in ("2019-03-31", "2026-09-30")])
    path = tmp_path / "store.parquet"
    m.write_store(q, str(path), "2026-11-28")
    back = m.read_store(str(path), False, str(tmp_path / "none.csv"))
    assert len(back) == 2 and "as_of" not in back.columns            # 2019 kept: R2 holds the whole history
    assert pd.read_parquet(path)["as_of"].iloc[0] == pd.Timestamp("2026-11-28")


def test_the_weekly_job_publishes_the_store_to_r2():
    text = (ROOT / ".github" / "workflows" / "screener_earnings.yml").read_text(encoding="utf-8")
    assert "--from-r2" in text and "--dataset fundamentals/screener_quarters" in text and "--skip-if-published" in text


def test_a_page_is_read_only_when_it_can_have_something_new():
    m = _script()
    stored = pd.DataFrame([
        {"symbol": "HAS", "quarter_end": "2026-09-30", "fetched": "2026-11-21"},     # has the Sep quarter
        {"symbol": "WAIT", "quarter_end": "2026-06-30", "fetched": "2026-11-21"},    # results meeting 25 Nov
        {"symbol": "LATE", "quarter_end": "2026-06-30", "fetched": "2026-11-21"},    # no meeting yet, window closed
    ])
    cal = pd.DataFrame([{"symbol": "WAIT", "date": "2026-11-25", "results": 1}])
    got, why = m.pages_to_read(["HAS", "WAIT", "LATE", "NEW"], stored, cal, date(2026, 11, 28))
    assert sorted(got) == ["NEW", "WAIT"] and why["skipped"] == 2


def test_once_a_quarter_after_the_filing_deadline_every_page_is_read_again():
    m = _script()
    assert m.due_quarter(date(2027, 1, 9)) == ("2026-12-31", date(2027, 2, 14))     # 45 days
    assert m.due_quarter(date(2027, 4, 10)) == ("2027-03-31", date(2027, 5, 30))    # 60 after March: annual results
    stored = pd.DataFrame([{"symbol": "HAS", "quarter_end": "2026-12-31", "fetched": "2027-02-06"}])
    assert m.pages_to_read(["HAS"], stored, None, date(2027, 2, 20))[0] == ["HAS"]   # first run after 14 Feb
    stored["fetched"] = "2027-02-20"
    assert m.pages_to_read(["HAS"], stored, None, date(2027, 2, 27))[0] == []        # then not again


def test_rajesh_exports_is_left_out_of_every_index_sum():
    m = _script()
    assert "RAJESHEXPO" in m.LEFT_OUT
    for key in m.research.INDICES:
        assert "RAJESHEXPO" not in m.members(key, "2025-09-30")
