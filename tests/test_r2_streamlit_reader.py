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
    assert DEEP_HISTORY_DATASET == "prices/yahoo"
