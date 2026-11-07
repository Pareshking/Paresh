"""Screener marks from the owner's parked items (S87, 7 Nov)."""
import pandas as pd

from src.ui import screener_table as st_


def _rows():
    return pd.DataFrame([
        {"Symbol": "AAA", "Rank": 1, "CMP": 100.0, "Score": 2.345, "Qualified Rank": 20,
         "Held": True, "Above 50 EMA": True, "Near 52W High": True, "% 50 EMA": 4.0, "% High": -3.0,
         "Volume": "High"},
        {"Symbol": "BBB", "Rank": 2, "CMP": 50.0, "Score": 2.1, "Qualified Rank": None,
         "Held": False, "Above 50 EMA": False, "Near 52W High": False, "% 50 EMA": -3.24, "% High": -28.4,
         "Volume": "Normal"},
    ])


def test_full_quant_shows_qualified_place_and_score():
    keys = [c[0] for c in st_.columns_for("Full Quant (35)")]
    assert keys[:5] == ["rank", "stock", "price", "qrank", "score"]
    assert "qrank" in [c[0] for c in st_.columns_for("Core (17)")]


def test_held_tag_cut_line_and_failed_filters_say_how_much():
    html = st_.table_html(_rows(), None, "Full Quant (35)")
    aaa = html.split('<tr data-stock="AAA"')[1].split("</tr>")[0]
    bbb = html.split('<tr data-stock="BBB"')[1].split("</tr>")[0]
    assert "class=held" in aaa and ">Held<" in aaa
    assert '<tr data-stock="AAA" class="cut">' in html and '<table class="byrank">' in html
    assert ">2.35<" in aaa and "Spike" in aaa
    assert "3.2% below its 50D EMA" in bbb and "−3.2%" in bbb
    assert "28.4% below its 52W high; the filter is within 20%" in bbb and "−28%" in bbb
    assert "Held" not in bbb
