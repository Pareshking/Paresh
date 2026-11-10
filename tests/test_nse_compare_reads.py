"""`nse_compare.read_nse` reads R2 concurrently and returns the serial answer.

The `Compare` step of run 42486769158 spent 44m41s of a 45m14s job inside
`read_nse`, reading ~520 R2 days one at a time (four round trips and a parquet
parse each) and printing nothing. The reads now run in a thread pool. These
tests pin the two things that matters about that: the result is identical to
the serial read, in date order, and the failures are still reported in date
order.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from scripts import nse_compare
from scripts.nse_collect import DATASETS

DAYS = [date(2023, 10, 2), date(2023, 10, 3), date(2023, 10, 4),
        date(2023, 10, 5), date(2023, 10, 6), date(2023, 10, 9)]
CA_DAYS = {date(2023, 10, 3), date(2023, 10, 6)}
BROKEN = {date(2023, 10, 5)}
MCAP_DAY = date(2023, 10, 9)


class _Archive:
    def list_keys(self, prefix: str):
        if prefix == f"archive/manifests/{DATASETS['prices'][0]}/":
            days = DAYS
        elif prefix == f"archive/manifests/{DATASETS['corporate_actions'][0]}/":
            days = sorted(CA_DAYS)
        elif prefix == f"archive/manifests/{DATASETS['market_caps'][0]}/":
            days = [MCAP_DAY]
        else:  # pragma: no cover - nothing else is listed
            days = []
        for d in days:
            yield f"{prefix}{d.isoformat()}/current.json"


class _Reader:
    """One reader per thread, as the real code builds them."""

    instances = 0

    def __init__(self):
        type(self).instances += 1
        self.archive = _Archive()

    def resolve_current(self, dataset: str, *, as_of: str):
        return (dataset, as_of)

    def read_parquet(self, ref):
        dataset, as_of = ref
        day = date.fromisoformat(as_of)
        if dataset == DATASETS["prices"][0]:
            if day in BROKEN:
                raise RuntimeError("object SHA mismatch")
            # Two rows that survive the series filter and one that does not.
            return pd.DataFrame({
                "date": [as_of] * 3,
                "mkt": ["CM"] * 3,
                "series": ["EQ", "BE", "SM"],
                "symbol": ["AAA", "BBB", "CCC"],
                "close": [100.0, 200.0, 300.0],
                "prev_close": [99.0, 199.0, 299.0],
                "high": [101.0, 201.0, 301.0],
                "low": [98.0, 198.0, 298.0],
                "volume": [10, 20, 30],
                "value": [1000.0, 2000.0, 3000.0],
                "spare": ["x", "y", "z"],
            })
        if dataset == DATASETS["corporate_actions"][0]:
            return pd.DataFrame({
                "date": [as_of],
                "symbol": ["AAA"],
                "ex_date": [as_of],
                "purpose": ["BONUS 1:1"],
            })
        return pd.DataFrame({"symbol": ["AAA"], "mcap": [1.0e10]})


@pytest.fixture(autouse=True)
def _count_readers():
    _Reader.instances = 0
    yield


def _read(workers: int):
    return nse_compare.read_nse(
        date(2023, 10, 1), workers=workers, make_reader=_Reader
    )


def test_concurrent_and_serial_reads_agree_exactly():
    serial_prices, serial_acts, serial_mcaps, serial_bad = _read(1)
    conc_prices, conc_acts, conc_mcaps, conc_bad = _read(8)

    pd.testing.assert_frame_equal(serial_prices, conc_prices)
    pd.testing.assert_frame_equal(serial_acts, conc_acts)
    pd.testing.assert_frame_equal(serial_mcaps, conc_mcaps)
    assert serial_bad == conc_bad


def test_the_frames_come_back_in_date_order():
    prices, acts, _mcaps, _bad = _read(8)
    readable = [d.isoformat() for d in DAYS if d not in BROKEN]
    assert list(prices["date"].unique()) == readable
    assert list(acts["ex_date"]) == [d.isoformat() for d in sorted(CA_DAYS)]
    assert list(prices.columns) == nse_compare.KEEP
    assert set(prices["series"]) == {"EQ", "BE"}


def test_an_unreadable_day_is_named_once_in_date_order():
    _prices, _acts, _mcaps, bad = _read(8)
    assert bad == ["2023-10-05: RuntimeError"]


def test_each_worker_builds_its_own_reader():
    """A boto3 client per thread, not one shared across the pool."""
    _read(4)
    assert _Reader.instances > 1


def test_progress_says_where_the_read_is(capsys):
    _read(8)
    out = capsys.readouterr().out
    assert "NSE sessions since 2023-10-01" in out
    assert f"read {len(DAYS)}/{len(DAYS)} sessions" in out
