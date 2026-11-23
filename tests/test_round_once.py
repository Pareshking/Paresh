"""S193 A13 and A14 (owner, 23 Nov 2026: both approved).

A13: CUPID read +188.5% since entry on Actions and +188.6% on Portfolio. Portfolio rounded
the return to 2 dp in Python (188.549 -> 188.55) and the page rounded it again to 1 dp
(+188.6); Actions rounds once. Portfolio's tables now send unrounded figures and the page
rounds once, half up, as every other page does.

A14: the Guide's "pts" example quoted the live book's own figures (+46.3% against +1.3%),
so it read as a third, slightly different copy of them (45.0 against the live 44.9).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from src.engine import portfolio_report as pr
from src.ui import formats
from src.ui.views import portfolio_page

ROOT = Path(__file__).resolve().parents[1]
node = shutil.which("node")
EDGE = 188.549  # rounds to 188.5 once; to 188.55 and then 188.6 twice


def _trade(ret: float) -> dict:
    row = dict.fromkeys(pr.TRADE_FIELDS)
    row.update({"Symbol": "CUPID", "Industry": "X", "Entry signal date": "2026-03-01", "Entry date": "2026-03-02",
                "Entry price": 100.449, "Entry rank": 3, "Entry weight %": 5.0, "Exit price": 289.949,
                "Exit rank": 9, "Return %": ret, "Days held": 200, "Exit rule": "Rank", "Status": "Closed"})
    return row


def test_trade_history_sends_prices_and_returns_unrounded():
    spec = portfolio_page.history_spec(pd.DataFrame([_trade(EDGE)]), None, [])
    row = spec["trades"][0] if isinstance(spec, dict) and spec.get("trades") else None
    assert row is not None, "history_spec's rows moved; update this test"
    assert EDGE in row and 100.449 in row and 289.949 in row


def test_holdings_send_prices_weights_and_returns_unrounded():
    src = (ROOT / "src" / "ui" / "views" / "portfolio_page.py").read_text(encoding="utf-8")
    body = src[src.index("def holdings_spec("):src.index("def growth_spec(")]
    for key in ("ep", "px", "w", "dayp", "ret"):
        assert not re.search(rf'"{key}": round\(', body), f"holdings_spec rounds {key} before the page does"


@pytest.mark.skipif(node is None, reason="node is not installed")
def test_the_page_rounds_once_as_actions_does():
    s = (ROOT / "static" / "dash_charts.js").read_text(encoding="utf-8")
    kit = s[s.index("const rnd = "):s.index("\n", s.index("const sg = "))]
    script = kit + f"\nconsole.log(JSON.stringify([sg({EDGE}), sg({round(EDGE, 2)})]));"
    once, twice = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)
    actions = formats.pct(EDGE / 100)  # Actions: Return % as a fraction, rounded once
    assert f"{once}%" == actions == "+188.5%"
    assert twice == "+188.6"  # what the double rounding showed


def test_the_guides_pts_example_is_not_the_live_books_figures():
    src = (ROOT / "src" / "ui" / "views" / "guide_view.py").read_text(encoding="utf-8")
    assert "+46.3% against +1.3%" not in src
    # The example's own arithmetic holds: 20 - 5 = 15 pts; 1.20 / 1.05 - 1 = 14.3% relative.
    assert "+20.0% against +5.0% is 15.0 pts" in src and "(14.3%)" in src
    assert round((1.20 / 1.05 - 1) * 100, 1) == 14.3
