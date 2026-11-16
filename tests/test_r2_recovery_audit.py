from scripts import r2_recovery_audit

def test_recovery_revalidates_every_current_pointer():
    class FakeArchive:
        def list_keys(self, prefix):
            return iter(["archive/manifests/prices/screener/2026-09-21/current.json"])

    class FakeReader:
        def __init__(self, archive):
            pass
        def resolve_current(self, dataset, as_of):
            class Ref:
                revision_sha256 = "a" * 64
            return Ref()
        def read_bytes(self, ref):
            return b"payload"

    old = r2_recovery_audit.R2DatasetReader
    r2_recovery_audit.R2DatasetReader = FakeReader
    try:
        result = r2_recovery_audit.audit_recovery(FakeArchive())
    finally:
        r2_recovery_audit.R2DatasetReader = old

    assert result["status"] == "PASS"
    assert result["current_pointers"] == 1
    assert result["verified"][0]["dataset"] == "prices/screener"
    assert result["verified"][0]["size_bytes"] == 7


def test_recovery_revalidates_every_immutable_revision():
    class FakeArchive:
        def list_keys(self, prefix):
            return iter([
                "archive/manifests/prices/screener/2026-09-21/revisions/" + "b" * 64 + ".json",
                "archive/manifests/prices/screener/2026-09-21/current.json",
            ])

    class FakeReader:
        def __init__(self, archive):
            pass
        def resolve_revision(self, dataset, as_of, revision_sha256):
            class Ref:
                pass
            ref = Ref()
            ref.revision_sha256 = revision_sha256
            return ref
        def resolve_current(self, dataset, as_of):
            class Ref:
                revision_sha256 = "b" * 64
            return Ref()
        def read_bytes(self, ref):
            return b"payload"

    old = r2_recovery_audit.R2DatasetReader
    r2_recovery_audit.R2DatasetReader = FakeReader
    try:
        result = r2_recovery_audit.audit_recovery(FakeArchive())
    finally:
        r2_recovery_audit.R2DatasetReader = old

    assert result["immutable_revisions"] == 1
    assert len(result["immutable_verified"]) == 1
    assert result["immutable_verified"][0]["revision_sha256"] == "b" * 64



def test_manifest_contract_excludes_only_creation_timestamp():
    from scripts.r2_publish import _immutable_manifest_contract
    manifest = {
        "dataset": "d",
        "pipeline_version": "v1",
        "ranking_contract": {"universe": ["A"]},
        "created_at": "2026-09-22T00:00:00+00:00",
    }
    contract = _immutable_manifest_contract(manifest)
    assert "created_at" not in contract
    assert contract["pipeline_version"] == "v1"
    assert contract["ranking_contract"] == {"universe": ["A"]}


def _run_with(reader_cls, keys):
    class FakeArchive:
        def list_keys(self, prefix):
            return iter(keys)

    old = r2_recovery_audit.R2DatasetReader
    r2_recovery_audit.R2DatasetReader = reader_cls
    try:
        return r2_recovery_audit.audit_recovery(FakeArchive())
    finally:
        r2_recovery_audit.R2DatasetReader = old


class _Ref:
    def __init__(self, sha):
        self.revision_sha256 = sha


def test_an_unreadable_revision_fails_the_audit_instead_of_passing():
    """The audit gates every retention delete; a payload that no longer reads
    (deleted, truncated, SHA mismatch) must stop it, never be reported PASS."""
    import pytest

    class Reader:
        def __init__(self, archive):
            pass

        def resolve_revision(self, dataset, as_of, sha):
            return _Ref(sha)

        def read_bytes(self, ref):
            raise FileNotFoundError("payload missing")

    key = "archive/manifests/prices/yahoo/2026-09-21/revisions/" + "c" * 64 + ".json"
    with pytest.raises(FileNotFoundError):
        _run_with(Reader, [key])


def test_a_malformed_revision_key_fails_the_audit():
    import pytest

    key = "archive/manifests/prices/yahoo/2026-09-21/revisions/short.json"
    with pytest.raises(RuntimeError, match="Invalid immutable manifest"):
        _run_with(lambda archive: None, [key])


def test_nested_dataset_names_are_resolved_whole():
    """prices/yahoo/raw must not be read as prices/yahoo (or prices)."""
    seen = []

    class Reader:
        def __init__(self, archive):
            pass

        def resolve_revision(self, dataset, as_of, sha):
            seen.append((dataset, as_of))
            return _Ref(sha)

        def read_bytes(self, ref):
            return b"x"

    key = "archive/manifests/prices/yahoo/raw/2026-09-21/revisions/" + "d" * 64 + ".json"
    result = _run_with(Reader, [key])
    assert seen == [("prices/yahoo/raw", "2026-09-21")]
    assert result["status"] == "PASS"


def test_scope_keeps_only_the_named_datasets_not_their_nested_ones():
    k = "archive/manifests/{}/2026-09-25/current.json".format
    scope = ("prices/yahoo", "app/prices_extra")
    assert r2_recovery_audit._in_scope(k("prices/yahoo"), scope)
    assert r2_recovery_audit._in_scope(k("app/prices_extra"), scope)
    assert not r2_recovery_audit._in_scope(k("prices/yahoo/raw"), scope)
    assert not r2_recovery_audit._in_scope(k("nse/prices_daily"), scope)
    assert r2_recovery_audit._in_scope(k("nse/prices_daily"), None)


# --- A3: the weekly run downloads only what can still change (owner, 15 Nov 2026) ---

from datetime import date as _date  # noqa: E402

_M = "archive/manifests/"


def _rev(ds, as_of, c):
    return f"{_M}{ds}/{as_of}/revisions/{c * 64}.json"


def test_the_full_read_set_is_the_last_days_and_each_datasets_newest_date():
    keys = [_rev("prices/nse", "2026-01-05", "a"), _rev("prices/nse", "2026-11-10", "b"),
            _rev("prices/nse", "2026-11-15", "c"), _rev("rankings/s750", "2026-03-31", "d"),
            f"{_M}prices/nse/2026-01-05/current.json"]
    got = r2_recovery_audit.full_read_set(keys, _date(2026, 11, 16), 14)
    assert got == {("prices/nse", "2026-11-10"), ("prices/nse", "2026-11-15"),
                   ("rankings/s750", "2026-03-31")}              # newest of a dataset, however old
    assert ("prices/nse", "2026-01-05") in r2_recovery_audit.full_read_set(keys, _date(2026, 11, 16), None)


def test_an_old_revision_is_resolved_and_size_checked_but_not_downloaded():
    keys = [_rev("prices/nse", "2026-01-05", "a"), _rev("prices/nse", "2026-11-15", "b")]
    downloaded = []

    class FakeArchive:
        def list_keys(self, prefix):
            return iter(keys)

    class FakeReader:
        def __init__(self, archive):
            pass

        def resolve_revision(self, dataset, as_of, revision_sha256):
            ref = type("Ref", (), {})()
            ref.revision_sha256, ref.manifest = revision_sha256, {"size_bytes": 9}
            return ref

        def read_bytes(self, ref):
            downloaded.append(ref.revision_sha256)
            return b"payload!!"

    old = r2_recovery_audit.R2DatasetReader
    r2_recovery_audit.R2DatasetReader = FakeReader
    try:
        out = r2_recovery_audit.audit_recovery(FakeArchive(), full_days=14, today=_date(2026, 11, 16))
    finally:
        r2_recovery_audit.R2DatasetReader = old
    assert downloaded == ["b" * 64]                              # only the recent one
    assert out["immutable_revisions"] == 2 and out["downloaded_in_full"] == 1
    checked = {r["as_of"]: r["checked"] for r in out["immutable_verified"]}
    assert checked == {"2026-01-05": "manifest+size", "2026-11-15": "sha256"}


def test_the_weekly_run_is_bounded_and_a_full_run_can_still_be_asked_for():
    import yaml
    from pathlib import Path
    wf = yaml.safe_load(Path(".github/workflows/r2_recovery_audit.yml").read_text(encoding="utf-8"))
    on = wf.get("on", wf.get(True))
    assert "full" in on["workflow_dispatch"]["inputs"]
    run = wf["jobs"]["recovery"]["steps"][-1]["run"]
    assert "--full" in run and "inputs.full" in run
