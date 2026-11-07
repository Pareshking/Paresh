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


def test_the_screener_frame_never_scrolls_inside_the_page():
    # Owner, 8 Nov: blank space after row 750 on a phone. "Show all" is a
    # Streamlit button that redraws the frame at full height; the frame
    # carries no button of its own and its table does not scroll vertically.
    rows = pd.concat([_rows()] * 30, ignore_index=True)
    rows["Symbol"] = [f"S{i}" for i in range(len(rows))]
    rows["Rank"] = range(1, len(rows) + 1)
    paged = st_.table_html(rows, None, "Core (17)", page_rows=50, full=True)
    full = st_.table_html(rows, None, "Core (17)", full=True)
    assert 'id="showall"' not in paged and 'id="showall"' not in full
    assert ".wrap{height:auto;overflow-y:visible}" in full
    assert "nth-child(n+51){display:none}" in paged and "nth-child(n+51)" not in full
