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

def test_every_name_in_the_drop_list_is_a_real_column():
    """The test this replaces compared my list against my own typo.

    It said "Chandelier Exit"; the engine has always produced "Chand Exit". The
    column was therefore never dropped, and production rendered a Chandelier
    Exit of 930 beside a blank ATR -- a stop computed from an ATR measured at
    0.47x its true width, which is worse than showing nothing.

    The truth now comes from the module that PRODUCES the columns, so a rename
    there cannot leave the drop list silently stale.
    """
    from src.engine.momentum import ATR_DERIVED_COLUMNS
    from src.engine.pipeline import _INTRADAY_ONLY_COLUMNS

    assert tuple(_INTRADAY_ONLY_COLUMNS) == tuple(ATR_DERIVED_COLUMNS)
    assert "Chand Exit" in _INTRADAY_ONLY_COLUMNS, (
        "the chandelier column is not in the drop list under its real name"
    )


def test_the_engine_writes_exactly_the_columns_the_drop_list_names():
    """Derived from the engine's own assignment loop, not from a copy."""
    import inspect
    from src.engine import momentum
    from src.engine.momentum import ATR_DERIVED_COLUMNS

    src = inspect.getsource(momentum.MomentumEngine.compute_atr_and_stops)
    for col in ATR_DERIVED_COLUMNS:
        assert f'"{col}"' in src, (
            f"{col!r} is in the drop list but compute_atr_and_stops never "
            "produces it; the list and the engine have drifted"
        )


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


# ── The served page must not name the vendor ─────────────────────────────────
#
# app.py embeds the startup metrics in a hidden div so a probe can read timings
# out of the served HTML. Hidden is not private -- it is in view-source for
# anyone who opens the page. Which upstream feed the prices came from is the
# operator's business and has no bearing on the timings that div carries.

def test_no_vendor_name_reaches_the_served_page():
    import json
    from src.core import startup_metrics as m

    m.reset_for_tests()
    m.note("price_as_of", "2026-09-18")
    m.note("price_coverage", "750/750")
    m.note("price_source", "screener")
    m.note("screener_store_fetch", "ok")
    m.note("screener_symbols_fetched", 750)
    m.note("price_source_rejected", "screener_too_short")

    served = json.dumps(m.public_snapshot()).lower()
    for word in ("screener", "yahoo", "yfinance"):
        assert word not in served, f"'{word}' leaked into the served page"


def test_redaction_is_prefix_based_so_new_facts_are_safe_by_default():
    """A fact added later must not leak until someone remembers to list it."""
    import json
    from src.core import startup_metrics as m

    m.reset_for_tests()
    m.note("screener_something_invented_tomorrow", "value")
    assert "screener" not in json.dumps(m.public_snapshot()).lower()


def test_redaction_keeps_everything_the_probe_needs():
    """Stripping the timings would make the div pointless."""
    from src.core import startup_metrics as m

    m.reset_for_tests()
    m.note("price_as_of", "2026-09-18")
    m.incr("memo_miss_prices")
    pub = m.public_snapshot()
    assert "uptime_s" in pub and "stages" in pub and "counters" in pub
    assert pub["facts"].get("price_as_of") == "2026-09-18"
    assert pub["counters"].get("memo_miss_prices") == 1


def test_the_app_serves_the_redacted_snapshot():
    src = open("app.py", encoding="utf-8").read()
    assert "metrics.public_snapshot()" in src
    assert "json.dumps(metrics.snapshot())" not in src, (
        "the raw snapshot is being embedded in the page again"
    )


def test_the_ribbon_never_prints_the_source():
    """It is held on the item for internal use, and must stay unrendered."""
    from src.core import startup_metrics as m
    from src.ui.components import age_phrase, data_freshness

    m.reset_for_tests()
    m.note("price_as_of", "2026-09-18"); m.note("price_coverage", "750/750")
    m.note("price_path", "cache_fresh"); m.note("price_source", "screener")
    m.note("price_high_basis", "closing prices"); m.note("price_intraday", "no")

    for item in data_freshness():
        printed = f"{item['label']}: {item['as_of']}"
        printed += f" · {item['coverage']}" if item.get("coverage") else ""
        printed += age_phrase(item)
        assert "screener" not in printed.lower(), f"chip names the vendor: {printed}"
        assert "yahoo" not in printed.lower(), f"chip names the vendor: {printed}"


# ── What the front end calls each source ────────────────────────────────────
#
# The internal ids stay as they are -- they are the contract term, the config
# value and what the logs say -- so the display name cannot change which table
# is accepted or which source gets chosen.

def test_the_display_names():
    assert ps.display_name("screener") == "Personal"
    assert ps.display_name("yahoo") == "Yahoo"


def test_display_is_case_and_whitespace_tolerant():
    assert ps.display_name("  SCREENER ") == "Personal"
    assert ps.display_name("") == ""
    assert ps.display_name(None) == ""


def test_an_unknown_source_still_renders_something():
    """A third source added later must not render as a blank chip."""
    assert ps.display_name("some_new_feed") == "Some New Feed"


def test_renaming_does_not_touch_the_contract():
    """Display is presentation; the contract keeps the id it always had."""
    from src.loaders.ranking_store import contract

    terms = contract(price_fingerprint="a", symbols_fingerprint="b",
                     weights=(0.2,) * 5, pipeline_version="v4",
                     universe=["AAA"], price_source="screener")
    assert terms["price_source"] == "screener", (
        "the display name leaked into the contract; a table written under one "
        "spelling would stop matching one written under the other"
    )


def test_the_source_is_always_shown_now():
    """No token, no query parameter -- every viewer sees it."""
    from src.core import startup_metrics as m
    from src.ui.components import age_phrase, data_freshness

    m.reset_for_tests()
    for k, v in (("price_as_of", "2026-09-18"), ("price_coverage", "750/750"),
                 ("price_path", "cache_fresh"), ("price_source", "screener"),
                 ("price_high_basis", "closing prices"), ("price_intraday", "no")):
        m.note(k, v)
    printed = " | ".join(
        f"{i['label']}: {i['as_of']}{age_phrase(i)}" for i in data_freshness()
    )
    assert "Ranked from: Personal" in printed
    assert "screener" not in printed.lower(), "the raw source id reached the page"


def test_yahoo_shows_under_its_own_name():
    from src.core import startup_metrics as m
    from src.ui.components import data_freshness

    m.reset_for_tests()
    m.note("price_as_of", "2026-09-18"); m.note("price_path", "cache_fresh")
    m.note("price_source", "yahoo"); m.note("price_intraday", "yes")
    chip = next(i for i in data_freshness() if i["label"] == "Ranked from")
    assert chip["as_of"] == "Yahoo"


def test_the_raw_id_still_never_reaches_the_served_html():
    """The hidden metrics div is unchanged by the rename.

    The chip says "Personal"; the div must not say "screener" beside it.
    """
    import json
    from src.core import startup_metrics as m

    m.reset_for_tests()
    m.note("price_source", "screener")
    m.note("screener_store_fetch", "ok")
    m.note("price_as_of", "2026-09-18")
    served = json.dumps(m.public_snapshot()).lower()
    assert "screener" not in served
    assert m.public_snapshot()["facts"].get("price_as_of") == "2026-09-18"


def test_the_app_serves_the_redacted_snapshot():
    src = open("app.py", encoding="utf-8").read()
    assert "metrics.public_snapshot()" in src
    assert "json.dumps(metrics.snapshot())" not in src


# ── Dropping the ATR columns must not break the pages that read them ─────────
#
# Stop Loss is ATR-derived, so it vanishes whenever the ranking came from a
# source with no intraday high. Three places read it and only two degraded
# gracefully: the Portfolio page indexed it directly and took the whole page
# down with a KeyError, and the footer stated "Stop Loss: CMP - 2xATR" for a
# column that was no longer anywhere on screen.

def test_the_portfolio_page_survives_a_missing_stop_loss():
    """The crash. rank_df["Stop Loss"] raises when the column is dropped."""
    import inspect
    from src.ui.views import portfolio_view

    src = inspect.getsource(portfolio_view)
    assert 'rank_df.set_index("Symbol")["Stop Loss"]' not in src or \
           '"Stop Loss" in rank_df.columns' in src, (
        "Stop Loss is read without checking it exists; the Portfolio page "
        "raises KeyError whenever the ranking came from a close-only source"
    )


def test_a_missing_stop_loss_column_maps_to_nothing_rather_than_nan():
    """Mapping an empty dict would fill the column with NaN and still show it."""
    import inspect
    from src.ui.views import portfolio_view

    src = inspect.getsource(portfolio_view)
    assert "if sl_map:" in src, (
        "an absent Stop Loss is being written as an all-NaN column instead of "
        "left out, so the table shows an empty column rather than no column"
    )


def test_the_footer_drops_the_stop_loss_formula_without_intraday_data():
    from src.core import startup_metrics as m
    import inspect
    from src.ui import components

    src = inspect.getsource(components)
    assert "stop_loss_note" in src, (
        "the footer states the 2xATR formula unconditionally, describing a "
        "number the reader cannot find when the column is absent"
    )
    assert 'price_intraday' in src


def test_the_footer_keeps_the_formula_on_yahoo_data():
    """It must not disappear for the source that does have ATR."""
    import inspect
    from src.ui import components

    src = inspect.getsource(components)
    assert '_intraday == "no"' in src, (
        "the footer note is gated on something other than the absence of "
        "intraday data; it would vanish for Yahoo too"
    )



# ── The ribbon must describe the frame that was actually ranked ─────────────
#
# price_as_of was computed straight after extract_ohlcv -- before the source
# was chosen -- so it described the YAHOO frame while the table came from
# screener. Production showed "Prices: 16 Sep - 2 trading days behind" over a
# ranking dated 18 Sep, because Yahoo's 17th and 18th were too thin to rank
# while screener had both at 100%.

def test_the_as_of_metric_is_recorded_after_the_source_is_chosen():
    src = open("app.py", encoding="utf-8").read()
    resolve_at = src.index("_src = _resolve_price_source(")
    as_of_at = src.index('metrics.note("price_as_of"')
    assert as_of_at > resolve_at, (
        "price_as_of is recorded before the source is resolved, so the ribbon "
        "describes a frame the engine may never have scored"
    )


def test_the_coverage_metric_is_recorded_after_the_source_is_chosen():
    src = open("app.py", encoding="utf-8").read()
    resolve_at = src.index("_src = _resolve_price_source(")
    cov_at = src.index('metrics.note("price_coverage"')
    assert cov_at > resolve_at


def test_the_ribbon_date_matches_the_frame_the_engine_ranked():
    """End to end on the two real frames, which disagree by two sessions."""
    import numpy as np
    import pandas as pd
    from src.engine import pipeline

    idx = pd.bdate_range("2025-09-18", "2026-09-18")
    cols = [f"S{i}" for i in range(100)]

    # Yahoo's shape on 2026-09-18: the last two sessions thin/empty
    yahoo = pd.DataFrame(100.0, index=idx, columns=cols)
    yahoo.iloc[-1, :] = np.nan                  # 09-18 at 0%
    yahoo.iloc[-2, 40:] = np.nan                # 09-17 at ~40%
    # screener's shape: complete throughout
    screener = pd.DataFrame(100.0, index=idx, columns=cols)

    assert pipeline.ranking_as_of(yahoo) != pipeline.ranking_as_of(screener), (
        "fixture is wrong: the two sources must disagree for this to mean "
        "anything"
    )
    assert pipeline.ranking_as_of(screener) == str(idx[-1].date())
