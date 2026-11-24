

def _live_months():
    # The live Sectors page, closes of 17 Nov 2026 (two of its rows).
    import pandas as pd

    cols = ["Nov 2025", "Dec 2025", "Jan 2026", "Feb 2026", "Mar 2026", "Apr 2026", "May 2026",
            "Jun 2026", "Jul 2026", "Aug 2026", "Sep 2026", "Oct 2026", "Nov so far"]
    rows = {
        "Financial Services": [-0.9, -0.5, 0.4, -0.7, -2.5, 4.6, -0.2, 3.1, -1.9, -0.2, -0.7, -4.6, 2.6],
        "Healthcare": [-2.6, -2.2, -2.4, 4.2, 5.0, 0.9, 6.5, 3.6, -0.7, 0.6, 2.5, -3.2, -4.9],
    }
    out = pd.DataFrame.from_dict(rows, orient="index", columns=cols)
    out["run"] = [-4, -1]
    out["total"] = [-4.0, 12.2]          # the page's own (from unrounded months)
    return out




