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
    # Rank 3M and 1M ago, then the qualified place now, then the score. The qualified place 3M and 1M ago
    # (Screener decision A, 21 Nov 2026) left the Screener (owner, 24 Nov 2026: "Qualified: Now only").
    assert keys[:7] == ["rank", "stock", "price", "p3", "p1", "qrank", "score"]
    assert "q3" not in keys and "q1" not in keys
    assert {"q3", "q1"} <= {c[0] for c in st_.columns_for("Watchlist")}   # the Watchlist keeps them
    assert "qrank" in [c[0] for c in st_.columns_for("Core (17)")]


def test_held_tag_cut_line_and_failed_filters_say_how_much():
    html = st_.table_html(_rows(), None, "Full Quant (35)")
    aaa = html.split('<tr data-stock="AAA"')[1].split("</tr>")[0]
    bbb = html.split('<tr data-stock="BBB"')[1].split("</tr>")[0]
    assert "class=held" in aaa and ">Held<" in aaa
    assert '<tr data-stock="AAA" class="cut">' in html and '<table class="byrank">' in html
    assert ">2.35<" in aaa and "Spike" in aaa
    assert "3.2% below its 50D EMA" in bbb and "−3.2%" in bbb
    assert "28.4% below its 52-week high; the filter is within 20%" in bbb and "−28%" in bbb
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


def test_the_qualified_place_alone_has_no_group_label():
    """Owner, 24 Nov 2026: "Qualified: Now only". Alone, the column is headed "Qualified #"; a "Qualified" group
    label over it would say it twice (as Score, S189 item 8)."""
    groups = dict((lab, n) for lab, n, _ in st_.column_groups([c[0] for c in st_.columns_for("Full Quant (35)")]))
    assert "Qualified" not in groups
    assert "Qualified" in [lab for lab, _, _ in st_.column_groups([c[0] for c in st_.columns_for("Watchlist")])]
