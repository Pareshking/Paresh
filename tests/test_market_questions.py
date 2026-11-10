"""The Dashboard's three market questions: each rule on small frames."""
import numpy as np
import pandas as pd
import pytest

from src.engine import market_questions as mq


def _days(n, end="2026-11-06"):
    return pd.bdate_range(end=end, periods=n)


def test_the_ten_month_rule_ignores_the_month_in_progress():
    idx = pd.date_range("2025-01-01", "2026-11-06", freq="B")
    s = pd.Series(100.0, index=idx)
    s[s.index >= "2026-11-01"] = 200.0            # a jump in November only
    # October's close against Jan-Oct: flat, though November's prices doubled.
    assert mq.ten_month_gap(s, idx[-1]) == pytest.approx(0.0)
    s2 = s.copy()
    s2[(s2.index >= "2026-10-01") & (s2.index < "2026-11-01")] = 110.0
    # October at 110 against an average of (9 x 100 + 110) / 10 = 101.
    assert mq.ten_month_gap(s2, idx[-1]) == pytest.approx((110 / 101 - 1) * 100)


def test_votes_and_the_five_words():
    words = ("Strong downtrend", "Downtrend", "No clear trend", "Uptrend", "Strong uptrend")
    assert mq.word_for(0.7, words) == "Strong uptrend"
    assert mq.word_for(0.3, words) == "Uptrend"
    assert mq.word_for(0.0, words) == "No clear trend"
    assert mq.word_for(-0.3, words) == "Downtrend"
    assert mq.word_for(-0.9, words) == "Strong downtrend"
    assert mq._vote(61, 60, 40) == mq.UP and mq._vote(40, 60, 40) == mq.DOWN and mq._vote(50, 60, 40) == mq.MID


def test_primary_measures_count_twice():
    up = mq._measure("a", "pct", [70, 70, 70], 60, 40, "", primary=True)
    down = mq._measure("b", "pct", [30, 30, 30], 60, 40, "")
    assert mq._score([up, down], "now") == pytest.approx((2 - 1) / 3)
    # a past reading is voted by the same cut-offs
    m = mq._measure("c", "pct", [70, 30, None], 60, 40, "")
    assert mq._score([m], "month_ago") == -1 and mq._score([m], "year_ago") is None


def test_breadth_answer_counts_the_stocks_ahead_of_the_index():
    idx = _days(400)
    rising = pd.Series(np.linspace(100, 200, len(idx)), index=idx)
    falling = pd.Series(np.linspace(200, 100, len(idx)), index=idx)
    prices = pd.DataFrame({"A": rising, "B": rising, "C": rising, "D": falling})
    bench = pd.Series(np.linspace(100, 120, len(idx)), index=idx)
    a = mq.breadth_answer(prices, bench)
    beat = next(m for m in a.measures if m.name.startswith("Stocks ahead"))
    assert beat.now == pytest.approx(75.0) and beat.vote == mq.UP
    a200 = next(m for m in a.measures if "200D" in m.name)
    assert a200.now == pytest.approx(75.0)
    assert a.verdict in ("Broad", "Very broad")


def test_leaders_groups_industries_by_six_months_and_one_month():
    idx = _days(200)
    n = len(idx)
    up_all = np.linspace(100, 160, n)
    late_turn = np.r_[np.linspace(100, 60, n - 22), np.linspace(60, 70, 22)]
    flat = np.full(n, 100.0)
    cols = {}
    for i in range(5):
        cols[f"L{i}"] = up_all
        cols[f"G{i}"] = late_turn
    prices = pd.DataFrame(cols, index=idx)
    industry = pd.Series({**{f"L{i}": "Leaders" for i in range(5)}, **{f"G{i}": "Turning" for i in range(5)}})
    out = mq.leaders_answer(prices, industry, pd.Series(flat, index=idx), None)
    g = out.sectors.set_index("Industry")["group"]
    assert g["Leaders"] == "ahead on both" and g["Turning"] == "gaining"
    assert "1 of 2 industries" in out.sentence and "Leaders" in out.sentence


def test_a_past_verdict_needs_most_of_the_weight():
    a = mq._measure("a", "pct", [70, 70, None], 60, 40, "", primary=True)
    b = mq._measure("b", "pct", [70, 70, None], 60, 40, "", primary=True)
    c = mq._measure("c", "pct", [70, 70, 70], 60, 40, "")
    # a year ago only c (1 of 5 weight) is known: no verdict, not "strongly up"
    assert mq._score([a, b, c], "year_ago") is None
    assert mq._score([a, b, c], "month_ago") == 1


def test_sentences_keep_their_capitals():
    m = [mq._measure("Stocks above their 200D EMA", "pct", [43, 40, 60], 60, 40, ""),
         mq._measure("Stocks ahead of the Nifty 500 over a year", "pct", [45, 47, None], 55, 45, "")]
    text = mq._breadth_sentence("Narrow", m)
    assert text == "43% of the ranked stocks are above their 200D EMA and 45% beat the Nifty 500 over the year."


def test_what_would_change_names_the_measures_one_step_from_another_word():
    words = ("Very narrow", "Narrow", "About usual", "Broad", "Very broad")
    ms = [mq._measure("p", "pct", [41, 50, 60], 60, 40, "", primary=True),     # between
          mq._measure("q", "pct", [30, 50, 60], 55, 45, "", primary=True),     # down
          mq._measure("r", "pct", [50, 50, 60], 60, 40, "")]                  # between
    a = mq._answer("Q", ms, words, lambda w, m: "")
    assert a.verdict == "Narrow"                         # score (0 - 2 + 0) / 5 = -0.4
    lower = {m.name: c for m, c in mq.what_would_change(a)["lower"]}
    higher = {m.name: c for m, c in mq.what_would_change(a)["higher"]}
    assert lower == {"p": 40, "r": 40}                   # p down: -0.8; r down: -0.6; both very narrow
    assert higher["q"] == 45                              # q back between -> 0, about usual
    assert "p" in higher                                  # p up -> 0, about usual


def test_changes_are_largest_first_against_each_measures_band():
    a = mq._answer("Q", [mq._measure("x", "pct", [50, 48, None], 60, 40, ""),
                         mq._measure("y", "pts", [5, -5, None], 5, -5, "")],
                   ("a", "b", "c", "d", "e"), lambda w, m: "")
    assert [m.name for m, _, _ in mq.changes(a)] == ["y", "x"]


def test_industry_months_counts_the_current_run_and_marks_the_month_to_date():
    idx = pd.bdate_range("2025-10-01", "2026-11-06")
    bench = pd.Series(100.0, index=idx)
    # "Ahead" gains 1% a month from June; flat before. "Behind" loses 1% a month all year.
    month_no = (idx.year - 2025) * 12 + idx.month
    ahead = pd.Series(np.where(idx >= "2026-06-01", 1.01 ** (month_no - month_no[idx >= "2026-06-01"][0]), 1.0), index=idx)
    behind = pd.Series(0.99 ** (month_no - month_no[0]), index=idx)
    prices = pd.DataFrame({**{f"A{i}": ahead for i in range(5)}, **{f"B{i}": behind for i in range(5)}})
    industry = pd.Series({**{f"A{i}": "Ahead" for i in range(5)}, **{f"B{i}": "Behind" for i in range(5)}})
    out = mq.industry_months(prices, industry, bench)
    assert out.columns[-3] == "Nov MTD" and list(out.columns[-2:]) == ["run", "total"]
    assert out.loc["Ahead", "run"] == 4          # Jul, Aug, Sep, Oct ahead (June's first close is the base)
    assert out.loc["Behind", "run"] <= -11
    assert out.index[0] == "Ahead"


def test_net_new_highs_uses_a_calendar_year_on_sparse_history():
    # Weekly rows for two years, then daily: a 252-row window would span
    # years in the weekly part; a 365-day window does not.
    weekly = pd.date_range("2022-01-07", "2024-01-05", freq="W-FRI")
    daily = pd.bdate_range("2024-01-08", "2025-06-30")
    idx = weekly.append(daily)
    rising = pd.Series(np.linspace(100, 300, len(idx)), index=idx)
    prices = pd.DataFrame({f"S{i}": rising for i in range(10)})
    nnh = mq._net_new_highs(prices)
    assert nnh.loc["2023-06-02"] == pytest.approx(100.0)      # all 10 stocks made a new high this week, each counted once
    assert nnh.dropna().index[0] < pd.Timestamp("2023-02-01")  # readings start a year in, not years in


def test_a_reading_needs_enough_stocks():
    counts = pd.Series([30, 60, 400, 750])
    assert mq._enough(counts).tolist() == [False, False, True, True]


def test_market_strip_reads_the_day_and_the_month_and_draws_an_image_line():
    from src.ui.views.market_questions_view import market_strip_html
    idx = pd.bdate_range(end="2026-11-06", periods=80)
    s = pd.Series(np.linspace(100, 110, len(idx)), index=idx)
    s.iloc[-1] = s.iloc[-2] * 1.01
    out = market_strip_html({"Nifty 500": s})
    assert "+1.0%" in out and 'src="data:image/svg+xml;base64,' in out and "<svg" not in out
    assert "Nifty 500: +1.0% on the day" in out


def test_market_strip_never_shows_a_weeks_move_as_a_day():
    from src.ui.views.market_questions_view import market_strip_html
    weekly = pd.Series(np.linspace(100, 110, 30), index=pd.date_range(end="2026-11-06", periods=30, freq="W-FRI"))
    assert market_strip_html({"Midcap 150": weekly}) == ""


def test_size_against_the_index_uses_the_same_dates_for_both():
    # A weekly size index ending a week before the daily Nifty 500: the
    # comparison must end on the size index's last close for both series.
    daily = pd.bdate_range("2026-01-01", "2026-11-06")
    bench = pd.Series(100.0, index=daily)
    bench[bench.index > "2026-10-30"] = 110.0          # a jump after the weekly file ends
    weekly = pd.Series(100.0, index=pd.date_range("2026-01-02", "2026-10-30", freq="W-FRI"))
    assert mq._rel(weekly, bench, daily[-1], 6) == pytest.approx(0.0)


def test_header_and_the_uptrend_card_measure_the_200d_ema_the_same_way():
    """The header said 2.9% above the 200D EMA while the uptrend card said
    +3.0 (audit, 8 Nov 2026): the header's EMA ran on a two-year window, which
    has not converged. Both read the whole series now."""
    import inspect

    from src.engine.market_questions import ema_gap
    from src.loaders import price_loader

    src = inspect.getsource(price_loader.get_market_regime)
    assert 'period="max"' in src, "the header's regime must read the whole benchmark series"

    s = price_loader.fetch_benchmark_history(period="max").dropna()
    if s.empty:
        return
    ema = s.ewm(span=200, min_periods=160).mean()
    header = (float(s.iloc[-1]) - float(ema.iloc[-1])) / float(ema.iloc[-1]) * 100
    assert round(header, 1) == round(ema_gap(s, s.index[-1]), 1)


def test_a_half_written_benchmarks_file_degrades_instead_of_crashing(tmp_path, monkeypatch):
    """Launch slot 5, 10 Nov 2026: a benchmarks.csv cut off mid-row still
    parses, but its dates come back as STRINGS. Three pages then died inside
    pandas -- "'<' not supported between instances of 'str' and 'Timestamp'"
    on searchsorted and asof -- and served Streamlit's redacted error page.

    One file, two readers, so both reject an undated file; and the comparison
    on the market-questions path returns None rather than raising, wherever
    its index came from.
    """
    import pandas as pd

    from src.engine.market_questions import _on_or_before
    from src.loaders import benchmark_store, index_levels

    half = tmp_path / "benchmarks.csv"
    half.write_text("date,nifty500,nifty50,source\n2026-11-0")   # cut mid-row

    monkeypatch.setattr(index_levels, "BENCHMARKS_FILE", str(half))
    assert index_levels.nse_benchmarks() is None, "an undated file is not usable"

    empty = benchmark_store.read(half)
    assert isinstance(empty.index, pd.DatetimeIndex) and empty.empty

    # And the comparison refuses to raise on a string index.
    assert _on_or_before(pd.Index(["2026-11-05", "2026-11-06"]), pd.Timestamp("2026-11-09")) is None


def test_an_unknown_regime_reads_as_unknown_not_as_zero():
    """With no usable benchmark the header printed "Nifty 500 0.0% above its
    200D EMA" beside a level of "0" -- a wrong number stated as fact, which is
    worse than an error page (launch slot 5)."""
    from src.core.types import MarketRegime, RegimeData
    from src.ui import components

    unknown = RegimeData(status=MarketRegime.UNKNOWN, current_price=0.0,
                         dma_200=0.0, distance_pct=0.0)
    html = components.market_snapshot_html(unknown) if hasattr(
        components, "market_snapshot_html") else None
    if html is None:          # rendered inside render_header_kpi_bar
        import inspect
        src = inspect.getsource(components)
        assert '"— no reading"' in src and 'level_text = "—"' in src
    else:
        assert "no reading" in html and "0.0%" not in html


def test_a_month_end_bar_is_labelled_the_session_that_closed_the_month():
    """Breadth's month-end chart labelled October 2026's close "31 Oct 2026", a
    Saturday with no row in `benchmarks.csv`, while the Dashboard called the
    same close "the 30 Oct month-end" (launch slot 10, TODO S117). A bucket's
    label must be the last session IN the bucket, never the calendar period's
    last day."""
    from src.ui.views.market_questions_view import bucket_by_last_session

    # NSE sessions: October 2026 ends on Friday 30 Oct, November on Monday 30
    # Nov; neither month's calendar last day is 31/30 by accident.
    idx = pd.bdate_range("2026-08-03", "2026-11-09")
    s = pd.Series(range(len(idx)), index=idx, dtype=float)

    monthly = bucket_by_last_session(s, "M")
    for label, value in monthly.items():
        inside = s.loc[(s.index.year == label.year) & (s.index.month == label.month)]
        assert label == inside.index[-1], f"{label:%-d %b %Y} is not the last session of its month"
        assert value == inside.iloc[-1]
        assert label in s.index                      # a date the source carries
    assert pd.Timestamp("2026-10-30") in monthly.index
    assert pd.Timestamp("2026-10-31") not in monthly.index

    # The same for weeks, and for a month whose last session is not its last
    # weekday either (a holiday on 30 Oct would move the label to 29 Oct).
    weekly = bucket_by_last_session(s, "W-FRI")
    for label in weekly.index:
        assert label in s.index
    short = s.drop(pd.Timestamp("2026-10-30"))
    assert pd.Timestamp("2026-10-29") in bucket_by_last_session(short, "M").index
