import pytest

from r2.consumers.r2_research import R2ResearchPin
from r2.consumers.r2_streamlit import (
    configured_dataset,
    configuration_key,
    enabled,
    read_historical,
    DEEP_HISTORY_DATASET,
)


def test_streamlit_reader_disabled_by_default(monkeypatch):
    monkeypatch.delenv("R2_STREAMLIT_READER_ENABLED", raising=False)
    assert enabled() is False
    with pytest.raises(RuntimeError, match="disabled"):
        read_historical(object(), pin=R2ResearchPin("d", "2026-01-01", "a" * 64))


def test_streamlit_reader_flag(monkeypatch):
    monkeypatch.setenv("R2_STREAMLIT_READER_ENABLED", "true")
    assert enabled() is True


def test_streamlit_reader_uses_daily_current_dataset(monkeypatch):
    monkeypatch.setenv("R2_STREAMLIT_READER_ENABLED", "1")
    monkeypatch.delenv("R2_STREAMLIT_DATASET", raising=False)
    assert configured_dataset() == "prices/screener"
    assert configuration_key() == "r2|prices/screener|current"


def test_streamlit_reader_dataset_can_be_configured(monkeypatch):
    monkeypatch.setenv("R2_STREAMLIT_READER_ENABLED", "1")
    monkeypatch.setenv("R2_STREAMLIT_DATASET", "prices/custom")
    assert configured_dataset() == "prices/custom"
    assert configuration_key() == "r2|prices/custom|current"


def test_streamlit_reader_deep_history_dataset():
    # The adjusted archive the daily sync republishes, not the frozen,
    # unadjusted raw capture.
    assert DEEP_HISTORY_DATASET == "prices/yahoo"


def test_streamlit_reader_deep_history_is_current_pointer(monkeypatch):
    monkeypatch.setenv("R2_STREAMLIT_READER_ENABLED", "1")
    import r2.consumers.r2_streamlit as mod

    class Ref:
        dataset = "prices/yahoo"
        as_of = "2026-09-21"
        revision_sha256 = "b" * 64

    class Reader:
        def __init__(self, archive):
            self.archive = archive
        def resolve_current(self, dataset):
            assert dataset == "prices/yahoo"
            return Ref()
        def read_parquet(self, ref):
            return {"ok": True}

    monkeypatch.setattr(mod, "R2DatasetReader", Reader)
    monkeypatch.setattr(mod, "R2Archive", lambda cfg: object())
    monkeypatch.setattr(mod, "R2Config", type("Cfg", (), {"from_env": classmethod(lambda cls: object())}))

    frame, pin = mod.read_configured_deep_history()
    assert frame == {"ok": True}
    assert pin.dataset == "prices/yahoo"
    assert pin.as_of == "2026-09-21"
    assert pin.revision_sha256 == "b" * 64
