"""One 52-week high everywhere: the calendar year, opening on the last session on or before the date a
year back (owner, 24 Nov 2026: "Use calendar date everywhere"). Frozen record months keep the 252-row
high they were struck under (TRACK_RECORD_CONFIG["high_rule_from"])."""
import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.engine.backtester import _rolling_high_at
from src.engine.calendar_momentum import year_window_start, year_window_starts
from src.engine.track_record import TRACK_RECORD_CONFIG, config_for_month

ROOT = Path(__file__).resolve().parents[1]


def _frame():
    idx = pd.bdate_range("2024-01-01", "2026-11-20")
    rng = np.random.default_rng(1)
    return pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0, 0.01, (len(idx), 3)), axis=0)),
                        index=idx, columns=["A", "B", "C"])


def test_the_window_opens_on_or_before_a_year_back():
    idx = pd.DatetimeIndex(["2025-11-19", "2025-11-21", "2026-11-20"])   # 20 Nov 2025 missing
    assert idx[year_window_start(idx, 2)] == pd.Timestamp("2025-11-19")
    assert list(year_window_starts(idx)) == [0, 0, 0]


def test_the_vector_and_single_forms_agree():
    px = _frame()
    starts = year_window_starts(px.index)
    for i in (0, 10, 300, len(px) - 1):
        assert starts[i] == year_window_start(px.index, i)


def test_a_high_inside_the_year_but_outside_252_rows_counts():
    px = _frame()
    end = len(px) - 1
    first = year_window_start(px.index, end)
    assert end - first + 1 > 252                       # a business-day year holds ~262 rows
    px.iloc[first + 2, 0] = 10_000.0
    assert _rolling_high_at(px, end)["A"] == 10_000.0
    assert _rolling_high_at(px, end, legacy=True)["A"] < 10_000.0


def test_frozen_months_do_not_carry_the_rule():
    go = TRACK_RECORD_CONFIG["high_rule_from"]
    assert "high_rule_from" not in config_for_month(TRACK_RECORD_CONFIG, "2026-10")
    nxt = (pd.Timestamp(go) + pd.offsets.MonthBegin(1)).strftime("%Y-%m")
    assert config_for_month(TRACK_RECORD_CONFIG, nxt)["high_rule_from"] == go


def test_no_engine_or_page_reads_a_52_week_high_over_252_rows():
    offenders = []
    for path in list((ROOT / "src").rglob("*.py")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if re.search(r"rolling\(\s*252", code):
                offenders.append(f"{path.relative_to(ROOT)}:{n}")
    assert offenders == []


def test_breadth_new_highs_read_the_calendar_year():
    from src.engine.breadth import _rolling_extremes
    px = _frame()
    end = len(px) - 1
    first = year_window_start(px.index, end)
    px.iloc[first + 2, 1] = 10_000.0
    hi, _ = _rolling_extremes(px, 252, 151, tail=1)
    assert hi.iloc[-1]["B"] == 10_000.0
