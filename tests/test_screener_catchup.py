"""The nightly catch-up acts only when the published prices are behind (owner, 24 Nov 2026)."""
import importlib.util
from datetime import date, datetime, UTC
from pathlib import Path

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("screener_catchup", Path(__file__).resolve().parents[1] / "scripts/screener_catchup.py")
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)

IST = UTC  # the times below are only compared with each other


def test_holiday_is_not_a_due_session():
    # 24 Nov 2026 is Guru Nanak Jayanti on NSE's list: at 05:07 IST on the 25th the due session is the 23rd.
    from src.core.market_time import INDIA_TZ
    assert sc.target_session(datetime(2026, 11, 25, 5, 7, tzinfo=INDIA_TZ)) == date(2026, 11, 23)
    # Before the 22:30 IST settle the same day's session is not due yet.
    assert sc.target_session(datetime(2026, 11, 23, 21, 0, tzinfo=INDIA_TZ)) == date(2026, 11, 20)


def test_decisions():
    t = date(2026, 11, 23)
    pub = datetime(2026, 11, 23, 23, 0, tzinfo=IST)
    assert sc.decide(t, date(2026, 11, 20), pub, None)[0] == "screener"
    assert sc.decide(t, None, None, None)[0] == "screener"
    assert sc.decide(None, t, pub, pub)[0] == "screener"
    assert sc.decide(t, t, pub, datetime(2026, 11, 23, 10, 0, tzinfo=IST))[0] == "daily"
    assert sc.decide(t, t, pub, datetime(2026, 11, 23, 23, 30, tzinfo=IST))[0] == "none"


def test_store_last_session_reads_the_index(tmp_path):
    idx = pd.date_range("2026-11-16", "2026-11-20", freq="B")
    cols = pd.MultiIndex.from_product([["A", "B"], ["Close", "Volume"]])
    p = tmp_path / "s.parquet"
    pd.DataFrame(np.ones((5, 4)), index=idx, columns=cols).to_parquet(p)
    assert sc.store_last_session(str(p)) == date(2026, 11, 20)
    assert sc.store_last_session(str(tmp_path / "missing.parquet")) is None
