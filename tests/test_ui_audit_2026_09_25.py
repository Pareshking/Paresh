"""Regressions from the 2026-09-25 UI audit: tickers with '&', escaping, watchlist."""

from src.ui import screener_table
from src.ui.views import sector_view, watchlist_view


def test_table_link_survives_an_ampersand_ticker():
    """?stock=M&M parsed as stock "M" -- the link opened the wrong page."""
    row = {"Symbol": "M&M", "Industry": "Autos <b>", "Rank": 1}
    html = screener_table._row_html(row, screener_table.columns_for("Core"), {})
    assert 'href="?stock=M%26M"' in html
    assert 'data-stock="M&amp;M"' in html
    assert "Autos &lt;b&gt;" in html


def test_sector_leader_link_survives_an_ampersand_ticker():
    html = sector_view._leader_link("J&KBANK")
    assert 'href="?stock=J%26KBANK"' in html
    assert ">J&amp;KBANK</a>" in html


def test_watchlist_never_reads_a_server_side_file():
    """The disk copy was shared by every visitor of the public deployment."""
    import inspect

    from src.ui import watchlist_store

    assert not hasattr(watchlist_view, "WATCHLIST_FILE")
    for mod in (watchlist_view, watchlist_store):
        src = inspect.getsource(mod)
        for call in ("open(", "write_text(", "read_text(", "json.dump", "json.load"):
            assert call not in src, f"{mod.__name__} touches the server's disk: {call}"
