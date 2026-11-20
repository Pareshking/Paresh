

def _live_months():
    # The live Sectors page, closes of 17 Nov 2026 (two of its rows).
    import pandas as pd

    cols = ["Nov 2025", "Dec 2025", "Jan 2026", "Feb 2026", "Mar 2026", "Apr 2026", "May 2026",
            "Jun 2026", "Jul 2026", "Aug 2026", "Sep 2026", "Oct 2026", "Nov MTD"]
    rows = {
        "Financial Services": [-0.9, -0.5, 0.4, -0.7, -2.5, 4.6, -0.2, 3.1, -1.9, -0.2, -0.7, -4.6, 2.6],
        "Healthcare": [-2.6, -2.2, -2.4, 4.2, 5.0, 0.9, 6.5, 3.6, -0.7, 0.6, 2.5, -3.2, -4.9],
    }
    out = pd.DataFrame.from_dict(rows, orient="index", columns=cols)
    out["run"] = [-4, -1]
    out["total"] = [-4.0, 12.2]          # the page's own (from unrounded months)
    return out


def test_the_run_example_reads_the_live_rows_back():
    """Owner, 18 Nov 2026: one live example on the page explains Run and 12 months."""
    from src.ui.views.market_questions_view import run_example

    text = run_example(_live_months())
    assert text.startswith("For example, Financial Services: Oct ")
    for month in ("Oct", "Sep", "Aug", "Jul"):
        assert month in text
    assert "Jun was +3.1, ahead, so the count stops there and Run reads 4 behind" in text
    assert "all behind all ranked stocks" in text   # S147: the market, equal-weighted
    assert "Its 12 months, \u22124.0, is the twelve completed months added up." in text
    assert "Nov" not in text.split("Its 12 months")[0].replace("Nov MTD", ""), "the month so far is not in the run"
    print(text)


def test_the_run_example_is_empty_without_a_run():
    from src.ui.views.market_questions_view import run_example

    m = _live_months()
    m["run"] = 0
    assert run_example(m) == ""
