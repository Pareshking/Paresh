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


class _ToggleMenu:
    """A ☰ that toggles on click and shows its links a few polls later."""

    def __init__(self, links_after_polls=3):
        self.expanded = False
        self.clicks = 0
        self.polls = 0
        self.links_after = links_after_polls

    def locator(self, sel):
        menu = self
        if sel == '[data-testid="stPopoverButton"]':
            class _Btn(_Loc):
                def click(self, timeout=None):
                    menu.clicks += 1
                    menu.expanded = not menu.expanded
                    menu.polls = 0

                def get_attribute(self, name):
                    return "true" if menu.expanded else "false"

                @property
                def first(self):
                    return self
            return _Btn(["☰"])
        if "stPopoverBody" in sel and "stPageLink" in sel:
            self.polls += 1
            ready = self.expanded and self.polls > self.links_after
            return _Loc(["Screener"] if ready else [], ready)
        return _Loc([])

    def get_by_role(self, *a, **k):
        return _Loc([])


def test_a_menu_that_is_still_opening_is_not_clicked_shut(monkeypatch):
    """Run 577: the second click closed a menu whose links were on their way."""
    monkeypatch.setattr(nav.time, "sleep", lambda s: None)
    menu = _ToggleMenu(links_after_polls=3)
    assert nav._open_custom_popover(menu) is True
    assert menu.clicks == 1 and menu.expanded
