"""Lists drawn with CSS grids are tables to a screen reader (audit F25).

Each list keeps its grid look but carries the ARIA table roles, and every row
offers as many cells as there are column headers, so a screen reader can say
"row 3, 50D EMA, 2.8% cushion" instead of reading a run of words.
"""
from html.parser import HTMLParser

import pandas as pd

from src.engine.exit_watch import Rules, assess
from src.ui.views import actions_view, sector_view
from src.ui.views import dashboard_view as dv

CELL_ROLES = {"cell", "rowheader", "columnheader"}
VOID = {"br", "img", "input", "hr", "meta", "link"}


class _Rows(HTMLParser):
    """Counts, per role=row, the cells a screen reader would announce."""

    def __init__(self):
        super().__init__()
        self.stack: list[dict] = []
        self.rows: list[list[str]] = []
        self.tables = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        hidden = a.get("aria-hidden") == "true" or any(f.get("hidden") for f in self.stack)
        role = a.get("role")
        frame = {"role": role, "hidden": hidden}
        if role == "table":
            self.tables += 1
        if role == "row" and not hidden:
            self.rows.append([])
        if role in CELL_ROLES and not hidden:
            assert self.stack and any(f["role"] == "row" for f in self.stack), "cell outside a row"
            self.rows[-1].extend([role] * int(a.get("aria-colspan", 1)))
        if tag not in VOID:
            self.stack.append(frame)

    def handle_endtag(self, tag):
        if tag not in VOID and self.stack:
            self.stack.pop()


def _check(out: str) -> list[list[str]]:
    p = _Rows()
    p.feed(out)
    assert p.tables >= 1
    assert p.rows, "no rows"
    head, *body = p.rows
    assert set(head) == {"columnheader"}
    assert body, "no data rows"
    for r in body:
        assert len(r) == len(head), (len(r), len(head))
        assert r.count("rowheader") == 1
        assert r[0] == "rowheader" or r[1] == "rowheader"
    return p.rows


def _assessed():
    rows = [{"Symbol": f"S{i}", "Rank": i, "Above 50 EMA": True, "Near 52W High": True,
             "% 50 EMA": 30.0, "% High": 0.0, "Industry": "X", "vs 50 EMA %": 30.0}
            for i in range(1, 41)]
    rows[2].update(**{"% 50 EMA": 2.0})
    return assess(pd.DataFrame(rows), ["S1", "S3", "NOTLISTED"], Rules())


def test_book_at_risk_is_a_table():
    _check(dv._at_risk_html(_assessed(), Rules()))


def test_exit_watch_is_a_table_including_an_unknown_holding():
    a = _assessed()
    rows = _check(actions_view.rows_html(a, {"S1": 0.05}, Rules()))
    assert len(rows) == 1 + len(a)


def test_industry_board_is_a_table():
    board, _ = sector_view.industry_board(pd.DataFrame({
        "Symbol": ["A", "B", "C", "D"],
        "Industry": ["Health", "Health", "Metals", "Metals"],
        "Rank": [1, 60, 3, 200],
        "3M Return": [0.30, -0.10, 0.05, -0.20],
        "6M Return": [0.50, 0.00, 0.10, -0.30],
        "Above 50 EMA": [True, False, True, False],
        "Near 52W High": [True, False, False, False],
    }))
    _check(sector_view.board_html(board))
