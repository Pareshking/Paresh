"""S198 (a): the Ultra Nano Cap rule and the turnover count the measurement reports.

Owner, 22 Nov 2026: buyable from ₹1,000 Cr, tracked to ₹500 Cr, prices from
₹800 Cr, a holding below ₹1,000 Cr sold at the rebalance, outside the
Nifty 1000 on each month-end date.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from src.engine import ultra_nano as un
from src.engine.membership import members_on

CR = 10_000_000


def _caps(rows: dict[str, float], series: str = "EQ") -> pd.DataFrame:
    """One session of nse/market_caps, caps in ₹ Cr."""
    return pd.DataFrame({"symbol": list(rows), "series": series, "security": [f"{s} Ltd" for s in rows],
                         "category": "Listed", "mcap": [v * CR for v in rows.values()]})


def test_floors_are_the_owners():
    assert (un.BUY_FLOOR_CR, un.TRACK_FLOOR_CR, un.PRICE_FLOOR_CR) == (1_000, 500, 800)
    assert un.TODAY_FLOOR_CR == 2_000


def test_screened_caps_keeps_the_exact_figure_and_drops_funds_sme_and_below_floor():
    caps = _caps({"AAA": 999.6, "BBB": 1_000.0, "NIFTYBEES": 5_000.0, "CCC": 400.0})
    sme = _caps({"SMEX": 3_000.0}, series="SM")
    got = un.screened_caps(pd.concat([caps, sme], ignore_index=True))
    assert set(got.index) == {"AAA", "BBB"}
    assert got["AAA"] == pytest.approx(999.6)     # not rounded up over the buy line


def test_buy_line_and_outside_the_nifty_1000():
    caps = pd.Series({"IN1000": 50_000.0, "BIG": 1_500.0, "EDGE": 1_000.0, "JUST": 999.9, "SMALL": 850.0})
    states = un.classify(caps, nifty_1000={"IN1000"})
    assert "IN1000" not in states                  # inside the Nifty 1000: that system, whatever its size
    assert states["BIG"] == states["EDGE"] == un.ELIGIBLE
    # Below ₹1,000 Cr and never a member: prices collected from ₹800 Cr, not buyable.
    assert states["JUST"] == states["SMALL"] == un.PRICED
    assert un.eligible(states) == {"BIG", "EDGE"}


def test_a_member_below_the_buy_line_is_tracked_to_500_then_leaves():
    prev = {"FALL": un.ELIGIBLE, "SLIDE": un.TRACKED, "GONE": un.TRACKED}
    caps = pd.Series({"FALL": 700.0, "SLIDE": 500.0, "GONE": 499.0, "NEWLOW": 600.0})
    states = un.classify(caps, set(), prev)
    assert states["FALL"] == un.TRACKED and states["SLIDE"] == un.TRACKED
    assert "GONE" not in states                    # below ₹500 Cr: out of the tracked set
    assert "NEWLOW" not in states                  # ₹500-800 Cr and never a member: not even priced
    assert un.members(states) == {"FALL", "SLIDE"} and not un.eligible(states)


def test_prices_collected_from_800_for_joiners_in_waiting():
    states = un.classify(pd.Series({"A": 799.0, "B": 800.0, "C": 1_200.0}), set())
    assert un.price_set(states) == {"B", "C"}


def test_a_tracked_member_back_above_1000_is_buyable_again():
    states = un.classify(pd.Series({"BACK": 1_050.0}), set(), {"BACK": un.TRACKED})
    assert states["BACK"] == un.ELIGIBLE


def test_the_nifty_1000_is_taken_on_each_month_end_date():
    caps = pd.Series({"X": 3_000.0})
    assert un.classify(caps, {"X"}) == {}              # inside on this date
    assert un.classify(caps, set()) == {"X": un.ELIGIBLE}   # outside on the next


def test_holding_below_1000_sold_at_rebalance_whatever_its_rank():
    prev = {"KEEP": un.ELIGIBLE, "FALL": un.ELIGIBLE, "UP": un.ELIGIBLE, "DEAD": un.ELIGIBLE, "LOW": un.ELIGIBLE}
    all_caps = pd.Series({"KEEP": 1_400.0, "FALL": 900.0, "UP": 9_000.0, "LOW": 300.0})
    states = un.classify(all_caps[all_caps >= un.TRACK_FLOOR_CR], {"UP"}, prev)
    sold = un.sell_at_rebalance(prev, states, {"UP"}, all_caps)
    assert sold == {"FALL": un.SOLD_BELOW_FLOOR, "LOW": un.SOLD_BELOW_FLOOR,
                    "UP": un.SOLD_INTO_1000, "DEAD": un.SOLD_NO_CAP}
    assert "KEEP" not in sold


def test_turnover_counts_joiners_leavers_and_reasons():
    prev = {"A": un.ELIGIBLE, "B": un.ELIGIBLE, "C": un.ELIGIBLE, "D": un.ELIGIBLE, "T": un.TRACKED}
    now = {"A": un.ELIGIBLE, "B": un.TRACKED, "E": un.ELIGIBLE, "T": un.ELIGIBLE}
    all_caps = pd.Series({"A": 1_100.0, "B": 900.0, "C": 20_000.0, "E": 1_300.0, "T": 1_050.0})
    t = un.turnover(prev, now, all_caps, nifty_1000={"C"})
    assert (t.before, t.after) == (4, 3)
    assert t.joined == ["E", "T"]                  # a tracked name back over the line counts as a buy
    assert t.left == ["B", "C", "D"]
    assert t.left_why == {un.SOLD_BELOW_FLOOR: 1, un.SOLD_INTO_1000: 1, un.SOLD_NO_CAP: 1}
    assert t.rate == pytest.approx(3 / 4)
    assert t.as_dict()["rate"] == 0.75


def test_turnover_of_an_empty_list_has_no_rate():
    assert un.turnover({}, {"A": un.ELIGIBLE}, pd.Series({"A": 1_200.0}), set()).rate is None


def test_today_list_is_2000_outside_the_750():
    caps = pd.Series({"IN750": 90_000.0, "BIG": 2_000.0, "MID": 1_999.0})
    assert un.today_list(caps, {"IN750"}) == {"BIG"}


def test_nifty_1000_proxy_is_the_750_plus_the_largest_others():
    caps = pd.Series({f"S{i}": float(10_000 - i) for i in range(10)})
    tm = {"S9", "S8"}
    got = un.nifty_1000_proxy(caps, tm, size=5)
    assert got == {"S9", "S8", "S0", "S1", "S2"}


def test_cap_buckets():
    caps = pd.Series({"A": 1_200.0, "B": 2_500.0, "C": 12_000.0, "D": 900.0})
    b = un.cap_buckets(caps, ["A", "B", "C"])
    assert b["1,000-2,000"] == 1 and b["2,000-5,000"] == 1 and b["10,000+"] == 1 and b["800-1,000"] == 0


# ── The measurement script on a three-month fixture ─────────────────────────

class _Caps:
    def __init__(self, days):
        self.days = days

    def dates(self):
        return set(self.days)

    def read(self, day):
        return self.days[day]


def test_measure_lists_month_by_month_and_the_engine_timeline_sells_below_1000():
    from scripts import s198_measure as sm

    d1, d2, d3 = date(2026, 7, 31), date(2026, 8, 31), date(2026, 9, 30)
    big = {f"L{i}": 50_000.0 - i for i in range(3)}            # the 750 (here three names)
    days = {
        d1: _caps({**big, "AAA": 1_500.0, "BBB": 1_100.0, "CCC": 2_500.0, "DDD": 850.0}),
        d2: _caps({**big, "AAA": 1_600.0, "BBB": 950.0, "CCC": 2_600.0, "DDD": 1_050.0}),
        d3: _caps({**big, "AAA": 1_700.0, "BBB": 450.0, "CCC": 2_700.0, "DDD": 1_100.0}),
    }
    h750 = {"schema_version": 1, "baseline": {"date": "2026-01-01", "symbols": sorted(big)}, "changes": []}
    # The Nifty 1000 recorded (here: the 750 plus C) from d3 on; before it, the proxy (size 1000 takes all).
    h1000 = {"baseline": {"date": d3.isoformat(), "symbols": sorted(big) + ["CCC"]}, "changes": []}
    rows, tl, _ = sm.measure_lists(_Caps(days), sorted(days), h750, h1000)
    by = {r["date"]: r for r in rows}
    assert by[d1.isoformat()]["nifty_1000"] == "proxy" and by[d3.isoformat()]["nifty_1000"] == "recorded"
    # Proxy months: everything here is inside a 1000-name proxy, so nothing is eligible.
    assert by[d1.isoformat()]["eligible"] == 0
    assert by[d3.isoformat()]["eligible"] == 2                     # AAA and DDD; CCC inside the 1000, BBB below ₹500 Cr
    assert by[d3.isoformat()]["proxy_check"]["recorded"] == 4
    assert members_on(tl["ultra_nano"], d3) == {"AAA", "DDD"}
    # Today's list on the same dates: ≥ ₹2,000 Cr outside the 750.
    assert members_on(tl["nano_today"], d3) == {"CCC"}
    assert by[d3.isoformat()]["vs_today"]["today_only_inside_1000"] == 1


def test_measure_lists_tracks_and_sells_with_a_small_proxy(monkeypatch):
    from scripts import s198_measure as sm

    monkeypatch.setattr(un, "NIFTY_1000_SIZE", 3)
    monkeypatch.setattr(un.nifty_1000_proxy, "__defaults__", (3,))
    d1, d2, d3 = date(2026, 7, 31), date(2026, 8, 31), date(2026, 9, 30)
    big = {f"L{i}": 50_000.0 - i for i in range(3)}
    days = {
        d1: _caps({**big, "AAA": 1_500.0, "BBB": 1_100.0, "DDD": 850.0}),
        d2: _caps({**big, "AAA": 1_600.0, "BBB": 950.0, "DDD": 1_050.0}),
        d3: _caps({**big, "AAA": 1_700.0, "BBB": 450.0, "DDD": 1_100.0}),
    }
    h750 = {"schema_version": 1, "baseline": {"date": "2026-01-01", "symbols": sorted(big)}, "changes": []}
    rows, tl, _ = sm.measure_lists(_Caps(days), sorted(days), h750, None)
    r1, r2, r3 = rows
    assert (r1["eligible"], r1["priced_only"]) == (2, 1)            # A, B buyable; D priced only
    assert (r2["eligible"], r2["tracked"]) == (2, 1)                # A, D buyable; B tracked at ₹950 Cr
    assert r2["turnover"]["joined"] == 1 and r2["turnover"]["left"] == 1
    assert r2["sold_by_rule"] == {un.SOLD_BELOW_FLOOR: 1}           # B sold at the rebalance
    assert r3["tracked"] == 0                                       # B below ₹500 Cr: no longer tracked
    # The engine's timeline holds the eligible names only, so a holding below ₹1,000 Cr is not in
    # "the index" on the signal date and the backtester sells it (backtester._exit_reason).
    assert members_on(tl["ultra_nano"], d2) == {"AAA", "DDD"}


def test_month_ends_skip_an_unfinished_month():
    from scripts import s198_measure as sm

    held = {date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 29), date(2026, 10, 30), date(2026, 11, 20)}
    assert sm.month_ends(held, date(2026, 11, 24)) == [date(2026, 9, 30), date(2026, 10, 30)]
    held.add(date(2026, 11, 30))
    assert sm.month_ends(held, date(2026, 12, 1))[-1] == date(2026, 11, 30)


def test_pass_rule_is_applied_as_fixed():
    from scripts import s198_measure as sm

    runs = [{"system": "ultra_nano", "cost_bps": 60.0, "a_year": 0.20, "max_drawdown": -0.30,
             "context": {"nifty_total_market": 0.10}},
            {"system": "nano_today", "cost_bps": 60.0, "a_year": 0.25, "max_drawdown": -0.26, "context": {}}]
    assert sm.verdict(runs)["result"] == "pass"
    runs[0]["max_drawdown"] = -0.32                                   # 6 pts deeper than today's
    assert sm.verdict(runs)["result"] == "fail"
    assert sm.verdict(runs[:1])["result"].startswith("not decided")


def test_s224_walk_does_not_descend_into_dated_folders():
    from scripts import s224_r2_copies as rc

    tree = {"": (["archive/", "track_record/"], []),
            "archive/": (["archive/manifests/"], []),
            "archive/manifests/": (["archive/manifests/nse/"], []),
            "archive/manifests/nse/": (["archive/manifests/nse/2026-11-24/"], []),
            "track_record/": ([], ["track_record/track_record_nano.json"])}
    seen = []

    def lister(prefix):
        seen.append(prefix)
        return tree.get(prefix, ([], []))
    names = rc.walk(lister)
    assert "archive/manifests/nse/2026-11-24/" in names and "archive/manifests/nse/2026-11-24/" not in seen
    assert rc.matches(names)["a_track_record"]["track_record"] == ["track_record/", "track_record/track_record_nano.json"]
