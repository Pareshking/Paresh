"""All five calendar windows are computed, published, and rendered.

get_rankings previously published only 3M and 6M return/Sharpe/drawdown, even
though apply_calendar_momentum had already computed every one of the five
canonical windows and stored them in period_metrics. The other three were
discarded, so the Full Quant view and the CSV could not show 1M, 9M or 12M.

Also guards the table's column arithmetic: the group header row, the sub-header
row and the body cells must agree, or every group label sits over the wrong
column. The Core tier was already off by one before these columns were added.
"""
import re

import numpy as np
import pandas as pd
import pytest

from src.core.config import MOMENTUM_WINDOWS
from src.engine.momentum import MomentumEngine
from src.ui import theme
from src.ui.views.ranking_view import DISPLAY_COLS


@pytest.fixture(scope="module")
def ranked():
    n, cols = 500, 6
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    rng = np.random.default_rng(4)
    px = pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0, 0.012, (n, cols)), axis=0)),
        index=idx, columns=[f"S{i}" for i in range(cols)],
    )
    info = pd.DataFrame({
        "Symbol": [f"S{i}" for i in range(cols)],
        "Industry": ["IT", "Bank"] * (cols // 2),
        "Indices": ["NIFTY"] * cols,
    })
    calc = MomentumEngine(
        px, high_df=px * 1.01, low_df=px * 0.99, close_df=px,
        volume_df=pd.DataFrame(1e5, index=idx, columns=px.columns),
    )
    rank_df = calc.get_rankings(
        info, pd.Series(1e4, index=px.columns),
        close_prices_df=px, high_prices_df=px * 1.01,
    )
    return rank_df, px


@pytest.mark.parametrize("months", MOMENTUM_WINDOWS)
def test_every_window_publishes_return_sharpe_and_drawdown(ranked, months):
    rank_df, _ = ranked
    for col in (f"{months}M Return", f"{months}M Sharpe", f"Max DD {months}M"):
        assert col in rank_df.columns, col
        assert rank_df[col].notna().any(), f"{col} is entirely NaN"


def test_all_five_windows_are_covered():
    assert sorted(MOMENTUM_WINDOWS) == [1, 3, 6, 9, 12]


@pytest.mark.parametrize("months", MOMENTUM_WINDOWS)
def test_period_columns_are_in_the_display_list(months):
    for col in (f"{months}M Return", f"{months}M Sharpe", f"Max DD {months}M"):
        assert col in DISPLAY_COLS, col


def test_longer_windows_are_not_copies_of_shorter_ones(ranked):
    """A wiring slip that mapped every window to the same series would pass
    the presence checks above."""
    rank_df, _ = ranked
    series = {m: rank_df[f"{m}M Return"] for m in MOMENTUM_WINDOWS}
    assert not series[1].equals(series[12])
    assert not series[3].equals(series[9])


def test_reused_period_metrics_match_a_direct_recompute(ranked):
    """Reading period_metrics must equal recomputing, or the reuse is a bug."""
    from src.engine.calendar_momentum import _calendar_period_metrics, latest_as_of_date

    rank_df, px = ranked
    calc = MomentumEngine(px)
    as_of = latest_as_of_date(pd.DatetimeIndex(calc.prices.index))
    for months in MOMENTUM_WINDOWS:
        _, cal_ret, _, _ = _calendar_period_metrics(
            calc.prices, calc.log_ret, months, latest_as_of=as_of
        )
        direct = cal_ret.iloc[-1]
        published = rank_df.set_index("Symbol")[f"{months}M Return"]
        for sym in published.index:
            assert published[sym] == pytest.approx(direct[sym], rel=1e-9)


# ── Table column arithmetic ─────────────────────────────────────────────────

def _span(block: str) -> int:
    total = 0
    for m in re.finditer(r"<th([^>]*)>", block):
        cs = re.search(r'colspan="(\d+)"', m.group(1))
        total += int(cs.group(1)) if cs else 1
    return total


def _render(rank_df, px, density):
    captured = {}
    orig_iframe, orig_info = theme.st.iframe, theme.st.info
    theme.st.iframe = lambda h, **k: captured.setdefault("html", h)
    theme.st.info = lambda *a, **k: None
    try:
        theme.render_master_screener_table(
            rank_df, prices_df=px, key="t", density=density
        )
    finally:
        theme.st.iframe, theme.st.info = orig_iframe, orig_info
    return captured["html"]


@pytest.mark.parametrize("density", ["Executive (11)", "Core (17)", "Full Quant (35)"])
def test_header_groups_subheaders_and_cells_all_agree(ranked, density):
    rank_df, px = ranked
    html = _render(rank_df, px, density)
    groups = re.search(r'<tr class="group-header-row">(.*?)</tr>', html, re.S).group(1)
    subs = re.search(r'<tr class="sub-header-row">(.*?)</tr>', html, re.S).group(1)
    first = re.search(r'<tr class="screener-row">(.*?)</tr>', html, re.S).group(1)

    assert _span(groups) == _span(subs) == len(re.findall(r"<td", first))


@pytest.mark.parametrize("months", MOMENTUM_WINDOWS)
def test_full_quant_renders_a_column_for_every_window(ranked, months):
    rank_df, px = ranked
    html = _render(rank_df, px, "Full Quant (35)")
    assert f"{months}M RET" in html
    assert f"{months}M SHARPE" in html
    assert f"MAX DD {months}M" in html


def test_full_quant_is_wider_than_core_which_is_wider_than_executive(ranked):
    rank_df, px = ranked
    widths = []
    for d in ("Executive (11)", "Core (17)", "Full Quant (35)"):
        html = _render(rank_df, px, d)
        first = re.search(r'<tr class="screener-row">(.*?)</tr>', html, re.S).group(1)
        widths.append(len(re.findall(r"<td", first)))
    assert widths[0] < widths[1] < widths[2]


def test_52w_high_carries_the_date_it_was_printed(ranked):
    """A high without its date is the same assertion in a shorter window.

    "12% off the high" reads very differently if that high was last week rather
    than eleven months ago, so the 52-week high now carries a date exactly as
    the all-time high does.
    """
    rank_df, _ = ranked
    assert "52W High Date" in rank_df.columns
    dates = rank_df["52W High Date"].astype(str)
    assert (dates.str.len() == 10).all(), "expected ISO dates"
    assert dates.str.match(r"\d{4}-\d{2}-\d{2}").all()


def test_an_all_nan_column_does_not_break_the_52w_high_date():
    """idxmax() raises "Encountered all NA values" on an empty column, which is
    exactly what a rate-limited ticker looks like."""
    import numpy as np
    import pandas as pd

    from src.engine.momentum import MomentumEngine

    n = 300
    idx = pd.bdate_range(end="2026-08-18", periods=n)
    px = pd.DataFrame(
        {"GOOD": np.linspace(100, 200, n), "DEAD": np.full(n, np.nan)}, index=idx
    )
    info = pd.DataFrame({"Symbol": ["GOOD", "DEAD"], "Industry": ["IT", "IT"]})
    calc = MomentumEngine(px, high_df=px, low_df=px, close_df=px,
                          volume_df=pd.DataFrame(1e5, index=idx, columns=px.columns))
    rank_df = calc.get_rankings(info, pd.Series(dtype=float),
                                close_prices_df=px, high_prices_df=px)
    assert "52W High Date" in rank_df.columns          # must not raise
