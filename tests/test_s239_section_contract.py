"""S239: restored sections are built to PAGE_DESIGN §2b (owner, 28 Nov 2026: "we have those sections ready as per
benchmark"): one function, a heading that answers, history as a line with its usual range and a stated range,
the detail folded, no source line."""
import numpy as np
import pandas as pd

from src.engine import momentum_health as mh
from src.ui.views import dashboard_home_view as v


def _spreads(n=60):
    rng = np.random.default_rng(1)
    m = pd.period_range("2010-01", periods=n, freq="M").astype(str)
    return pd.DataFrame({"month": m, "top": rng.normal(1.5, 3, n), "bottom": rng.normal(-.5, 3, n),
                         "nifty500": rng.normal(1, 3, n), "top50": rng.normal(2, 3, n), "d2": rng.normal(1, 3, n)})


def test_split_carries_its_record():
    s = mh.top_fifth_split(_spreads())
    r = s["rows"][0]
    assert len(r["series"]) == 60 - 11 and r["series"].iloc[-1] == r["now"]
    assert r["series"].index[0] == pd.Timestamp("2010-12-31")


def test_split_section_meets_the_contract():
    parts = v.split_parts(mh.top_fifth_split(_spreads()))
    charts = [p for p in parts if isinstance(p, v.Chart)]
    assert len(charts) == 1 and charts[0].kind == "lines"
    spec = charts[0].spec
    assert spec["range"] == v.SPLIT_RANGE and spec["bands"] and len(spec["marks"]) == 2
    assert [x["name"] for x in spec["series"]] == ["Top 50", "Ranks 51–100"]
    html = v.html_of(parts)
    assert "Show the table" in html and "What it is" in html and "Source" not in html
    assert ("lead ranks 51–100 by" in html) or ("lead the top 50 by" in html) or ("are level" in html)


def test_split_head_colours_the_figure_only():
    h = v.split_head([{"label": "Top 50", "now": 15.7}, {"label": "Ranks 51–100", "now": 8.8}])
    assert h == 'The top 50 lead ranks 51–100 by <span class="dh-up">6.9 points</span>'
    h = v.split_head([{"label": "Top 50", "now": 2.0}, {"label": "Ranks 51–100", "now": 5.0}])
    assert h.startswith("Ranks 51–100 lead the top 50 by")


def test_no_data_no_section():
    assert v.split_parts(None) == [] and mh.top_fifth_split(None) is None
