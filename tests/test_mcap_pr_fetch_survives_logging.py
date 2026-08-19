"""A successful NSE fetch must survive being reported on.

Found on 2026-08-19 by making the failure legible. Every daily sync logged

    NSE PR fetch failed for 2026-08-18
      (AttributeError: 'datetime.date' object has no attribute 'date')

for five dates in a row. NSE had answered all of them: the zip downloaded, the
archive opened, the CSV parsed, and the dict of 2800 market caps was built. The
NEXT line -- a logger.info reporting the success -- called target_date.date(),
but recent_trading_days() hands out datetime.date, which has no .date(). It
threw, the broad `except Exception` caught it, and the caller received {}.

The result was thrown away on the way out the door, and the silence was read as
"NSE blocks this host's IP". That belief then justified the committed snapshot,
its missing date, and "Market caps: date unknown" in the footer.
"""
from datetime import date, datetime

import pandas as pd
import pytest

from src.loaders import mcap_loader


class _Resp:
    status_code = 200

    def __init__(self, content: bytes):
        self.content = content


def _pr_zip_bytes(trade_date: date) -> bytes:
    """A miniature PR archive shaped like the real one."""
    import io
    import zipfile

    frame = pd.DataFrame({
        "Symbol": ["RELIANCE", "CIPLA"],
        "Series": ["EQ", "EQ"],
        "Market Cap": ["1,000,000", "2,000,000"],
    })
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"mcap{trade_date.strftime('%d%m%Y')}.csv", frame.to_csv(index=False))
    return buf.getvalue()


@pytest.fixture
def served(monkeypatch):
    def _serve(trade_date):
        monkeypatch.setattr(
            mcap_loader.requests, "get",
            lambda *a, **k: _Resp(_pr_zip_bytes(trade_date)),
        )
    return _serve


@pytest.mark.parametrize("kind", ["date", "datetime"])
def test_a_date_and_a_datetime_both_come_back_with_the_caps(served, kind):
    """recent_trading_days() yields date; other callers may pass datetime.

    The old code worked for one and destroyed the result for the other, which
    is exactly why it went unnoticed for so long.
    """
    trade_date = date(2026, 8, 18) if kind == "date" else datetime(2026, 8, 18, 15, 30)
    served(trade_date)

    caps = mcap_loader._fetch_mcap_from_pr_zip(trade_date)

    assert caps == {"RELIANCE": 1_000_000.0, "CIPLA": 2_000_000.0}


def test_the_type_the_real_caller_actually_passes(served):
    """Guards the specific mismatch: the walker's output feeds this function."""
    from src.core.market_time import recent_trading_days

    candidate = recent_trading_days(1)[0]
    assert isinstance(candidate, date)
    served(candidate)

    assert mcap_loader._fetch_mcap_from_pr_zip(candidate)


def test_a_broken_success_log_cannot_swallow_the_result(served, monkeypatch):
    """The structural fix, not just the symptom.

    Reporting on a result must not be able to destroy it, whatever goes wrong
    in the reporting. If logging throws, that is a logging bug and it should
    surface -- never be laundered into "NSE returned nothing".
    """
    trade_date = date(2026, 8, 18)
    served(trade_date)

    def exploding(*args, **kwargs):
        raise AttributeError("boom, exactly like .date() did")

    monkeypatch.setattr(mcap_loader.logger, "info", exploding)

    with pytest.raises(AttributeError):
        mcap_loader._fetch_mcap_from_pr_zip(trade_date)


def test_a_genuine_refusal_is_still_reported_as_one(monkeypatch):
    """The distinction the diagnostics exist to draw."""
    class _Refused:
        status_code = 403
        content = b""

    monkeypatch.setattr(mcap_loader.requests, "get", lambda *a, **k: _Refused())

    with pytest.raises(mcap_loader._NSEBlocked):
        mcap_loader._fetch_mcap_from_pr_zip(date(2026, 8, 18))


def test_an_unpublished_archive_is_not_a_refusal(monkeypatch):
    """404 means try the day before; 403 means stop. Opposite actions."""
    class _Missing:
        status_code = 404
        content = b""

    monkeypatch.setattr(mcap_loader.requests, "get", lambda *a, **k: _Missing())

    assert mcap_loader._fetch_mcap_from_pr_zip(date(2026, 8, 19)) == {}
