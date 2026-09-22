import pytest
from r2.consumers.r2_research import R2ResearchPin
from r2.consumers.r2_streamlit import enabled, read_historical

def test_streamlit_reader_disabled_by_default(monkeypatch):
    monkeypatch.delenv("R2_STREAMLIT_READER_ENABLED", raising=False)
    assert enabled() is False
    with pytest.raises(RuntimeError, match="disabled"):
        read_historical(object(), pin=R2ResearchPin("d","2026-01-01","a"*64))

def test_streamlit_reader_flag(monkeypatch):
    monkeypatch.setenv("R2_STREAMLIT_READER_ENABLED","true")
    assert enabled() is True


def test_streamlit_reader_requires_explicit_pin(monkeypatch):
    from r2.consumers.r2_streamlit import configured_pin
    monkeypatch.setenv("R2_STREAMLIT_READER_ENABLED", "1")
    monkeypatch.setenv("R2_STREAMLIT_AS_OF", "2026-09-21")
    monkeypatch.delenv("R2_STREAMLIT_REVISION_SHA256", raising=False)
    with pytest.raises(RuntimeError, match="REVISION_SHA256"):
        configured_pin()


def test_streamlit_reader_configuration_key_changes_with_pin(monkeypatch):
    from r2.consumers.r2_streamlit import configuration_key
    monkeypatch.setenv("R2_STREAMLIT_READER_ENABLED", "1")
    monkeypatch.setenv("R2_STREAMLIT_AS_OF", "2026-09-21")
    monkeypatch.setenv("R2_STREAMLIT_REVISION_SHA256", "a" * 64)
    first = configuration_key()
    monkeypatch.setenv("R2_STREAMLIT_REVISION_SHA256", "b" * 64)
    second = configuration_key()
    assert first != second
