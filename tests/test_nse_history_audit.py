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


def test_read_actions_keeps_the_lists_date_over_a_swapped_bc_row(monkeypatch):
    # HCG's 1:17 rights: the yearly list says 2 Mar 2026; a Bc row of 25 Feb
    # stored it as 3 Feb, inside the listing window, so the swap repair keeps it.
    rows = {
        "bc": pd.DataFrame({"date": pd.to_datetime(["2026-02-25", "2026-02-25"]), "symbol": ["HCG", "HCG"],
                            "ex_date": pd.to_datetime(["2026-02-03", "2026-03-02"]),
                            "purpose": ["RIGHTS 1:17 @ PREMIUM RS 502/-", "RIGHTS 1:17 @ PREMIUM RS 502/-"]}),
        "list": pd.DataFrame({"date": pd.to_datetime(["2026-03-02"]), "symbol": ["HCG"],
                              "ex_date": pd.to_datetime(["2026-03-02"]),
                              "purpose": ["RIGHTS 1:17 @ PREMIUM RS 502/-"]}),
    }

    class Reader:
        def resolve_current(self, dataset, as_of):
            return dataset

        def read_parquet(self, key):
            return rows["list" if key == audit.nh.R2_ACTIONS_HISTORY else "bc"].copy()

    monkeypatch.setattr(audit.nh, "r2_days", lambda archive, dataset: {date(2026, 2, 25)})
    got = audit.read_actions(Reader(), None, date(2026, 1, 1), date(2026, 3, 31))
    assert list(got["ex_date"]) == [pd.Timestamp("2026-03-02")]
    assert list(got["source"]) == ["list"]
