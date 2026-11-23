"""S193 A3 (23 Nov 2026): on a book begun 1 Oct, "3 months", "6 months" and "This year" showed
since-start figures under their own labels. Rows whose window starts before the record are dropped
and the since-start row is kept."""
import numpy as np
import pandas as pd

from src.engine import portfolio_report as pr


def _series(start, end, drift):
    idx = pd.bdate_range(start, end)
    return pd.Series(np.cumprod(np.full(len(idx), 1 + drift)), index=idx)


def test_a_young_book_drops_windows_older_than_its_record():
    book = _series("2026-09-30", "2026-11-20", -0.001)
    market = _series("2025-01-01", "2026-11-20", 0.0005)
    labels = [r[0] for r in pr.periods(book, market, market, pd.Timestamp("2026-11-20"))]
    assert "3 months" not in labels and "6 months" not in labels
    assert not any(lab.startswith("This year") for lab in labels)
    assert "1 month" in labels and labels[-1] == "Since start"


def test_the_index_column_of_each_kept_row_is_its_own_window():
    book = _series("2026-09-30", "2026-11-20", -0.001)
    market = _series("2025-01-01", "2026-11-20", 0.0005)
    rows = {r[0]: r for r in pr.periods(book, market, market, pd.Timestamp("2026-11-20"))}
    one_month, since = rows["1 month"][2], rows["Since start"][2]
    assert one_month < since  # a month of the index, not the whole record


def test_a_book_older_than_a_year_keeps_every_row():
    book = _series("2025-06-30", "2026-11-20", 0.0005)
    labels = [r[0] for r in pr.periods(book, book, book, pd.Timestamp("2026-11-20"))]
    for want in ("3 months", "6 months", "1 year", "Since start"):
        assert want in labels
    assert any(lab.startswith("This year") for lab in labels)
