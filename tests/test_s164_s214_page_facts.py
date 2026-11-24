"""S164 (staleness audit): the domestic-institutions tile reads NSE's own DII file, which runs a few sessions
behind; the days after it come from NSE's provisional all-exchange report, named as such and never added into
NSE's own total (the two cover different exchanges)."""
import pandas as pd

from src.ui.views import dashboard_home_view as d


def test_days_after_nse_s_last_are_read_from_the_provisional_report(monkeypatch):
    rows = pd.DataFrame({"date": ["2026-11-19", "2026-11-20", "2026-11-20", "2026-11-23", "2026-12-01"],
                         "category": ["DII", "DII", "FII/FPI", "DII", "DII"],
                         "net": [-100.0, -4859.8, 10308.4, -2760.12, 50.0]})
    monkeypatch.setattr(d, "_read_csv", lambda *a, **k: rows)
    net, days = d._dii_provisional_after(pd.Timestamp("2026-11-19"))
    assert round(net, 2) == -7619.92
    assert [f"{x:%d}" for x in days] == ["20", "23"]          # not 19 Nov (NSE's), not December


def test_nothing_after_the_last_day_gives_none(monkeypatch):
    rows = pd.DataFrame({"date": ["2026-11-19"], "category": ["DII"], "net": [-100.0]})
    monkeypatch.setattr(d, "_read_csv", lambda *a, **k: rows)
    assert d._dii_provisional_after(pd.Timestamp("2026-11-19")) is None


def test_the_tile_names_the_provisional_days():
    src = (d.__file__ and open(d.__file__, encoding="utf-8").read())
    assert 'f"Provisional, all exchanges, {when} {days[-1]:%b}: "' in src


def test_out_of_the_filters_is_the_site_s_word():
    from src.engine.dashboard_insights import rank_trail_word
    from src.ui.missing_words import OUT
    assert rank_trail_word([None, None, None], 20)[0] == OUT


def test_the_long_file_names_its_revision_in_the_page_metrics(tmp_path):
    """S214: which revision the Backtest read, and whether it was held or downloaded, is in the page's
    hidden metrics, so production's answer is read from the site."""
    from src.core import startup_metrics as metrics
    from src.loaders import nse_long
    f = tmp_path / "nse_long_close.parquet"
    f.write_bytes(b"x")
    (tmp_path / "nse_long_close.parquet.revision").write_text("r2:abcdef0123456789abcdef", encoding="utf-8")
    nse_long._note_source("nse_long_close.parquet", f, "held")
    assert metrics.public_snapshot()["facts"]["nse_long_close_revision"] == "r2:abcdef0123456789abcde held"
