"""The NSE history audit (scripts/nse_history_audit.py) on a small made-up history."""
from datetime import date

import numpy as np
import pandas as pd

from scripts import nse_history_audit as audit

DAYS = [d.date() for d in pd.bdate_range("2010-01-04", "2010-01-29")]


def _prices(days, symbols=("AAA", "BBB")):
    rows = []
    for s in symbols:
        last = 100.0
        for d in days:
            close = last * 1.01
            if s == "AAA" and d == date(2010, 1, 18):
                close = last * 0.2            # a 1:5 split, filed below
            if s == "BBB" and d == date(2010, 1, 25):
                close = last * 2.5            # nothing explains this
            rows.append({"date": pd.Timestamp(d), "mkt": "N", "series": "EQ", "symbol": s,
                         "close": close, "prev_close": last, "high": close, "low": close,
                         "volume": 1.0, "value": close})
            last = close
    return pd.DataFrame(rows)


SPLIT = pd.DataFrame([{"symbol": "AAA", "ex_date": pd.Timestamp("2010-01-18"), "kind": "split",
                       "price_factor": 0.2, "purpose": "FACE VALUE SPLIT FROM RS 10 TO RS 2"}])


def test_missing_weekdays_skip_held_and_known_closed_days():
    held = set(DAYS) - {date(2010, 1, 14), date(2010, 1, 26)}
    assert audit.missing_weekdays(held, {date(2010, 1, 26)}, DAYS[0], DAYS[-1]) == [date(2010, 1, 14)]


def test_the_audit_confirms_the_split_and_lists_the_unexplained_jump():
    r = audit.audit(_prices(DAYS), SPLIT, set(DAYS), set(), DAYS[0], DAYS[-1])
    assert r["verdicts"].set_index("symbol").loc["AAA", "verdict"] == "applied"
    assert list(r["jumps"]["symbol"]) == ["BBB"]
    assert r["missing"] == [] and r["per_year"].loc[2010] == len(DAYS)


def test_a_session_missing_from_the_files_shows_in_the_previous_closes(tmp_path):
    """Drop a day's file: NSE's next previous close no longer matches what we hold."""
    days = [d for d in DAYS if d != date(2010, 1, 13)]
    prices = _prices(DAYS)
    prices = prices[prices["date"] != pd.Timestamp("2010-01-13")]
    r = audit.audit(prices, SPLIT, set(days), set(), DAYS[0], DAYS[-1])
    assert pd.Timestamp("2010-01-14") in set(pd.to_datetime(r["gap_days"].index))
    assert r["missing"] == [date(2010, 1, 13)]
    text = audit.write(r, tmp_path, DAYS[0], DAYS[-1])
    assert "Weekdays neither held nor a known closed day: 1" in text
    for name in ("report.md", "summary.json", "actions.csv", "jumps.csv", "missing_weekdays.csv"):
        assert (tmp_path / name).exists()
    assert np.isfinite(r["gap_days"]).all()
