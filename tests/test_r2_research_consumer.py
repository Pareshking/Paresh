import pandas as pd
import pytest

from src.storage.reader import R2DatasetIntegrityError

from r2.consumers.r2_research import (
    R2ResearchConsumerError,
    R2ResearchPin,
    pin_from_ref,
    read_pinned_dataset,
)


class FakeReader:
    def __init__(self):
        self.calls = []

    def resolve_revision(self, dataset, as_of, revision):
        self.calls.append(("resolve", dataset, as_of, revision))
        return type(
            "Ref",
            (),
            {
                "dataset": dataset,
                "as_of": as_of,
                "revision_sha256": revision,
            },
        )()

    def read_parquet(self, ref):
        self.calls.append(("read", ref.dataset, ref.as_of, ref.revision_sha256))
        return pd.DataFrame({"symbol": ["AAA"], "close": [100.0]})


def test_reader_uses_explicit_immutable_pin_and_never_current_pointer():
    reader = FakeReader()
    revision = "a" * 64
    result = read_pinned_dataset(
        reader,
        pin=R2ResearchPin(
            dataset="prices/screener",
            as_of="2026-09-21",
            revision_sha256=revision,
        ),
    )
    assert result.pin.revision_sha256 == revision
    assert result.frame.to_dict("records") == [{"symbol": "AAA", "close": 100.0}]
    assert reader.calls == [
        ("resolve", "prices/screener", "2026-09-21", revision),
        ("read", "prices/screener", "2026-09-21", revision),
    ]


def test_empty_dataset_is_rejected():
    with pytest.raises(R2ResearchConsumerError, match="dataset"):
        read_pinned_dataset(
            FakeReader(),
            pin=R2ResearchPin(dataset="", as_of="2026-09-21", revision_sha256="a" * 64),
        )


def test_missing_as_of_is_rejected():
    with pytest.raises(R2ResearchConsumerError, match="as_of"):
        read_pinned_dataset(
            FakeReader(),
            pin=R2ResearchPin(dataset="prices/screener", as_of="", revision_sha256="a" * 64),
        )


def test_pin_from_verified_ref():
    ref = type(
        "Ref",
        (),
        {
            "dataset": "indices/membership",
            "as_of": "2026-09-18",
            "revision_sha256": "b" * 64,
        },
    )()
    assert pin_from_ref(ref) == R2ResearchPin(
        dataset="indices/membership",
        as_of="2026-09-18",
        revision_sha256="b" * 64,
    )


def test_integrity_failure_is_exposed_as_consumer_error():
    class IntegrityReader(FakeReader):
        def resolve_revision(self, dataset, as_of, revision):
            raise R2DatasetIntegrityError("manifest mismatch")

    with pytest.raises(R2ResearchConsumerError, match="manifest mismatch"):
        read_pinned_dataset(
            IntegrityReader(),
            pin=R2ResearchPin(
                dataset="prices/screener",
                as_of="2026-09-21",
                revision_sha256="a" * 64,
            ),
        )
