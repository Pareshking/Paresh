"""Exit dates mix dates and words; parsing must not warn or change (production log, 7 Nov)."""
import warnings

import pandas as pd


def test_mixed_exit_dates_parse_without_a_warning_and_as_before():
    s = pd.Series(["—", "06 Nov 2026", "Not exited (mark 06 Nov 2026)", "02 Mar 2026"])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = pd.to_datetime(s, format="mixed", errors="coerce")
    assert out.isna().tolist() == [True, False, True, False]
    assert out[1] == pd.Timestamp("2026-11-06") and out[3] == pd.Timestamp("2026-03-02")
