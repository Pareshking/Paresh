from datetime import date

import pytest

from contracts import Evidence, EvidenceKind, QuantSnapshot, SourceTier, validate_snapshot


def test_snapshot_requires_identity() -> None:
    snapshot = QuantSnapshot(
        as_of=date(2026, 9, 19),
        benchmark="",
        universe="NIFTY TOTAL MARKET",
        model="System-1",
        config_fingerprint="abc",
    )
    with pytest.raises(ValueError, match="benchmark"):
        validate_snapshot(snapshot)


def test_evidence_confidence_is_bounded() -> None:
    with pytest.raises(ValueError):
        Evidence(
            entity="ABC",
            kind=EvidenceKind.POSITIVE,
            claim="claim",
            source="source",
            source_tier=SourceTier.PRIMARY,
            confidence=1.1,
        )


def test_evidence_accepts_unknown_without_fake_claim() -> None:
    item = Evidence(
        entity="ABC",
        kind=EvidenceKind.UNKNOWN,
        claim="No reliable public evidence found for the question.",
        source="research-log",
        source_tier=SourceTier.DERIVED,
    )
    assert item.kind is EvidenceKind.UNKNOWN
