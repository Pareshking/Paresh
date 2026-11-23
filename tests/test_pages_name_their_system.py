"""S193 item C (owner, 23 Nov 2026: "Rest all with your recommendation"): every page follows the
chosen system, or says what it shows.

K1 labels named the 750 under every system; K2 sentences stated what is true only of the 750;
K3 (the momentum test named "this ranking's") is held for the owner, as Dashboard requirement 43
fixes that caption; K4 divided the > ₹2,000 Cr list's flows by the market value of the 192 of its 411 stocks NSE's file covers; K5 Backtest ignored the system silently.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def _src(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_no_page_label_names_the_750_for_every_system():
    # K1: the literal forms that were wrong under ?sys=1000 / nano / combined.
    banned = re.compile(r"of the 750 above their 200D EMA|\"All 750\"")
    for path in [*ROOT.glob("src/ui/**/*.py"), *ROOT.glob("static/*.js")]:
        assert not banned.search(path.read_text(encoding="utf-8")), path


def test_breadth_chart_readout_carries_the_systems_universe():
    from src.ui.views.dashboard_home_view import _breadth_spec

    idx = pd.bdate_range("2026-01-01", periods=30)
    n500 = pd.Series(range(30), index=idx, dtype=float) + 100
    spec = _breadth_spec(n500, pd.Series(50.0, index=idx), idx[-1], "> ₹2,000 Cr list")
    assert spec["uni"] == "> ₹2,000 Cr list"
    assert "of the ${esc(s.uni || '750')} above their 200D EMA" in _src("static/dash_charts.js")


def test_market_note_says_members_of_each_date_only_when_it_is_so():
    src = _src("src/ui/views/market_questions_view.py")
    assert '("Members of each date, leavers included." if pit else' in src
    assert "_breadth_charts(bench.dropna(), share200, weekly, nnh, pit, universe)" in src


def test_portfolio_names_the_books_own_size_groups():
    import dataclasses

    from src.ui.views import portfolio_page as pp

    exposure = pd.DataFrame({"kind": ["size"] * 4, "date": pd.to_datetime(["2026-10-01"] * 2 + ["2026-11-02"] * 2),
                             "name": ["Small", "Micro", "Nano Cap", "Ultra Nano Cap"], "weight": [60, 40, 41, 59]})
    blank = {f.name: None for f in dataclasses.fields(pp.Page)}
    blank.update(exposure=exposure)
    assert pp.book_size_words(pp.Page(**blank)) == "Ultra Nano Cap and Nano Cap"
    blank.update(exposure=pd.DataFrame())
    assert pp.book_size_words(pp.Page(**blank)) == "Small Cap and Micro Cap"
    assert "The book is mostly Small Cap and Micro Cap" not in _src("src/ui/views/portfolio_page.py")


def test_market_caps_cover_the_whole_list(tmp_path):
    from src.loaders.extra_universe_loader import system_market_caps

    nse = tmp_path / "nse.csv"
    pd.DataFrame({"Symbol": ["A", "B"], "MarketCap": [3e11, 2e11]}).to_csv(nse, index=False)
    lst = tmp_path / "list.csv"
    pd.DataFrame({"Company Name": ["A", "C", "D"], "Industry": ["X"] * 3, "Symbol": ["A", "C", "D"],
                  "Series": ["EQ"] * 3, "ISIN Code": [""] * 3, "MarketCapCr": [9999.0, 2500.0, 2100.0]}).to_csv(lst, index=False)
    caps = system_market_caps(["A", "C", "D", "E"], str(nse), str(lst))
    assert caps["A"] == 3e11                     # NSE's own figure first
    assert caps["C"] == 2500 * 1e7 and caps["D"] == 2100 * 1e7   # the list's month-end value for the rest
    assert "E" not in caps                       # neither has it: left out, not zero


def test_backtest_and_guide_say_what_the_system_changes():
    assert "does not change these runs" in _src("src/ui/views/backtest_view.py")
    assert "follow the same steps on their own lists" in _src("src/ui/views/guide_view.py")


def test_nightly_snapshot_keeps_the_lists_stocks(tmp_path, monkeypatch):
    # K4's root cause: daily_sync read NSE's whole market-cap file but committed only the 750 and the 1000.
    import importlib.util

    import src.loaders.extra_universe_loader as xl

    lst = tmp_path / "list.csv"
    pd.DataFrame({"Symbol": ["AAA", "BBB", "aaa ", "CCC"]}).to_csv(lst, index=False)
    monkeypatch.setattr(xl, "LIST_PATH", str(lst))
    spec = importlib.util.spec_from_file_location("sync_data_t", ROOT / "scripts" / "sync_data.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod._extra_list_symbols({"BBB"}) == ["AAA", "CCC"]
    assert "cap_symbols += _extra_list_symbols(set(cap_symbols))" in _src("scripts/sync_data.py")
