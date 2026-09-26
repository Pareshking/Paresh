import pytest

from scripts.r2_membership_live_validation import _resolve_membership_revision, main
from src.storage.reader import R2DatasetRef


def test_cli_requires_a_date(monkeypatch):
    monkeypatch.setattr("sys.argv", ["r2_membership_live_validation"])
    with pytest.raises(SystemExit):
        main()


def test_cli_rejects_invalid_date(monkeypatch):
    monkeypatch.setattr(
        "sys.argv", ["r2_membership_live_validation", "--as-of", "not-a-date"]
    )
    with pytest.raises(ValueError, match="isoformat"):   # the date, not R2 config
        main()


def test_membership_resolution_does_not_require_current_pointer():
    revision = "a" * 64
    ref = R2DatasetRef(
        dataset="indices/membership/nifty_total_market",
        as_of="2026-09-18",
        revision_sha256=revision,
        manifest_key=(
            "archive/manifests/indices/membership/nifty_total_market/"
            "2026-09-18/revisions/" + revision + ".json"
        ),
        object_key="archive/indices/membership/nifty_total_market/2026-09-18/revisions/"
        + revision
        + "/membership_nifty_total_market.parquet",
        manifest={"created_at": "2026-09-18T00:00:00Z"},
    )

    class FakeArchive:
        def list_keys(self, prefix):
            assert prefix.endswith("/2026-09-18/revisions/")
            return iter([ref.manifest_key])

    class FakeReader:
        archive = FakeArchive()

        @staticmethod
        def resolve_latest_revision(dataset, as_of):
            assert dataset == "indices/membership/nifty_total_market"
            assert as_of == "2026-09-18"
            return ref

    resolved = _resolve_membership_revision(FakeReader(), as_of="2026-09-18")
    assert resolved.revision_sha256 == revision


def test_membership_resolution_fails_closed_without_immutable_revision():
    class FakeArchive:
        def list_keys(self, prefix):
            return iter(())

    class FakeReader:
        archive = FakeArchive()

        @staticmethod
        def resolve_latest_revision(dataset, as_of):
            raise FileNotFoundError("no immutable R2 revisions")

    with pytest.raises(FileNotFoundError):
        _resolve_membership_revision(FakeReader(), as_of="2026-09-18")
