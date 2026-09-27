"""The chosen system survives a stock link's reload via ?sys=."""

import pytest

from src.ui import system_param as sp


class _Params(dict):
    def from_dict(self, d):
        self.clear()
        self.update(d)


class _St:
    def __init__(self, query):
        self.session_state = {}
        self.query_params = _Params(query)


@pytest.fixture
def fake(monkeypatch):
    def make(query=None):
        st = _St(query or {})
        monkeypatch.setattr(sp, "st", st)
        return st
    return make


def test_a_fresh_session_adopts_the_system_in_the_address(fake):
    st = fake({"sys": "combined", "stock": "ABB"})
    assert sp.current() == "combined"
    assert st.session_state["cfg_system"] == "combined"


def test_an_unknown_value_falls_back_to_the_750(fake):
    fake({"sys": "bogus"})
    assert sp.current() == "750"


def test_the_session_wins_over_the_address_once_chosen(fake):
    st = fake({"sys": "nano"})
    st.session_state["cfg_system"] = "combined"
    assert sp.current() == "combined"


def test_stock_links_carry_a_non_default_system_only(fake):
    st = fake()
    st.session_state["cfg_system"] = "750"
    assert sp.stock_href("M&M") == "?stock=M%26M"
    st.session_state["cfg_system"] = "nano"
    assert sp.stock_href("ABB") == "?stock=ABB&sys=nano"


def test_sync_and_back_keep_only_the_system(fake):
    st = fake({"stock": "ABB"})
    st.session_state["cfg_system"] = "combined"
    sp.sync_url("combined")
    assert st.query_params == {"stock": "ABB", "sys": "combined"}
    sp.keep_system_only()
    assert st.query_params == {"sys": "combined"}
    st.session_state["cfg_system"] = "750"
    sp.sync_url("750")
    assert "sys" not in st.query_params
