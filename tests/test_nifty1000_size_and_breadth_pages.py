"""S194 L3/L4 (owner, 23 Nov 2026: "L3 yes", "ensure whatever required to update to different pages
like breadth, dashboard, market, etc etc is also updated").

L3: the Nifty 1000's other 250 are "Nano Cap" and anything outside the 1000 "Ultra Nano Cap" (owner,
23 Nov 2026: "Nifty indices available will carry their names. Added 250 after nifty 750 from N1000
are Nano Cap, after 1000, everything is Ultra Nano Cap"), on every page that splits a book by size.
L4: the 750's members-of-the-day breadth history is joined only under the 750's own live line; the
pages that compare a group with "the 750" name the system's universe instead.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from src.engine import book_exposure as bx
from src.engine import book_risk as br

ROOT = Path(__file__).resolve().parents[1]


def test_book_risk_gives_the_250_their_own_tier_and_keeps_nse_tiers_first(tmp_path):
    (tmp_path / "ind_niftymicrocap250_list.csv").write_text("Company Name,Symbol\nM,MMM\n")
    (tmp_path / "ind_nifty1000_list.csv").write_text("Company Name,Symbol\nM,MMM\nN,NNN\n")
    assert br.tier_of(["MMM", "NNN", "ZZZ"], tmp_path) == {
        "MMM": "Microcap 250", "NNN": "Nano Cap", "ZZZ": "Ultra Nano Cap"}


def test_the_dashboard_size_bar_counts_the_250_and_outside_names():
    from src.ui.views import dashboard_home_view as hv

    class Nifty750:
        tiers = {"Nifty 100": 0.25, "Midcap 150": 0.25, "Smallcap 250": 0.25, "Microcap 250": 0.2, "Cash": 0.05}

    class Nifty1000:
        tiers = {"Smallcap 250": 0.4, "Microcap 250": 0.3, "Nano Cap": 0.2, "Ultra Nano Cap": 0.05, "Cash": 0.05}

    assert list(hv._book_sizes(Nifty750())) == ["Large", "Mid", "Small", "Micro"]   # the 750 page unchanged
    sizes = hv._book_sizes(Nifty1000())
    assert sizes == pytest.approx({"Large": 0, "Mid": 0, "Small": 40, "Micro": 30, "Nano Cap": 20,
                                   "Ultra Nano Cap": 5})
    assert sum(sizes.values()) == pytest.approx(95)                                   # the invested share
    for k in sizes:   # every segment the bar draws has a colour
        assert f".{hv.size_class(k)}{{" in hv.HOME_CSS or f".{hv.size_class(k)}," in hv.HOME_CSS, k


def test_book_exposure_sizes_the_250_from_the_nifty_1000_history():
    membership = {"indices": {
        "nifty_microcap_250": {"baseline": {"date": "2026-01-01", "symbols": ["MMM"]}, "changes": []},
        "nifty_1000": {"baseline": {"date": "2026-10-30", "symbols": ["MMM", "NNN"]}, "changes": []}}}
    on = pd.Timestamp("2026-11-02")
    assert bx.size_of(["MMM", "NNN", "ZZZ"], on, membership) == {
        "MMM": "Micro", "NNN": "Nano Cap", "ZZZ": "Ultra Nano Cap"}
    # Before the index's history starts the boundary is unknown: "Other", as the kept rows say.
    assert bx.size_of(["NNN", "ZZZ"], pd.Timestamp("2026-10-01"), membership) == {"NNN": "Other", "ZZZ": "Other"}
    assert bx.SIZES[3:] == ("Micro", "Nano Cap", "Ultra Nano Cap", "Other")


def test_portfolio_reads_the_750s_exposure_file_only_for_the_750():
    src = (ROOT / "src" / "ui" / "views" / "portfolio_page.py").read_text(encoding="utf-8")
    assert "bx.load() if system == SYSTEM_750 else" in src


def test_actions_and_portfolio_show_the_nano_size():
    actions = (ROOT / "src" / "ui" / "views" / "actions_page.py").read_text(encoding="utf-8")
    assert "for k in bx.SIZES" in actions and "Nano Cap the Nifty 1000" in actions and "Ultra Nano Cap" in actions
    portfolio = (ROOT / "src" / "ui" / "views" / "portfolio_page.py").read_text(encoding="utf-8")
    assert "for k in drawn" in portfolio and "bx.SIZES" in portfolio


def test_the_750s_breadth_history_is_joined_only_under_the_750():
    """Every place that loads the 750's members-of-the-day history does so behind the system check."""
    found = 0
    for path in (ROOT / "src" / "ui").rglob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if 'pit_breadth.load("total_market")' in line:
                found += 1
                assert re.search(r'pit_breadth\.load\("total_market"\) if pit(_ok)? else None', line), f"{path.name}: {line.strip()}"
    assert found >= 4   # dashboard, market participation, market answers, market charts


def test_market_by_index_lists_the_250_where_the_system_ranks_them():
    from src.ui.views.market_view import index_members
    rank_df = pd.DataFrame({"Symbol": ["AAA", "NNN"], "Indices": ["MICRO250", "NANO250"]})
    assert index_members(rank_df, "NANO250") == ["NNN"]
    src = (ROOT / "src" / "ui" / "views" / "market_view.py").read_text(encoding="utf-8")
    assert '"NIFTY MICROCAP 250", NANOCAP_250_SHORT' in src


def test_sectors_name_the_systems_universe_and_leave_the_750_unchanged():
    from src.ui.views.dashboard_home_view import Chart, Cols
    from src.ui.views.sector_view import for_universe
    parts = ["Each month against the 750.", Chart("trows", {"label": "Each sector's lead over the 750"}),
             Cols(["The 750’s 12 stocks"], ["the 750"])]
    assert for_universe(parts, "750") is parts
    out = for_universe(parts, "1000")
    assert out[0] == "Each month against the 1000."
    assert out[1].spec["label"] == "Each sector's lead over the 1000"
    assert out[2].left == ["The 1000’s 12 stocks"] and out[2].right == ["the 1000"]
    assert for_universe(["Nifty 750 and 7500 stay"], "1000") == ["Nifty 750 and 7500 stay"]


def test_the_250_carry_the_owners_name_on_every_page():
    from src.engine.extra_universe import NANOCAP_250_NAME, ULTRA_NANO_NAME
    from src.ui.screener_table import INDEX_NAMES
    assert (NANOCAP_250_NAME, ULTRA_NANO_NAME) == ("Nano Cap", "Ultra Nano Cap")
    assert INDEX_NAMES["NANO250"] == "Nano Cap"
    stock = (ROOT / "src" / "ui" / "views" / "stock_view.py").read_text(encoding="utf-8")
    assert '"NANO250": "Nano Cap"' in stock


def test_every_system_has_a_universe_name():
    from src.engine.extra_universe import SYSTEMS, UNIVERSE_SHORT
    assert set(UNIVERSE_SHORT) == set(SYSTEMS) and UNIVERSE_SHORT["750"] == "750"


def test_portfolio_and_dashboard_name_the_systems_universe_not_the_750():
    portfolio = (ROOT / "src" / "ui" / "views" / "portfolio_page.py").read_text(encoding="utf-8")
    assert "UNIVERSE_SHORT.get(p.system" in portfolio and "the sector’s weight in the {uni}" in portfolio
    assert "At its first rebalance, {pd.Timestamp(first_date):%b %Y}" in portfolio   # S203 pf.exp.1
    assert '<span class="dh-num">The 750</span>' not in portfolio
    dash = (ROOT / "src" / "ui" / "views" / "dashboard_home_view.py").read_text(encoding="utf-8")
    assert '"Equal-weighted 750"' not in dash and "Nano Cap and Ultra Nano Cap are our own groups" in dash
