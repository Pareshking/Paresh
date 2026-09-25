"""missing_pages reports a page the opened menu does not list.

It used to return [] whenever the hamburger button existed, whether or not the
menu had been opened and read, so a page dropped from the menu passed
reachability on every narrow viewport.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import _streamlit_nav as nav  # noqa: E402


class _Loc:
    def __init__(self, texts, visible=True):
        self._texts, self._visible = list(texts), visible

    def count(self):
        return len(self._texts)

    @property
    def first(self):
        return _Loc(self._texts[:1], self._visible)

    def nth(self, i):
        return _Loc([self._texts[i]], self._visible)

    def is_visible(self):
        return self._visible and bool(self._texts)

    def inner_text(self, timeout=None):
        return self._texts[0]

    def click(self, timeout=None):
        pass

    def filter(self, has_text=None):
        return _Loc([t for t in self._texts if has_text in t], self._visible)


class _Frame:
    """A menu that is (or is not) openable and lists `listed` page names."""

    def __init__(self, listed, opens=True):
        self.listed, self.opens = listed, opens

    def locator(self, sel):
        if "stPopoverBody" in sel and "stPageLink" in sel:
            return _Loc(self.listed if self.opens else [], self.opens)
        if sel == '[data-testid="stPageLink"]':
            return _Loc(self.listed if self.opens else [])
        if sel in ('[data-testid="stPopoverButton"]', '[data-testid="stPopover"] button'):
            return _Loc(["☰"])
        return _Loc([])

    def get_by_role(self, role, name=None, exact=None):
        return _Loc([])


PAGES = ["Screener", "Sectors", "Guide"]


def test_a_page_missing_from_an_opened_menu_is_reported(monkeypatch):
    monkeypatch.setattr(nav.time, "sleep", lambda s: None)
    assert nav.missing_pages(_Frame(["Screener", "Guide"]), PAGES) == ["Sectors"]


def test_a_complete_menu_reports_nothing(monkeypatch):
    monkeypatch.setattr(nav.time, "sleep", lambda s: None)
    assert nav.missing_pages(_Frame(PAGES), PAGES) == []


def test_a_menu_that_will_not_open_falls_back_to_the_button(monkeypatch):
    monkeypatch.setattr(nav.time, "sleep", lambda s: None)
    t = iter(range(0, 10**6, 10))
    monkeypatch.setattr(nav.time, "perf_counter", lambda: next(t))
    assert nav.missing_pages(_Frame(PAGES, opens=False), PAGES) == []
