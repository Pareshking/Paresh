"""Which sectors lead, and is leadership changing? (TODO S109)."""
import numpy as np
import pandas as pd

from src.engine import sector_indices as si


def _levels(drifts: dict[str, tuple[float, float]], days: int = 120):
    """Each sector's daily drift before and after the last 21 sessions."""
    dates = pd.bdate_range("2026-05-01", periods=days)
    rows = []
    for key, (early, late) in drifts.items():
        steps = np.r_[np.full(days - 21, early), np.full(21, late)]
        close = 100 * np.cumprod(1 + steps)
        rows += [{"date": d, "index": key, "close": c, "source": "test"} for d, c in zip(dates, close)]
    return pd.DataFrame(rows), pd.Series(100.0, index=dates)   # a flat Nifty 500


def _all(early=0.0, late=0.0):
    return {k: (early, late) for k, _ in si.SECTORS}


def test_sectors_are_ranked_by_three_months_and_grouped_by_the_last_month():
    d = _all()
    d["sector_bank"] = (0.002, 0.002)       # ahead on both
    d["sector_it"] = (-0.003, 0.004)        # behind over 3M, ahead over 1M: gaining
    d["sector_pharma"] = (0.004, -0.002)    # ahead over 3M, behind over 1M: fading
    d["sector_fmcg"] = (-0.002, -0.002)     # behind on both
    levels, n500 = _levels(d)
    res = si.sector_rotation(levels, n500)
    t = res.table
    assert t.index[0] in ("Bank", "Pharma") and t.index[-1] == "FMCG"
    assert t.at["Bank", "group"] == "ahead on both"
    assert t.at["IT", "group"] == "gaining" and t.at["Pharma", "group"] == "fading"
    assert t.at["FMCG", "group"] == "behind on both"
    # Against a flat Nifty 500 the relative figure is the index's own return.
    assert np.isclose(t.at["Bank", "1M vs 500"], t.at["Bank", "1M"])
    verdict, sentence = si.changing_sentence(res)
    assert "gaining: IT" in sentence and "fading: Pharma" in sentence


def test_too_few_sector_indices_leave_the_answer_out():
    keys = dict(list(_all().items())[: si.MIN_SECTORS - 1])
    levels, n500 = _levels(keys)
    assert si.sector_rotation(levels, n500) is None
    assert si.sector_rotation(None, n500) is None


def test_a_missing_sector_is_named_and_the_rest_answer():
    d = _all(0.001, 0.001)
    d.pop("sector_media")
    levels, n500 = _levels(d)
    res = si.sector_rotation(levels, n500)
    assert res.missing == ("Media",) and "Media" not in res.table.index


def test_the_leaders_sentence_names_the_top_and_bottom():
    d = _all()
    d["sector_media"] = (0.003, 0.003)
    d["sector_energy"] = (-0.003, -0.003)
    levels, n500 = _levels(d)
    verdict, sentence = si.leaders_sentence(si.sector_rotation(levels, n500))
    assert verdict.startswith("Media")
    assert "Media leads by +" in sentence and "Energy trails by −" in sentence
