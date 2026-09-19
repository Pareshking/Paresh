from datetime import date

import pytest

from agent.contracts import (
    AdversarialReview,
    Evidence,
    EvidenceKind,
    QuantSnapshot,
    ResearchItem,
    SourceTier,
    WeeklyReport,
    validate_report,
    validate_snapshot,
)
from agent.fingerprint import canonical_config_payload, config_fingerprint


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


def test_fingerprint_is_stable_and_uses_canonical_config() -> None:
    first = config_fingerprint()
    second = config_fingerprint()
    assert first == second
    assert len(first) == 64
    assert canonical_config_payload()["benchmark_symbol"] == "^CRSLDX"


def test_report_rejects_duplicate_symbols() -> None:
    item = ResearchItem(symbol="ABC", rank=1)
    report = WeeklyReport(
        as_of=date(2026, 9, 19),
        model="System-1",
        universe="NIFTY TOTAL MARKET",
        benchmark="^CRSLDX",
        items=(item, item),
    )
    with pytest.raises(ValueError, match="duplicate"):
        validate_report(report)


def test_report_rejects_mismatched_evidence_bucket() -> None:
    evidence = Evidence(
        entity="ABC",
        kind=EvidenceKind.NEGATIVE,
        claim="negative fact",
        source="source",
        source_tier=SourceTier.PRIMARY,
    )
    report = WeeklyReport(
        as_of=date(2026, 9, 19),
        model="System-1",
        universe="NIFTY TOTAL MARKET",
        benchmark="^CRSLDX",
        items=(ResearchItem(symbol="ABC", rank=1, positive_evidence=(evidence,)),),
    )
    with pytest.raises(ValueError, match="positive_evidence"):
        validate_report(report)


def test_report_rejects_review_for_unknown_symbol() -> None:
    report = WeeklyReport(
        as_of=date(2026, 9, 19),
        model="System-1",
        universe="NIFTY TOTAL MARKET",
        benchmark="^CRSLDX",
        items=(ResearchItem(symbol="ABC", rank=1),),
        reviews=(
            AdversarialReview(
                symbol="XYZ",
                original_claims=("claim",),
                challenged_claims=("challenge",),
                unresolved_questions=("question",),
            ),
        ),
    )
    with pytest.raises(ValueError, match="review symbol"):
        validate_report(report)
