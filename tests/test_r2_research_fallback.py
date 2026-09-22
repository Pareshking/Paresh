from pathlib import Path
import pandas as pd
import pytest

from r2.consumers.r2_research import R2ResearchConsumerError, R2ResearchPin
from r2.consumers.r2_research_fallback import R2ResearchFallbackError, read_with_explicit_fallback


def test_fallback_requires_explicit_opt_in():
    class Broken:
        def resolve_revision(self, *args):
            raise R2ResearchConsumerError("pinned revision unavailable")
    with pytest.raises(R2ResearchFallbackError, match="no fallback was authorized"):
        read_with_explicit_fallback(Broken(), pin=R2ResearchPin("d","2026-01-01","a"*64))


def test_fallback_reads_local_parquet(tmp_path: Path):
    path = tmp_path / "fallback.parquet"
    frame = pd.DataFrame({"symbol": ["AAA"], "value": [1.0]})
    frame.to_parquet(path, index=False)
    class Broken:
        def resolve_revision(self, *args):
            raise R2ResearchConsumerError("pinned revision unavailable")
    result = read_with_explicit_fallback(
        Broken(),
        pin=R2ResearchPin("d","2026-01-01","a"*64),
        fallback_path=str(path),
    )
    assert result.source.startswith("fallback:")
    assert result.pin is None
    assert result.sha256
    pd.testing.assert_frame_equal(result.frame, frame)


def test_unexpected_r2_programming_error_is_not_silently_masked():
    class Broken:
        def resolve_revision(self, *args):
            raise RuntimeError("unexpected bug")

    with pytest.raises(RuntimeError, match="unexpected bug"):
        read_with_explicit_fallback(
            Broken(),
            pin=R2ResearchPin("d", "2026-01-01", "a" * 64),
            fallback_path="/does/not/matter.parquet",
        )
