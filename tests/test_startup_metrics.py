"""Startup telemetry must observe without influencing anything."""
import json

from src.core import startup_metrics as metrics


def setup_function():
    metrics.reset_for_tests()


def test_stage_records_first_execution_and_counts_repeats():
    with metrics.stage("universe"):
        pass
    with metrics.stage("universe"):
        pass
    snap = metrics.snapshot()
    assert snap["stages"]["universe"]["repeats"] == 1
    assert snap["stages"]["universe"]["duration_s"] >= 0


def test_stage_records_even_when_the_body_raises():
    try:
        with metrics.stage("price_history"):
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert "price_history" in metrics.snapshot()["stages"]


def test_stage_does_not_swallow_exceptions():
    """Telemetry must never change control flow."""
    raised = False
    try:
        with metrics.stage("quant_engine"):
            raise ValueError("must propagate")
    except ValueError:
        raised = True
    assert raised


def test_counters_and_facts_round_trip():
    metrics.incr("price_batches_attempted", 8)
    metrics.incr("price_batches_attempted")
    metrics.note("price_path", "full_download")
    snap = metrics.snapshot()
    assert snap["counters"]["price_batches_attempted"] == 9
    assert snap["facts"]["price_path"] == "full_download"


def test_cold_container_detection(tmp_path):
    present = tmp_path / "prices.parquet"
    present.write_bytes(b"x" * 10)
    metrics.record_cache_presence({
        "prices": str(present),
        "market_caps": str(tmp_path / "absent.parquet"),
    })
    facts = metrics.snapshot()["facts"]
    assert facts["cold_container"] is False
    assert facts["cache_at_startup"]["prices"]["exists"] is True
    assert facts["cache_at_startup"]["market_caps"]["exists"] is False


def test_cold_container_when_nothing_cached(tmp_path):
    metrics.record_cache_presence({"prices": str(tmp_path / "nope.parquet")})
    assert metrics.snapshot()["facts"]["cold_container"] is True


def test_cache_presence_is_recorded_once(tmp_path):
    """A later rerun must not overwrite the pre-fetch snapshot."""
    metrics.record_cache_presence({"prices": str(tmp_path / "nope.parquet")})
    warm = tmp_path / "prices.parquet"
    warm.write_bytes(b"x")
    metrics.record_cache_presence({"prices": str(warm)})
    assert metrics.snapshot()["facts"]["cold_container"] is True


def test_snapshot_is_json_serialisable():
    metrics.note("universe_symbols", 752)
    with metrics.stage("delivery"):
        pass
    json.dumps(metrics.snapshot())


def test_snapshot_contains_no_angle_brackets():
    """It is embedded in an HTML element, so it must not be able to break out."""
    metrics.note("price_path", "full_download")
    metrics.note("universe_symbols", 752)
    assert "<" not in json.dumps(metrics.snapshot())
    assert ">" not in json.dumps(metrics.snapshot())
