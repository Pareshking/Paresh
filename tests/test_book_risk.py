"""How risky is the book? (TODO S110, item 3)."""
import numpy as np
import pandas as pd

from src.engine import book_risk as br


def _prices(n=200, seed=3):
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2026-01-01", periods=n)
    m = rng.normal(0.0005, 0.01, n)
    a = 100 * np.cumprod(1 + 1.5 * m + rng.normal(0, 0.002, n))   # beta about 1.5 to the market
    b = 100 * np.cumprod(1 + 0.5 * m + rng.normal(0, 0.002, n))   # about 0.5
    bench = pd.Series(100 * np.cumprod(1 + m), index=days)
    return pd.DataFrame({"AAA": a, "BBB": b}, index=days), bench


def test_beta_and_volatility_of_the_book_at_its_weights():
    px, bench = _prices()
    res = br.book_risk(pd.Series({"AAA": 50, "BBB": 50}), px, bench)
    assert 0.9 < res.beta < 1.1 and res.vol > 0 and res.bench_vol > 0 and res.sessions == br.WINDOW
    hi = br.book_risk(pd.Series({"AAA": 100}), px, bench)
    assert hi.beta > 1.3


def test_short_history_and_missing_traded_value_are_named_not_dropped_silently():
    px, bench = _prices()
    px["NEWCO"] = np.nan
    px.iloc[-20:, px.columns.get_loc("NEWCO")] = 50.0
    vol = pd.DataFrame(1000.0, index=px.index, columns=["AAA", "BBB"])
    res = br.book_risk(pd.Series({"AAA": 40, "BBB": 40, "NEWCO": 20}), px, bench, volume=vol)
    assert any("NEWCO" in g and "price history" in g for g in res.gaps)
    assert any("NEWCO" in g and "traded value" in g for g in res.gaps)


def test_exit_days_and_drawdown():
    px, bench = _prices()
    vol = pd.DataFrame({"AAA": 10_000.0, "BBB": 1_000.0}, index=px.index)
    res = br.book_risk(pd.Series({"AAA": 50, "BBB": 50}), px, bench,
                       equity=pd.Series([100, 120, 90, 108], index=pd.bdate_range("2026-01-01", periods=4)),
                       volume=vol, capital=1e7)
    assert res.exit_days.index[0] == "BBB"          # the thinner one is slowest
    value_b = (px["BBB"] * 1_000).iloc[-20:].mean()
    assert np.isclose(res.exit_days["BBB"], 0.5 * 1e7 / (value_b * br.PARTICIPATION))
    assert np.isclose(res.drawdown, 108 / 120 - 1) and np.isclose(res.max_drawdown, 90 / 120 - 1)


def test_size_tiers_come_from_nses_lists(tmp_path):
    (tmp_path / "ind_nifty50list.csv").write_text("Company Name,Symbol\nA,AAA\n")
    (tmp_path / "ind_niftysmallcap250list.csv").write_text("Company Name,Symbol\nB,BBB\n")
    assert br.tier_of(["AAA", "BBB", "ZZZ"], tmp_path) == {"AAA": "Nifty 100", "BBB": "Smallcap 250", "ZZZ": "Outside"}


def test_the_card_renders():
    from src.ui.views import dashboard_view as dv

    px, bench = _prices()
    res = br.book_risk(pd.Series({"AAA": 50, "BBB": 50}), px, bench,
                       volume=pd.DataFrame(1000.0, index=px.index, columns=["AAA", "BBB"]))
    out = dv.book_risk_html(res, pd.Timestamp("2026-10-30"))
    assert "beta" in out and "Volatility" in out and "Exit" in out and "Size" in out


def test_the_index_drawdown_covers_the_records_dates_only():
    px, bench = _prices()
    eq = pd.Series([100.0, 101.0, 102.0], index=bench.index[:3])
    bench = bench.copy()
    bench.iloc[3:] = bench.iloc[2] * 0.5          # a collapse after the record's last date
    res = br.book_risk(pd.Series({"AAA": 50, "BBB": 50}), px, bench, equity=eq)
    assert res.bench_drawdown > -0.05
