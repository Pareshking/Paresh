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


def test_strong_and_weak_is_cards_with_rotation_and_a_chart():
    """v8 (owner, 20 Nov 2026): the v7 cards, each industry's figures and rotation, the book's segments as a chart."""
    weights = pd.DataFrame({"Industry": ["Healthcare", "Capital Goods"], "Weight": [29.8, 9.7], "Holdings": [6, 2]})
    sectors = pd.DataFrame({"Industry": ["Healthcare", "Capital Goods"], "rel_6m": [6.6, -0.2], "rel_1m": [5.8, -5.2]})
    rrg = pd.DataFrame({"Quadrant": ["Weakening", "Lagging"], "RS_Ratio": [103.7, 96.4], "RS_Momentum": [99.3, 91.2]},
                       index=["Healthcare", "Capital Goods"])
    paths = {"Healthcare": ["Weakening"] * 3, "Capital Goods": ["Improving", "Weakening", "Lagging"]}
    parts = hv.section_strong_weak(weights, sectors, paths, rrg)
    out = hv.html_of(parts)
    assert ">Strong</h3>" in out and "29.8%" in out and ">Weak</h3>" in out and "9.7%" in out
    assert '<span class="dh-mono dh-up">+6.6</span>' in out
    assert "Rotation: Weakening → Weakening → <b>Weakening</b>" in out
    assert "Healthcare, the biggest at 30%, is slowing" in out
    assert "Show the table" in out
    charts = [p for p in parts if isinstance(p, hv.Chart)]
    assert [c.kind for c in charts] == ["segbar"] and charts[0].spec["segs"][0][0] == "Healthcare"


def test_rank_trail_is_an_image_the_cleaner_keeps():
    """st.html drops inline SVG; the trail is an <img> with the theme's colours written in."""
    img = hv._rank_trail_svg([21, 3, 38], 40)
    assert img.startswith('<img class="dh-trail"') and "data:image/svg+xml," in img
    assert "var(--" not in img and 'alt="Rank trail #21 → #3 → #38"' in img


def test_every_chart_has_its_explanation_and_table():
    h = hv.how("What.", "How.", ["Month", "Lead"], [["Oct 2026", "-3.40"]])
    assert "What it is · how to read it" in h and "Show the table" in h and "−3.40" in h


def test_a_signal_that_did_not_pass_is_shown_but_not_used():
    """S150: the participation jump was counted for momentum; its test does not pass."""
    from src.ui.views import dashboard_home_view as v
    t_pass = {"passed": True, "on": -0.23, "off": 1.16, "n_on": 52, "n": 201, "halves": [-2.1, -0.8]}
    t_fail = {"passed": False, "on": 0.85, "off": 0.79, "n_on": 46, "n": 201, "halves": [0.7, -0.6]}
    signals = [
        {"key": "breadth_thin", "name": "Breadth thin", "sub": "", "cells": ["55%", "34%", "50%"], "on": False,
         "test": t_pass, "like": 1.16, "flip": "Back to 40% or below"},
        {"key": "participation_jump", "name": "Participation jump", "sub": "", "cells": ["50%", "20%", "56%"], "on": True,
         "test": t_fail, "like": None, "flip": "A month without a jump"},
    ]
    html = v.html_of(v.section_momentum([("12 months", 12.2, "")], 0, signals, 0.8))
    assert "1 pass" in html and "1 is not confirmed" in html
    assert "Not confirmed" in html and "Not used" in html and "the halves disagree" in html
    assert "1 point to a stronger month" in html and "0 to a weaker one" in html
