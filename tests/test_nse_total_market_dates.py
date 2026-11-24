"""data/nse_total_market.csv and its collector (S181, 21 Nov 2026): NSE printed the files for 6, 10 and 11 Apr 2023
month-first, and reading them day-first filed three closes under 4 Jun, 4 Oct and 4 Nov 2023."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("collect_ntm", ROOT / "scripts" / "collect_nse_total_market.py")
collect = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collect)

HEAD = ("Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,Closing Index Value,"
        "Points Change,Change(%),Volume,Turnover (Rs. Cr.),P/E,P/B,Div Yield\n")


def _file(date_text: str) -> bytes:
    return (HEAD + f"Nifty Total Market,{date_text},1,1,1,8237.65,1,1,1,1,21.6,3.77,1.41\n").encode()


def test_a_month_first_file_is_read_as_the_session_it_was_asked_for():
    # NSE's own file for 10 Apr 2023 prints 04-10-2023.
    assert collect.parse(_file("04-10-2023"), pd.Timestamp("2023-04-10")) == (pd.Timestamp("2023-04-10"), 8237.65)
    assert collect.parse(_file("10-04-2023"), pd.Timestamp("2023-04-10"))[0] == pd.Timestamp("2023-04-10")


def test_a_file_dated_another_day_is_refused():
    assert collect.parse(_file("07-04-2023"), pd.Timestamp("2023-04-10")) is None


def test_the_committed_file_has_one_close_per_session():
    f = pd.read_csv(ROOT / "data" / "nse_total_market.csv", parse_dates=["date"])
    assert f["date"].is_unique and f["date"].is_monotonic_increasing
    # A weekend row only where NSE's own index history holds a special session that day (S163, 24 Nov 2026:
    # Muhurat, budget-day Saturdays). The misread dates S181 found (4 Jun, 4 Nov 2023) are not sessions there.
    hist = pd.read_parquet(ROOT / "data" / "nse_indices_history.parquet", columns=["date"])
    special = set(pd.to_datetime(hist["date"]).dt.normalize())
    weekend = f.loc[f["date"].dt.day_of_week.ge(5), "date"]
    assert set(weekend) <= special, sorted(set(weekend) - special)
    assert pd.Timestamp("2023-06-04") not in set(f["date"]) and pd.Timestamp("2023-11-04") not in set(f["date"])
    on = f.set_index("date")["close"]
    assert on[pd.Timestamp("2023-10-04")] == pytest.approx(9608.10)
    assert on[pd.Timestamp("2023-04-10")] == pytest.approx(8237.65)


def test_weekend_special_sessions_are_asked_for(tmp_path):
    """NSE's special weekend sessions (Muhurat 8 Nov 2026, budget Saturday 1 Feb 2025) are fetched (S163)."""
    import importlib.util
    from datetime import date
    from pathlib import Path

    import pandas as pd
    spec = importlib.util.spec_from_file_location(
        "cntm", Path(__file__).resolve().parents[1] / "scripts" / "collect_nse_total_market.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    hist = tmp_path / "h.parquet"
    pd.DataFrame({"date": pd.to_datetime(["2025-01-31", "2025-02-01", "2026-11-08", "2019-01-05"]),
                  "key": "nifty_50", "close": 1.0}).to_parquet(hist)
    days = m.sessions_to_try(date(2021, 10, 1), date(2026, 11, 24), hist)
    assert pd.Timestamp("2025-02-01") in days and pd.Timestamp("2026-11-08") in days
    assert pd.Timestamp("2025-02-02") not in days            # an ordinary Sunday is not asked for
    assert pd.Timestamp("2019-01-05") not in days            # outside the range
    assert pd.Timestamp("2026-11-23") in days                # weekdays as before
