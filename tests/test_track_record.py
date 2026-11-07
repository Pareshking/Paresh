

def test_a_forward_dated_rule_keeps_earlier_months_fingerprint():
    """Owner, 7 Nov 2026: the model scores members only from the 30 Nov signal;
    months governed by earlier signals keep their fingerprint, December changes."""
    from src.engine.track_record import TRACK_RECORD_CONFIG, config_fingerprint_for_month
    cfg = TRACK_RECORD_CONFIG
    assert cfg["members_only_scoring_from"] == "2026-11-30"
    assert config_fingerprint_for_month(cfg, "2026-10") == config_fingerprint_for_month(cfg, "2026-11")
    assert config_fingerprint_for_month(cfg, "2026-11") != config_fingerprint_for_month(cfg, "2026-12")
    assert config_fingerprint_for_month(cfg, "2026-11") == "4cc739e503d7"


def test_members_only_scoring_applies_from_its_date_only():
    import numpy as np
    import pandas as pd
    from src.engine.backtester import _signal_scores
    from src.engine.calendar_momentum import anchor_frame

    idx = pd.bdate_range("2025-06-01", "2026-12-15")
    rng = np.random.default_rng(3)
    cols = [f"M{i}" for i in range(10)] + ["GONE"]
    px = pd.DataFrame(100 * np.exp(np.cumsum(rng.normal(0.001, 0.02, (len(idx), len(cols))), axis=0)),
                      index=idx, columns=cols)
    px["GONE"] = 100 * np.exp(np.linspace(0, 3, len(idx)))
    lr = np.log(px / px.shift(1))
    members = pd.Series([True] * 10 + [False], index=cols)
    w = [0.1, 0.3, 0.3, 0.2, 0.1]
    kw = dict(anchor=anchor_frame(px), metric="sharpe", members=members, members_from="2026-11-30")
    before = idx.get_loc(pd.Timestamp("2026-10-30"))
    after = idx.get_loc(pd.Timestamp("2026-11-30"))
    full_b = _signal_scores(px, lr, before, (1, 3, 6, 9, 12), w, on=idx[before], **{**kw, "members_from": None})
    assert np.allclose(_signal_scores(px, lr, before, (1, 3, 6, 9, 12), w, on=idx[before], **kw), full_b,
                       equal_nan=True)
    only_a = _signal_scores(px, lr, after, (1, 3, 6, 9, 12), w, on=idx[after], **kw)
    alone = _signal_scores(px[cols[:-1]], lr[cols[:-1]], after, (1, 3, 6, 9, 12), w, on=idx[after],
                           anchor=anchor_frame(px[cols[:-1]]), metric="sharpe", members=None, members_from=None)
    assert np.allclose(only_a.reindex(alone.index), alone) and pd.isna(only_a["GONE"])
