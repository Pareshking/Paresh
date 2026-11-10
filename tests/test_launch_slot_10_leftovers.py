"""The content items left open by launch slot 10 (TODO S117, 10 Nov 2026).

(a) -- a bucket's label must be the session that closed it -- is in
tests/test_market_questions.py, beside the rest of the Breadth rules.
"""
from pathlib import Path

import pandas as pd

from src.engine.backtester import EMA_MIN_PRINTS, EMA_WARMUP_FROM, MEMBERS_ONLY_SCORING_FROM
from src.engine.track_record import TRACK_RECORD_CONFIG

DOC = Path(__file__).resolve().parents[1] / "docs" / "TRACK_RECORD.md"


def _guide() -> str:
    from src.ui.views.guide_view import _body
    return _body()


def test_the_guide_states_the_ema_warm_up_with_the_figures_from_config():
    """A stock with fewer than EMA_MIN_PRINTS closes has no EMA at all, so it
    cannot pass the trend filter and cannot be bought. The Guide never said
    so."""
    body = _guide()
    assert f"{EMA_MIN_PRINTS} closes" in body
    assert f"fewer than {EMA_MIN_PRINTS} daily closes" in body
    assert pd.Timestamp(EMA_WARMUP_FROM).strftime("%-d %b %Y") in body
    assert "cannot pass the trend filter" in body


def test_the_guide_says_the_52_week_high_is_read_from_closes():
    body = _guide()
    assert "highest <i>close</i> of the last year" in body
    assert "not the highest\nprice touched during a day" in body.replace("\r", "")
    # The basis, not a count: the Guide once quoted a hardcoded "2.9% above its
    # 200D EMA" against the 3.4% on the same render, so no figure that depends
    # on the basis is typed here.
    assert "22 names" not in body and "50 names" not in body


def test_the_guide_names_the_members_only_scoring_rule():
    body = _guide()
    assert pd.Timestamp(MEMBERS_ONLY_SCORING_FROM).strftime("%-d %b %Y") in body
    assert "index members of that day only" in body
    assert MEMBERS_ONLY_SCORING_FROM == TRACK_RECORD_CONFIG["members_only_scoring_from"]


def test_track_record_md_carries_both_rules_before_the_guide_quotes_them():
    """The Guide's statements have to have a home in the record's own contract:
    neither rule was written down anywhere when slot 10 found them missing."""
    doc = DOC.read_text(encoding="utf-8")
    assert "ema_warmup_from" in doc and str(EMA_MIN_PRINTS) in doc
    assert "members_only_scoring_from" in doc
    assert "high_basis" in doc
    assert "highest close" in doc
    # The 22-against-50 measurement, attributed to where it was taken.
    flat = " ".join(doc.split())
    assert "50 names on closes against 22 on intraday highs" in flat
    assert "src/ui/components.py:566-570" in flat


def test_watchlist_renders_the_footer_even_with_an_empty_list(monkeypatch):
    """Watchlist was the only page of eleven with no data-quality footer: the
    empty list returned before it, so a fresh browser saw the empty state and
    nothing else."""
    from src.ui.views import watchlist_view

    calls: list[dict] = []
    monkeypatch.setattr(watchlist_view, "render_data_quality_footer",
                        lambda **kw: calls.append(kw))
    monkeypatch.setattr(watchlist_view.watchlist_store, "symbols", lambda: [])
    rank_df = pd.DataFrame({"Symbol": ["TCS"], "Rank": [1], "Short History": ["No"]})

    watchlist_view.render_watchlist_view(rank_df)

    assert calls == [{"total_stocks": 1, "gap_count": 0, "short_count": 0}]
