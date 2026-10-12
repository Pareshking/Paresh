"""S56: rights issues reach the committed NSE actions, with the face value that prices them.

The committed data/nse_prices/actions.parquet predated keeping rights rows and had
no face_value column, so the NSE middle source moved raw across 14 rights ex-dates
since Sep 2024 (reports/followups_s52_s53_2026-10-07.md: HCC -23% on 5 Dec 2025).
"""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd

import src.engine.pipeline  # noqa: F401  (import order, as the script does)
from src.loaders import nse_adjusted as na
from src.loaders import nse_bundle as nb
from src.loaders import nse_prices as npx

sync = importlib.import_module("scripts.sync_nse_prices")


def _acts(rows: list[dict]) -> pd.DataFrame:
    a = pd.DataFrame(rows)
    a["ex_date"] = pd.to_datetime(a["ex_date"])
    parsed = pd.DataFrame([nb.classify_purpose(p) for p in a["purpose"]], index=a.index)
    a[["kind", "price_factor"]] = parsed[["kind", "price_factor"]]
    return a


def test_face_value_is_an_action_column_and_old_files_read_it_as_missing(tmp_path):
    assert "face_value" in npx.ACTION_COLS
    pd.DataFrame({"A": [1.0, 2.0]}, index=pd.to_datetime(["2025-01-01", "2025-01-02"])).to_parquet(
        tmp_path / "closes.parquet")
    old = pd.DataFrame({c: ["x"] for c in npx.ACTION_COLS if c != "face_value"})
    old.to_parquet(tmp_path / "actions.parquet")
    (tmp_path / "notes.json").write_text("{}")
    loaded = npx.load(tmp_path)["actions"]
    assert list(loaded.columns[:len(npx.ACTION_COLS)]) == npx.ACTION_COLS
    assert loaded["face_value"].isna().all()


def test_a_daily_rights_row_takes_the_face_value_of_the_yearly_list():
    acts = _acts([
        {"symbol": "HCC", "series": "EQ", "ex_date": "2025-12-05", "purpose": "Rights 21:79 @ Premium Rs 11.5/-"},
        {"symbol": "HCC", "series": "EQ", "ex_date": "2023-09-20", "purpose": "Dividend - Re 0.10 Per Share",
         "face_value": 1.0},
    ])
    kept = sync.keep_actions(acts, {"HCC"}, today_fv={})
    assert list(kept["kind"]) == ["rights"]                # the dividend row is not kept
    assert kept["face_value"].iloc[0] == 1.0


def test_today_s_face_value_is_used_only_when_no_split_since():
    rights = {"symbol": "ABC", "series": "EQ", "ex_date": "2025-03-03", "purpose": "Rights 1:4 @ Premium Rs 90/-"}
    kept = sync.keep_actions(_acts([rights]), {"ABC"}, today_fv={"ABC": 10.0})
    assert kept["face_value"].iloc[0] == 10.0
    split = {"symbol": "ABC", "series": "EQ", "ex_date": "2025-08-01",
             "purpose": "Face Value Split (Sub-Division) - From Rs 10/- Per Share To Re 1/- Per Share"}
    kept = sync.keep_actions(_acts([rights, split]), {"ABC"}, today_fv={"ABC": 1.0})
    assert np.isnan(kept.loc[kept["kind"] == "rights", "face_value"].iloc[0])  # Rs 1 today was Rs 10 then


def test_a_refresh_never_drops_an_action_on_file():
    old = pd.DataFrame([{"symbol": "A", "series": "EQ", "kind": "bonus", "ex_date": pd.Timestamp("2025-01-02"),
                         "purpose": "Bonus 1:1", "price_factor": 0.5, "face_value": np.nan}])
    new = pd.DataFrame([{"symbol": "B", "series": "EQ", "kind": "rights", "ex_date": pd.Timestamp("2025-02-03"),
                         "purpose": "Rights 1:5 @ Premium Rs 10/-", "price_factor": np.nan, "face_value": 1.0}])
    out = sync.refreshed(old, new)
    assert set(out["symbol"]) == {"A", "B"} and len(out) == 2
    assert len(sync.refreshed(old, pd.concat([new, old]))) == 2


def test_the_refresh_reads_the_committed_span_and_keeps_the_rights(monkeypatch):
    audit = importlib.import_module("scripts.nse_history_audit")
    seen = {}

    def fake_read_actions(reader, archive, since, until):
        seen["window"] = (since, until)
        return _acts([
            {"symbol": "HCC", "series": "EQ", "ex_date": "2025-12-05", "purpose": "Rights 21:79 @ Premium Rs 11.5/-",
             "face_value": 1.0},
            {"symbol": "HCC", "series": "EQ", "ex_date": "2019-01-01", "purpose": "Rights 1:1 @ Premium Rs 1/-",
             "face_value": 2.0},                           # before the span: not kept
        ])

    monkeypatch.setattr(audit, "read_actions", fake_read_actions)
    closes = pd.DataFrame({"HCC": [40.0, 33.7]}, index=pd.to_datetime(["2024-09-30", "2026-10-09"]))
    out = sync.refresh_actions(closes, pd.DataFrame(columns=npx.ACTION_COLS), {}, reader=object(), archive=object())
    assert seen["window"] == (pd.Timestamp("2024-09-30").date(), pd.Timestamp("2026-10-09").date())
    assert list(out["ex_date"]) == [pd.Timestamp("2025-12-05")] and out["face_value"].iloc[0] == 1.0


def test_a_kept_rights_row_is_applied_at_its_ex_date():
    # HCC 21:79 at Rs 12.5 (face 1 + premium 11.5) against a Rs 40.0 close: the theoretical
    # ex-rights price over the close, (79 x 40 + 21 x 12.5) / (100 x 40) = 0.8556.
    days = pd.bdate_range("2025-12-01", "2025-12-10")
    close = pd.DataFrame({"HCC": [40.0] * 4 + [34.2] * (len(days) - 4)}, index=days)
    kept = sync.keep_actions(_acts([{"symbol": "HCC", "series": "EQ", "ex_date": "2025-12-05",
                                     "purpose": "Rights 21:79 @ Premium Rs 11.5/-"}]), {"HCC"},
                             today_fv={"HCC": 1.0})
    factors, verdicts = na.action_factors(close, kept)
    assert verdicts["verdict"].tolist() == ["rights"]
    assert abs(factors.loc["2025-12-05", "HCC"] - na.rights_factor(40.0, 12.5, 21, 79)) < 1e-9
    assert abs(na.rights_factor(40.0, 12.5, 21, 79) - 0.855625) < 1e-9


def test_update_re_reads_the_actions_and_the_mode_exists(monkeypatch):
    calls = []
    monkeypatch.setattr(sync, "refresh", lambda *a, **k: calls.append("refresh") or 0)
    monkeypatch.setattr(sync.sys, "argv", ["sync", "--refresh-actions"])
    assert sync.main() == 0 and calls == ["refresh"]
    closes = pd.DataFrame({"A": [1.0]}, index=pd.DatetimeIndex([pd.Timestamp.today().normalize()]))
    monkeypatch.setattr(npx, "load", lambda *a, **k: {"closes": closes, "actions": pd.DataFrame(), "notes": {}})
    monkeypatch.setattr(sync.nh, "weekdays", lambda *a: [])
    assert sync.update(0.0, "r2") == 0 and calls == ["refresh", "refresh"]   # up to date: still re-read
