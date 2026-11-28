"""28 Nov 2026: the weekly earnings run's R2 pack was live at 06:23 UTC and the Indices page still
read 25 Nov's table: the reader's cache was keyed on the repo's file, which a pack refresh does not
touch. A reader that serves a pack file keys its cache on the file it reads."""
from pathlib import Path

import pandas as pd

from src.engine import earnings_review as er


def test_earnings_reader_follows_a_new_pack(tmp_path, monkeypatch):
    repo = tmp_path / "screener_earnings.csv"
    pd.DataFrame({"quarter": ["Q1FY27"], "as_of": ["2026-11-25"]}).to_csv(repo, index=False)
    old_pack = tmp_path / "pack_a" / "screener_earnings.csv"
    new_pack = tmp_path / "pack_b" / "screener_earnings.csv"
    for p, day in ((old_pack, "2026-11-25"), (new_pack, "2026-11-28")):
        p.parent.mkdir()
        pd.DataFrame({"quarter": ["Q1FY27"], "as_of": [day]}).to_csv(p, index=False)

    served = {"path": old_pack}
    monkeypatch.setattr(er, "_pack", lambda path: served["path"])
    er._read.cache_clear()
    assert er.load(repo)["as_of"].iloc[0] == "2026-11-25"
    served["path"] = new_pack                     # R2's pack refreshed; the repo file untouched
    assert er.load(repo)["as_of"].iloc[0] == "2026-11-28"
    er._read.cache_clear()


def test_indices_stamp_names_the_pack_copy(tmp_path, monkeypatch):
    from src.ui import indices_data

    f = tmp_path / "pack_b" / "nse_indices_recent.csv"
    f.parent.mkdir()
    f.write_text("date\n")
    monkeypatch.setattr(indices_data, "_pack", lambda p: f if Path(p).name == f.name else p)
    assert str(f) in indices_data._stamp()


def test_ath_snapshot_reads_the_pack_copy(tmp_path, monkeypatch):
    from src.loaders import ath_loader as al

    repo = tmp_path / "nse_all_time_highs.csv"
    repo.write_text("Symbol,ATH,ATHDate,AsOf\nAAA,100,2026-11-20,2026-11-25\n")
    pack = tmp_path / "pack_b" / "nse_all_time_highs.csv"
    pack.parent.mkdir()
    pack.write_text("Symbol,ATH,ATHDate,AsOf\nAAA,120,2026-11-27,2026-11-27\n")
    al.clear_snapshot_cache()
    monkeypatch.setattr(al, "_pack", lambda p: pack)
    assert float(al.load_ath_snapshot(str(repo))["ATH"].iloc[0]) == 120.0
    al.clear_snapshot_cache()
