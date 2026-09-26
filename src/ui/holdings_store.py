"""The reader's own holdings, kept in their own browser.

Same arrangement as the watchlist (src/ui/watchlist_store.py), for the same
reason: the public deployment is shared, so a list saved on the server would be
every visitor's list. Here it lives in the reader's localStorage, private to
them and to that device, and Python keeps a working copy in session state.

The stored text is "SYMBOL" or "SYMBOL@price" entries separated by commas.
"""
from __future__ import annotations

import streamlit as st

from src.engine.exit_watch import parse_holdings

STORAGE_KEY = "mt_holdings_v1"
_TEXT = "hl_text"
_PENDING = "_hl_write"
_SEEN = "_hl_seen"
_EXPECT = "_hl_expect"

# Report only when the browser holds something Python has not heard yet.
_JS = """
export default function(component) {
  const { data, setStateValue } = component;
  const KEY = %s;
  let stored = '';
  try { stored = window.localStorage.getItem(KEY) || ''; } catch (e) { stored = ''; }
  const write = (data && typeof data.write === 'string') ? data.write : null;
  if (write !== null && write !== stored) {
    try { window.localStorage.setItem(KEY, write); stored = write; } catch (e) {}
  }
  const seen = (data && typeof data.seen === 'string') ? data.seen : '';
  if (stored !== seen) setStateValue('stored', stored);
}
""" % repr(STORAGE_KEY)

_component = None


def _bridge():
    global _component
    if _component is None:
        _component = st.components.v2.component("holdings_store", js=_JS)
    return _component


def to_text(items: list[tuple[str, float | None]]) -> str:
    return ",".join(s if p is None else f"{s}@{p:g}" for s, p in items)


def sync() -> None:
    """Mount the bridge; call once on the page that reads the holdings."""
    ss = st.session_state
    pending = ss.pop(_PENDING, None)
    try:
        result = _bridge()(
            key="hl_store",
            data={"write": pending, "seen": ss.get(_SEEN, "")},
            default={"stored": None},
            on_stored_change=lambda: None,
        )
        stored = getattr(result, "stored", None)
    except Exception:
        # No browser (tests, bare mode): the session copy is the list.
        stored = None
    if pending is not None:
        # Until the browser reports this value back, anything it reports is
        # the list from before the save and must not overwrite the new one.
        ss[_EXPECT] = pending
    if isinstance(stored, str):
        ss[_SEEN] = stored
        expect = ss.get(_EXPECT)
        if expect is not None:
            if stored == expect:
                ss.pop(_EXPECT, None)
        else:
            ss[_TEXT] = to_text(parse_holdings(stored))


def items() -> list[tuple[str, float | None]]:
    return parse_holdings(st.session_state.get(_TEXT, ""))


def save(entries: list[tuple[str, float | None]]) -> None:
    text = to_text(entries)
    st.session_state[_TEXT] = text
    if text != st.session_state.get(_SEEN, ""):
        st.session_state[_PENDING] = text
