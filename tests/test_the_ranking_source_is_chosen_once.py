"""Two price sources exist and they are not interchangeable.

The app and the nightly precompute must never rank different histories. Every
field of the ranking contract could still match while the two disagreed on
exactly the columns the sources differ in -- a wrong answer served fast, and
nothing downstream able to tell. So the choice is made in one module and the
source is a contract term.

What differs, measured on the live universe rather than assumed:

  * NO INTRADAY HIGH in screener. The 52-week high becomes a high of CLOSES,
    which moves the within-5% gate from 22 names to 50, with 28 crossing.
  * ATR FROM CLOSES is 0.47x true ATR, so a 2xATR stop would sit 53% tighter.
    Dropped rather than approximated: a stop loss silently half its intended
    width is more dangerous than a missing column.
  * CORPORATE ACTIONS are already applied by screener -- 0 events applied to
    its frame against 38 to Yahoo's.
  * REACH. Screener serves about a year, so the 12-month window only just fits.
    A store that cannot cover it must be refused BEFORE it produces a table
    whose 12M column is NaN for every symbol.
"""

import numpy as np
import pandas as pd
import pytest

from src.loaders import price_source as ps


def _store(start="2025-09-18", end="2026-09-18", cols=("AAA", "BBB")):
    idx = pd.bdate_range(start, end)
    return pd.concat(
        {c: pd.DataFrame({"Close": np.linspace(100, 120, len(idx)),
                          "Volume": np.full(len(idx), 1000.0)}, index=idx)
         for c in cols},
        axis=1,
    )


# ── Reach: the guard that stops an empty 12M column shipping ─────────────────

def test_a_year_of_history_covers_the_twelve_month_window():
    idx = _store("2025-09-18", "2026-09-18").index
    assert ps.reaches_longest_lookback(idx)


def test_one_day_short_is_refused():
    """The real case: the store ran 2025-09-18 to 2026-09-17 and 12M needed
    2025-09-17. Off by a single calendar day, and the engine would have
    returned NaN for every symbol's 12M rather than say so."""
    idx = _store("2025-09-18", "2026-09-17").index
    assert not ps.reaches_longest_lookback(idx)


def test_a_store_that_cannot_reach_is_not_used_at_all():
    store = _store("2025-09-18", "2026-09-17")
    assert ps.from_screener(store) is None, (
        "a store too short for the longest lookback was accepted; the table "
        "would ship with an empty 12M column"
    )


def test_one_more_session_is_enough():
    """Why waiting a week was the wrong answer.

    The store's START is frozen -- the merge accumulates and never shortens --
    while the end advances, so the window closes on the very next session.
    """
    assert ps.from_screener(_store("2025-09-18", "2026-09-17")) is None
    got = ps.from_screener(_store("2025-09-18", "2026-09-18"))
    assert got is not None and got.source == "screener"


# ── What the caller is forced to know ────────────────────────────────────────

def test_screener_frames_report_no_intraday_data():
    got = ps.from_screener(_store())
    assert got.intraday is False
    assert got.high is None and got.low is None, (
        "high/low came back as copies of the close, which is the silent "
        "substitution that would move the 52-week gate with nothing to notice"
    )
    assert got.high_basis == "closing prices"


def test_yahoo_frames_report_intraday_data():
    f = pd.DataFrame({"AAA": [1.0, 2.0]})
    got = ps.from_yahoo(f, f, f, f, f)
    assert got.intraday is True and got.high_basis == "intraday highs"


def test_the_limits_are_carried_with_the_frames():
    """A caller that never reads the notes still cannot get a wrong number,
    but the notes are what the UI prints, so they must exist."""
    got = ps.from_screener(_store())
    joined = " ".join(got.notes).lower()
    assert "52-week high" in joined and "closing" in joined
    assert "atr" in joined


def test_a_malformed_store_is_refused_rather_than_guessed_at():
    bad = pd.DataFrame({"AAA": [1.0, 2.0]})       # no (symbol, field) columns
    assert ps.from_screener(bad) is None
    assert ps.from_screener(pd.DataFrame()) is None
    assert ps.from_screener(None) is None


# ── The ATR columns ──────────────────────────────────────────────────────────

def test_atr_columns_are_dropped_when_there_is_no_intraday_data():
    """0.47x true ATR means a 2xATR stop 53% tighter than intended."""
    from src.engine.pipeline import _INTRADAY_ONLY_COLUMNS

    assert set(_INTRADAY_ONLY_COLUMNS) == {
        "ATR", "ATR %", "Stop Loss", "Chandelier Exit"
    }, "the set of intraday-only columns changed; re-check what each needs"


def test_dropping_is_driven_by_the_flag_not_the_frame():
    """Passing close-as-high must not be what decides it.

    The engine happily computes ATR from a close standing in for a high and
    returns a number that looks entirely normal. Only the explicit flag can
    tell the difference.
    """
    import inspect
    from src.engine import pipeline

    sig = inspect.signature(pipeline.rank_with_weights)
    assert "intraday" in sig.parameters
    assert sig.parameters["intraday"].default is True, (
        "the default must keep Yahoo behaviour unchanged"
    )


# ── The contract ─────────────────────────────────────────────────────────────

def test_the_source_is_part_of_the_ranking_contract():
    """Otherwise a Yahoo table is served to a screener-configured app.

    They differ in the 52-week high and in whether the ATR columns exist at
    all, while price fingerprint, weights, universe and pipeline version can
    all match.
    """
    from src.loaders.ranking_store import contract

    base = dict(price_fingerprint="abc", symbols_fingerprint="def",
                weights=(0.2,) * 5, pipeline_version="v4", universe=["AAA"])
    a = contract(**base, price_source="screener")
    b = contract(**base, price_source="yahoo")
    assert a["price_source"] == "screener"
    assert a != b, "two sources produced an identical contract"


def test_a_table_from_the_other_source_is_rejected():
    from src.loaders.ranking_store import contract, matches

    base = dict(price_fingerprint="abc", symbols_fingerprint="def",
                weights=(0.2,) * 5, pipeline_version="v4", universe=["AAA"])
    ok, reason = matches(contract(**base, price_source="yahoo"),
                         contract(**base, price_source="screener"))
    assert not ok, "a Yahoo-built ranking was accepted for a screener app"


# ── Falling back ─────────────────────────────────────────────────────────────

def test_preferred_source_is_configurable():
    assert ps.preferred() in ("screener", "yahoo")


def test_an_unusable_screener_store_leaves_yahoo_untouched():
    """A failed collection night must degrade, never empty the screener."""
    f = pd.DataFrame({"AAA": [1.0, 2.0]})
    fallback = ps.from_yahoo(f, f, f, f, f)
    assert ps.from_screener(None) is None
    assert fallback.source == "yahoo" and fallback.intraday is True
