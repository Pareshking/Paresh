
from scripts import r2_inventory

def test_inventory_groups_current_pointers_and_revisions():
    class FakeArchive:
        def list_keys(self, prefix):
            return iter([
                "archive/manifests/prices/screener/2026-09-21/current.json",
                "archive/manifests/prices/screener/2026-09-21/revisions/aaa.json",
                "archive/manifests/prices/screener/2026-09-20/current.json",
                "archive/manifests/market_caps/nse_history/2026-09-18/current.json",
                "archive/manifests/market_caps/nse_history/2026-09-18/revisions/bbb.json",
            ])
    result = r2_inventory.inventory(FakeArchive())
    assert result["status"] == "PASS"
    assert result["current_pointers"] == 3
    assert result["immutable_revision_manifests"] == 2
    assert result["datasets"]["prices/screener"]["as_of_count"] == 2
    assert result["datasets"]["prices/screener"]["last_as_of"] == "2026-09-21"
    assert result["datasets"]["market_caps/nse_history"]["immutable_revisions"] == 1

def test_summary_is_machine_readable():
    result = {
        "status":"PASS","manifest_keys":1,"current_pointers":1,
        "immutable_revision_manifests":1,
        "datasets":{"prices/screener":{"first_as_of":"2026-09-21","last_as_of":"2026-09-21","current_pointers":1,"immutable_revisions":1}},
    }
    summary = r2_inventory._summary(result)
    assert "R2_ARCHIVE_INVENTORY=PASS" in summary
    assert "DATASET=prices/screener" in summary


def _result(**last_as_of):
    return {"datasets": {name.replace("__", "/"): {"last_as_of": d} for name, d in last_as_of.items()}}


def test_freshness_passes_when_every_daily_dataset_is_recent():
    from datetime import date
    result = _result(**{d.replace("/", "__"): "2026-09-24" for d in r2_inventory.DAILY_DATASETS})
    report = r2_inventory.freshness(result, date(2026, 9, 25))
    assert report["status"] == "PASS"
    assert report["stale"] == {}


def test_freshness_flags_a_stalled_and_a_missing_dataset():
    from datetime import date
    fresh = {d.replace("/", "__"): "2026-09-24" for d in r2_inventory.DAILY_DATASETS}
    fresh["universes__point_in_time"] = "2026-09-15"
    del fresh["calculations__rankings"]
    report = r2_inventory.freshness(_result(**fresh), date(2026, 9, 25), max_age_days=6)
    assert report["status"] == "FAIL"
    assert report["stale"]["universes/point_in_time"] == {"last_as_of": "2026-09-15", "age_days": 10}
    assert report["stale"]["calculations/rankings"] == {"last_as_of": None, "age_days": None}
    assert len(report["stale"]) == 2


def test_a_weekend_plus_holiday_is_not_stale():
    from datetime import date
    # Friday's session read on the next Thursday: six days, still healthy.
    result = _result(**{d.replace("/", "__"): "2026-09-18" for d in r2_inventory.DAILY_DATASETS})
    assert r2_inventory.freshness(result, date(2026, 9, 24))["status"] == "PASS"


def test_storage_report_splits_recent_from_old_per_dataset():
    from datetime import date

    from scripts.r2_inventory import storage_report

    class Archive:
        def list_objects(self, prefix):
            return iter([
                ("archive/prices/yahoo/2026-09-24/revisions/a/prices_full.parquet", 30),
                ("archive/prices/yahoo/2026-06-01/revisions/b/prices_full.parquet", 25),
                ("archive/manifests/prices/yahoo/2026-09-24/current.json", 1),
                ("README.txt", 2),
            ])

    report = storage_report(Archive(), date(2026, 9, 25))
    yahoo = report["by_dataset"]["archive/prices/yahoo"]
    assert (yahoo["objects"], yahoo["bytes"]) == (2, 55)
    assert (yahoo["recent_bytes"], yahoo["old_bytes"]) == (30, 25)
    assert report["by_dataset"]["archive/manifests/prices/yahoo"]["recent_bytes"] == 1
    assert report["total"]["undated_bytes"] == 2
    assert report["total"]["bytes"] == 58
