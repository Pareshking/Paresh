"""The app's copy of NSE's index files as the Indices page's frames, cached (S170).
Shared by the Indices page and the Dashboard's "Valuation and styles" card."""
from __future__ import annotations

import streamlit as st

from src.engine import indices_page as ip
from src.loaders import nse_indices as ni


def _stamp() -> str:
    return "|".join(f"{p.stat().st_mtime_ns}" if p.exists() else "-" for p in (ni.COMPACT_HISTORY, ni.COMPACT_RECENT))


# Plain fields in the cache, the Frames built outside it (S232): st.cache_data pickles what it
# keeps, and a pull that re-imports src/ between building an object and writing it made pickle find
# another class under the same name ("PicklingError: ... it's not the same object", 24 Nov log).
@st.cache_data(show_spinner=False, ttl=3600)
def _frame_fields(stamp: str) -> dict | None:
    store = ni.read_compact()
    if store.empty:
        return None
    f = ip.frames(store, ni.groups())
    return {"close": f.close, "pe": f.pe, "pb": f.pb, "dy": f.dy, "names": dict(f.names), "groups": dict(f.groups)}


def _frames(stamp: str) -> ip.Frames | None:
    fields = _frame_fields(stamp)
    return None if fields is None else ip.Frames(**fields)


_frames.clear = _frame_fields.clear  # type: ignore[attr-defined]


def frames() -> ip.Frames | None:
    """None when the copy is missing (the page then says so)."""
    return _frames(_stamp())
