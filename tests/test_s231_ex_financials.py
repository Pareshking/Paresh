"""S231 (owner, 25 Nov 2026; decided by benchmark, owner to confirm): Indices earnings with and without financials."""
from __future__ import annotations

import pandas as pd

from src.engine import earnings_review as er
from src.ui.views import indices_view as iv
from src.ui.views.dashboard_home_view import html_of


def test_the_stored_file_holds_both_scopes_with_identical_all_rows():
    df = pd.read_csv(er.OURS_PATH)
    assert set(df["scope"]) == {"all", "ex_financials"}
    a, x = df[df["scope"] == "all"], df[df["scope"] == "ex_financials"]
    assert len(a) == len(x)
    k = ["quarter", "index", "measure"]
    both = a.merge(x, on=k, suffixes=("_a", "_x"))
    assert len(both) == len(a)
    assert (both["members_x"] < both["members_a"]).all()          # every index holds some financials
    # a past member the classification file does not name stays in (1 of the 750's members in six quarters)
    assert (df["unclassified"] <= 0.01 * df["size"]).all()


def test_readers_take_a_scope_and_a_file_without_one_reads_as_all():
    old = pd.read_csv(er.OURS_PATH)
    old = old[old["scope"] == "all"].drop(columns=["scope", "unclassified"])
    assert er.ours(old).values == er.ours(scope="all").values
    assert er.ours(old, scope="ex_financials") is None
    assert er.ours(scope="ex_financials").values["Nifty 500"] != er.ours().values["Nifty 500"]


def test_the_page_says_which_companies_it_counts():
    lt = er.ours(scope="ex_financials")
    doc = html_of(iv.section_earnings(lt, None, "ex_financials"))
    assert "profit without financials" in doc and "Profit, all but financials" in doc
    assert "macro sector Financial Services (banks, NBFCs" in doc
    plain = html_of(iv.section_earnings(er.ours(), None))
    assert "without financials" not in plain.lower() and "Profit, all companies" in plain
