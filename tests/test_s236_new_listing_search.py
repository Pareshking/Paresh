"""S236 F18: a stock NSE listed lately, too new for the ranking, is found by the Screener's search."""
from pathlib import Path

import pandas as pd

from src.loaders import nse_identity

ROOT = Path(__file__).resolve().parents[1]


def test_recent_listings_reads_nses_listing_dates(tmp_path):
    f = tmp_path / "EQUITY_L.csv"
    f.write_text("SYMBOL,NAME OF COMPANY, SERIES, DATE OF LISTING, PAID UP VALUE, MARKET LOT, ISIN NUMBER, FACE VALUE\n"
                 "HEGRAPHITE,HEG Limited,BE,27-NOV-2026,2,1,INE0Y9J01020,2\n"
                 "RELIANCE,Reliance Industries,EQ,29-NOV-1995,10,1,INE002A01018,10\n")
    got = nse_identity.recent_listings(pd.Timestamp("2025-11-28"), f)
    assert got == {"HEGRAPHITE": pd.Timestamp("2026-11-27")}


def test_the_search_offers_them_as_stocks():
    from src.ui.views import ranking_view as rv
    src = (ROOT / "src/ui/views/ranking_view.py").read_text(encoding="utf-8")
    assert '[STOCK] {sym} — listed {day:%-d %b %Y}' in src
    assert rv.search_label("[STOCK] HEGRAPHITE — listed 27 Nov 2026") == "HEGRAPHITE · listed 27 Nov 2026"


def test_a_falling_relative_strength_reads_in_the_down_colour():
    """S238 inventory (28 Nov): RELIANCE's "its relative strength fell 11.9%" was drawn in the up colour."""
    src = (ROOT / "src/ui/views/stock_view.py").read_text(encoding="utf-8")
    assert 'tone = "down" if len(rs) and float(rs.iloc[-1]) < 100 else "up"' in src
    assert "tone=tone)" in src
