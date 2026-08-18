"""Market cap follows today's price instead of the last sync.

NSE publishes a market cap and the close price behind it. Shares outstanding is
the ratio of the two and only moves on a corporate action; the price moves every
session. So the stale half of a day-old market cap is the price, and that half
can be replaced:

    live = published * (today's close / bhavcopy close)

which is shares outstanding times the current price, anchored to NSE's own
figure. Anchoring to the published cap rather than the bhavcopy's "Issue Size"
column matters: that column pairs with "Close Price/Paid up value", which for
partly-paid securities is a paid-up value and not a price -- 160 of 2295 rows
disagreed by more than 0.1% on 18 Aug 2026.
"""
import numpy as np
import pandas as pd
import pytest

from src.loaders.mcap_loader import scale_market_caps_to_price


CAPS = pd.Series({"A": 1_000.0, "B": 2_000.0, "C": 500.0})
REF = pd.Series({"A": 100.0, "B": 200.0, "C": 50.0})


def test_price_up_ten_percent_lifts_the_cap_ten_percent():
    now = pd.Series({"A": 110.0, "B": 200.0, "C": 50.0})
    scaled, n = scale_market_caps_to_price(CAPS, now, REF)
    assert scaled["A"] == pytest.approx(1_100.0)
    assert scaled["B"] == pytest.approx(2_000.0)
    assert n == 3


def test_price_down_halves_the_cap():
    now = pd.Series({"A": 50.0, "B": 200.0, "C": 50.0})
    scaled, _ = scale_market_caps_to_price(CAPS, now, REF)
    assert scaled["A"] == pytest.approx(500.0)


def test_an_unchanged_price_leaves_the_published_figure_alone():
    scaled, n = scale_market_caps_to_price(CAPS, REF, REF)
    assert scaled.to_dict() == pytest.approx(CAPS.to_dict())
    assert n == 3


def test_implied_shares_are_preserved():
    """live / today's price must equal published / reference price."""
    now = pd.Series({"A": 137.0, "B": 191.5, "C": 62.25})
    scaled, _ = scale_market_caps_to_price(CAPS, now, REF)
    for sym in CAPS.index:
        assert (scaled[sym] / now[sym]) == pytest.approx(CAPS[sym] / REF[sym])


def test_a_symbol_without_a_reference_keeps_its_published_cap():
    ref = pd.Series({"A": 100.0})          # B and C missing
    now = pd.Series({"A": 110.0, "B": 400.0, "C": 90.0})
    scaled, n = scale_market_caps_to_price(CAPS, now, ref)
    assert scaled["A"] == pytest.approx(1_100.0)
    assert scaled["B"] == pytest.approx(2_000.0)   # untouched, not dropped
    assert scaled["C"] == pytest.approx(500.0)
    assert n == 1


@pytest.mark.parametrize("bad", [0.0, np.nan, -5.0])
def test_a_useless_reference_price_does_not_corrupt_the_cap(bad):
    ref = pd.Series({"A": bad, "B": 200.0, "C": 50.0})
    now = pd.Series({"A": 110.0, "B": 200.0, "C": 50.0})
    scaled, _ = scale_market_caps_to_price(CAPS, now, ref)
    assert scaled["A"] == pytest.approx(1_000.0)


def test_no_reference_at_all_is_a_no_op():
    scaled, n = scale_market_caps_to_price(CAPS, REF, pd.Series(dtype=float))
    assert scaled.to_dict() == pytest.approx(CAPS.to_dict())
    assert n == 0


def test_empty_caps_return_empty():
    scaled, n = scale_market_caps_to_price(pd.Series(dtype=float), REF, REF)
    assert scaled.empty and n == 0


def test_missing_today_price_keeps_the_published_cap():
    now = pd.Series({"A": np.nan, "B": 200.0, "C": 50.0})
    scaled, n = scale_market_caps_to_price(CAPS, now, REF)
    assert scaled["A"] == pytest.approx(1_000.0)
    assert n == 2


def test_the_ranking_reports_which_basis_it_used():
    from src.engine.momentum import MomentumEngine
    import src.loaders.mcap_loader as ml

    n, cols = 300, 4
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    rng = np.random.default_rng(5)
    px = pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0.0004, 0.012, (n, cols)), axis=0)),
        index=idx, columns=[f"S{i}" for i in range(cols)],
    )
    info = pd.DataFrame({"Symbol": [f"S{i}" for i in range(cols)],
                         "Industry": ["IT"] * cols})
    caps = pd.Series({f"S{i}": 1e12 for i in range(cols)})

    ml._PR_CLOSE_PRICES.clear()
    calc = MomentumEngine(px, high_df=px, low_df=px, close_df=px,
                          volume_df=pd.DataFrame(1e5, index=idx, columns=px.columns))
    plain = calc.get_rankings(info, caps, close_prices_df=px, high_prices_df=px)
    assert (plain["Market Cap Basis"] == "as_published").all()

    # With reference closes present the caps move with the price.
    ml._PR_CLOSE_PRICES.update({f"S{i}": float(px[f"S{i}"].iloc[-1]) / 2 for i in range(cols)})
    calc2 = MomentumEngine(px, high_df=px, low_df=px, close_df=px,
                           volume_df=pd.DataFrame(1e5, index=idx, columns=px.columns))
    live = calc2.get_rankings(info, caps, close_prices_df=px, high_prices_df=px)
    ml._PR_CLOSE_PRICES.clear()

    assert (live["Market Cap Basis"] == "live").all()
    # Price is double the reference, so every cap should have doubled.
    merged = plain.set_index("Symbol")["Market Cap (Cr)"].align(
        live.set_index("Symbol")["Market Cap (Cr)"], join="inner")
    assert (merged[1] / merged[0]).round(6).eq(2.0).all()
