"""S236 F19 (owner, 28 Nov 2026): every CSV in percent, two decimals, no emoji; the Kite basket unchanged."""
from pathlib import Path

import pandas as pd

from src.ui.export import tidy

ROOT = Path(__file__).resolve().parents[1]


def test_returns_become_percent_and_say_so_in_the_header():
    out = tidy(pd.DataFrame({"12M Return": [0.20871], "Max DD 12M": [30.46581], "Score": [0.593412]}))
    assert list(out.columns) == ["12M Return %", "Max DD 12M", "Score"]
    assert out.iloc[0].tolist() == [20.87, 30.47, 0.5934]   # the score keeps four: the ranking sorts by it


def test_rebalance_lines_use_the_trades_unit_without_emoji():
    tb = pd.DataFrame({"Action": ["🔴 SELL (Exit)", "🟢 BUY (Entry)"], "Price": [930.2000122070312, 1110.4000244140625],
                       "Return %": [-0.16228386909674242, 0.0], "Weight %": [0.0, 4.999999999999999]})
    out = tidy(tb, fractions=("Return %",))
    assert out["Action"].tolist() == ["SELL (Exit)", "BUY (Entry)"]
    assert out["Price"].tolist() == [930.2, 1110.4]
    assert out["Return %"].tolist() == [-16.23, 0.0]
    assert out["Weight %"].tolist() == [0.0, 5.0]


def test_every_page_export_goes_through_tidy_but_the_kite_basket():
    for f in ("ranking_view", "qualified_view", "watchlist_view", "portfolio_page"):
        src = (ROOT / "src/ui/views" / f"{f}.py").read_text()
        assert "csv_bytes(" in src and ".to_csv(index=False).encode()" not in src, f
    assert "orders.to_csv(index=False).encode()" in (ROOT / "src/ui/views/actions_page.py").read_text()
