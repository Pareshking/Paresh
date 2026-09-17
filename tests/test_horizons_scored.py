"""The composite renormalises over available horizons, and nothing said so.

`_apply_weight_composite` divides by the weight that actually carried a score,
not by the full weight, so a stock listed four months ago is scored on 1M and
3M alone and still lands on the same 0-centred scale as a name with all five.
That is the right way to combine them -- but it means two ranks sitting beside
each other can be averages over different numbers of terms, and the shorter one
moves more between sessions for reasons that are about its listing date.

"Short History" does not cover this: it thresholds raw observation count at 126
sessions, and a stock can clear that and still be missing the 12M horizon.
"""
import re
import types

import numpy as np
import pandas as pd
import pytest

from src.engine.calendar_momentum import (
    _apply_weight_composite,
    _compute_period_z_scores,
    apply_calendar_momentum,
    horizons_scored,
)
from src.engine.momentum import MomentumEngine
from src.engine.pipeline import build_engine, rank_with_weights
from src.ui import theme
from src.ui.views.ranking_view import DISPLAY_COLS

# Sessions of history per symbol, newest-first. Spans every boundary that
# matters: full history, just under each horizon, and far too little.
HISTORY = {
    "S00": 600, "S01": 600, "S02": 400, "S03": 200, "S04": 130, "S05": 85,
    "S06": 45, "S07": 20, "S08": 260, "S09": 600, "S10": 310, "S11": 5,
}
SYMBOLS = list(HISTORY)


def _staggered_prices() -> pd.DataFrame:
    n = 600
    idx = pd.bdate_range(end="2026-08-31", periods=n)
    rng = np.random.default_rng(11)
    px = pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0.0005, 0.015, (n, len(SYMBOLS))), axis=0)),
        index=idx,
        columns=SYMBOLS,
    )
    for sym, sessions in HISTORY.items():
        px.loc[px.index[: n - sessions], sym] = np.nan
    return px


def _index_info() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Symbol": SYMBOLS,
            "Company Name": SYMBOLS,
            "Industry": ["IT"] * len(SYMBOLS),
            "Indices": ["N50"] * len(SYMBOLS),
        }
    )


def _engine() -> MomentumEngine:
    calc = MomentumEngine(_staggered_prices(), weights=[0.2] * 5)
    _compute_period_z_scores(calc)
    return calc


def test_the_count_is_exactly_the_set_the_composite_renormalised_over():
    """Not an approximation of history length -- the same notna() test."""
    calc = _engine()
    counts = horizons_scored(calc)

    for sym in SYMBOLS:
        expected = sum(
            bool(pd.notna(calc._period_z_scores[m].iloc[-1].get(sym)))
            for m in (1, 3, 6, 9, 12)
        )
        assert counts[sym] == expected, sym

    assert counts.dtype == "int64", "a count of horizons is an integer"
    assert (counts >= 0).all() and (counts <= 5).all()


def test_more_history_never_scores_fewer_horizons():
    counts = horizons_scored(_engine())
    by_history = sorted(SYMBOLS, key=lambda s: -HISTORY[s])
    for longer, shorter in zip(by_history, by_history[1:]):
        assert counts[longer] >= counts[shorter], f"{longer} vs {shorter}"

    # The two ends of the range, pinned: full history scores all five, and a
    # week of prints scores none.
    assert counts["S00"] == 5
    assert counts["S11"] == 0


def test_the_count_does_not_move_when_the_weight_sliders_do():
    """A horizon weighted to zero was still evaluated.

    The count describes how much history is behind the number, which is a
    property of the data, not of the user's slider positions. It is read off
    the weight-independent z-score matrices for exactly that reason.
    """
    calc = _engine()
    before = horizons_scored(calc)
    _apply_weight_composite(calc, [1.0, 0.0, 0.0, 0.0, 0.0])
    assert horizons_scored(calc).equals(before)
    _apply_weight_composite(calc, [0.0, 0.0, 0.0, 0.0, 1.0])
    assert horizons_scored(calc).equals(before)


def test_both_ranking_paths_publish_the_same_integer_column():
    """The fast path joins _static_signals; the slow path computes inline.

    Two code paths producing one column is how a column comes to mean two
    things, so pin them against each other rather than against a literal.
    """
    px = _staggered_prices()
    info = _index_info()
    mcaps = pd.Series({s: 1e11 for s in SYMBOLS})
    vol = pd.DataFrame(1e6, index=px.index, columns=SYMBOLS)

    _, fast = rank_with_weights(
        build_engine(px, px, px, px, vol, info, mcaps),
        [0.2] * 5, info, mcaps, px, px,
    )
    slow = MomentumEngine(
        px, high_df=px, low_df=px, close_df=px, volume_df=vol, weights=[0.2] * 5
    ).get_rankings(info, mcaps, close_prices_df=px, high_prices_df=px)

    a = fast.set_index("Symbol")["Horizons Scored"].sort_index()
    b = slow.set_index("Symbol")["Horizons Scored"].sort_index()
    assert a.equals(b)
    assert a.dtype == "int64" and b.dtype == "int64"
    assert not a.empty


def test_it_flags_stocks_short_history_calls_long_enough():
    """The reason this is not redundant with the column next to it.

    "Short History" is a 126-session threshold on raw observation count. A
    stock with 200 sessions clears it and is still missing the 12M horizon.
    """
    px = _staggered_prices()
    info = _index_info()
    mcaps = pd.Series({s: 1e11 for s in SYMBOLS})
    vol = pd.DataFrame(1e6, index=px.index, columns=SYMBOLS)

    _, ranked = rank_with_weights(
        build_engine(px, px, px, px, vol, info, mcaps),
        [0.2] * 5, info, mcaps, px, px,
    )
    ranked = ranked.set_index("Symbol")
    missed = [
        s for s in ranked.index
        if ranked.loc[s, "Short History"] == "No"
        and int(ranked.loc[s, "Horizons Scored"]) < 5
    ]
    assert missed, "the fixture must contain a stock the old column calls fine"


def test_an_empty_engine_reports_no_horizons_rather_than_raising():
    calc = MomentumEngine(pd.DataFrame(), weights=[0.2] * 5)
    apply_calendar_momentum(calc)
    counts = horizons_scored(calc)
    assert counts.empty and counts.dtype == "int64"


def test_the_screener_column_is_on_screen_and_in_the_export():
    assert "Horizons Scored" in DISPLAY_COLS
    assert theme.FORMAT_MAP["Horizons Scored"] == "{:.0f}"


@pytest.mark.parametrize(
    "density", ["Executive (11)", "Core (18)", "Full Quant (35)"]
)
def test_every_density_tier_keeps_its_headers_over_its_cells(density, monkeypatch):
    """A new column is three edits: the cell, the sub-header, and the colspan.

    Miss the colspan and the group bar silently slides one column left for
    every reader, which no assertion about the DataFrame would catch.
    """
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        theme, "st",
        types.SimpleNamespace(
            iframe=lambda html, height=None: captured.setdefault("html", html),
            info=lambda *a, **k: None,
        ),
    )
    theme.render_master_screener_table(
        pd.DataFrame(
            {
                "Rank": [1, 2, 3],
                "Symbol": ["AAA", "BBB", "CCC"],
                "Industry": ["Tech", "Bank", "Auto"],
                "Indices": ["NIFTY 50"] * 3,
                "CMP": [100.0, 200.0, 300.0],
                "Horizons Scored": [5, 2, 0],
            }
        ),
        prices_df=None,
        density=density,
    )
    html = captured["html"]

    cells = {
        len(re.findall(r"<td[ >]", row))
        for row in re.findall(r'<tr class="screener-row">(.*?)</tr>', html, re.S)
    }
    assert len(cells) == 1, "rows disagree on their own column count"
    n_cells = cells.pop()

    group = re.search(r'<tr class="group-header-row">(.*?)</tr>', html, re.S).group(1)
    spans = sum(
        int(m or 1)
        for m in re.findall(r'<th(?:[^>]*?colspan="(\d+)")?[^>]*>', group)
    )
    sub = re.search(r'<tr class="sub-header-row">(.*?)</tr>', html, re.S).group(1)
    n_sub = len(re.findall(r"<th[ >]", sub))

    assert n_cells == n_sub == spans


def test_a_partial_composite_is_marked_and_a_full_one_is_not(monkeypatch):
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        theme, "st",
        types.SimpleNamespace(
            iframe=lambda html, height=None: captured.setdefault("html", html),
            info=lambda *a, **k: None,
        ),
    )
    theme.render_master_screener_table(
        pd.DataFrame(
            {
                "Rank": [1, 2],
                "Symbol": ["FULL", "PART"],
                "Industry": ["Tech", "Tech"],
                "Indices": ["NIFTY 50"] * 2,
                "CMP": [100.0, 200.0],
                "Horizons Scored": [5, 2],
            }
        ),
        prices_df=None,
        density="Full Quant (35)",
    )
    html = captured["html"]
    assert ">5/5</span>" in html and ">2/5</span>" in html

    # Count inside the rows only -- the stylesheet in the same document
    # defines .td-short-hz and would otherwise be counted as a use.
    rows = "".join(re.findall(r'<tr class="screener-row">(.*?)</tr>', html, re.S))
    assert rows.count("td-short-hz") == 1, "only the partial composite is marked"
    assert "td-short-hz" in [r for r in rows.split("<tr") if "PART" in r][0]
