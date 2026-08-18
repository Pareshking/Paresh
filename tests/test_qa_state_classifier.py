"""The QA readiness classifier must not mistake market data for a cloud error.

Run 32129132689 reported production red with state 'cloud_not_found' at
t=412.4s, while the very same sample showed stApp=1, stTabs=1 and a fully
rendered header. The cause was a bare "404" in the wrapper-error needle list
matching the app's own KPI text, ">50 EMA: 404 (54%)" -- the number of stocks
trading above their 50-day EMA.
"""
import importlib.util
import pathlib

import pytest

_spec = importlib.util.spec_from_file_location(
    "production_qa", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "production_qa.py"
)
production_qa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(production_qa)


class _Locator:
    def __init__(self, n): self._n = n
    def count(self): return self._n


class _Frame:
    """Minimal stand-in for a Playwright frame."""
    def __init__(self, body, testids, url="https://paresh.streamlit.app/~/+/"):
        self._body, self._testids, self.url = body, testids, url

    def locator(self, selector):
        if selector == "body":
            return self
        for key, n in self._testids.items():
            if f'"{key}"' in selector:
                return _Locator(n)
        return _Locator(0)

    def inner_text(self, timeout=None): return self._body


class _Page:
    def __init__(self, frame): self.frames = [frame]; self.main_frame = frame


def _state(body, **testids):
    testids.setdefault("stApp", 1)
    return production_qa.read_state(_Page(_Frame(body, testids)))["state"]


HEALTHY_HEADER = (
    "Paresh Patel ● BULLISH NIFTY ₹23,472 (+1.7% 200D) Universe: 750 "
    ">50 EMA: 404 (54%) 📅 18 Aug 2026 21 stock(s) entered Top 50 this month"
)


def test_404_stocks_above_ema_is_not_a_cloud_404():
    """The exact production false negative."""
    assert _state(HEALTHY_HEADER, stTabs=1) == "ready"


@pytest.mark.parametrize("n", ["404", "1404", "404 (54%)"])
def test_no_bare_number_can_trigger_a_cloud_state(n):
    assert _state(f"Universe: 750 >50 EMA: {n}", stTabs=1) == "ready"


def test_real_cloud_not_found_is_still_detected():
    assert _state("You do not have access to this app", stTabs=0) == "cloud_not_found"


def test_real_sleeping_app_is_still_detected():
    assert _state("This app has gone to sleep", stTabs=0) == "cloud_asleep"


def test_app_exception_beats_ready():
    assert _state("traceback", stTabs=1, stException=1) == "app_exception"


def test_pipeline_running_is_not_ready():
    assert _state("Loading market data & executing quantitative momentum engine…",
                  stTabs=0, stSpinner=1) == "pipeline_running"


def test_data_init_failure_is_reported_as_such():
    assert _state("❌ Failed to initialize market data", stTabs=0) == "app_data_init_failed"


# ── Liveness without a browser ──────────────────────────────────────────────

def test_app_health_url_targets_the_app_not_the_cloud_wrapper():
    """Streamlit Cloud answers 200 with the SPA shell for ANY path.

    So the bare /_stcore/health proves nothing -- measured 2026-08-18 it
    returned 9272 bytes of HTML, while the app's own endpoint under /~/+/
    returned the literal "ok". Probing only the wrapper left the harness
    unable to say whether the Python process was alive whenever the browser
    could not run, which is precisely when that answer matters most.
    """
    assert production_qa.APP_HEALTH_URL.endswith("/~/+/_stcore/health")
    assert production_qa.HEALTH_URL != production_qa.APP_HEALTH_URL


def test_only_a_literal_ok_body_counts_as_healthy():
    """The SPA shell is HTTP 200 too, so status alone is not a health signal."""
    import inspect

    src = inspect.getsource(production_qa.http_probe)
    assert '"app_health"' in src
    assert 'body.strip().lower().startswith("ok")' in src
