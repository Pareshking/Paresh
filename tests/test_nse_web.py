"""NSE moved www.nseindia.com to www.nseindia.in (owner, 18 Nov 2026): .in first, .com as fallback."""
import re
from pathlib import Path

import pytest
import requests

from src.core import nse_web

ROOT = Path(__file__).resolve().parents[1]


class Resp:
    def __init__(self, code, body=b"[]"):
        self.status_code, self.content = code, body


def _factory(answers, seen):
    """answers: {url: status or Exception}; seen collects (url, headers) per call."""
    class S:
        def __init__(self):
            self.headers = {}

        def get(self, url, params=None, timeout=None):
            seen.append((url, dict(self.headers)))
            a = answers.get(url, 404)
            if isinstance(a, Exception):
                raise a
            return Resp(a)
    return S


def test_the_new_host_is_tried_first_with_its_own_referer_and_origin():
    seen = []
    r, base = nse_web.get("/api/x", page="/p", factory=_factory(
        {"https://www.nseindia.in/p": 200, "https://www.nseindia.in/api/x": 200}, seen))
    assert base == "https://www.nseindia.in" and r.status_code == 200
    assert all(u.startswith("https://www.nseindia.in") for u, _ in seen)
    _, h = seen[-1]
    assert h["Referer"] == "https://www.nseindia.in/p" and h["Origin"] == "https://www.nseindia.in"


def test_the_old_host_answers_when_the_new_one_refuses():
    seen = []
    r, base = nse_web.get("/api/x", page="/p", factory=_factory(
        {"https://www.nseindia.in/api/x": 403, "https://www.nseindia.com/p": 200,
         "https://www.nseindia.com/api/x": 200}, seen))
    assert base == "https://www.nseindia.com" and r.status_code == 200
    _, h = seen[-1]
    assert h["Referer"] == "https://www.nseindia.com/p" and h["Origin"] == "https://www.nseindia.com"


def test_a_refusal_everywhere_comes_back_for_the_callers_own_handling():
    r, base = nse_web.get("/api/x", page="/p", factory=_factory({}, []))
    assert r.status_code == 404 and base == "https://www.nseindia.com"
    boom = requests.ConnectionError("down")
    with pytest.raises(requests.ConnectionError):
        nse_web.get("/api/x", page="/p", factory=_factory(
            {f"{h}/p": boom for h in nse_web.WWW_HOSTS}, []))


def test_session_for_takes_the_first_host_whose_page_answers():
    s, base = nse_web.session_for("/p", factory=_factory(
        {"https://www.nseindia.in/p": 403, "https://www.nseindia.com/p": 200}, []))
    assert base == "https://www.nseindia.com" and s.headers["Origin"] == base


def test_the_reference_sync_falls_back_to_the_old_host():
    from scripts import sync_nse_reference as s

    asked = []

    def fetch(url, params):
        asked.append(url)
        if ".in/" in url:
            raise s.SyncError("refused")
        return b"[]"

    import datetime as dt
    assert s.fetch_corporate_actions(dt.datetime(2026, 11, 18), fetch=fetch) == []
    assert asked == list(s.CA_URLS) and asked[0].startswith("https://www.nseindia.in/")


def test_no_api_call_still_names_the_old_host_as_its_referer_or_origin():
    """Only nse_web's fallback list may name www.nseindia.com for the website/API."""
    hits = []
    for p in list((ROOT / "src").rglob("*.py")) + list((ROOT / "scripts").glob("*.py")):
        if p.name == "nse_web.py":
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"(Referer|Origin).{0,10}https://www\.nseindia\.com", line):
                hits.append(f"{p.relative_to(ROOT)}:{n}")
    assert hits == []
