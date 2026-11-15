
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


def test_a_dataset_whose_date_is_its_evidence_is_not_held_to_a_daily_age():
    from datetime import date
    # S136: classifications/tv_history moves only when TradingView reclassifies a
    # stock (4 Nov 2026), so a daily freshness rule failed the inventory every day
    # from 11 Nov although the weekly refresh ran and found "0 changed".
    assert "classifications/tv_history" not in r2_inventory.DAILY_DATASETS
    result = _result(**{d.replace("/", "__"): "2026-11-13" for d in r2_inventory.DAILY_DATASETS})
    result["datasets"]["classifications/tv_history"] = {"last_as_of": "2026-11-04"}
    assert r2_inventory.freshness(result, date(2026, 11, 14))["status"] == "PASS"


def test_storage_is_kept_under_half_of_cloudflares_free_allowance():
    # Owner, 15 Nov 2026: "keep it below 50% of Cloudflare limits" (10 GB-month free).
    def at(gb):
        return r2_inventory.storage_limit({"total": {"bytes": int(gb * 10**9)}})
    assert at(2.1)["status"] == "PASS"               # after the 15 Nov clean-up
    assert at(3.33)["status"] == "PASS"              # 14 Nov, before it
    assert at(4.0)["status"] == "WARN"
    assert at(5.0)["status"] == "FAIL"
    assert r2_inventory.storage_limit({"error": "x"})["status"] == "UNKNOWN"   # a failed listing never fails the run


class _Client:
    def __init__(self, buckets=None, refuse=False, sizes=None):
        self.buckets, self.refuse, self.sizes = buckets or [], refuse, sizes or {}

    def list_buckets(self):
        if self.refuse:
            raise PermissionError("AccessDenied")
        return {"Buckets": [{"Name": b} for b in self.buckets]}

    def get_paginator(self, _op):
        sizes = self.sizes

        class P:
            def paginate(self, Bucket):
                if sizes.get(Bucket) is None:
                    raise PermissionError("AccessDenied")
                return [{"Contents": [{"Size": sizes[Bucket]}]}]
        return P()


def test_the_limit_is_judged_on_every_bucket_in_the_account():
    # Owner, 15 Nov 2026: the Cloudflare account may be shared with other sites;
    # the 10 GB is per account, so another bucket's bytes count too.
    acct = r2_inventory.account_storage(_Client(["ours", "theirs"], sizes={"theirs": 3 * 10**9}), "ours", 2 * 10**9)
    assert acct["complete"] and acct["total"] == 5 * 10**9
    limit = r2_inventory.storage_limit({"total": {"bytes": 2 * 10**9}}, acct)
    assert limit["status"] == "FAIL" and limit["account_complete"] and limit["note"] == ""


def test_a_bucket_scoped_key_says_the_account_total_is_unknown():
    acct = r2_inventory.account_storage(_Client(refuse=True), "ours", 2 * 10**9)
    assert not acct["complete"] and "only this bucket" in acct["reason"]
    limit = r2_inventory.storage_limit({"total": {"bytes": 2 * 10**9}}, acct)
    assert limit["status"] == "PASS" and not limit["account_complete"] and limit["note"]
    part = r2_inventory.account_storage(_Client(["ours", "hidden"], sizes={}), "ours", 1)
    assert not part["complete"] and "hidden" in part["reason"] and part["buckets"]["hidden"] is None
