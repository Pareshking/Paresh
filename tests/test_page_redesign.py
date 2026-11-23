"""The redesigned pages: the figures they show are the right figures."""
import pandas as pd
import pytest

from src.ui import page_kit
from src.ui.views import qualified_view, sector_view


def _ranked():
    return pd.DataFrame({
        "Symbol": ["A", "B", "C", "D", "E", "F"],
        "Industry": ["Health", "Health", "Health", "Metals", "Metals", "Solo"],
        "Rank": [1, 60, 3, 200, 40, 5],
        "3M Return": [0.30, -0.10, 0.05, -0.20, 0.02, 0.9],
        "6M Return": [0.50, 0.00, 0.10, -0.30, 0.04, 1.0],
        "Above 50 EMA": [True, False, True, False, True, True],
        "Near 52W High": [True, False, False, False, True, True],
    })


def test_industry_board_uses_medians_and_the_screeners_own_flags():
    board, singles = sector_view.industry_board(_ranked())
    h = board.set_index("Industry").loc["Health"]
    assert h["Stocks"] == 3
    assert h["3M Return"] == pytest.approx(0.05)       # median, not the 0.30 outlier
    assert h["EMA %"] == pytest.approx(2 / 3)
    assert h["Pass"] == 1                               # A only: C is not near its high
    assert h["Top 50"] == 2                             # ranks 1 and 3
    assert h["Leaders"][:2] == ["A", "C"]               # by rank, not by return
    # A group of one is a stock, not an industry, and is named as left out.
    assert "Solo" not in board["Industry"].tolist()
    assert singles == ["Solo"]


def test_leader_links_escape_symbols_in_place():
    """The leaderboard's HTML went with the Sectors build (21 Nov 2026); its leader links stay escaped."""
    assert 'href="screener?stock=J%26K" target="_self"' in sector_view._leader_link("J&K")


def test_bar_list_clamps_and_flags():
    out = page_kit.bar_list([("A & B", 45.0, "45%", True), ("C", -3.0, "−3%", False)], scale=30)
    assert "A &amp; B" in out
    assert 'class="warn" style="width:100.0%"' in out
    assert 'style="width:0.0%"' in out


def test_industry_rows_fold_the_tail_into_others():
    df = pd.DataFrame({"Industry": list("AAABBCDEFGH")})
    rows = qualified_view.industry_rows(df)
    assert [r[0] for r in rows][:2] == ["A", "B"]
    assert rows[-1][0] == "2 others" and rows[-1][1] == 2   # G and H
    assert len(rows) == qualified_view.TOP_INDUSTRIES + 1


def test_alpha_is_shown_in_points_returns_in_percent():
    from src.ui import formats as fmt
    from src.ui import page_kit as kit

    assert fmt.pts(0.083) == "+8.3 pts" and fmt.pts(-0.012) == "−1.2 pts"
    assert kit.pts(0.083) == "+8.3 pts" and kit.pct(0.083) == "+8.3%"
    assert fmt.pts(None) == fmt.DASH


def test_a_small_trend_line_sits_beside_a_headline_figure():
    """S99 (owner, 8 Nov 2026): kit.spark_img, shared by the Dashboard strip and Portfolio."""
    import base64

    from src.ui import page_kit as kit
    from src.ui.tokens import C

    assert kit.spark_img([1, 2, 3]) == "" and kit.spark_img(None) == ""
    up = kit.spark_img([1, 2, 3, 4, 5, 6])
    down = kit.spark_img([6, 5, 4, 3, 2, 1])
    svg = lambda tag: base64.b64decode(tag.split("base64,")[1].split('"')[0]).decode()  # noqa: E731
    assert C.up in svg(up) and C.down in svg(down)
    assert kit.spark_img(range(100), last=63) == kit.spark_img(range(37, 100), last=None)
    assert kit.Reading("Since inception", "+41.4%", spark=up).spark == up
