"""The book's industry and size at each rebalance, kept (owner, 20 Nov 2026)."""
from __future__ import annotations

import pandas as pd

from src.engine import book_exposure as bx


def _tradebook():
    rows = []
    for period, lines in {"01 Jan 2026 → 01 Feb 2026": [("A", "🟢 BUY (Entry)"), ("B", "🟢 BUY (Entry)")],
                          "01 Feb 2026 → 02 Mar 2026": [("A", "⚪ HOLD (Retained)"), ("C", "🟢 BUY (Entry)"),
                                                        ("B", "🔴 SELL (Exit)")]}.items():
        for s, a in lines:
            rows.append({"Period": period, "Action": a, "Symbol": s, "Weight %": 0.0 if "SELL" in a else 50.0})
    return pd.DataFrame(rows)


def _membership():
    # B is a Nifty 50 name until 15 Jan, then leaves; C is small.
    return {"indices": {
        "nifty_50": {"baseline": {"date": "2025-12-01", "symbols": ["B"]}, "changes": [{"date": "2026-01-15", "added": [], "removed": ["B"]}]},
        "nifty_smallcap_250": {"baseline": {"date": "2025-12-01", "symbols": ["A", "C"]}, "changes": []}}}


def test_each_rebalance_sums_to_the_book_and_sizes_use_that_dates_lists():
    f = bx.exposure(_tradebook(), {"A": "Healthcare", "B": "Banks", "C": "Healthcare"}, _membership())
    for (d, kind), g in f.groupby(["date", "kind"]):
        assert g["weight"].sum() == 100.0, (d, kind)
    size = f[f.kind == "size"].pivot(index="date", columns="name", values="weight")
    assert size.loc["2026-01-01", "Large"] == 50.0          # B was in the Nifty 50 on 1 Jan
    assert size.loc["2026-02-01", "Small"] == 100.0         # sold B; A and C are small
    ind = f[f.kind == "industry"].set_index(["date", "name"])["weight"]
    assert ind.loc[(pd.Timestamp("2026-02-01"), "Healthcare")] == 100.0


def test_a_kept_rebalance_is_never_rewritten():
    first = bx.exposure(_tradebook(), {"A": "Healthcare", "B": "Banks", "C": "Healthcare"}, _membership())
    # Later the labels change; the kept dates stay as they were.
    relabelled = bx.exposure(_tradebook(), {"A": "Pharma", "B": "Banks", "C": "Pharma"}, _membership())
    out = bx.merge(first, relabelled)
    assert set(out[out.kind == "industry"]["name"]) == {"Healthcare", "Banks"}
    more = relabelled.assign(date=pd.Timestamp("2026-03-02"))
    out2 = bx.merge(out, more)
    assert out2["date"].nunique() == 3 and "Pharma" in set(out2["name"])


def test_the_committed_file_starts_with_the_first_book():
    f = bx.load()
    assert f["date"].min() == pd.Timestamp("2026-01-01")
    assert set(f["kind"]) == {"industry", "size"}
