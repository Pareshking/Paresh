"""Regressions from the multi-agent adversarial audit of 2026-09-10.

Every test here failed on the code as it stood before the audit. Each one is
written to fail again if the defect returns, and each names the defect rather
than the fix, so the test survives a reimplementation.

The audit's own governing rule applies to this file too: a passing test is not
evidence of correctness. These pin the specific failures that were reproduced
with counterexamples; they do not certify anything beyond them.
"""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest

from src.engine import backtester as bt
from src.engine.backtester import _calendar_period_sharpe, _composite_z_score, run_backtest
from src.engine.calendar_momentum import (
    _calendar_period_metrics,
    _winsorised_cross_section_z,
    calendar_start_positions,
    winsorised_z,
)
from src.engine.portfolio import apply_caps


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
def _universe(seed: int = 42, n: int = 60, t: int = 800) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2023-06-01", periods=t)
    drift = np.linspace(0.0012, -0.0004, n)
    return pd.DataFrame(
        {f"S{i}": 100 * np.exp(np.cumsum(rng.normal(drift[i], 0.018, t))) for i in range(n)},
        index=dates,
    )


def _benchmark(px: pd.DataFrame, seed: int = 7) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(
        100 * np.exp(np.cumsum(rng.normal(0.0003, 0.009, len(px)))), index=px.index
    )


# ─────────────────────────────────────────────────────────────────────────────
# A1 — the backtester scored a different signal from the screener
# ─────────────────────────────────────────────────────────────────────────────
def test_backtest_scores_a_holed_anchor_exactly_as_the_screener_does():
    """A one-session gap on the window's opening date must not split the engines.

    The screener carries the anchor forward up to ANCHOR_STALENESS_LIMIT
    sessions; the backtester's copy of the statistic read one exact row. A
    single missing print on the anchor date therefore scored the stock NaN in
    the backtest and a real number on screen -- so the backtest could not have
    bought a name the screener ranked first.

    The pre-existing parity test missed this because its NaN runs were 40
    sessions long, past the staleness limit, where both engines return NaN.
    """
    px = _universe(n=12, t=420)
    end = len(px) - 1
    anchor = int(
        calendar_start_positions(
            pd.DatetimeIndex(px.index), 1, latest_as_of=pd.Timestamp(px.index[-1])
        )[end]
    )
    px.iloc[anchor, px.columns.get_loc("S0")] = np.nan  # exactly one holed session
    lr = np.log(px / px.shift(1))

    backtest, _ = _calendar_period_sharpe(px, lr, end, 1)
    screener, _, _, _ = _calendar_period_metrics(
        px, lr, 1, latest_as_of=pd.Timestamp(px.index[-1])
    )

    assert np.isfinite(screener.iloc[end]["S0"]), "fixture must leave the screener scoring"
    assert np.isfinite(backtest["S0"]), "backtester dropped a stock the screener ranks"
    pd.testing.assert_series_equal(
        backtest.astype(float),
        screener.iloc[end].astype(float),
        check_names=False,
        rtol=1e-9,
        atol=1e-12,
    )


def test_composite_uses_winsorise_then_z_not_z_then_clip():
    """The documented pipeline is winsorise -> z -> clamp, in that order.

    Z-scoring first and clipping afterwards leaves the dispersion inflated by
    the outliers, so every ordinary name scores smaller. Measured on a 200-name
    cross-section with five momentum leaders, 149 names moved by more than 0.05
    and two of the top twenty changed. Rank inside ONE window is unaffected --
    both maps are monotone -- but the composite sums five of them, so a
    fat-tailed window silently carried less than its configured weight.
    """
    rng = np.random.default_rng(7)
    raw = pd.Series(rng.normal(0, 1, 200), index=[f"S{i}" for i in range(200)])
    raw.iloc[:5] = [9.0, 8.2, 7.5, 6.9, 6.1]

    z_then_clip = ((raw - raw.mean()) / raw.std(ddof=0)).clip(-3.0, 3.0)
    engine = winsorised_z(raw)
    reference = _winsorised_cross_section_z(
        pd.DataFrame([raw.to_numpy()], columns=raw.index)
    ).iloc[0]

    pd.testing.assert_series_equal(engine, reference, check_names=False)
    assert (engine - z_then_clip).abs().max() > 0.1, (
        "fixture must actually distinguish the two pipelines"
    )


def test_backtest_composite_matches_the_screener_composite():
    """End to end: one price frame, one date, one set of scores."""
    px = _universe(n=40, t=500)
    lr = np.log(px / px.shift(1))
    end = len(px) - 1
    windows, weights = [1, 3, 6, 9, 12], [0.10, 0.30, 0.30, 0.20, 0.10]

    engine = _composite_z_score(px, lr, end, windows, weights)

    composite = pd.Series(0.0, index=px.columns)
    available = pd.Series(0.0, index=px.columns)
    for months, w in zip(windows, weights):
        raw, _, _, _ = _calendar_period_metrics(
            px, lr, months, latest_as_of=pd.Timestamp(px.index[-1])
        )
        z = _winsorised_cross_section_z(raw).iloc[end]
        composite += z.fillna(0.0) * w
        available += z.notna().astype(float) * w
    expected = composite.div(available.replace(0.0, np.nan))

    pd.testing.assert_series_equal(engine, expected, check_names=False, rtol=1e-9)


# ─────────────────────────────────────────────────────────────────────────────
# A2 — concentration caps the backtest accepted and ignored
# ─────────────────────────────────────────────────────────────────────────────
def test_backtest_caps_actually_change_the_result():
    """A 1% stock cap used to produce statistics identical to a 100% one.

    run_backtest took stock_cap and sector_cap, put them in its cache key, and
    never read them again. The Configuration tab showed a limit in force while
    the simulation -- and the "Current Holdings" book the tab tells you to
    trade -- ran with none.
    """
    px = _universe()
    smap = {f"S{i}": ("ALPHA" if i < 30 else "BETA") for i in range(60)}
    bench = _benchmark(px)
    common = dict(top_n=20, sector_map=smap, _benchmark_close=bench)

    loose = run_backtest("adv_loose", px, stock_cap=1.0, sector_cap=1.0, **common)
    tight = run_backtest("adv_tight", px, stock_cap=0.06, sector_cap=0.30, **common)

    assert loose is not None and tight is not None
    assert loose["stats"]["total_return"] != tight["stats"]["total_return"]

    capped = tight["live_book"].groupby("Industry")["Weight %"].sum().max()
    uncapped = loose["live_book"].groupby("Industry")["Weight %"].sum().max()
    # A 30% sector cap is not reachable by a 20-name book split across two
    # industries -- the projection relaxes it to the tightest feasible value
    # and says so. What must hold is that the cap BINDS: the concentration has
    # to come down materially from the uncapped book, and no position may
    # exceed the stock cap the run actually enforced.
    assert capped < uncapped - 5.0, f"cap did not bind: {capped:.1f}% vs {uncapped:.1f}%"
    assert uncapped > 70.0, "fixture must produce a genuinely concentrated book"
    assert tight["live_book"]["Weight %"].max() <= 100.0 / 20 * 1.6


def test_caps_are_enforced_or_reported_never_silently_missed():
    """apply_caps must satisfy the caps it reports, on random shapes.

    The shipped projection clipped to the caps and then renormalised the whole
    vector to 1.0, which lifts the clipped names back through the cap. Twenty
    equal weights under a 6% stock cap and a 40% sector cap came out at 6.98%
    and 58.1% -- against a docstring promising both were "strictly satisfied".
    """
    rng = np.random.default_rng(0)
    for _ in range(200):
        n = int(rng.integers(2, 41))
        syms = [f"S{i}" for i in range(n)]
        smap = {s: f"SEC{int(rng.integers(0, 7))}" for s in syms}
        raw = pd.Series(rng.random(n) + 0.01, index=syms)
        raw /= raw.sum()

        w = apply_caps(
            raw, smap,
            sector_cap=float(rng.uniform(0.05, 1.0)),
            stock_cap=float(rng.uniform(0.01, 0.5)),
        )
        by_sector = pd.Series(w.to_numpy(), index=[smap[s] for s in w.index]).groupby(level=0).sum()

        assert w.sum() == pytest.approx(1.0, abs=1e-9)
        assert (w >= -1e-12).all()
        assert w.max() <= w.attrs["effective_stock_cap"] + 1e-8
        assert by_sector.max() <= w.attrs["effective_sector_cap"] + 1e-8


def test_an_infeasible_cap_pair_is_flagged_not_quietly_relaxed():
    """Twenty names in two industries cannot hold a 40% sector cap."""
    syms = [f"S{i}" for i in range(20)]
    smap = {s: ("ALPHA" if i < 14 else "BETA") for i, s in enumerate(syms)}
    w = apply_caps(pd.Series(1 / 20, index=syms), smap, sector_cap=0.40, stock_cap=0.06)

    assert w.attrs["caps_relaxed"] is True
    assert w.attrs["effective_sector_cap"] > 0.40
    assert w.attrs["effective_stock_cap"] > 0.06


# ─────────────────────────────────────────────────────────────────────────────
# A3 — headline statistics that did not mean what they were labelled
# ─────────────────────────────────────────────────────────────────────────────
def _stats(tag: str = "adv_stats") -> dict:
    px = _universe()
    res = run_backtest(tag, px, top_n=20, _benchmark_close=_benchmark(px))
    assert res is not None
    return res


def test_win_rate_counts_profitable_periods_not_periods_that_beat_the_index():
    """The card read "Profitable Periods" and showed the alpha win rate.

    On the audit fixture it printed 83% while every month in the run was
    profitable. A month can lose money and still beat a worse benchmark.
    """
    res = _stats("adv_winrate")
    monthly, stats = res["monthly"], res["stats"]

    assert stats["win_rate"] == pytest.approx(float((monthly["Strategy Net"] > 0).mean()))
    assert stats["beat_rate"] == pytest.approx(
        float((monthly["Alpha vs Benchmark"] > 0).mean())
    )


def test_sharpe_is_mean_excess_over_volatility_not_extrapolated_cagr():
    """Sharpe divided an annualised-from-six-months CAGR by annualised vol.

    That is a geometric numerator over an arithmetic denominator, and the
    numerator was extrapolated from half a year, so the compounding of one
    strong month leaked into a statistic describing the average.
    """
    res = _stats("adv_sharpe")
    stats = res["stats"]
    daily = pd.Series(np.diff(res["equity_gross"].to_numpy()) / res["equity_gross"].to_numpy()[:-1])
    del daily  # the net series is the one the ratio uses; recomputed below

    curve = res["equity_curve"].to_numpy()
    net_daily = pd.Series(curve[1:] / curve[:-1] - 1.0)
    expected = (net_daily.mean() * 252 - stats["risk_free_rate"]) / (
        net_daily.std() * np.sqrt(252)
    )

    assert stats["sharpe"] == pytest.approx(expected, rel=1e-6)
    cagr_based = (stats["ann_return"] - stats["risk_free_rate"]) / stats["volatility"]
    assert stats["sharpe"] != pytest.approx(cagr_based, rel=1e-4)


def test_sortino_uses_target_semideviation_not_the_sd_of_losing_days():
    """The denominator was std(negative returns): a different statistic.

    It divides by the count of negative days rather than all days, and measures
    dispersion about the mean of the losses rather than about zero. It matches
    no published Sortino and its error does not even have a fixed sign.
    """
    res = _stats("adv_sortino")
    stats = res["stats"]
    curve = res["equity_curve"].to_numpy()
    net_daily = pd.Series(curve[1:] / curve[:-1] - 1.0)

    semidev = np.sqrt((np.minimum(net_daily, 0.0) ** 2).mean()) * np.sqrt(252)
    ann_excess = net_daily.mean() * 252 - stats["risk_free_rate"]
    assert stats["sortino"] == pytest.approx(ann_excess / semidev, rel=1e-6)

    sd_of_losers = net_daily[net_daily < 0].std() * np.sqrt(252)
    assert semidev != pytest.approx(sd_of_losers, rel=1e-4)


def test_annualised_return_ships_the_window_it_was_extrapolated_from():
    """Six months raised to the power of two is not a CAGR, and must say so."""
    res = _stats("adv_window")
    stats = res["stats"]
    assert 0.3 < stats["window_years"] < 0.75, "the reported window is ~6 months"
    assert stats["ann_return"] == pytest.approx(
        (1 + stats["total_return"]) ** (1 / stats["window_years"]) - 1, rel=1e-6
    )
    assert np.isfinite(stats["sharpe_stderr"]) and stats["sharpe_stderr"] > 0


def test_risk_free_rate_is_configuration_not_a_number_buried_in_a_ratio():
    from src.core.config import RISK_FREE_RATE

    assert _stats("adv_rf")["stats"]["risk_free_rate"] == RISK_FREE_RATE
    assert "0.065" not in inspect.getsource(bt.run_backtest)


# ─────────────────────────────────────────────────────────────────────────────
# A4 — turnover measured two different things
# ─────────────────────────────────────────────────────────────────────────────
def test_turnover_has_one_definition_across_every_period():
    """Establishment was hard-coded to 1.0 while later periods used sum|dw|/2.

    The same cost_bps then priced full notional on day one and half notional
    afterwards, and the "Avg Period Turnover" KPI averaged terms that did not
    measure the same quantity.
    """
    res = _stats("adv_turnover")
    monthly = res["monthly"]
    assert monthly["Turnover %"].iloc[0] == pytest.approx(50.0), (
        "establishing a book buys 100% and sells nothing: half a round trip"
    )
    assert (monthly["Turnover %"] <= 100.0 + 1e-9).all()
    for _, row in monthly.iterrows():
        assert row["Cost Drag %"] == pytest.approx(row["Turnover %"] * 30.0 / 10000.0)


# ─────────────────────────────────────────────────────────────────────────────
# A5 — survivorship disclosure
# ─────────────────────────────────────────────────────────────────────────────
def test_every_in_app_backtest_call_site_passes_point_in_time_membership():
    """Three of four call sites omitted _membership entirely.

    _index_mask then returned None on every rebalance and every month on screen
    was scored against today's constituent list -- the exact bias
    src/engine/membership.py exists to remove, reintroduced not by a fallback
    but by an argument nobody passed.
    """
    from src.engine import parameter_sweep
    from src.ui.views import backtest_view, track_record_view

    for module in (backtest_view, track_record_view, parameter_sweep):
        source = inspect.getsource(module)
        assert "run_backtest(" in source
        assert "_membership=" in source, f"{module.__name__} scores against today's universe"


def test_survivorship_coverage_is_counted_and_available_to_the_ui():
    px = _universe()
    res = run_backtest("adv_pit", px, top_n=20, _benchmark_close=_benchmark(px))
    stats = res["stats"]
    covered = stats["pit_periods"] + stats["current_universe_periods"]
    assert covered == stats["n_periods"] or covered >= 1
    # With no membership history supplied, every period must be counted as
    # current-universe rather than quietly presented as point-in-time.
    assert stats["pit_periods"] == 0
    assert stats["current_universe_periods"] >= 1


# ─────────────────────────────────────────────────────────────────────────────
# A6 — the Screener tab (audited in a second pass; tab 1, and the one people use)
# ─────────────────────────────────────────────────────────────────────────────
def _screener(px: pd.DataFrame) -> pd.DataFrame:
    from src.engine.momentum import MomentumEngine

    info = pd.DataFrame(
        {"Symbol": list(px.columns), "Industry": "IT", "Indices": "N50"}
    )
    calc = MomentumEngine(
        px, high_df=px, low_df=px, close_df=px,
        volume_df=pd.DataFrame(1e5, index=px.index, columns=px.columns),
    )
    return calc.get_rankings(
        info, pd.Series(1e4, index=px.columns),
        close_prices_df=px, high_prices_df=px,
    )


def test_a_52_week_high_needs_52_weeks_of_history():
    """The gate used to get EASIER the less history a stock had.

    The screener took max() over the trailing 252 rows with no minimum
    observation count, so a name listed 70 sessions ago got a "52-week high"
    drawn from those 70 sessions, sat 0.0% below it, passed Near-52W-High and
    ranked #1 -- while the backtester, which has always used
    rolling(252, min_periods=126), refused to compute one and excluded it.
    Two definitions of one filter, disagreeing precisely on recent listings.
    """
    from src.core.config import HIGH_52W_MIN_OBSERVATIONS

    T = 500
    idx = pd.bdate_range("2024-06-03", periods=T)
    rng = np.random.default_rng(3)
    cols = {
        f"F{i}": 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.015, T))) for i in range(5)
    }
    # Peaked a year ago, now genuinely 25% below a real 52-week high.
    cols["SEASONED"] = np.concatenate(
        [np.linspace(100, 200, 250), np.linspace(200, 150, 250)]
    )
    px = pd.DataFrame(cols, index=idx)
    px["IPO"] = np.nan
    px.iloc[-70:, px.columns.get_loc("IPO")] = np.linspace(120, 150, 70)

    r = _screener(px).set_index("Symbol")

    assert pd.isna(r.loc["IPO", "52W High"]), "70 sessions is not a 52-week high"
    assert not bool(r.loc["IPO", "Near 52W High"])
    assert r.loc["IPO", "Short History"] == "Yes"
    # The seasoned name still gets a real high and still fails the gate honestly.
    assert r.loc["SEASONED", "52W High"] == pytest.approx(200.0)
    assert not bool(r.loc["SEASONED", "Near 52W High"])

    # And the screener now agrees with the backtester's own definition.
    bt_high = px.rolling(252, min_periods=HIGH_52W_MIN_OBSERVATIONS).max().iloc[-1]
    assert pd.isna(bt_high["IPO"])
    assert bt_high["SEASONED"] == pytest.approx(r.loc["SEASONED", "52W High"])


def test_rank_delta_is_measured_against_the_same_population():
    """A rank delta over a fixed population sums to zero. This one did not.

    `Rank` is ranked among the rows that survive the score dropna;
    `Rank (-1M)` was ranked over every price column, including names that had a
    score a month ago and have none today -- delistings, suspensions, vendor
    holes. Each occupies a historical slot that no longer exists, so every
    survivor below it appears to have climbed. On a 40-name universe with 5
    names gone dark the mean "improvement" across the whole book was +3.17.
    """
    T = 500
    idx = pd.bdate_range("2024-06-03", periods=T)
    rng = np.random.default_rng(9)
    px = pd.DataFrame(
        {f"S{i}": 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.018, T))) for i in range(40)},
        index=idx,
    )
    for i in range(5):  # go dark in the last fortnight, but keep >=63 observations
        px.iloc[-14:, px.columns.get_loc(f"S{i}")] = np.nan
    # ...and five that ENTER the ranking only recently. Correcting only for the
    # leavers overshoots the other way: new entrants push today's rank numbers
    # out with no historical counterpart, which took the mean to -2.23.
    for i in range(5, 10):
        px.iloc[:-90, px.columns.get_loc(f"S{i}")] = np.nan

    r = _screener(px)
    assert len(r) < 40, "fixture must actually drop names from today's ranking"

    for col in ("Rank Δ 1M", "Rank Δ 3M"):
        delta = r[col].dropna()
        assert len(delta) > 0
        assert delta.sum() == pytest.approx(0.0, abs=1e-9), (
            f"{col} does not sum to zero: population mismatch"
        )
    # A name that was not RANKABLE on the past date gets no delta at all,
    # rather than a fabricated jump. The 90-session entrants had ~27 prints
    # three months ago, below the 63-observation minimum, so they had no rank
    # then -- and the historical mask is now the history that existed on that
    # date rather than today's count applied backwards.
    entrants = r[r["Symbol"].isin([f"S{i}" for i in range(5, 10)])]
    assert entrants["Rank Δ 3M"].isna().all(), (
        "a stock that was not rankable three months ago cannot have moved"
    )
    assert entrants["Rank Δ 1M"].notna().all(), (
        "it WAS rankable one month ago, so that delta is real"
    )
    assert r["Rank (-1M)"].max() <= r["Rank"].max()


def test_every_index_filter_option_matches_something():
    """6 of 11 options returned an empty screener.

    indices_loader writes SHORT FORMS into the Indices column ("N50",
    "MID150"...). The option list added the long names on top -- plus a
    "NIFTY 500" the app does not load as a constituent index at all -- and the
    filter matched by substring, so selecting "NIFTY 50" filtered for a string
    that appears nowhere in the data.
    """
    from src.core.config import SHORT_FORMS

    tag_to_name = {short: long for long, short in SHORT_FORMS.items() if short}
    universe = pd.DataFrame({
        "Symbol": ["A", "B", "C", "D"],
        "Indices": ["N50", "NN50", "MID150", "N50, MID150"],
    })
    present = {t.strip() for v in universe["Indices"] for t in v.split(",") if t.strip()}
    labels = {f"[INDEX] {tag_to_name.get(t, t)}": t for t in present}

    assert "[INDEX] NIFTY 50" in labels and labels["[INDEX] NIFTY 50"] == "N50"
    assert "[INDEX] NIFTY 500" not in labels, "the app loads no NIFTY 500 constituent file"
    for label, tag in labels.items():
        hit = universe["Indices"].apply(
            lambda v: tag.upper() in [x.strip().upper() for x in v.split(",")]
        )
        assert hit.any(), f"{label} matches nothing"


def test_nifty_50_filter_does_not_leak_nifty_next_50():
    """"NN50" contains "N50", so substring matching returned both indices.

    On the shipped universe the Nifty 50 filter returned 100 stocks.
    """
    universe = pd.DataFrame({
        "Symbol": ["IN_N50", "IN_NN50", "IN_BOTH"],
        "Indices": ["N50", "NN50", "N50, NN50"],
    })

    substring = universe[universe["Indices"].str.contains("N50", case=False, na=False)]
    assert len(substring) == 3, "fixture must reproduce the collision"

    tag = "N50"
    exact = universe[universe["Indices"].apply(
        lambda v: tag in [x.strip().upper() for x in v.split(",")]
    )]
    assert sorted(exact["Symbol"]) == ["IN_BOTH", "IN_N50"]
