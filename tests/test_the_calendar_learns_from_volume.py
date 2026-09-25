"""The volume test's findings must reach the calendar, with their evidence.

The zero-volume test reads something no coverage threshold can: a session where
every priced symbol is flat at zero volume is one on which nothing changed
hands. It found four such sessions in the published frame, and TWO OF THEM SAT
AT 100% VENDOR COVERAGE -- 2026-05-28 and 2026-06-26 -- where no floor of any
value could ever have reached them.

Leaving that knowledge inside the loader means re-deriving it from the whole
frame on every read, and means a human cannot see it at all. Written into the
calendar it becomes a fact with a source attached.

It is recorded as EVIDENCE, not as an assertion that NSE declared a holiday.
The source string says what was observed and at what coverage, so a wrong entry
traces back to the run that made it instead of appearing as an anonymous date
somebody once decided was closed. The exchange still outranks it: record_closed
refuses any date NSE published a bhavcopy for.
"""

import json

import pandas as pd

from src.loaders.trading_days import (
    load_closed, load_confirmed, record_closed, record_confirmed,
)


def _dead_session_frame(n_cols=120):
    """Two live sessions and one on which nothing traded."""
    idx = pd.to_datetime(["2026-05-27", "2026-05-28", "2026-05-29"])
    cols = pd.MultiIndex.from_product(
        [[f"S{i}" for i in range(n_cols)], ["Close", "Open", "High", "Low", "Volume"]]
    )
    df = pd.DataFrame(index=idx, columns=cols, dtype=float)
    for i in range(n_cols):
        s = f"S{i}"
        df[(s, "Close")] = [100.0, 100.0, 101.0]
        df[(s, "Open")] = [99.0, 100.0, 100.5]
        df[(s, "High")] = [101.0, 100.0, 101.5]
        df[(s, "Low")] = [98.0, 100.0, 100.0]
        df[(s, "Volume")] = [5_000.0, 0.0, 6_000.0]   # the middle day: nobody traded
    return df


def test_the_loader_reports_which_dates_it_found(monkeypatch):
    """A count cannot be recorded against anything; the dates can."""
    from src.core import startup_metrics as m
    from src.loaders import price_loader
    import src.loaders.trading_days as td

    monkeypatch.setattr(td, "load_confirmed", lambda path=None: set())
    monkeypatch.setattr(td, "load_closed", lambda path=None: set())
    m.reset_for_tests()

    out = price_loader._drop_phantom_sessions(_dead_session_frame())
    assert pd.Timestamp("2026-05-28") not in out.index

    facts = m.snapshot().get("facts", {})
    assert facts.get("price_zero_trade_dates") == "2026-05-28"
    assert "2026-05-28:" in str(facts.get("price_zero_trade_coverage"))


def test_a_finding_is_recorded_with_what_was_observed(tmp_path):
    """The source must be auditable, not an anonymous assertion."""
    path = str(tmp_path / "days.json")
    added, total = record_closed(
        ["2026-05-28"],
        source="zero-volume evidence (100% priced, all flat at zero volume)",
        path=path,
    )
    assert (added, total) == (1, 1)
    payload = json.loads(open(path).read())
    src = payload["closed_days_source"]["2026-05-28"]
    assert "zero-volume evidence" in src
    assert "100%" in src, "the coverage that decided it was not written down"


def test_the_exchange_still_outranks_the_volume_test(tmp_path):
    """A bhavcopy beats a heuristic, however confident the heuristic is.

    Without this, one bad reading would delete a real session permanently --
    the precise failure the confirmations-only rule exists to prevent, arriving
    through the automated door instead of a human one.
    """
    path = str(tmp_path / "days.json")
    record_confirmed({"2026-05-28"}, path)
    added, _ = record_closed(
        ["2026-05-28"], source="zero-volume evidence (100% priced)", path=path
    )
    assert added == 0
    assert load_closed(path) == set()
    assert load_confirmed(path) == {"2026-05-28"}


def test_learning_the_same_day_twice_rewrites_nothing(tmp_path):
    """The job runs daily over the same 45-day window; it must not churn."""
    path = str(tmp_path / "days.json")
    record_closed(["2026-05-28"], source="zero-volume evidence (100% priced)", path=path)
    before = open(path).read()
    added, _ = record_closed(
        ["2026-05-28"], source="zero-volume evidence (100% priced)", path=path
    )
    assert added == 0
    assert open(path).read() == before


def test_learned_closures_and_human_ones_coexist(tmp_path):
    """Both write the same field, and neither may erase the other's source."""
    path = str(tmp_path / "days.json")
    record_closed(["2026-09-14"], source="user-confirmed NSE holiday", path=path)
    record_closed(["2026-05-28"], source="zero-volume evidence (100% priced)", path=path)
    sources = json.loads(open(path).read())["closed_days_source"]
    assert sources["2026-09-14"] == "user-confirmed NSE holiday"
    assert "zero-volume" in sources["2026-05-28"]
    assert load_closed(path) == {"2026-09-14", "2026-05-28"}


def test_the_sync_records_what_the_loader_found():
    """The wiring itself: a finding must not stop at the log line."""
    src = open("scripts/sync_data.py", encoding="utf-8").read()
    assert "price_zero_trade_dates" in src, (
        "the sync never reads the dates the volume test found, so the calendar "
        "cannot learn and the test re-derives them from scratch every run"
    )
    assert "record_closed(" in src
    assert "zero-volume evidence" in src, "findings are recorded without their source"


def test_a_live_session_is_never_learned_as_closed(monkeypatch):
    """The false positive that would matter: real trading, recorded as a holiday."""
    from src.core import startup_metrics as m
    from src.loaders import price_loader
    import src.loaders.trading_days as td

    monkeypatch.setattr(td, "load_confirmed", lambda path=None: set())
    monkeypatch.setattr(td, "load_closed", lambda path=None: set())
    m.reset_for_tests()

    df = _dead_session_frame()
    for c in [c for c in df.columns if c[1] == "Volume"]:
        df[c] = [5_000.0, 4_000.0, 6_000.0]      # every session traded
    price_loader._drop_phantom_sessions(df)
    facts = m.snapshot().get("facts", {})
    assert not str(facts.get("price_zero_trade_dates") or ""), (
        "a session with real volume was reported as a non-session"
    )
