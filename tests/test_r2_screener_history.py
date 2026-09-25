"""The Screener history survey reads each R2 revision's shape correctly."""
import io
import json

import numpy as np
import pandas as pd

from scripts import r2_screener_history as sh


def _store(dates):
    idx = pd.DatetimeIndex(dates)
    cols = pd.MultiIndex.from_product([["AAA", "BBB"], ["Close", "Volume"]])
    return pd.DataFrame(np.ones((len(idx), 4)), index=idx, columns=cols)


def _weekly_then_daily():
    weekly = pd.date_range("2016-09-30", "2025-09-12", freq="W-FRI")
    daily = pd.bdate_range("2025-09-15", "2026-09-24")
    return weekly.append(daily)


def test_the_daily_history_starts_where_weekly_points_stop():
    got = sh.describe_store(_store(_weekly_then_daily()))
    assert got["first_date"] == "2016-09-30"
    assert got["first_daily_date"] == "2025-09-12"   # last weekly Friday, then Monday
    assert got["daily_dates"] == len(pd.bdate_range("2025-09-15", "2026-09-24")) + 1
    assert got["symbols"] == 2


def test_a_long_weekend_does_not_end_the_daily_run():
    dates = pd.bdate_range("2026-09-01", "2026-09-24").drop(pd.Timestamp("2026-09-14"))
    got = sh.describe_store(_store(dates))
    assert got["first_daily_date"] == "2026-09-01"
    assert got["daily_dates"] == got["distinct_dates"]


class _Archive:
    def __init__(self, stores):
        self.objects = {}
        for i, (as_of, frame) in enumerate(stores):
            sha = f"{i:064x}"
            obj = f"archive/prices/screener/{as_of}/revisions/{sha}/screener_prices.parquet"
            buf = io.BytesIO()
            frame.to_parquet(buf)
            self.objects[obj] = buf.getvalue()
            self.objects[f"archive/manifests/prices/screener/{as_of}/revisions/{sha}.json"] = json.dumps(
                {"object_key": obj, "created_at": f"{as_of}T20:00:00+00:00"}).encode()
            self.objects[f"archive/manifests/prices/screener/{as_of}/current.json"] = b"{}"

    def list_keys(self, prefix):
        return iter(sorted(k for k in self.objects if k.startswith(prefix)))

    def get_bytes(self, key):
        return self.objects[key]


def test_a_store_that_lost_dates_between_revisions_shows_it():
    full = _weekly_then_daily()
    archive = _Archive([
        ("2026-09-21", _store(full.append(pd.bdate_range("2014-01-01", "2016-09-29")))),
        ("2026-09-24", _store(full)),
    ])
    rows = sh.history(archive)
    assert [r["as_of"] for r in rows] == ["2026-09-21", "2026-09-24"]
    assert rows[0]["distinct_dates"] > rows[1]["distinct_dates"]
    assert rows[1]["first_date"] == "2016-09-30"
    # Pointers are not revisions and are not surveyed.
    assert all("error" not in r for r in rows)
