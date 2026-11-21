"""Nifty 1000 is recorded from 21 Nov 2026 but not ranked (S175)."""
import copy
import importlib.util
import json
import pathlib

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


def test_recorded_only_lists_do_not_widen_the_long_price_file():
    full = {"index": "nifty_total_market", "baseline": {"date": "2021-10-29", "symbols": ["A"]}, "changes": [],
            "indices": {"nifty_total_market": {"baseline": {"date": "2021-10-29", "symbols": ["A"]}, "changes": []},
                        "nifty_1000": {"baseline": {"date": "2026-11-21", "symbols": ["A", "NEWCO"]}, "changes": []}}}
    assert "NEWCO" not in iu.all_ever_members(full)
    assert "nifty_1000" in iu.RECORDED_ONLY
