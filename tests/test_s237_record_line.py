"""S237 G3 (owner approved 28 Nov 2026): one measure against its own record, on Indices and Market."""
import re

import numpy as np
import pandas as pd

from src.engine import market_questions as mq
from src.ui import record_line as rl
from src.ui import formats as _fmt
from src.ui.views import market_questions_view as mqv

f1 = lambda v: _fmt.fixed(v, 1)  # noqa: E731


def _series():
    idx = pd.bdate_range("2021-04-01", "2026-11-27")
    v = pd.Series(20 + 3 * np.sin(np.arange(len(idx)) / 90), index=idx)
    v.iloc[100] = 35.0
    v.iloc[400] = 12.0
    return v


def test_facts_find_the_extremes_and_the_middle_half():
    x = rl.facts(_series())
    assert x["hi"] == 35.0 and x["hi_d"] == _series().index[100]
    assert x["lo"] == 12.0 and x["lo_d"] == _series().index[400]
    assert x["q25"] < x["now"] or x["now"] <= x["q25"]
    assert x["ago"] is not None


def test_too_short_a_record_reads_none():
    assert rl.facts(_series().iloc[:100]) is None


def test_the_words_say_where_today_sits():
    x = rl.facts(_series())
    t = rl.words(x, f1, "Apr 2021")
    assert t.startswith(("Inside", "Below", "Above")) and "the middle half of days since Apr 2021" in t
    assert "The highest was 35.0, in" in t and "the lowest 12.0, in" in t
    assert re.search(r"(Down from|Up from) \d+\.\d a year ago\.|Level with a year ago\.", t)


def test_the_chart_labels_the_two_extremes_and_names_the_band():
    x = rl.facts(_series())
    spec = rl.chart_spec(x, "P/E", f1)
    assert [m["v"] for m in spec["marks"]] == [35.0, 12.0]
    assert spec["bands"][0]["label"].startswith("usual range, ")
    assert all(m["date"] in spec["dates"] for m in spec["marks"])


def _breadth(now, pct, vote):
    m = mq.Measure("Stocks above their 200D EMA", "pct", now, None, None, vote, "", primary=True,
                   history=(10, 40, 70, 90, pct, pd.Timestamp("2021-10-29")))
    return mq.Answer("Are most stocks taking part?", "About usual", "", 0.0, None, None, [m])


def test_the_market_lede_colours_the_share_only_and_by_its_vote():
    t = mqv.head_lede(_breadth(45, 29, "MID"), None, "750")
    assert t == ("<b>45%</b> of the 750 closed above their 200D EMA, a reading lower than on 71% of days since "
                 "Oct 2021: participation is about usual.")
    assert 'class="dh-up"' in mqv.head_lede(_breadth(65, 80, "UP"), None, "750")
    assert "higher than on 80%" in mqv.head_lede(_breadth(65, 80, "UP"), None, "750")
