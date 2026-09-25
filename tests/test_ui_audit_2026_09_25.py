"""Regressions from the 2026-09-25 UI audit: tickers with '&', escaping, watchlist."""
import pandas as pd

from src.ui.views import ranking_view, sector_view, watchlist_view


def test_card_link_survives_an_ampersand_ticker():
    """?stock=M&M parsed as stock "M" -- the card opened the wrong page."""
    row = pd.Series({"Symbol": "M&M", "Industry": "Autos <b>", "Rank": 1})
    html = ranking_view._card_html(row)
    assert 'href="?stock=M%26M"' in html
    assert "Autos &lt;b&gt;" in html


def test_sector_leader_link_survives_an_ampersand_ticker():
    html = sector_view._leader_link("J&KBANK")
    assert 'href="?stock=J%26KBANK"' in html
    assert ">J&amp;KBANK</a>" in html


def test_watchlist_never_reads_a_server_side_file(monkeypatch, tmp_path):
    """The disk copy was shared by every visitor of the public deployment."""
    monkeypatch.setattr(watchlist_view.st, "query_params", {})
    assert watchlist_view._load_persisted_watchlist() == ""
    watchlist_view._save_persisted_watchlist("ABB, TCS")
    assert watchlist_view.st.query_params["wl"] == "ABB, TCS"
    assert not hasattr(watchlist_view, "WATCHLIST_FILE")
