"""The chosen system, carried in the address as ?sys= so a reload keeps it.

A stock link (?stock=X) reloads the page, and a reload is a new Streamlit
session: whatever the session held is gone. The system is the one choice
every page depends on, so it rides in the URL whenever it is not the default
(owner, 2026-09-27: "coming back from stock page to screener it is reverting
to default view").
"""

from __future__ import annotations

from urllib.parse import quote

import streamlit as st

from src.engine.extra_universe import SYSTEM_750, SYSTEMS

PARAM = "sys"
KEY = "cfg_system"


def current() -> str:
    """The session's system, adopting ?sys= when the session has none yet."""
    if KEY not in st.session_state:
        from_url = str(st.query_params.get(PARAM) or "")
        st.session_state[KEY] = from_url if from_url in SYSTEMS else SYSTEM_750
    system = st.session_state[KEY]
    return system if system in SYSTEMS else SYSTEM_750


def sync_url(system: str) -> None:
    """Write ?sys= for a non-default system, drop it for the default."""
    want = None if system == SYSTEM_750 else system
    if st.query_params.get(PARAM) != want:
        if want is None:
            st.query_params.pop(PARAM, None)
        else:
            st.query_params[PARAM] = want


def suffix(system: str | None = None) -> str:
    system = st.session_state.get(KEY, SYSTEM_750) if system is None else system
    return "" if system == SYSTEM_750 else f"&{PARAM}={quote(system, safe='')}"


def stock_href(sym: str) -> str:
    """The relative link to a stock's page, keeping the system."""
    return f"?stock={quote(str(sym), safe='')}{suffix()}"


def url_params() -> dict[str, str]:
    """{sys: ...} for a non-default system, else nothing."""
    system = st.session_state.get(KEY, SYSTEM_750)
    return {} if system == SYSTEM_750 else {PARAM: system}


def keep_system_only() -> None:
    """Drop every parameter but ?sys= -- the Back button's clear().

    Always a write, so the host's address bar follows (see ranking_view).
    """
    st.query_params.from_dict(url_params())
