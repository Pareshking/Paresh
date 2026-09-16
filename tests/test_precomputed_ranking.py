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
