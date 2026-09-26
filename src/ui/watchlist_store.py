"""The reader's watchlist, kept in their own browser.

It used to live only in the address bar (?wl=...). That kept it private, but
every link inside the app -- a ticker in the table, a peer on the stock page
-- would have had to carry it along, and one that did not would silently empty
the list. Browser storage is still per reader and per device, survives a
refresh and a new visit, and needs nothing from the links.

The bridge is a tiny st.components.v2 component with no visible output. Its
JavaScript reads localStorage once and reports the value to Python, and writes
whatever Python hands it. Python keeps the working copy in session state, so a
page never waits on the browser to know the list.

An old ?wl= link still works: its symbols are merged into the stored list once
and the parameter is dropped from the address.
"""
from __future__ import annotations

import re

import streamlit as st

from src.core.tickers import normalise_symbol

STORAGE_KEY = "mt_watchlist_v1"
_TEXT = "wl_text"          # the working copy, "ABB,TCS"
_PENDING = "_wl_write"      # a value Python wants written to the browser
_SEEN = "_wl_seen"          # the last value the browser reported
_EXPECT = "_wl_expect"      # a value written but not yet reported back

# Report only when the browser holds something Python has not heard yet, so a
# reader with nothing saved costs no extra rerun, and a known value costs none.
_JS = """
export default function(component) {
  const { data, setStateValue } = component;
  const KEY = %s;
  let stored = '';
  try { stored = window.localStorage.getItem(KEY) || ''; } catch (e) { stored = ''; }
  let write = (data && typeof data.write === 'string') ? data.write : null;
  // A shared ?wl= link adds to what this browser already saved. Only the
  // browser knows that list on a fresh visit, so the union is taken here.
  const merge = (data && typeof data.merge === 'string') ? data.merge : '';
  if (merge) {
    const all = [];
    for (const s of (stored + ',' + merge).split(',')) {
      const t = s.trim().toUpperCase();
      if (t && !all.includes(t)) all.push(t);
    }
    write = all.join(',');
  }
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
        _component = st.components.v2.component("watchlist_store", js=_JS)
    return _component


def parse(text: str | None) -> list[str]:
    """Symbols from free text, cleaned to ticker characters, order kept, no repeats."""
    out: list[str] = []
    for part in re.split(r"[,;\s]+", str(text or "")):
        sym = re.sub(r"[^A-Z0-9&._-]", "", normalise_symbol(part).upper())[:20]
        if sym and sym not in out:
            out.append(sym)
    return out[:200]


def sync() -> None:
    """Mount the bridge once per run, before any page reads the list."""
    ss = st.session_state
    pending = ss.pop(_PENDING, None)

    # A shared ?wl= link: the browser merges it into its saved list (see the
    # JS), and it leaves the address so a refresh does not merge it again.
    merge = ""
    url_wl = st.query_params.get("wl")
    if url_wl:
        merge = ",".join(parse(str(url_wl)))
        ss[_TEXT] = ",".join(parse(",".join([ss.get(_TEXT, ""), merge])))
        st.query_params.pop("wl", None)

    try:
        result = _bridge()(
            key="wl_store",
            data={"write": pending, "merge": merge, "seen": ss.get(_SEEN, "")},
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
            # The browser is the source of truth for what was saved.
            ss[_TEXT] = ",".join(parse(stored))


def symbols() -> list[str]:
    return parse(st.session_state.get(_TEXT, ""))


def save(syms: list[str]) -> None:
    """Replace the list; the next run writes it to the browser."""
    text = ",".join(parse(",".join(syms)))
    st.session_state[_TEXT] = text
    # Nothing to write when the browser already holds exactly this; waiting
    # for it to report a value it has no reason to send would stall reads.
    if text != st.session_state.get(_SEEN, ""):
        st.session_state[_PENDING] = text


def toggle(sym: str) -> bool:
    """Add or remove one symbol; returns whether it is now on the list."""
    cur = symbols()
    s = parse(sym)
    if not s:
        return False
    if s[0] in cur:
        cur.remove(s[0])
        on = False
    else:
        cur.append(s[0])
        on = True
    save(cur)
    return on
