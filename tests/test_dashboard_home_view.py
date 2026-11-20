"""The home page rebuilt from the approved mock-up (S149)."""
import re
from pathlib import Path

import pandas as pd
import pytest

from src.ui.views import dashboard_home_view as hv

ROOT = Path(__file__).resolve().parents[1]


def test_the_dashboard_page_draws_the_new_home_view():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "render_home_view(rank_df, deep_adj_close" in src
    assert "from src.ui.views.dashboard_home_view import render_home_view" in src
    # The header's market line is left out on the Dashboard only.
    assert 'show_market=getattr(_nav, "title", "") != "Dashboard"' in src


def test_the_stylesheet_survives_streamlits_sanitiser_and_uses_theme_sizes():
    assert not re.search(r"<[/\w]", hv.HOME_CSS)
    assert not re.search(r"font-size:\s*\d", hv.HOME_CSS), "type sizes come from the theme (--fs-*)"


def test_every_contents_link_has_its_section():
    src = Path(hv.__file__).read_text(encoding="utf-8")
    for anchor in re.findall(r'\("(s-[a-z]+)", "', src):
        assert f'id="{anchor}"' in src, anchor


def test_signal_trails_are_three_cells_not_one_string():
    assert hv._trail_cell([44.2, None, 16.6], lambda v: f"{v:.0f}%") == ["44%", "—", "17%"]


def test_indian_money_formatting():
    assert hv.cr(114959) == "+₹1.15 lakh Cr"
    assert hv.cr(-37999.1) == "−₹38,000 Cr"
    assert hv.sg(-0.07, 2) == "−0.07" and hv.sg(0.0) == "0.0"


def test_book_sizes_read_book_risks_tiers():
    class R:
        tiers = {"Nifty 100": 0.05, "Midcap 150": 0.05, "Smallcap 250": 0.55, "Microcap 250": 0.35}
    assert hv._book_sizes(R()) == pytest.approx({"Large": 5.0, "Mid": 5.0, "Small": 55.0, "Micro": 35.0})


def test_strong_and_weak_is_one_table_with_a_cell_per_figure():
    weights = pd.DataFrame({"Industry": ["Healthcare", "Capital Goods"], "Weight": [29.8, 9.7], "Holdings": [6, 2]})
    sectors = pd.DataFrame({"Industry": ["Healthcare", "Capital Goods"], "rel_6m": [6.6, -0.2], "rel_1m": [5.8, -5.2]})
    rrg = pd.DataFrame({"Quadrant": ["Weakening", "Lagging"], "RS_Ratio": [103.7, 96.4], "RS_Momentum": [99.3, 91.2]},
                       index=["Healthcare", "Capital Goods"])
    paths = {"Healthcare": ["Weakening"] * 3, "Capital Goods": ["Improving", "Weakening", "Lagging"]}
    out = hv.section_strong_weak(weights, sectors, paths, rrg)
    assert "<table" in out and "29.8%" in out and "Strong · 29.8%" in out and "Weak · 9.7%" in out
    assert '<td class="dh-num dh-up">+6.6</td>' in out
    assert "Healthcare, the biggest at 30%, is slowing" in out
