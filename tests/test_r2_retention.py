"""R2 retention: last 7 dates + month-ends, for two datasets only, dry run first."""

import json

from scripts import r2_retention as rr

SHA = "{:064x}"


class FakeArchive:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def put(self, key, body=b"x", size=None):
        self.objects[key] = body if size is None else b"x" * size

    def list_keys(self, prefix):
        return iter(sorted(k for k in self.objects if k.startswith(prefix)))

    def list_objects(self, prefix):
        return iter(sorted((k, len(v)) for k, v in self.objects.items()
                           if k.startswith(prefix)))

    def get_bytes(self, key):
        return self.objects[key]

    def delete(self, key):
        self.deleted.append(key)
        del self.objects[key]


def publish(archive, dataset, root, as_of, n, size=100, object_key=None,
            created_at="2026-09-25T10:00:00+00:00", move_pointer=True):
    """What scripts/r2_publish.py writes: payload, manifest, then the pointer."""
    sha = SHA.format(n)
    obj = object_key or f"{root}/{as_of}/revisions/{sha}/file.parquet"
    manifest_key = f"archive/manifests/{dataset}/{as_of}/revisions/{sha}.json"
    archive.put(obj, size=size)
    archive.put(manifest_key, json.dumps(
        {"object_key": obj, "revision_sha256": sha, "created_at": created_at}).encode())
    if move_pointer:
        archive.put(f"archive/manifests/{dataset}/{as_of}/current.json", json.dumps(
            {"object_key": obj, "revision_sha256": sha, "manifest_key": manifest_key}).encode())
    return obj


AUG = ["2026-08-27", "2026-08-28", "2026-08-31"]
SEP = [f"2026-09-{d:02d}" for d in (1, 2, 3, 4, 7, 8, 9, 10, 11, 14, 15, 16, 17, 18, 21, 22, 23, 24, 25)]


def test_keep_dates_is_last_seven_plus_every_month_end():
    keep = rr.keep_dates(AUG + SEP)
    assert keep == {"2026-08-31", *SEP[-7:]}
    # The newest date is always kept (it is also September's month-end here).
    assert "2026-09-25" in keep


def _archive():
    a = FakeArchive()
    for i, d in enumerate(AUG + SEP):
        publish(a, "prices/yahoo", "archive/prices/yahoo", d, i, size=1000)
        publish(a, "snapshots/application", "snapshots/application", d, 500 + i, size=200)
        # Nested and unrelated datasets that must never be touched.
        publish(a, "prices/yahoo/raw", "archive/prices/yahoo/raw", d, 900 + i)
        publish(a, "prices/screener", "archive/prices/screener", d, 1500 + i, size=1000)
        publish(a, "prices/screener/bootstrap", "archive/prices/screener/bootstrap", d, 1900 + i)
        publish(a, "market_caps/nse_history", "archive/market_caps/nse_history", d, 2300 + i)
    return a


def test_plan_drops_only_the_retained_datasets_and_only_unkept_dates():
    a = _archive()
    plans = {p.dataset: p for p in rr.make_plan(a)}
    yahoo = plans["prices/screener"]
    dropped = set(AUG + SEP) - ({"2026-08-31"} | set(SEP[-7:]))
    assert set(yahoo.drop) == dropped
    # pointer + manifest + payload per dropped date
    assert len(yahoo.delete_keys) == 3 * len(dropped)
    assert set(plans) == {"prices/screener", "bse/daily",
                          "prices/nse_long_close", "prices/nse_long_value", "prices/nse_long_report",
                          "snapshots/rankings", "snapshots/rankings_nano", "snapshots/rankings_combined",
                          "snapshots/rankings_1000",
                          "snapshots/application", "prices/yahoo/bootstrap",
                          "calculations/rankings", "indices/prices/research",   # retired 22 Nov (S195)
                          "prices/yahoo", "prices/yahoo/raw", "app/prices_snapshot",
                          "app/prices_extra",
                          # retired 24 Nov 2026 (owner, S224 (d)): R2 copies nothing reads
                          "market_caps/nse_history", "market_caps/nse_snapshot", "prices/ss", "nse/source_checks"}
    assert set(plans["market_caps/nse_history"].drop) == set(AUG + SEP)
    # Every Yahoo dataset goes whole, each key planned once.
    assert set(plans["prices/yahoo"].drop) == set(AUG + SEP)
    every = [k for p in plans.values() for k in p.delete_keys]
    assert len(every) == len(set(every))
    assert not [k for k in every if "screener/bootstrap" in k]
    # Pointers go first, payloads last.
    assert yahoo.delete_keys[0].endswith("/current.json")
    assert not yahoo.delete_keys[-1].startswith("archive/manifests/")


def test_apply_deletes_exactly_the_plan_and_keeps_readers_whole():
    a = _archive()
    before = set(a.objects)
    plans = rr.make_plan(a)
    planned = {k for p in plans for k in p.delete_keys}
    assert rr.apply_plan(a, plans) == len(planned)
    assert set(a.deleted) == planned
    assert set(a.objects) == before - planned
    # The newest date of each retained dataset still resolves end to end.
    for ds, _root in rr.RETAINED_DATASETS.items():
        if f"archive/manifests/{ds}/2026-09-24/current.json" not in before:
            continue  # not in this fixture
        ptr = json.loads(a.objects[f"archive/manifests/{ds}/2026-09-25/current.json"])
        assert ptr["object_key"] in a.objects


def test_a_payload_still_named_by_a_kept_date_is_not_deleted():
    """A kept manifest naming a dropped date's payload keeps that payload."""
    a = FakeArchive()
    for i, d in enumerate(SEP[:-1]):
        publish(a, "prices/yahoo", "archive/prices/yahoo", d, i)
    dropped_obj = "archive/prices/yahoo/2026-09-01/revisions/%s/file.parquet" % SHA.format(0)
    # The newest date (always kept) re-publishes the very same payload.
    publish(a, "prices/yahoo", "archive/prices/yahoo", SEP[-1], 0, object_key=dropped_obj)
    plan = rr.plan_dataset(a, "prices/yahoo", "archive/prices/yahoo", dict(a.list_objects("")))
    assert "2026-09-01" in plan.drop
    assert dropped_obj not in plan.delete_keys
    # Its pointer and manifest still go.
    assert "archive/manifests/prices/yahoo/2026-09-01/current.json" in plan.delete_keys


def test_a_manifest_pointing_outside_its_dataset_is_refused():
    a = FakeArchive()
    for i, d in enumerate(SEP):
        publish(a, "prices/yahoo", "archive/prices/yahoo", d, i)
    stray = "archive/prices/screener/2026-09-01/revisions/x/file.parquet"
    publish(a, "prices/yahoo", "archive/prices/yahoo", "2026-09-01", 77, object_key=stray)
    plan = rr.plan_dataset(a, "prices/yahoo", "archive/prices/yahoo", dict(a.list_objects("")))
    assert plan.refused and stray not in plan.delete_keys


def test_apply_refuses_when_the_count_differs_from_the_dry_run(monkeypatch, capsys):
    a = _archive()
    monkeypatch.setattr(rr, "R2Archive", lambda cfg: a)
    monkeypatch.setattr(rr.R2Config, "from_env", classmethod(lambda cls: None))
    monkeypatch.setattr("sys.argv", ["r2_retention.py"])
    assert rr.main() == 0
    assert a.deleted == []  # dry run by default
    count = rr.report(rr.make_plan(a))["delete_count"]
    monkeypatch.setattr("sys.argv", ["r2_retention.py", "--apply", "--expect-deletes", str(count + 1)])
    assert rr.main() == 1
    assert a.deleted == []
    monkeypatch.setattr("sys.argv", ["r2_retention.py", "--apply", "--expect-deletes", str(count)])
    assert rr.main() == 0
    assert len(a.deleted) == count


def _revisions(a, dataset, as_of):
    prefix = f"archive/manifests/{dataset}/{as_of}/revisions/"
    return sorted(k for k in a.objects if k.startswith(prefix))


def _republished_archive():
    """Every date published once, then the newest date republished twice."""
    a = FakeArchive()
    for i, d in enumerate(SEP):
        publish(a, "prices/yahoo", "archive/prices/yahoo", d, i, size=1000,
                created_at=f"{d}T10:00:00+00:00")
    for n, hour in ((101, 11), (102, 12)):
        publish(a, "prices/yahoo", "archive/prices/yahoo", "2026-09-25", n, size=1000,
                created_at=f"2026-09-25T{hour}:00:00+00:00")
    return a


def test_a_kept_date_keeps_only_its_newest_revision():
    a = _republished_archive()
    plan = rr.plan_dataset(a, "prices/yahoo", "archive/prices/yahoo", dict(a.list_objects("")))
    root = "archive/prices/yahoo/2026-09-25/revisions"
    old = [f"archive/manifests/prices/yahoo/2026-09-25/revisions/{SHA.format(n)}.json"
           for n in (len(SEP) - 1, 101)]
    assert sorted(plan.superseded) == old
    for n in (len(SEP) - 1, 101):
        assert f"{root}/{SHA.format(n)}/file.parquet" in plan.delete_keys
    newest = f"{root}/{SHA.format(102)}/file.parquet"
    assert newest not in plan.delete_keys
    assert "archive/manifests/prices/yahoo/2026-09-25/current.json" not in plan.delete_keys

    # After applying, both ways of reading the date give the same revision.
    rr.apply_plan(a, [plan])
    assert _revisions(a, "prices/yahoo", "2026-09-25") == [
        f"archive/manifests/prices/yahoo/2026-09-25/revisions/{SHA.format(102)}.json"]
    ptr = json.loads(a.objects["archive/manifests/prices/yahoo/2026-09-25/current.json"])
    assert ptr["object_key"] == newest and newest in a.objects


def test_the_revision_current_json_names_is_kept_even_if_not_newest():
    """A newer manifest whose pointer was never moved (a failed publish): keep both."""
    a = _republished_archive()
    publish(a, "prices/yahoo", "archive/prices/yahoo", "2026-09-25", 103,
            created_at="2026-09-25T13:00:00+00:00", move_pointer=False)
    plan = rr.plan_dataset(a, "prices/yahoo", "archive/prices/yahoo", dict(a.list_objects("")))
    kept = set(_revisions(a, "prices/yahoo", "2026-09-25")) - set(plan.superseded)
    assert {k.rsplit("/", 1)[-1][:-5] for k in kept} == {SHA.format(102), SHA.format(103)}


def test_a_kept_date_that_cannot_be_ordered_is_left_whole():
    a = _republished_archive()
    publish(a, "prices/yahoo", "archive/prices/yahoo", "2026-09-25", 104, created_at=None)
    plan = rr.plan_dataset(a, "prices/yahoo", "archive/prices/yahoo", dict(a.list_objects("")))
    assert plan.superseded == []
    assert not [k for k in plan.delete_keys if "/2026-09-25/" in k]
    assert plan.skipped and "created_at" in plan.skipped[0]
    # Not an error: the rest of the plan still stands.
    assert not plan.refused and plan.drop


def test_a_pointer_without_manifest_key_is_resolved_by_revision_sha():
    a = _republished_archive()
    ptr_key = "archive/manifests/prices/yahoo/2026-09-25/current.json"
    ptr = json.loads(a.objects[ptr_key])
    del ptr["manifest_key"]
    a.put(ptr_key, json.dumps(ptr).encode())
    plan = rr.plan_dataset(a, "prices/yahoo", "archive/prices/yahoo", dict(a.list_objects("")))
    assert len(plan.superseded) == 2 and not plan.skipped


# ── Retired datasets: deleted whole (owner, 2026-09-27) ──────────────────────

def test_a_retired_dataset_goes_whole_and_nothing_beside_it():
    a = FakeArchive()
    for i, d in enumerate(SEP[-3:]):
        publish(a, "prices/yahoo", "archive/prices/yahoo", d, i)
        publish(a, "prices/yahoo/raw", "archive/prices/yahoo/raw", d, 100 + i)
        publish(a, "snapshots/application", "snapshots/application", d, 200 + i)
    publish(a, "prices/yahoo/bootstrap", "archive/prices/yahoo/bootstrap", "2026-09-21", 300)
    plans = {p.dataset: p for p in rr.make_plan(a)}
    # prices/yahoo's own plan leaves the nested datasets' payloads to theirs.
    assert not [k for k in plans["prices/yahoo"].delete_keys if "/raw/" in k or "/bootstrap/" in k]

    boot = plans["prices/yahoo/bootstrap"]
    assert set(boot.delete_keys) == {
        k for k in a.objects
        if k.startswith(("archive/prices/yahoo/bootstrap/",
                         "archive/manifests/prices/yahoo/bootstrap/"))}
    app = plans["snapshots/application"]
    assert set(app.delete_keys) == {
        k for k in a.objects
        if k.startswith(("snapshots/application/",
                         "archive/manifests/snapshots/application/"))}
    assert len(app.delete_keys) == 3 * 3        # pointer + manifest + payload per date
    # Pointers first, payloads last.
    assert app.delete_keys[0].endswith("/current.json")
    assert not app.delete_keys[-1].startswith("archive/manifests/")

    rr.apply_plan(a, list(plans.values()))
    # prices/yahoo and prices/yahoo/raw are retired too: nothing Yahoo is left.
    assert not a.objects
    assert len(a.deleted) == len(set(a.deleted))


def test_a_retired_manifest_naming_a_payload_elsewhere_refuses_the_run(monkeypatch):
    a = FakeArchive()
    publish(a, "prices/yahoo", "archive/prices/yahoo", "2026-09-25", 1)
    publish(a, "prices/yahoo/bootstrap", "archive/prices/yahoo/bootstrap", "2026-09-21", 2,
            object_key="archive/prices/yahoo/2026-09-25/revisions/x/file.parquet")
    plan = rr.plan_retired(a, "prices/yahoo/bootstrap", "archive/prices/yahoo/bootstrap",
                           dict(a.list_objects("")))
    assert plan.refused
    monkeypatch.setattr(rr, "R2Archive", lambda cfg: a)
    monkeypatch.setattr(rr.R2Config, "from_env", classmethod(lambda cls: None))
    monkeypatch.setattr("sys.argv", ["r2_retention.py"])
    assert rr.main() == 1
    assert a.deleted == []


def test_a_retired_dataset_also_loses_its_first_publisher_manifests():
    """2026-09-21 layout: archive/manifests/<ds>/<as_of>.json -> <root>/<as_of>/<file>."""
    a = FakeArchive()
    publish(a, "prices/yahoo", "archive/prices/yahoo", "2026-09-18", 1)
    legacy_obj = "archive/prices/yahoo/bootstrap/2026-09-18/prices_full.parquet"
    a.put(legacy_obj, size=50)
    a.put("archive/manifests/prices/yahoo/bootstrap/2026-09-18.json",
          json.dumps({"object_key": legacy_obj}).encode())
    # The live dataset's own flat-looking neighbour is never matched.
    a.put("archive/manifests/prices/yahoo/2026-09-18.json",
          json.dumps({"object_key": "archive/prices/yahoo/2026-09-18/x.parquet"}).encode())
    plan = rr.plan_retired(a, "prices/yahoo/bootstrap", "archive/prices/yahoo/bootstrap",
                           dict(a.list_objects("")))
    assert not plan.refused
    assert plan.delete_keys == ["archive/manifests/prices/yahoo/bootstrap/2026-09-18.json",
                                legacy_obj]


def test_the_app_snapshot_keeps_only_its_newest_three_dates(monkeypatch):
    monkeypatch.setitem(rr.KEEP_LATEST_ONLY, "app/prices_snapshot", 3)
    a = FakeArchive()
    for i, d in enumerate(AUG + SEP):
        publish(a, "app/prices_snapshot", "snapshots/app_prices", d, 3000 + i)
    plan = rr.plan_dataset(a, "app/prices_snapshot", "snapshots/app_prices",
                           dict(a.list_objects("")))
    assert plan.keep == SEP[-3:]                 # no month-ends
    assert "2026-08-31" in plan.drop
    assert all(k.startswith(("archive/manifests/app/prices_snapshot/", "snapshots/app_prices/"))
               for k in plan.delete_keys)


def test_protected_reference_datasets_can_never_be_pruned_or_retired():
    import pytest

    from scripts import r2_retention as rr

    rr.check_protected(rr.RETAINED_DATASETS, rr.RETIRED_DATASETS)   # today's tables are fine
    with pytest.raises(ValueError, match="protected"):
        rr.check_protected({"reference/yahoo_close": "archive/reference/yahoo_close"}, {})
    with pytest.raises(ValueError, match="protected"):
        rr.check_protected({}, {"prices/screener/max_history": "archive/prices/screener/max_history"})
    # A root that would sweep a protected dataset's objects is refused too.
    with pytest.raises(ValueError, match="would reach"):
        rr.check_protected({}, {"old/thing": "archive/reference"})


def test_the_nse_history_and_its_products_are_protected_too():
    import pytest

    from scripts import r2_retention as rr

    for ds in ("nse/prices_daily", "nse/corporate_actions_history", "indices/membership/nifty_500",
               "indices/constituents/nifty50", "indices/nse_close_all",
               "snapshots/rankings", "snapshots/rankings_nano", "snapshots/rankings_1000",
               "market_caps/nse_market_caps", "trading_sessions/confirmed"):
        with pytest.raises(ValueError, match="protected"):
            rr.check_protected({ds: f"archive/{ds}"}, {})
    # A retired root that would sweep the NSE archive, or the published rankings, is refused.
    with pytest.raises(ValueError, match="would reach"):
        rr.check_protected({}, {"old/nse": "archive/nse"})
    with pytest.raises(ValueError, match="would reach"):
        rr.check_protected({}, {"old/snap": "snapshots"})


def test_a_large_plan_is_not_applied_by_a_capped_run(monkeypatch):
    a = _archive()
    monkeypatch.setattr(rr, "R2Archive", lambda cfg: a)
    monkeypatch.setattr(rr.R2Config, "from_env", classmethod(lambda cls: None))
    count = rr.report(rr.make_plan(a))["delete_count"]
    assert count > 1
    monkeypatch.setattr("sys.argv", ["r2_retention.py", "--apply", "--expect-deletes", str(count),
                                     "--max-deletes", str(count - 1)])
    assert rr.main() == 1
    assert a.deleted == []
    monkeypatch.setattr("sys.argv", ["r2_retention.py", "--apply", "--expect-deletes", str(count),
                                     "--max-deletes", str(count)])
    assert rr.main() == 0
    assert len(a.deleted) == count


def test_bse_daily_keeps_only_its_newest_monthly_copy():
    # Owner, 13 Oct 2026 (S52): newest two; 17 Nov 2026 (S141): newest one. Each
    # copy is the whole table, rebuilt from BSE's bhavcopies if the newest is bad.
    a = FakeArchive()
    months = ["2026-11-02", "2026-12-01", "2027-01-04"]
    for i, d in enumerate(months):
        publish(a, "bse/daily", "archive/bse/daily", d, 9000 + i)
    plan = {p.dataset: p for p in rr.make_plan(a)}["bse/daily"]
    assert plan.keep == months[-1:] and plan.drop == months[:-1]
    assert plan.delete_keys and not [k for k in plan.delete_keys if "2027-01-04" in k]
    # With one copy nothing is deleted.
    b = FakeArchive()
    publish(b, "bse/daily", "archive/bse/daily", months[0], 9100)
    assert not {p.dataset: p for p in rr.make_plan(b)}["bse/daily"].delete_keys


def test_a_protected_dataset_is_never_emptied_or_also_pruned():
    import pytest

    with pytest.raises(ValueError, match="at least"):
        rr.check_protected({}, {}, {"bse/daily": ("archive/bse/daily", 0)})
    with pytest.raises(ValueError, match="thinned"):
        rr.check_protected({}, {"bse/daily": "archive/bse/daily"}, {"bse/daily": ("archive/bse/daily", 2)})
    with pytest.raises(ValueError, match="protected"):
        rr.check_protected({"bse/daily": "archive/bse/daily"}, {})
    with pytest.raises(ValueError, match="not protected"):
        rr.check_protected({}, {}, {"prices/screener": ("archive/prices/screener", 2)})
    with pytest.raises(ValueError, match="SUPERSEDED_ONLY"):
        rr.make_plan(FakeArchive(), superseded_only={"prices/screener": "archive/prices/screener"})


def test_the_owners_retired_datasets_go_whole_and_only_they_leave_protection():
    # Owner, 24 Nov 2026 (S224 (d), "Yes"): four R2 copies nothing reads go whole; the rest of market_caps/ and
    # nse/ stays protected.
    a = FakeArchive()
    for i, d in enumerate(SEP):
        publish(a, "prices/ss", "archive/prices/ss", d, 3000 + i, size=1000)
        publish(a, "nse/source_checks", "archive/nse/source_checks", d, 3100 + i)
        publish(a, "nse/prices_daily", "archive/nse/prices_daily", d, 3200 + i)
    plans = {p.dataset: p for p in rr.make_plan(a)}
    assert set(plans["prices/ss"].drop) == set(SEP) and set(plans["nse/source_checks"].drop) == set(SEP)
    assert "nse/prices_daily" not in plans
    assert "prices/ss" not in rr.KEEP_LATEST_ONLY and "market_caps/nse_history" not in rr.PROTECTED_KEEP_NEWEST
    assert set(rr.RETIRED_DATASETS) >= rr.RETIRED_BY_OWNER


def test_rankings_keep_every_date_and_only_the_newest_revision_of_each():
    # Owner, 17 Nov 2026 (S141): "newest per date". A re-run republishes a date.
    a = FakeArchive()
    for i, d in enumerate(SEP):
        publish(a, "snapshots/rankings", "snapshots/rankings", d, 4000 + i,
                created_at="2026-09-25T09:00:00+00:00")
    old = publish(a, "snapshots/rankings", "snapshots/rankings", SEP[3], 4900,
                  created_at="2026-09-25T08:00:00+00:00", move_pointer=False)
    newer = publish(a, "snapshots/rankings", "snapshots/rankings", SEP[5], 4901,
                    created_at="2026-09-25T11:00:00+00:00")
    plan = {p.dataset: p for p in rr.make_plan(a)}["snapshots/rankings"]
    assert plan.keep == SEP and plan.drop == []
    assert old in plan.delete_keys and newer not in plan.delete_keys
    # The superseded revision on SEP[5] (pointer moved to `newer`) goes too.
    assert any(SEP[5] in k and SHA.format(4005) in k for k in plan.delete_keys)
    assert not [k for k in plan.delete_keys if k.endswith("/current.json")]


def test_the_post_retention_audit_covers_every_dataset_that_keeps_some_keys():
    covered = set(rr.deleted_from())
    assert {"prices/screener", "bse/daily", "snapshots/rankings"} <= covered
    assert not covered & set(rr.RETIRED_DATASETS)


def test_a_pinned_date_survives_thinning(monkeypatch):
    monkeypatch.setitem(rr.PINNED_DATES, "bse/daily", frozenset({SEP[0]}))
    a = FakeArchive()
    for i, d in enumerate(SEP):
        publish(a, "bse/daily", "archive/bse/daily", d, 7000 + i)
    plan = {p.dataset: p for p in rr.make_plan(a)}["bse/daily"]
    assert set(plan.keep) == {SEP[0], SEP[-1]}


def test_the_long_nse_file_keeps_its_newest_two_builds_and_nothing_else_of_it():
    # Owner, 17 Nov 2026 ("Yes weekly"): published to R2 each Saturday.
    a = FakeArchive()
    weeks = ["2026-10-30", "2026-11-06", "2026-11-13"]
    for i, d in enumerate(weeks):
        for k, kind in enumerate(("close", "value", "report")):
            publish(a, f"prices/nse_long_{kind}", f"archive/prices/nse_long_{kind}", d, 8000 + 10 * i + k)
    plans = {p.dataset: p for p in rr.make_plan(a)}
    for kind in ("close", "value", "report"):
        plan = plans[f"prices/nse_long_{kind}"]
        assert plan.keep == weeks[1:] and plan.drop == weeks[:1]
    assert set(rr.deleted_from()) >= {"prices/nse_long_close", "prices/nse_long_value", "prices/nse_long_report"}


def test_the_two_datasets_the_owner_let_go_are_retired_and_nothing_else_lost_protection():
    """S195 4.1 and 4.6 (owner, 22 Nov 2026): calculations/rankings and indices/prices/research are
    retired; every other indices/ dataset on R2 stays protected, and the table passes the guard."""
    from scripts import r2_retention as rr

    assert rr.RETIRED_DATASETS["calculations/rankings"] == "archive/calculations/rankings"
    assert rr.RETIRED_DATASETS["indices/prices/research"] == "archive/indices/prices/research"
    assert not rr._protected("calculations/rankings") and not rr._protected("indices/prices/research")
    for ds in ("indices/constituents/nifty_total_market", "indices/membership/nifty_total_market",
               "indices/nse_close_all"):
        assert rr._protected(ds), ds
    rr.check_protected(rr.RETAINED_DATASETS, rr.RETIRED_DATASETS, rr.PROTECTED_KEEP_NEWEST)
    for ds in rr.PROTECTED_SUPERSEDED_ONLY:      # make_plan's other guard: each must still be protected
        assert rr._protected(ds), ds
