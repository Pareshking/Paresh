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
    assert "_breadth_charts(bench.dropna(), share200, weekly, nnh, pit, universe, name)" in src


def test_portfolio_names_the_books_own_size_groups():
    import dataclasses

    from src.ui.views import portfolio_page as pp

    exposure = pd.DataFrame({"kind": ["size"] * 4, "date": pd.to_datetime(["2026-10-01"] * 2 + ["2026-11-02"] * 2),
                             "name": ["Small", "Micro", "Nano Cap", "Ultra Nano Cap"], "weight": [60, 40, 41, 59]})
    blank = {f.name: None for f in dataclasses.fields(pp.Page)}
    blank.update(exposure=exposure)
    assert pp.book_size_words(pp.Page(**blank)) == "Ultra Nano Cap and Nano Cap"
    blank.update(exposure=pd.DataFrame())
    assert pp.book_size_words(pp.Page(**blank)) == ""      # no size split: no claim (S203 pf.ret.4)
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


def test_market_size_rows_survive_a_nifty_500_close_the_stocks_do_not_have(monkeypatch):
    # 23 Nov 2026, after the close: the live Nifty 500 had 23 Nov, the stocks and the size indices 20 Nov.
    # The one-session rule emptied every size index and "By size" showed the Nifty 500 alone.
    import src.ui.views.market_questions_view as mqv

    idx = pd.bdate_range("2026-01-01", "2026-11-20")
    prices = pd.DataFrame({"A": range(len(idx))}, index=idx, dtype=float) + 100
    bench = pd.Series(range(len(idx) + 1), index=idx.append(pd.DatetimeIndex(["2026-11-23"])), dtype=float) + 100
    size = {"Nifty Microcap 250": pd.Series(range(len(idx)), index=idx, dtype=float) + 50}
    seen = {}
    monkeypatch.setattr(mqv, "_answers", lambda key, px, ind, b, s, pit, name: seen.update(b=b, s=s) or (None, None, None))
    monkeypatch.setattr(mqv.st, "html", lambda *a, **k: None)
    mqv.render_market_page_questions(pd.DataFrame({"Symbol": ["A"], "Industry": ["X"]}), prices, bench, size)
    assert seen["b"].index[-1] == pd.Timestamp("2026-11-20")
    assert list(seen["s"]) == ["Nifty Microcap 250"]


def test_header_regime_ends_on_the_prices_session(monkeypatch):
    # S216: the header printed the Nifty 500's 23 Nov close beside "Prices · closes of 20 Nov".
    import src.loaders.price_loader as pl

    idx = pd.bdate_range("2025-06-02", "2026-11-20").append(pd.DatetimeIndex(["2026-11-23"]))
    close = pd.Series(100.0, index=idx)
    close.iloc[-2], close.iloc[-1] = 120.0, 90.0
    monkeypatch.setattr(pl, "fetch_benchmark_history", lambda period="2y", symbol=None: close)
    pl.get_market_regime.clear()
    assert pl.get_market_regime(end="2026-11-20").current_price == 120.0
    assert pl.get_market_regime().current_price == 90.0
    assert pl.get_market_regime(end="2020-01-01").current_price == 0.0
    pl.get_market_regime.clear()
    src = _src("app.py")
    assert 'regime_data = get_market_regime(TOTAL_MARKET_REGIME, end=f"{_last_px:%Y-%m-%d}")' in src
    assert "_pool.submit(get_market_regime, TOTAL_MARKET_REGIME)" in src
