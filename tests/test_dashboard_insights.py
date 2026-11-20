"""src/engine/dashboard_insights.py: the Dashboard's inferences (S149)."""
import numpy as np
import pandas as pd
import pytest

from src.engine import dashboard_insights as di


def _line(start, end, a, b):
    idx = pd.bdate_range(start, end)
    return pd.Series(np.linspace(a, b, len(idx)), index=idx)


def test_window_return_reads_the_session_on_or_before_each_date():
    s = pd.Series([100.0, 110.0, 121.0], index=pd.to_datetime(["2026-10-30", "2026-11-18", "2026-11-19"]))
    assert di.window_return(s, pd.Timestamp("2026-10-31"), pd.Timestamp("2026-11-19")) == pytest.approx(21.0)
    assert di.window_return(s, pd.Timestamp("2026-01-01"), pd.Timestamp("2026-11-19")) is None


def test_book_month_counts_months_ahead_and_compounds_the_year():
    market = pd.concat([_line("2025-12-01", "2025-12-31", 100, 100),
                        pd.Series([100.0, 110.0, 99.0, 108.9], index=pd.to_datetime(
                            ["2026-01-30", "2026-02-27", "2026-03-31", "2026-04-17"]))])
    ledger = {"2026-01": {"strategy": 0.12}, "2026-02": {"strategy": -0.05}, "2026-03": {"strategy": -0.12}}
    mom = {"M": pd.Series([100.0, 105.0], index=pd.to_datetime(["2026-03-31", "2026-04-17"]))}
    r = di.book_month(ledger, 5.0, market, mom, pd.Timestamp("2026-04-17"))
    # Market: Jan 0%, Feb +10%, Mar −10%, Apr so far +10%. Book: +12 (ahead), −5, −12, +5 (behind).
    assert r.months == 4 and r.months_ahead == 1 and r.behind_months == ["Feb", "Mar", "Apr"]
    assert r.book_ytd == pytest.approx((1.12 * 0.95 * 0.88 * 1.05 - 1) * 100)
    assert r.market_mtd == pytest.approx(10.0)
    assert r.momentum_mtd["M"] == pytest.approx(5.0) and r.level_with_momentum == 1 and r.ahead_of_momentum == 0


def test_momentum_lead_compounds_each_window_and_adds_the_month_so_far():
    sp = pd.DataFrame({"month": [f"2026-{m:02d}" for m in range(1, 13)],
                       "top": [2.0] * 9 + [5.0, -1.0, -4.0], "nifty500": [1.0] * 9 + [0.0, -2.0, -1.0]})
    idx = pd.to_datetime(["2026-12-31", "2027-01-15"])
    out = di.momentum_lead(sp, pd.Series([100.0, 103.0], index=idx), pd.Series([100.0, 108.0], index=idx),
                           pd.Timestamp("2027-01-15"))
    names = [w for w, _, _ in out]
    assert names == ["12 months", "Last 3 months", "December", "Month so far"]
    assert out[2][1] == pytest.approx(-3.0)
    three = ((1.05 * 0.99 * 0.96) - (1.0 * 0.98 * 0.99)) * 100
    assert out[1][1] == pytest.approx(three)
    assert out[3][1] == pytest.approx(-5.0)
    assert di.losing_streak(sp, out[3][1]) == 2


def test_month_end_trail_reads_the_month_ends_before_each_date():
    s = pd.Series([44.2, 42.2, 19.6, 16.6], index=pd.to_datetime(["2026-07-31", "2026-08-31", "2026-09-30", "2026-10-30"]))
    assert di.month_end_trail(s, pd.Timestamp("2026-11-19")) == [44.2, 19.6, 16.6]


def test_flows_summary_finds_records_streaks_and_the_months_before():
    idx = pd.bdate_range("2025-01-01", "2026-11-19")
    net = pd.Series(-100.0, index=idx)
    net[idx >= "2026-11-01"] = 5000.0
    f = di.flows_summary(pd.DataFrame({"date": idx, "equity_net": net.values}))
    assert f.month_rank == 1 and f.streak == (idx >= "2026-11-01").sum()
    assert f.before_selling_months == 11 and f.before < 0
    assert f.last20_is_record and len(f.monthly) == 12


def test_flow_evidence_finds_a_planted_effect_and_reports_both_halves():
    months = pd.period_range("2016-01", "2025-12", freq="M")
    rng = np.random.default_rng(1)
    fpi = rng.normal(0, 10000, len(months))
    heavy = fpi >= np.quantile(fpi, 0.75)
    lead_next = np.where(heavy, 2.0, 0.0) + rng.normal(0, 0.1, len(months))
    lead = np.r_[0.0, lead_next[:-1]]                  # lead[t+1] follows fpi[t]
    days = pd.DatetimeIndex([p.to_timestamp(how="end").normalize() for p in months])
    nsdl = pd.DataFrame({"date": list(days) + [pd.Timestamp("2026-01-15")], "equity_net": list(fpi) + [1.0]})
    spreads = pd.DataFrame({"month": [str(p) for p in months], "top": lead, "nifty500": 0.0})
    bench = pd.DataFrame({"nifty500": np.linspace(100, 200, len(days)), "nifty50": np.linspace(100, 190, len(days))}, index=days)
    ev = di.flow_evidence(nsdl, spreads, bench)
    assert ev.after_heavy == pytest.approx(2.0, abs=0.1) and ev.after_rest == pytest.approx(0.0, abs=0.1)
    assert len(ev.halves) == 2 and all(h > r for _, h, r in ev.halves)


def test_size_table_reads_size_against_market_and_momentum_against_its_size():
    end = pd.Timestamp("2026-11-19")
    mk = _line("2026-01-01", end, 100, 110)
    closes = {"nifty200": _line("2026-01-01", end, 100, 112), "nifty200_mom30": _line("2026-01-01", end, 100, 105),
              "midcap150": mk, "midcap150_mom50": mk, "smallcap250": mk, "smallcap250_mq100": mk, "microcap250": mk}
    rows = dict((s, (v, p)) for s, v, p in di.size_table(closes, mk, end))
    assert rows["Large"][0][2] > 0 and rows["Large"][1][2] < 0
    assert rows["Micro"][1] == [None, None, None]


def test_book_by_status_and_rotation_moves():
    sectors = pd.DataFrame({"Industry": ["A", "B", "C"], "rel_6m": [5.0, -1.0, 3.0], "rel_1m": [1.0, -2.0, -1.0]})
    b = di.book_by_status(pd.Series({"A": 70.0, "B": 20.0, "C": 10.0}), sectors)
    assert (b["strong"], b["weak"], b["turning"]) == (70.0, 20.0, 10.0)
    moves = di.rotation_moves({"FS": ["Lagging", "Improving", "Leading"], "IT": ["Leading", "Leading", "Weakening"],
                               "CG": ["Improving", "Weakening", "Lagging"], "HC": ["Weakening"] * 3})
    assert moves == {"risen": ["FS"], "fading": ["IT"], "slid": ["CG"], "weakening_3m": ["HC"]}


@pytest.mark.parametrize("trail,word", [
    ([None, 83, 52], "Climbing, not fast enough"), ([5, None, None], "Fell out of the filters"),
    ([7, None, 45], "Faded from #7"), ([21, 3, 38], "Sliding fast"), ([13, 44, 7], "Rising fast"),
    ([57, 15, 28], "Slipping"), ([15, 28, 27], "Steady")])
def test_rank_words_match_the_trails_seen_on_19_nov(trail, word):
    assert di.rank_trail_word(trail, 40)[0] == word
