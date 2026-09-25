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
        publish(a, "prices/screener", "archive/prices/screener", d, 1500 + i)
    return a


def test_plan_drops_only_the_two_datasets_and_only_unkept_dates():
    a = _archive()
    plans = {p.dataset: p for p in rr.make_plan(a)}
    yahoo = plans["prices/yahoo"]
    dropped = set(AUG + SEP) - ({"2026-08-31"} | set(SEP[-7:]))
    assert set(yahoo.drop) == dropped
    # pointer + manifest + payload per dropped date
    assert len(yahoo.delete_keys) == 3 * len(dropped)
    assert yahoo.delete_bytes == 1000 * len(dropped) + sum(
        len(a.objects[k]) for k in yahoo.delete_keys if k.startswith("archive/manifests/"))
    every = [k for p in plans.values() for k in p.delete_keys]
    assert not [k for k in every if "/raw/" in k or "screener" in k]
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
    for ds, root in rr.RETAINED_DATASETS.items():
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
