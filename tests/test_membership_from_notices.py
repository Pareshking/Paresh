"""Point-in-time membership rebuilt from NSE's own press releases.

The daily sync only began recording the Nifty Total Market list on 2026-08-19, so
every earlier backtest rebalance was scored on today's list and held names the
index only added later (MBAPL, PAISALO, SHREEJISPG and SIGMAADV all joined on
2026-09-30, yet the January-August book held them and the 1 Sep rebalance "sold"
them). NSE announces each change in a press release; the list on an earlier date
is the later list with those changes undone.
"""
from __future__ import annotations

import copy
import csv
import json
import sys
from datetime import date
from pathlib import Path

import pytest

import src.engine.pipeline  # noqa: F401  (pipeline first: it and momentum import each other)
from src.engine.membership import coverage, load_history, members_on, record_snapshot
from src.core.membership_history import coverage_gaps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import extend_membership_from_notices as emn  # noqa: E402
import parse_index_notices as pin  # noqa: E402

NOTICE = """\
PRESS RELEASE
Mumbai, February 23, 2026

                                    Replacements in indices
     These changes shall become effective from March 30, 2026 (close of March 27, 2026).

     2) Nifty 500

     The following companies are being excluded:

         Sr. No.                      Company Name                               Symbol
           1       Akums Drugs and Pharmaceuticals Ltd.                      AKUMS
           2       Mahindra & Mahindra Ltd.                                  M&M

     The following companies are being included:

         Sr. No.                      Company Name                               Symbol
           1       Aditya Infotech Ltd.                                      CPPLUS
                   Nam India Asset Management Company
           2       Ltd.                                                      NAM-INDIA

   3) Nifty 100

     The following company is being excluded:

         Sr. No.                      Company Name                               Symbol
           1       Havells India Ltd.                                        HAVELLS

  16) Nifty Total Market

     The following companies are being excluded:

         Sr. No.                      Company Name                               Symbol
           1       Akums Drugs and Pharmaceuticals Ltd.                      AKUMS
   Sr. No.                      Company Name                               Symbol
           2       Dummy Entity Ltd.                                         DUMMYXYZ

     The following company is being included:

         Sr. No.                      Company Name                               Symbol
           1       Aditya Infotech Ltd.                                      CPPLUS
"""


# ── the parser ───────────────────────────────────────────────────────────────

def test_the_parser_reads_dates_and_the_right_section_only():
    assert pin.issued_on(NOTICE) == date(2026, 2, 23)
    assert pin.effective_dates(NOTICE) == [date(2026, 3, 30)]
    assert pin.sections(NOTICE, "Nifty 500") == {
        "excluded": ["AKUMS", "M&M"], "included": ["CPPLUS", "NAM-INDIA"]}
    assert pin.sections(NOTICE, "Nifty 100") == {"excluded": ["HAVELLS"]}
    # the table's repeated page header does not break the serial run
    assert pin.sections(NOTICE, "Nifty Total Market") == {
        "excluded": ["AKUMS", "DUMMYXYZ"], "included": ["CPPLUS"]}
    assert pin.sections(NOTICE, "Nifty Next 50") == {}


def test_a_dropped_row_is_an_error_not_a_shorter_list():
    broken = NOTICE.replace("           2       Mahindra & Mahindra Ltd.                                  M&M\n", "")
    broken = broken.replace("           1       Akums Drugs and Pharmaceuticals Ltd.                      AKUMS\n",
                            "           2       Akums Drugs and Pharmaceuticals Ltd.                      AKUMS\n", 1)
    with pytest.raises(pin.NoticeParseError):
        pin.sections(broken, "Nifty 500")


def test_placeholders_are_dropped_from_the_ledger():
    assert emn._tradeable(["AKUMS", "DUMMYXYZ", "M&M"]) == ["AKUMS", "M&M"]


# ── rewinding ────────────────────────────────────────────────────────────────

def _history(symbols, day="2026-08-19", changes=()):
    return {"index": emn.INDEX, "baseline": {"date": day, "symbols": sorted(symbols)},
            "changes": list(changes)}


def _ledger(*notices, unexplained=None):
    return {"notices": [dict({"issued": None, "url": "", "sha256": ""}, **n) for n in notices],
            "known_unexplained": unexplained or {}}


def _n(name, eff, inc, exc):
    return {"notice": name, "effective": eff, "included": sorted(inc), "excluded": sorted(exc)}


def test_rewinding_undoes_each_change_in_reverse_order():
    # truth: A,B,C on 12-31;  B->D on 03-30;  D->E on 05-12  =>  A,C,E on 08-19
    hist = _history({"A", "C", "E"})
    led = _ledger(_n("n1", "2026-03-30", {"D"}, {"B"}), _n("n2", "2026-05-12", {"E"}, {"D"}))
    out, report = emn.reconstruct(hist, led, "2025-12-31")
    assert out["baseline"] == {"date": "2025-12-31", "symbols": ["A", "B", "C"]}
    assert [c["date"] for c in out["changes"]] == ["2026-03-30", "2026-05-12"]
    assert members_on(out, "2026-03-29") == {"A", "B", "C"}
    assert members_on(out, "2026-03-30") == {"A", "C", "D"}
    assert members_on(out, "2026-08-19") == {"A", "C", "E"}
    assert members_on(out, "2025-12-30") is None  # honest: no record before the baseline
    assert report["status"] == "extended" and report["list_sizes_seen"] == [3]


def test_rewinding_twice_changes_nothing():
    hist = _history({"A", "C", "E"})
    led = _ledger(_n("n1", "2026-03-30", {"D"}, {"B"}), _n("n2", "2026-05-12", {"E"}, {"D"}))
    once, _ = emn.reconstruct(hist, led, "2025-12-31")
    again, report = emn.reconstruct(once, led, "2025-12-31")
    assert again == once and report["status"] == "already covers"


def test_later_recorded_changes_are_kept_after_the_rewound_ones():
    later = [{"date": "2026-09-30", "added": ["Z"], "removed": ["E"]}]
    out, _ = emn.reconstruct(_history({"A", "E"}, changes=later),
                             _ledger(_n("n1", "2026-03-30", {"E"}, {"B"})), "2025-12-31")
    assert [c["date"] for c in out["changes"]] == ["2026-03-30", "2026-09-30"]
    assert members_on(out, "2026-09-30") == {"A", "Z"}


@pytest.mark.parametrize("notice, why", [
    (_n("bad1", "2026-03-30", {"GHOST"}, {"B"}), "included but not in the list"),
    (_n("bad2", "2026-03-30", {"D"}, {"A"}), "excluded but still in the list"),
    (_n("bad3", "2026-03-30", {"D"}, {"D"}), "both included and excluded"),
])
def test_a_notice_that_does_not_fit_the_recorded_list_stops_the_run(notice, why):
    with pytest.raises(emn.ReconstructionError, match=why):
        emn.reconstruct(_history({"A", "D"}), _ledger(notice), "2025-12-31")


def test_an_older_notice_that_contradicts_the_rewound_list_stops_the_run():
    # A was included on 2025-12-26, so it must be in the list on 2025-12-31.
    hist = _history({"B", "C"})
    led = _ledger(_n("old", "2025-12-26", {"A"}, set()), _n("n1", "2026-03-30", {"C"}, {"D"}))
    with pytest.raises(emn.ReconstructionError, match="contradicts notices"):
        emn.reconstruct(hist, led, "2025-12-31")
    # ...unless the ledger records that name as unexplained
    out, report = emn.reconstruct(hist, _ledger(*led["notices"], unexplained={"A": "why"}), "2025-12-31")
    assert report["known_unexplained_skipped"] == ["A"] and "A" not in out["baseline"]["symbols"]


def test_a_ticker_change_is_followed_not_mistaken_for_an_exit():
    # OLD was included on 2025-10-01 under its old ticker and trades as NEW from
    # 2025-10-16 on; NSE issues no notice for a plain ticker change.
    notice = _n("n1", "2026-03-30", {"CCC"}, {"DDD"})
    old = _n("old", "2025-10-01", {"OLD"}, set())
    plain = _ledger(old, notice)
    with pytest.raises(emn.ReconstructionError, match="contradicts notices"):
        emn.reconstruct(_history({"BBB", "NEW", "CCC"}), plain, "2025-12-31")
    aliased = dict(plain, symbol_aliases={"OLD": {"new_symbol": "NEW", "effective": "2025-10-16"}})
    out, report = emn.reconstruct(_history({"BBB", "NEW", "CCC"}), aliased, "2025-12-31")
    assert report["aliases_followed"] == ["OLD"] and "NEW" in out["baseline"]["symbols"]


def test_the_two_copies_in_the_file_must_agree_before_either_is_rewritten():
    flat = _history({"A", "E"})
    ext, _ = emn.reconstruct(flat, _ledger(_n("n1", "2026-03-30", {"E"}, {"B"})), "2025-12-31")
    good = dict(flat, indices={emn.INDEX_KEY: {"baseline": flat["baseline"], "changes": flat["changes"]}})
    written = emn._apply_to_file(good, ext)
    assert written["indices"][emn.INDEX_KEY]["baseline"] == written["baseline"] == ext["baseline"]
    bad = copy.deepcopy(good)
    bad["indices"][emn.INDEX_KEY]["baseline"] = {"date": "2026-08-19", "symbols": ["A"]}
    with pytest.raises(emn.ReconstructionError, match="differs from the flat history"):
        emn._apply_to_file(bad, ext)


def test_the_daily_sync_can_still_append_to_a_rewound_history():
    out, _ = emn.reconstruct(_history({"AAA", "EEE"}),
                             _ledger(_n("n1", "2026-03-30", {"EEE"}, {"BBB"})), "2025-12-31")
    nxt, changed = record_snapshot(out, "2026-10-02", ["AAA", "FFF"])
    assert changed and nxt["changes"][-1] == {"date": "2026-10-02", "added": ["FFF"],
                                              "removed": ["EEE"]}


# ── the committed data ───────────────────────────────────────────────────────

LEDGER = json.loads((ROOT / "data" / "membership_notices.json").read_text(encoding="utf-8"))
HISTORY = load_history()


def test_the_committed_history_now_reaches_back_to_the_first_signal_of_2026():
    first, last = coverage(HISTORY)
    assert first == date(2025, 12, 31) and last >= date(2026, 9, 30)


def test_the_committed_history_agrees_with_every_notice_in_the_ledger():
    assert emn.check(HISTORY, LEDGER) == []


def test_nothing_is_left_unexplained_and_the_one_ticker_change_is_recorded():
    assert LEDGER["known_unexplained"] == {}
    a = LEDGER["symbol_aliases"]["SUNDARMHLD"]
    assert a["new_symbol"] == "TSFINV" and a["isin"] == "INE202Z01029"
    # the same security stays in the list through the whole window, under its new ticker
    for day in ("2025-12-31", "2026-03-30", "2026-08-19", "2026-09-29"):
        assert "TSFINV" in members_on(HISTORY, day) and "SUNDARMHLD" not in members_on(HISTORY, day)


def test_total_market_tracks_temporary_listed_corporate_action_members():
    dates = [HISTORY["baseline"]["date"]] + [c["date"] for c in HISTORY["changes"]]
    counts = {d: len(members_on(HISTORY, d)) for d in dates}
    assert counts["2026-06-15"] == 754
    assert counts["2026-06-19"] == 752
    assert counts["2026-06-23"] == 751
    assert counts["2026-06-24"] == 750
    assert counts["2026-07-17"] == counts["2026-09-30"] == 750


def test_the_30_sep_notice_matches_what_the_daily_sync_recorded_for_that_day():
    n = next(n for n in LEDGER["notices"] if n["effective"] == "2026-09-30")
    change = next(c for c in HISTORY["changes"] if c["date"] == "2026-09-30")
    assert set(n["included"]) == set(change["added"]) and set(n["excluded"]) == set(change["removed"])


@pytest.mark.parametrize("symbol, first_day", [
    ("SIGMAADV", "2026-09-30"), ("MBAPL", "2026-09-30"), ("PAISALO", "2026-09-30"),
    ("SHREEJISPG", "2026-09-30"), ("LENSKART", "2026-03-30"), ("GRINDWELL", "2026-07-17"),
])
def test_a_name_is_in_the_list_only_from_the_day_nse_added_it(symbol, first_day):
    day = date.fromisoformat(first_day)
    assert symbol not in members_on(HISTORY, date.fromordinal(day.toordinal() - 1))
    assert symbol in members_on(HISTORY, day)


def test_march_changes_take_effect_on_the_effective_date_not_the_announcement():
    # announced 2026-02-23, effective 2026-03-30 (close of 03-27)
    n = next(n for n in LEDGER["notices"] if n["notice"] == "ind_prs23022026.pdf")
    assert n["effective"] == "2026-03-30" and n["issued"] == "2026-02-23"
    for s in n["included"]:
        assert s not in members_on(HISTORY, "2026-03-27") and s in members_on(HISTORY, "2026-03-30")
    for s in n["excluded"]:
        assert s in members_on(HISTORY, "2026-03-27") and s not in members_on(HISTORY, "2026-03-30")


def test_every_ledger_notice_carries_its_source_and_a_checksum():
    for n in LEDGER["notices"]:
        assert n["url"].startswith("https://www.niftyindices.com/Press_Release/ind_prs")
        assert len(n["sha256"]) == 64 and n["effective"]
        assert len(n["included"]) == len(n["excluded"])  # a constant-size index swaps names


def test_the_backtester_now_scores_the_whole_2026_window_on_the_index_as_it_stood():
    from src.engine.backtester import _index_mask
    import pandas as pd

    cols = pd.Index(["SIGMAADV", "LENSKART", "TCS"])
    jan = _index_mask(HISTORY, cols, pd.Timestamp("2026-01-30"))
    assert jan is not None and jan.to_dict() == {"SIGMAADV": False, "LENSKART": False, "TCS": True}
    assert _index_mask(HISTORY, cols, pd.Timestamp("2025-12-30")) is None  # before the record


MULTI_HISTORY = json.loads((ROOT / "data" / "membership_history.json").read_text(encoding="utf-8"))


def _members_on_index(key: str, on: str) -> set[str]:
    entry = MULTI_HISTORY["indices"][key]
    target = date.fromisoformat(on)
    members = set(entry["baseline"]["symbols"])
    if target < date.fromisoformat(entry["baseline"]["date"]):
        raise ValueError("requested date predates membership baseline")
    for change in entry["changes"]:
        if date.fromisoformat(change["date"]) > target:
            break
        members.update(change.get("added", []))
        members.difference_update(change.get("removed", []))
    return members


def test_all_six_histories_cover_the_start_of_2026():
    gaps = coverage_gaps(MULTI_HISTORY)
    assert set(gaps) == {
        "nifty_50", "nifty_next_50", "nifty_midcap_150",
        "nifty_smallcap_250", "nifty_microcap_250", "nifty_total_market",
    }
    assert all(g["status"] == "covered" for g in gaps.values())
    assert all(g["actual_start"] == "2025-12-31" for g in gaps.values())


def test_reconstructed_histories_replay_to_today_csvs_without_dummy_symbols():
    paths = {
        "nifty_50": "data/indices/ind_nifty50list.csv",
        "nifty_next_50": "data/indices/ind_niftynext50list.csv",
        "nifty_midcap_150": "data/indices/ind_niftymidcap150list.csv",
        "nifty_smallcap_250": "data/indices/ind_niftysmallcap250list.csv",
        "nifty_microcap_250": "data/indices/ind_niftymicrocap250_list.csv",
        "nifty_total_market": "data/indices/ind_niftytotalmarket_list.csv",
    }
    expected_counts = {
        "nifty_50": 50, "nifty_next_50": 50, "nifty_midcap_150": 150,
        "nifty_smallcap_250": 250, "nifty_microcap_250": 250,
        "nifty_total_market": 750,
    }
    for key, relative_path in paths.items():
        entry = MULTI_HISTORY["indices"][key]
        assert entry["baseline"]["date"] == "2025-12-31"
        members = set(entry["baseline"]["symbols"])
        assert not any(s.startswith("DUMMY") for s in members)
        previous_date = entry["baseline"]["date"]
        for change in entry["changes"]:
            assert change["date"] > previous_date
            previous_date = change["date"]
            members.update(change["added"])
            members.difference_update(change["removed"])
            assert not any(s.startswith("DUMMY") for s in members)
            if change["date"] >= "2026-03-30":
                expected = expected_counts[key]
                if key in {"nifty_next_50", "nifty_total_market"}:
                    expected = {"2026-06-15": 54, "2026-06-19": 52,
                                "2026-06-23": 51, "2026-06-24": 50}.get(change["date"], expected)
                assert len(members) == expected, (key, change["date"], len(members))
        with (ROOT / relative_path).open(encoding="utf-8", newline="") as fh:
            rows = csv.DictReader(fh)
            symbol_col = next(k for k in rows.fieldnames if k.lower() == "symbol")
            current = {row[symbol_col].strip().upper() for row in rows
                       if row[symbol_col].strip() and not row[symbol_col].strip().upper().startswith("DUMMY")}
        assert members == current, (key, sorted(current - members), sorted(members - current))


def test_rename_and_midyear_replacements_are_real_timeline_events():
    small = MULTI_HISTORY["indices"]["nifty_smallcap_250"]
    rename = next(c for c in small["changes"] if c["date"] == "2026-04-15")
    assert rename["added"] == ["JSWDULUX"] and rename["removed"] == ["AKZOINDIA"]
    july = next(c for c in small["changes"] if c["date"] == "2026-07-17")
    assert july["added"] == ["PFOCUS"] and july["removed"] == ["JBCHEPHARM"]
    micro = MULTI_HISTORY["indices"]["nifty_microcap_250"]
    july_micro = next(c for c in micro["changes"] if c["date"] == "2026-07-17")
    assert july_micro["added"] == ["GRINDWELL"] and july_micro["removed"] == ["PFOCUS"]
    assert "TSFINV" in _members_on_index("nifty_microcap_250", "2026-09-29")
    assert "TSFINV" not in _members_on_index("nifty_microcap_250", "2026-09-30")
