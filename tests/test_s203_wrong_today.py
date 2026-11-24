"""S203: the sentences that were wrong today, now true in every case (indices, backtest, market)."""
import re

import pandas as pd
import pytest

from src.engine import indices_page as ip
from src.ui.views import indices_view as iv


def _v(key: str, pct: float, pe: float = 22.0) -> ip.Valuation:
    return ip.Valuation(key=key, name=key, pe_3m=pe, pe_1m=pe, pe_now=pe, pct_3m=pct, pct_1m=pct, pct_now=pct,
                        since=ip.PE_FROM, pb_now=3.0, dy_now=1.2)


def _title(big, small) -> str:
    vals = [v for v in (big, small) if v is not None]
    html = iv.head(vals, pd.Timestamp("2026-11-20"))[0]
    return re.sub(r"<[^>]+>", "", re.search(r'<h1[^>]*>(.*?)</h1>', html).group(1))


@pytest.mark.parametrize("b,s,want", [
    (20, 80, "The Nifty 50's P/E is below its median since Mar 2021; the Nifty Smallcap 250's is above it."),
    (80, 20, "The Nifty 50's P/E is above its median since Mar 2021; the Nifty Smallcap 250's is below it."),
    (20, 30, "The Nifty 50's P/E is at the 20th percentile of its days since Mar 2021; the Nifty Smallcap 250's at the 30th."),
    (90, 70, "The Nifty 50's P/E is at the 90th percentile of its days since Mar 2021; the Nifty Smallcap 250's at the 70th."),
    (50, 70, "The Nifty 50's P/E is at its median since Mar 2021; the Nifty Smallcap 250's at the 70th."),
])
def test_the_title_reads_each_case(b, s, want):
    assert _title(_v("nifty_50", b), _v("nifty_smallcap_250", s)) == want


def test_the_title_without_the_figures():
    assert _title(None, None) == "NSE's index P/Es are not in yet."


@pytest.mark.parametrize("b,s,want", [
    (20, 80, "At 22.0 times earnings, the Nifty 50 is cheaper than on 80% of days since 31 Mar 2021; "
             "the Nifty Smallcap 250 is dearer than on 80%."),
    (80, 20, "At 22.0 times earnings, the Nifty 50 is dearer than on 80% of days since 31 Mar 2021; "
             "the Nifty Smallcap 250 is cheaper than on 80%."),
    (50, 50, "At 22.0 times earnings, the Nifty 50 is at its median since 31 Mar 2021; "
             "the Nifty Smallcap 250 is at its median."),
])
def test_the_valuation_heading_reads_each_way(b, s, want):
    assert iv.valuation_headline(_v("nifty_50", b), _v("nifty_smallcap_250", s)) == want


def test_the_valuation_heading_without_the_figures():
    assert iv.valuation_headline(None, None) == "Each index's P/E against its own past since 31 Mar 2021."


# ── Backtest (S203 bt.head.1, bt.lead.1, bt.trd.2) ──
def test_the_backtest_verbs_carry_the_sign():
    from src.ui.views import backtest_view as bv
    assert bv._against(0.121) == ", against a gain of 12.1% for the Nifty 500"
    assert bv._against(-0.03) == ", against a loss of 3.0% for the Nifty 500"
    assert bv._against(None) == ""
    assert bv._updown(-0.05) == "down 5.0%" and bv._updown(0.05) == "up 5.0%"


# ── Market (S203 mk.head.1): a missing score is said, not "Not enough data participation" ──
def test_the_market_title_says_a_missing_score():
    """S203 Q2 (owner, 24 Nov 2026): the trend names its index; a missing score is said."""
    from types import SimpleNamespace as N

    from src.ui.views.market_questions_view import market_title
    assert market_title(N(verdict="Narrow"), N(verdict="Strong uptrend")) == \
        "Participation is narrow; Nifty Total Market is in a strong uptrend."
    assert market_title(N(verdict="About usual"), N(verdict="No clear trend")) == \
        "Participation is about usual; Nifty Total Market has no clear trend."
    assert market_title(N(verdict="Not enough data"), N(verdict="Uptrend")) == \
        "Participation cannot be read today; Nifty Total Market is in an uptrend."
    assert market_title(N(verdict="Broad"), N(verdict="Not enough data")) == \
        "Participation is broad; Nifty Total Market's trend cannot be read today."
    assert "Not enough data" not in market_title(N(verdict="Not enough data"), N(verdict="Not enough data"))
