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
