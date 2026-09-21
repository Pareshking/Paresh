import json

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
