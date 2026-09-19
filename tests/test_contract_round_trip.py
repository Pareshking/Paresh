"""The publisher and the app must agree, built exactly the way each builds it.

Every existing contract test constructs BOTH sides from one fixture, so the two
call sites can drift apart and the suite stays green. They do not pass the same
arguments:

    scripts/sync_data.py   contract(..., price_as_of=as_of, price_source=...)
    app.py                 contract(...)          # no price_as_of

so any field the publisher fills and the reader leaves at its default must not
be compared in `matches`, or the precompute misses on every page load and the
app rebuilds the engine every cold start -- a silent ~60s regression that no
test here would have caught and no log line would call an error.

This pins the round trip itself: publisher terms in, reader terms in, accepted
out. It is written from the two call sites, not from a shared fixture, on
purpose.
"""
from __future__ import annotations

import pandas as pd

from src.engine import pipeline
from src.loaders.ranking_store import contract, matches

WEIGHTS = (0.10, 0.30, 0.30, 0.20, 0.10)
UNIVERSE = ["RELIANCE", "TCS", "HEG"]
ACTIONS = [{"date": "2026-09-07", "symbol": "HEG", "ratio": 0.373773}]


def _frame() -> pd.DataFrame:
    idx = pd.date_range("2026-09-14", periods=3, freq="D")
    return pd.DataFrame({s: [100.0, 101.0, 102.0] for s in UNIVERSE}, index=idx)


def _publisher_terms(frame: pd.DataFrame, *, as_of: str, source: str) -> dict:
    """scripts/sync_data.py::_precompute_rankings -- note price_as_of."""
    return contract(
        price_fingerprint=pipeline.price_fingerprint(frame),
        symbols_fingerprint=pipeline.symbols_fingerprint(UNIVERSE),
        weights=WEIGHTS,
        pipeline_version=pipeline.PIPELINE_VERSION,
        universe=UNIVERSE,
        price_as_of=as_of,
        price_source=source,
        applied_actions=ACTIONS,
    )


def _reader_terms(frame: pd.DataFrame, *, source: str) -> dict:
    """app.py::_precomputed_ranking -- note the ABSENT price_as_of."""
    return contract(
        price_fingerprint=pipeline.price_fingerprint(frame),
        price_source=source,
        symbols_fingerprint=pipeline.symbols_fingerprint(UNIVERSE),
        weights=WEIGHTS,
        pipeline_version=pipeline.PIPELINE_VERSION,
        universe=UNIVERSE,
        applied_actions=ACTIONS,
    )


def test_the_app_accepts_what_the_publisher_wrote():
    """The fast path, end to end. If this fails, every cold start rebuilds."""
    frame = _frame()
    ok, why = matches(
        _publisher_terms(frame, as_of="2026-09-18", source="screener"),
        _reader_terms(frame, source="screener"),
    )
    assert ok, (
        f"the published ranking would be REJECTED on every load: {why}. "
        "A field the publisher fills and app.py leaves at its default must not "
        "be a compared term."
    )


def test_this_holds_for_either_price_source():
    """The producer may fall back to Yahoo; the reader must still accept it."""
    frame = _frame()
    for source in ("screener", "yahoo"):
        ok, why = matches(
            _publisher_terms(frame, as_of="2026-09-16", source=source),
            _reader_terms(frame, source=source),
        )
        assert ok, f"{source}: {why}"


def test_no_compared_term_is_one_only_the_publisher_supplies():
    """The rule behind the two tests above, stated where a reader will find it.

    A term compared in `matches` must be one BOTH call sites supply. Anything
    the publisher passes and app.py omits defaults to empty on one side only,
    so the comparison can never succeed.
    """
    frame = _frame()
    publisher = _publisher_terms(frame, as_of="2026-09-18", source="screener")
    reader = _reader_terms(frame, source="screener")
    disagree = {k for k in publisher if str(publisher[k]) != str(reader.get(k))}
    # price_as_of is recorded for provenance and is legitimately one-sided.
    assert disagree <= {"price_as_of"}, f"unexpected one-sided terms: {disagree}"
    for field in disagree:
        ok, _ = matches(publisher, dict(reader, **{field: publisher[field]}))
        assert ok
        ok, why = matches(publisher, reader)
        assert ok, (
            f"{field!r} is supplied only by the publisher, so comparing it "
            f"rejects every valid table: {why}"
        )
