"""A precomputed ranking is a cache of a pure function, and must behave like one.

The nightly job ranks the snapshot it publishes and ships the answer, so a cold
start can read a table instead of deriving it while somebody watches a spinner.

The failure that matters is NOT a miss. A miss costs what the app always paid.
The failure that matters is a HIT THAT SHOULD HAVE BEEN A MISS -- a ranking
served fast against prices, a universe or weights it does not describe. Nothing
downstream can detect that: every column looks plausible, the page renders, and
the reader acts on a number computed from something else. So every input is
written into the artifact and every input is re-checked, and these tests exist
to keep it that way.

The other half of the contract is that ONE implementation produces both tables.
If the job and the app ever compute the ranking differently, the artifact stops
being a cache and becomes a second opinion.
"""

import numpy as np
import pandas as pd
import pytest

from src.engine import pipeline
from src.loaders import ranking_store


@pytest.fixture
def rank_df():
    return pd.DataFrame(
        {
            "Symbol": ["AAA", "BBB", "CCC"],
            "Rank": [1, 2, 3],
            "Score": [2.5, 1.0, -0.5],
            "Near 52W High": [True, True, False],
        }
    )


@pytest.fixture
def terms():
    return ranking_store.contract(
        price_fingerprint="2026-09-15_499x3751_abc123",
        symbols_fingerprint="deadbeef",
        weights=(0.10, 0.30, 0.30, 0.20, 0.10),
        pipeline_version=pipeline.PIPELINE_VERSION,
        universe=["AAA", "BBB", "CCC"],
        price_as_of="2026-09-15",
    )


# ── The artifact carries its own contract ────────────────────────────────────

def test_the_table_round_trips_unchanged(tmp_path, rank_df, terms):
    path = str(tmp_path / "rankings.parquet")
    ranking_store.write_snapshot(path, rank_df, terms)
    back, published = ranking_store.read_snapshot(path)
    pd.testing.assert_frame_equal(back, rank_df)
    assert published == terms


def test_the_contract_travels_inside_the_file(tmp_path, rank_df, terms):
    """Not in a sidecar. Two assets can arrive out of step, at which point the
    app would check a contract that does not describe the table it holds."""
    path = str(tmp_path / "rankings.parquet")
    ranking_store.write_snapshot(path, rank_df, terms)
    assert list(tmp_path.iterdir()) == [tmp_path / "rankings.parquet"]
    _, published = ranking_store.read_snapshot(path)
    assert published["price_fingerprint"] == terms["price_fingerprint"]


def test_an_unreadable_file_is_reported_not_raised(tmp_path):
    bad = tmp_path / "rankings.parquet"
    bad.write_bytes(b"this is not a parquet file")
    frame, published = ranking_store.read_snapshot(str(bad))
    assert frame is None and published is None


# ── Every input is re-checked ────────────────────────────────────────────────

def test_an_exact_match_is_accepted(terms):
    ok, why = ranking_store.matches(dict(terms), terms)
    assert ok, why


@pytest.mark.parametrize(
    "field, value",
    [
        ("price_fingerprint", "2026-09-16_500x3751_zzz999"),
        ("symbols_fingerprint", "cafebabe"),
        ("pipeline_version", "v3_something_older"),
    ],
)
def test_a_changed_input_is_rejected(terms, field, value):
    published = dict(terms)
    published[field] = value
    ok, why = ranking_store.matches(published, terms)
    assert not ok, f"{field} changed and the table was still accepted"
    assert field in why


def test_different_weights_are_rejected(terms):
    """The reader moved a slider. Their ranking is not the published one."""
    published = dict(terms, weights=[0.2, 0.2, 0.2, 0.2, 0.2])
    ok, why = ranking_store.matches(published, terms)
    assert not ok and "weights" in why


def test_a_changed_universe_is_rejected(terms):
    published = dict(terms, universe=["AAA", "BBB"])
    ok, why = ranking_store.matches(published, terms)
    assert not ok and "universe" in why


def test_a_missing_contract_is_rejected(terms):
    ok, why = ranking_store.matches(None, terms)
    assert not ok


def test_float_noise_in_the_weights_does_not_cause_a_miss(terms):
    """A JSON round trip must not be the reason a valid table is thrown away."""
    published = dict(terms, weights=[0.1 + 1e-12, 0.3, 0.3, 0.2, 0.1])
    ok, why = ranking_store.matches(published, terms)
    assert ok, why


def test_the_stored_weights_are_normalised_the_same_way_both_sides():
    """The app normalises weights to sum to 1 before ranking; the job must too,
    or every cold start misses on a contract that is really the same setting."""
    a = ranking_store.contract(
        price_fingerprint="p", symbols_fingerprint="s",
        weights=(0.1, 0.3, 0.3, 0.2, 0.1), pipeline_version="v", universe=["A"],
    )
    raw = (1.0, 3.0, 3.0, 2.0, 1.0)
    total = sum(raw)
    b = ranking_store.contract(
        price_fingerprint="p", symbols_fingerprint="s",
        weights=tuple(w / total for w in raw), pipeline_version="v", universe=["A"],
    )
    ok, why = ranking_store.matches(a, b)
    assert ok, why


# ── The fingerprint actually discriminates ───────────────────────────────────

def test_the_fingerprint_moves_when_the_last_row_moves():
    """Within a session only the final row changes. A fingerprint blind to it
    would serve the morning's ranking on an afternoon page dated today."""
    idx = pd.date_range("2026-09-01", periods=5, freq="B")
    a = pd.DataFrame({"AAA": [10.0, 11, 12, 13, 14]}, index=idx)
    b = a.copy()
    b.iloc[-1, 0] = 14.5
    assert pipeline.price_fingerprint(a) != pipeline.price_fingerprint(b)


def test_the_fingerprint_is_stable_for_an_identical_frame():
    idx = pd.date_range("2026-09-01", periods=5, freq="B")
    a = pd.DataFrame({"AAA": [10.0, 11, 12, 13, 14]}, index=idx)
    assert pipeline.price_fingerprint(a) == pipeline.price_fingerprint(a.copy())


def test_the_fingerprint_survives_an_empty_frame():
    assert pipeline.price_fingerprint(pd.DataFrame()) == "empty"
    assert pipeline.price_fingerprint(None) == "empty"


def test_symbols_fingerprint_ignores_order_and_case():
    assert pipeline.symbols_fingerprint(["aaa", "BBB"]) == \
           pipeline.symbols_fingerprint(["BBB", "AAA"])


def test_symbols_fingerprint_notices_a_added_symbol():
    assert pipeline.symbols_fingerprint(["AAA"]) != \
           pipeline.symbols_fingerprint(["AAA", "BBB"])


# ── One implementation, two callers ──────────────────────────────────────────

def test_the_app_and_the_job_share_the_pipeline_functions():
    """If either grows its own copy of the arithmetic, the artifact stops being
    a cache and becomes a second opinion nothing can reconcile."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text()
    job = (root / "scripts/sync_data.py").read_text()
    for source, name in ((app, "app.py"), (job, "scripts/sync_data.py")):
        assert "pipeline.build_engine" in source, f"{name} no longer shares build_engine"
        assert "pipeline.rank_with_weights" in source, (
            f"{name} no longer shares rank_with_weights"
        )
    # And neither may construct the engine directly any more.
    assert "MomentumEngine(" not in app, (
        "app.py builds the engine itself again; that is how the two drift"
    )


def test_the_job_ranks_the_snapshot_it_publishes():
    """Ranking the 10y archive instead would fingerprint a frame production
    never sees, and every cold start would miss."""
    import pathlib

    job = (pathlib.Path(__file__).resolve().parents[1] / "scripts/sync_data.py").read_text()
    body = job[job.index("def _precompute_rankings"):job.index("def run_daily_sync")]
    assert "prices_snapshot.parquet" in body, (
        "the precompute no longer ranks the frame production seeds from"
    )
    assert "adjust_ohlc" in body, (
        "the precompute skips the corporate action step the live path applies"
    )


def test_the_pipeline_version_is_recorded_not_hardcoded_at_the_call_site():
    """A bumped engine must invalidate the artifact, which only works if both
    sides read the same constant."""
    import pathlib

    app = (pathlib.Path(__file__).resolve().parents[1] / "app.py").read_text()
    assert "pipeline.PIPELINE_VERSION" in app
    assert '"v4_calendar_periods"' not in app, (
        "app.py hardcodes a pipeline version again; bump it and the artifact "
        "would still be trusted"
    )


# ── Changing the lookback must never be served from a stale artifact ─────────
#
# Two different things go by "changing the lookback", and they fail differently.
#
# THE WEIGHTS are a reader's setting -- five sliders over fixed 1/3/6/9/12-month
# windows. They travel in the contract as their own field, so moving one misses
# and the engine runs live. Slower, never wrong.
#
# THE HORIZONS are build-time constants. Edit MOMENTUM_MONTHS and deploy, and
# the running app scores different windows immediately while the published table
# is still last night's, computed over the old ones -- with the price frame, the
# universe and the weights all still matching. A hand-bumped version string only
# catches that when somebody remembers, and the case where they forget is the
# dangerous one: a ranking for horizons nobody is running, reported as current.

def test_moving_a_weight_slider_misses_rather_than_serving_the_wrong_table(terms):
    """The reader's case. A miss is the correct, safe outcome."""
    published = dict(terms)                       # 10/30/30/20/10, as published
    reader_changed_a_slider = ranking_store.contract(
        price_fingerprint=terms["price_fingerprint"],
        symbols_fingerprint=terms["symbols_fingerprint"],
        weights=(0.20, 0.20, 0.20, 0.20, 0.20),   # equal weight instead
        pipeline_version=terms["pipeline_version"],
        universe=terms["universe"],
    )
    ok, why = ranking_store.matches(published, reader_changed_a_slider)
    assert not ok and "weights" in why


def test_changing_the_lookback_horizons_invalidates_the_artifact(monkeypatch):
    """The deploy case, which a hand-maintained version string would miss."""
    import src.core.config as cfg

    before = pipeline.pipeline_version()
    monkeypatch.setattr(cfg, "MOMENTUM_MONTHS", [1, 3, 6, 12, 18])
    after = pipeline.pipeline_version()
    assert before != after, (
        "MOMENTUM_MONTHS changed and the pipeline version did not; last "
        "night's table would still be served against new horizons"
    )


@pytest.mark.parametrize(
    "module, name, value",
    [
        ("src.core.config", "HIGH_52W_MIN_OBSERVATIONS", 999),
        ("src.engine.momentum", "MIN_OBSERVATIONS", 999),
        ("src.engine.calendar_momentum", "ANCHOR_STALENESS_LIMIT", 99),
    ],
)
def test_every_ranking_constant_is_in_the_digest(monkeypatch, module, name, value):
    """Each of these moves the numbers, so each must invalidate the artifact."""
    import importlib

    before = pipeline.pipeline_version()
    monkeypatch.setattr(importlib.import_module(module), name, value)
    assert pipeline.pipeline_version() != before, (
        f"{module}.{name} changed without invalidating the precomputed table"
    )


def test_the_version_is_stable_when_nothing_changes():
    """A digest that moved on its own would mean the precompute never hits."""
    assert pipeline.pipeline_version() == pipeline.pipeline_version()
    assert pipeline.PIPELINE_VERSION == pipeline.pipeline_version()


def test_the_version_still_carries_a_readable_tag():
    """The digest is for safety; the tag is so a human can read the log line."""
    assert pipeline.PIPELINE_VERSION.startswith("v4_calendar_periods")


# ── The corporate actions are an input the price fingerprint cannot see ──────
#
# An adjustment rewrites history BEFORE its own date and deliberately leaves
# the current price alone. Neutralising ABFRL's 1:3 split rewrites 168 rows of
# the shipped snapshot and changes the last row not at all -- so the frame's
# last row, shape and last date are identical either way, and
# price_fingerprint returns the same string with the adjustment and without it.
#
# The event set is therefore an input every other contract field is blind to.
# Not hypothetically: the daily sync publishes the ranking at step 5d and
# re-scans for corporate actions afterwards, so the 2026-09-16 run precomputed
# with 12 applied events and then appended a thirteenth (PGIL, 2026-08-03) to
# the log the app reads. One run, two event sets, one fingerprint.

ABFRL = {"symbol": "ABFRL", "date": "2025-05-22", "ratio": 0.3341}
PGIL = {"symbol": "PGIL", "date": "2026-08-03", "ratio": 0.5093}


def test_an_adjustment_really_is_invisible_to_the_price_fingerprint():
    """The premise. If this ever stops being true, the digest can go."""
    from src.engine.corporate_actions import adjust_ohlc

    idx = pd.date_range("2025-01-01", "2025-12-31", freq="B")
    before = idx < pd.Timestamp(ABFRL["date"])
    vals = np.where(before, 300.0, 300.0 * ABFRL["ratio"])
    close = pd.DataFrame({"ABFRL": vals}, index=idx)

    plain, none_applied = adjust_ohlc({"c": close}, [])
    fixed, applied = adjust_ohlc({"c": close}, [ABFRL])
    assert none_applied == [] and len(applied) == 1, "fixture did not apply the event"

    changed = int((plain["c"]["ABFRL"] != fixed["c"]["ABFRL"]).sum())
    assert changed > 0, "the adjustment changed nothing"
    assert plain["c"]["ABFRL"].iloc[-1] == fixed["c"]["ABFRL"].iloc[-1], (
        "the adjustment moved the last row; the premise no longer holds"
    )
    assert pipeline.price_fingerprint(plain["c"]) == pipeline.price_fingerprint(fixed["c"]), (
        "price_fingerprint now sees the adjustment"
    )


def test_a_different_event_set_is_rejected(terms):
    """The fix. Same prices, same weights, one more event -> miss."""
    published = ranking_store.contract(
        price_fingerprint=terms["price_fingerprint"],
        symbols_fingerprint=terms["symbols_fingerprint"],
        weights=terms["weights"], pipeline_version=terms["pipeline_version"],
        universe=terms["universe"], applied_actions=[ABFRL],
    )
    expected = ranking_store.contract(
        price_fingerprint=terms["price_fingerprint"],
        symbols_fingerprint=terms["symbols_fingerprint"],
        weights=terms["weights"], pipeline_version=terms["pipeline_version"],
        universe=terms["universe"], applied_actions=[ABFRL, PGIL],
    )
    ok, why = ranking_store.matches(published, expected)
    assert not ok and "actions_digest" in why


def test_the_same_event_set_matches_whatever_the_order(terms):
    """A reordered log must not force a miss every cold start."""
    a = ranking_store.actions_digest([ABFRL, PGIL])
    b = ranking_store.actions_digest([PGIL, ABFRL])
    assert a == b


def test_no_events_is_its_own_stable_value():
    assert ranking_store.actions_digest([]) == ranking_store.actions_digest(None) == "none"
    assert ranking_store.actions_digest([ABFRL]) != "none"


def test_a_changed_ratio_is_rejected():
    """Same symbol and date, restated ratio: a different adjustment."""
    assert ranking_store.actions_digest([ABFRL]) != ranking_store.actions_digest(
        [{**ABFRL, "ratio": 0.5}]
    )


def test_only_applied_events_count_not_the_whole_log():
    """An event the vendor restated is skipped on BOTH sides.

    If the digest were taken over the log rather than over what was applied,
    the log merely growing an entry nobody acts on would force a permanent
    miss -- which is what happened to TDPOWERSYS and PGIL's 2026-09-11 event
    on the 2026-09-16 sync: logged, no longer present in the prices, skipped.
    """
    import inspect

    from src.loaders import ranking_store as rs

    src = inspect.getsource(rs.actions_digest)
    assert "APPLIED" in src, "the applied-only contract is no longer documented"

    app = pathlib.Path(__file__).resolve().parents[1] / "app.py"
    job = pathlib.Path(__file__).resolve().parents[1] / "scripts/sync_data.py"
    assert "applied_actions=_ca_applied" in app.read_text().replace("\n", "").replace(" ", "") \
        or "_ca_applied," in app.read_text(), "app.py does not pass what it applied"
    assert "applied_actions=applied" in job.read_text(), (
        "the sync stamps the artifact with something other than what it applied"
    )


import pathlib  # noqa: E402  (used by the test above)
