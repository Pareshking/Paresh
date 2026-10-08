from src.core import startup_metrics


def test_memory_checkpoint_records_rss_fields():
    startup_metrics.reset_for_tests()
    point = startup_metrics.memory_checkpoint("unit")
    assert point["label"] == "unit"
    checkpoints = startup_metrics.snapshot()["facts"]["memory_checkpoints"]
    assert checkpoints[-1]["label"] == "unit"
    assert "VmRSS" in checkpoints[-1] or "error" in checkpoints[-1]


def test_stage_records_memory_boundaries():
    startup_metrics.reset_for_tests()
    with startup_metrics.stage("unit_stage"):
        pass
    checkpoints = startup_metrics.snapshot()["facts"]["memory_checkpoints"]
    labels = [item["label"] for item in checkpoints]
    assert "unit_stage:start" in labels
    assert "unit_stage:end" in labels
