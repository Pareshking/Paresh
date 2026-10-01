"""Actions preview dates follow the canonical model-book mark when available."""
import pandas as pd

from src.ui.views.actions_view import rebalance_dates_for_view


def test_model_book_preview_moves_past_a_fill_already_reflected_in_the_book():
    rank_as_of = pd.Timestamp("2026-09-30")
    book_as_of = pd.Timestamp("2026-10-01")

    basis, check, fill = rebalance_dates_for_view(rank_as_of, book_as_of, model_book=True)

    assert basis == book_as_of
    assert check == pd.Timestamp("2026-10-30")
    assert fill == pd.Timestamp("2026-11-02")


def test_custom_holdings_preview_uses_the_ranking_data_date():
    rank_as_of = pd.Timestamp("2026-09-30")
    book_as_of = pd.Timestamp("2026-10-01")

    basis, check, fill = rebalance_dates_for_view(rank_as_of, book_as_of, model_book=False)

    assert basis == rank_as_of
    assert check == pd.Timestamp("2026-09-30")
    assert fill == pd.Timestamp("2026-10-01")
