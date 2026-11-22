"""Nifty 1000 is recorded from 21 Nov 2026 but not ranked (S175)."""
import copy
import importlib.util
import json
import pathlib

import pandas as pd

from src.core import config
from src.engine import index_universe as iu
from src.loaders import indices_loader as il

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("freeze_history", ROOT / "nse_index_rebuild" / "freeze_history.py")
fh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fh)

CSV_HEAD = "Company Name,Industry,Symbol,Series,ISIN Code\n"


def _csv(n: int) -> str:
    return CSV_HEAD + "".join(f"Co {i},X,SYM{i},EQ,INE{i:09d}\n" for i in range(n))


def test_nifty1000_is_recorded_but_not_in_the_ranked_lists():
    # The ranked universe is the union of INDICES_URLS: the 1000 must not be in it.
    assert "NIFTY 1000" not in config.INDICES_URLS
    assert "NIFTY 1000" in config.RECORDED_INDICES_URLS
    assert set(config.RECORDED_INDICES_URLS) == set(config.RECORDED_INDICES_LOCAL)


def test_recorded_list_is_written_and_kept_out_of_the_ranked_sync_result(tmp_path, monkeypatch):
    path = tmp_path / "ind_nifty1000_list.csv"
    monkeypatch.setattr(il, "RECORDED_INDICES_LOCAL", {"NIFTY 1000": str(path)})
    monkeypatch.setattr(il, "_download_index_csv", lambda *a, **k: _csv(1000))
    results = {"downloaded": {}, "errors": {}}
    il._sync_recorded_indices(results)
    assert path.read_text().count("\n") == 1001
    assert results["recorded"]["NIFTY 1000"]["count"] == 1000
    assert results["downloaded"] == {} and results["errors"] == {}


def test_a_short_or_failed_download_keeps_the_committed_list(tmp_path, monkeypatch):
    path = tmp_path / "ind_nifty1000_list.csv"
    path.write_text(_csv(1000))
    monkeypatch.setattr(il, "RECORDED_INDICES_LOCAL", {"NIFTY 1000": str(path)})
    for body in (_csv(400), None):
        monkeypatch.setattr(il, "_download_index_csv", lambda *a, _b=body, **k: _b)
        results = {"downloaded": {}, "errors": {}}
        il._sync_recorded_indices(results)
        assert "NIFTY 1000" in results["recorded_errors"]
        assert results["errors"] == {}                      # the 750's sync is not marked failed
        assert path.read_text().count("\n") == 1001         # yesterday's list kept


def test_an_index_first_recorded_after_the_freeze_does_not_move_its_hash():
    hist = json.loads((ROOT / "data" / "membership_history.json").read_text(encoding="utf-8"))
    later = copy.deepcopy(hist)
    later["indices"]["nifty_1000"] = {"baseline": {"date": "2026-11-21", "symbols": ["A", "B"]}, "changes": []}
    assert fh.digest(fh.frozen_view(later)) == fh.digest(fh.frozen_view(hist))


def test_the_nifty_1000_widens_the_long_price_file():
    # Owner, 22 Nov 2026: its members follow the 750's price process, the long file included.
    full = {"index": "nifty_total_market", "baseline": {"date": "2021-10-29", "symbols": ["A"]}, "changes": [],
            "indices": {"nifty_total_market": {"baseline": {"date": "2021-10-29", "symbols": ["A"]}, "changes": []},
                        "nifty_1000": {"baseline": {"date": "2026-11-21", "symbols": ["A", "NEWCO"]}, "changes": []}}}
    assert "NEWCO" in iu.all_ever_members(full)
    assert "nifty_1000" not in iu.RECORDED_ONLY


# ── from 1 Nov 2026 (owner, 21 Nov: "start date is 01-Nov for us") ──────────

from src.engine import nifty1000_backfill as nb  # noqa: E402


def _tm(baseline, changes):
    return {"baseline": {"date": "2021-10-29", "symbols": baseline}, "changes": changes}


def test_reconstruction_is_the_750_of_each_day_plus_the_published_extra():
    tm = _tm(["A", "B", "C"], [{"date": "2026-10-13", "added": ["D"], "removed": ["C"]},
                               {"date": "2026-11-04", "added": ["E"], "removed": []},
                               {"date": "2026-11-17", "added": [], "removed": ["E"]}])
    e = nb.reconstruct(tm, ["A", "B", "D", "X", "Y"], "2026-11-21")
    assert e["baseline"] == {"date": "2026-10-30", "symbols": ["A", "B", "D", "X", "Y"]}
    assert e["changes"] == [{"date": "2026-11-04", "added": ["E"], "removed": []},
                            {"date": "2026-11-17", "added": [], "removed": ["E"]}]
    assert "reconstructed" in e["note"].lower()


def test_a_list_that_differs_from_the_reconstruction_is_recorded_on_its_own_day():
    tm = _tm(["A", "B"], [])
    e = nb.reconstruct(tm, ["A", "B", "X"], "2026-11-21")
    assert nb.members_at(e, "2026-11-21") == {"A", "B", "X"}
    assert e["changes"] == []
    # a 750 member missing from the published 1000 leaves on the day it was seen
    e = nb.reconstruct(_tm(["A", "B", "Z"], []), ["A", "B", "X"], "2026-11-21")
    assert e["changes"] == [{"date": "2026-11-21", "added": [], "removed": ["Z"]}]


def test_the_nightly_step_backfills_once_and_then_appends(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("umh", ROOT / "scripts" / "update_membership_history.py")
    umh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(umh)
    from src.core import membership_history as mh
    hist = tmp_path / "membership_history.json"
    hist.write_text(json.dumps({"schema_version": 2, "indices": {
        "nifty_total_market": {"baseline": {"date": "2021-10-29", "symbols": ["AAA", "BBB"]}, "changes": []}}}))
    monkeypatch.setattr(mh, "HISTORY_FILE", str(hist))
    tm, n1000 = tmp_path / "tm.csv", tmp_path / "n1000.csv"
    tm.write_text("Symbol\nAAA\nBBB\n")
    n1000.write_text("Symbol\nAAA\nBBB\nCCC\n")
    monkeypatch.setattr(umh, "RECORDED", {"NIFTY TOTAL MARKET": str(tm), "NIFTY 1000": str(n1000)})
    umh.main()
    e = json.loads(hist.read_text())["indices"]["nifty_1000"]
    assert e["baseline"] == {"date": "2026-10-30", "symbols": ["AAA", "BBB", "CCC"]} and e["changes"] == []
    n1000.write_text("Symbol\nAAA\nBBB\nDDD\n")          # a later night: an ordinary change, no rebuild
    umh.main()
    e = json.loads(hist.read_text())["indices"]["nifty_1000"]
    assert e["baseline"]["date"] == "2026-10-30"
    assert [(c["added"], c["removed"]) for c in e["changes"]] == [(["DDD"], ["CCC"])]


def test_the_record_answers_from_the_close_that_signals_november_and_not_earlier():
    # 1 Nov 2026 is a Sunday: the November book is signalled at Friday 30 Oct's close.
    full = {"indices": {"nifty_1000": nb.reconstruct(_tm(["A"], []), ["A", "X"], "2026-11-21")}}
    h = iu.index_history("nifty_1000", full)
    from src.engine.membership import members_on
    assert members_on(h, "2026-10-30") == {"A", "X"}
    assert members_on(h, "2026-10-29") is None
    assert iu.first_month(h) == pd.Period("2026-11", "M")


def test_the_screener_sync_collects_nifty1000_members_outside_the_750(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("sync_screener", ROOT / "scripts" / "sync_screener.py")
    sync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync)
    nano, n1000 = tmp_path / "nano.csv", tmp_path / "n1000.csv"
    nano.write_text("Symbol\nNANO1\nBOTH\n")
    n1000.write_text("Symbol\nAAA\nBOTH\nSMALL1\n")
    monkeypatch.setattr(sync, "EXTRA_LIST", str(nano))
    monkeypatch.setattr(sync, "RECORDED_LIST", str(n1000))
    assert sync.extra_symbols(["AAA"]) == ["BOTH", "NANO1", "SMALL1"]
    monkeypatch.setattr(sync, "RECORDED_LIST", str(tmp_path / "missing.csv"))
    assert sync.extra_symbols(["AAA"]) == ["BOTH", "NANO1"]       # before the first sync writes the list


# ── S196: tracked like the other indices ─────────────────────────────────────

def test_the_committed_nifty_1000_holds_exactly_1000_on_every_recorded_date():
    # The reconstruction held 1,002 from 4 Nov to 14 Nov 2026: ENNATURE and IGLSPIRITS, which NSE's own
    # exclusion notices place outside the Nifty 1000, came in from the Total Market.
    hist = json.loads((ROOT / "data" / "membership_history.json").read_text(encoding="utf-8"))
    e = hist["indices"]["nifty_1000"]
    # A count other than 1,000 is allowed only for names an NSE notice names for the Nifty 1000 (a demerger's
    # listed company held for a few days, as the Total Market held ENNATURE); anything else is a wrong entry.
    ledger = json.loads((ROOT / "data" / "reference" / "nse" / "nifty1000_notices.json").read_text(encoding="utf-8"))
    named = {s for n in ledger["notices"] if n.get("mentions") for s in n["included"] + n["excluded"]}
    for d in [e["baseline"]["date"]] + [c["date"] for c in e["changes"]]:
        m = nb.members_at(e, d)
        if len(m) != 1000:
            added = {s for c in e["changes"] if c["date"] <= d for s in c["added"]}
            assert len(m) - 1000 <= len(added & named), (d, len(m))
    assert set(e["not_carried"]) == {"ENNATURE", "IGLSPIRITS"}
    assert all("Nifty 1000 is not listed" in v for v in e["not_carried"].values())


def test_a_name_not_in_the_1000_is_never_carried_and_later_records_are_kept():
    tm = _tm(["A", "B"], [{"date": "2026-11-04", "added": ["X"], "removed": []},
                          {"date": "2026-11-17", "added": [], "removed": ["X"]}])
    e = nb.reconstruct(tm, ["A", "B", "N"], "2026-11-22", not_in={"X": "notice"})
    assert e["changes"] == [] and nb.members_at(e, "2026-11-05") == {"A", "B", "N"}
    later = dict(e, changes=[{"date": "2026-12-01", "added": ["C"], "removed": ["N"]}])
    again = nb.rebuild(later, tm, "2026-11-22", not_in={"X": "notice"})
    assert again["changes"] == later["changes"] and again["not_carried"] == {"X": "notice"}


def test_every_nifty_1000_industry_is_one_of_the_750s():
    # Owner, 22 Nov 2026: "industry are same, N1000 file writes it differently". After the spelling fix (S194 F2)
    # every label must be one the 750's file uses, or a new NSE spelling would make a second sector.
    import pandas as pd

    from src.loaders.extra_universe_loader import nifty_1000_members
    from src.loaders.former_members import INDEX_FILE
    idx = pd.read_csv(INDEX_FILE)
    idx.columns = [str(c).strip() for c in idx.columns]
    assert set(nifty_1000_members()["Industry"]) <= set(idx["Industry"])



def test_a_new_nse_spelling_of_an_industry_is_matched_to_the_750s_label():
    # Owner, 22 Nov 2026: future spellings handled automatically, not one fix per spelling.
    from src.loaders.extra_universe_loader import nse_industry
    assert nse_industry("Oil, Gas & Consumable Fuels") == "Oil Gas & Consumable Fuels"
    assert nse_industry("oil gas and consumable fuels") == "Oil Gas & Consumable Fuels"
    assert nse_industry("Fast-Moving Consumer Goods") == "Fast Moving Consumer Goods"
    assert nse_industry("Space Tourism") == "Space Tourism"             # unknown: kept, and logged



def test_the_nightly_step_warns_when_the_nifty_1000_is_not_1000(capsys):
    import importlib.util
    spec = importlib.util.spec_from_file_location("umh", ROOT / "scripts" / "update_membership_history.py")
    umh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(umh)
    entry = {"baseline": {"date": "2026-11-22", "symbols": [f"S{i}" for i in range(1001)]}, "changes": []}
    msg = umh.size_warning("nifty_1000", entry, [f"S{i}" for i in range(1001)], "2026-11-23")
    assert msg and "holds 1001 names" in msg and "::warning::" in capsys.readouterr().out
    ok = {"baseline": {"date": "2026-11-22", "symbols": [f"S{i}" for i in range(999)]}, "changes": []}
    assert umh.size_warning("nifty_1000", ok, [f"S{i}" for i in range(999)] + ["DUMMYX1"], "2026-11-23") is None
