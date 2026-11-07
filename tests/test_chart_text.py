"""Every chart frame carries its content in words (audit F26)."""
import pandas as pd

from src.ui import charts, lw_chart


def _panes():
    return [{"series": [
        {"name": "Strategy", "fmt": "rupee",
         "data": [("2026-01-30", 2_000_000.0), ("2026-06-01", 1_900_000.0), ("2026-11-06", 2_827_942.0)]},
        {"name": "Nifty 500", "fmt": "pct", "data": [("2026-01-30", 0.0), ("2026-11-06", -3.2)]},
        {"name": "Price", "type": "candlestick", "fmt": "num",
         "data": [("2026-11-05", 10, 12, 9, 11.0), ("2026-11-06", 11, 13, 10, 12.5)]},
    ]}]


def test_time_series_summary_reads_first_last_low_and_high():
    text = lw_chart.summary(_panes())
    assert ("Strategy: ₹20,00,000 on 30 Jan 2026, ₹28,27,942 on 6 Nov 2026; "
            "low ₹19,00,000, high ₹28,27,942.") in text
    assert "Nifty 500: 0.0% on 30 Jan 2026, −3.2% on 6 Nov 2026" in text
    assert "Price: 11.00 on 5 Nov 2026, 12.50 on 6 Nov 2026" in text   # a candle reads its close


def test_time_series_frame_hides_the_drawing_and_names_its_series():
    out = lw_chart.chart_html(_panes())
    assert "<title>Chart: Strategy, Nifty 500, Price</title>" in out
    assert "<div id='root' aria-hidden='true'>" in out
    assert "class='sr'>Strategy: ₹20,00,000" in out


def test_summary_text_is_escaped():
    out = lw_chart.chart_html([{"series": [{"name": "<b>x</b>", "data": [("2026-11-05", 1.0), ("2026-11-06", 2.0)]}]}])
    assert "<b>x</b>" not in out and "&lt;b&gt;x&lt;/b&gt;" in out


def test_rrg_summary_names_industries_by_quadrant():
    text = charts.rrg_summary([
        {"industry": "Pharma", "rs_ratio": 104, "quadrant": "Leading"},
        {"industry": "Banks", "rs_ratio": 97, "quadrant": "Lagging"},
        {"industry": "Metals", "rs_ratio": 106, "quadrant": "Leading"},
    ])
    assert text == "Leading: Metals, Pharma. Lagging: Banks."
    assert "Leading: Metals" in charts._build_rrg_html("{}", text)
    assert 'id="scroller" aria-hidden="true"' in charts._build_rrg_html("{}", text)


def test_correlation_summary_names_the_most_and_least_alike_pair():
    c = pd.DataFrame([[1, 0.8, 0.1], [0.8, 1, -0.2], [0.1, -0.2, 1]],
                     index=list("ABC"), columns=list("ABC"), dtype=float)
    assert charts.correlation_summary(c) == (
        "Correlation of daily returns of 3 stocks. Most alike: A and B (0.80). "
        "Least alike: B and C (−0.20).")


def test_portfolio_curve_ends_on_the_account_value_shown_above_it():
    from src.ui.views import portfolio_view as pv
    days = pd.bdate_range("2026-10-26", "2026-11-06")
    eq = pd.Series([100.0, 101.0], index=days[:2])
    history = {"equity_daily": eq, "benchmark_daily": eq.copy(),
               "equity": eq, "benchmark": eq}
    prices = pd.DataFrame({"A": [10.0] * len(days)}, index=days)
    prices.iloc[-1, 0] = 10.004                       # the store's close, paise off the table's CMP
    table = pd.DataFrame({"Symbol": ["A"], "Shares": [100.0]})
    out, _ = pv._daily_with_live(history, table, prices, {"fill_date": "2026-10-26"}, None,
                                 value=1_050.0, current=1_000.0)
    assert out.iloc[-1] == 1_050.0
    assert out.iloc[-2] == 10.0 * 100 + 50.0


def test_search_list_shows_plain_labels():
    from src.ui.views.ranking_view import search_label
    assert search_label("[STOCK] LAURUSLABS — Healthcare") == "LAURUSLABS · Healthcare"
    assert search_label("[STOCK] NEWCO — nan") == "NEWCO"
    assert search_label("[INDUSTRY] Healthcare") == "Healthcare · industry"
    assert search_label("[INDEX] Nifty 50") == "Nifty 50 · index"


def test_screener_filters_round_trip_through_the_address():
    from unittest import mock

    from src.ui.views import ranking_view as rv
    values = {"rank_quick_pills": "Passed Filters", "rank_index_filter": ["N50", "MID150"],
              "rank_only_passing": True, "rank_density_mode": "Full Quant (35)"}
    url = {rv._URL_KEYS[k]: rv._to_url(k, v) for k, v in values.items()}
    assert url == {"view": "pass", "idx": "N50,MID150", "pass": "1", "cols": "full"}
    with mock.patch.object(rv.st, "query_params", url):
        assert {k: rv._from_url(k) for k in values} == values
    # Defaults stay out of the address.
    assert rv._to_url("rank_quick_pills", "All Universe") is None
    assert rv._to_url("rank_density_mode", "Core (17)") is None
