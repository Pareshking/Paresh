"""NSE's website and API host, with the old one as a fallback (owner, 18 Nov 2026).

NSE moved its site from www.nseindia.com to www.nseindia.in. Checked that day:
`https://www.nseindia.com/api/marketStatus` answers 301 to the same path on
.in, and our jobs kept working because requests follows the redirect. A script
that still sends `Referer`/`Origin: https://www.nseindia.com` may be refused
once NSE enforces the new origin, so every call here goes to .in first, with
the Referer and Origin of the host it is talking to, and falls back to .com
only when .in does not answer with data.

The archives (nsearchives.nseindia.com, archives.nseindia.com) did not move
and are not handled here.
"""
from __future__ import annotations

import requests

WWW_HOSTS = ("https://www.nseindia.in", "https://www.nseindia.com")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36"


def headers(base: str, page: str, accept: str = "application/json") -> dict[str, str]:
    """A browser's headers for an API call made from `page` on `base`."""
    return {"User-Agent": UA, "Accept": accept, "Referer": base + page, "Origin": base}


def session_for(page: str, *, factory=requests.Session, timeout: int = 30) -> tuple[requests.Session, str]:
    """(session with the page's cookies, base) for the first host whose page answers.

    When no page answers, the session for the first host: NSE's API has also
    answered without the page's cookies, so the call itself decides.
    """
    first = None
    for base in WWW_HOSTS:
        s = factory()
        s.headers.update(headers(base, page))
        first = first or (s, base)
        try:
            if s.get(base + page, timeout=timeout).status_code < 400:
                return s, base
        except requests.RequestException:
            continue
    return first


def get(api_path: str, *, page: str, params: dict | None = None, factory=requests.Session,
        timeout: int = 60) -> tuple[requests.Response, str]:
    """(response, base): the first host that answers `api_path` with HTTP 200 and a body.

    Each host gets its own session, its page visited first for the cookies.
    When none does, the last host's response is returned for the caller's own
    status handling; when none answered at all, the last error is raised.
    """
    last_resp, last_exc = None, None
    for base in WWW_HOSTS:
        s = factory()
        s.headers.update(headers(base, page))
        try:
            s.get(base + page, timeout=30)
            r = s.get(base + api_path, params=params, timeout=timeout)
        except requests.RequestException as exc:
            last_exc = exc
            continue
        if r.status_code == 200 and r.content:
            return r, base
        last_resp = (r, base)
    if last_resp is not None:
        return last_resp
    raise last_exc
