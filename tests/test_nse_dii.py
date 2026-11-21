"""NSE's category-wise DII figures (scripts/collect_nse_dii.py, S153, 21 Nov 2026)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("collect_nse_dii", ROOT / "scripts" / "collect_nse_dii.py")
cd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cd)


def _history(labels):
    rows = [["title"] + [None] * 13, [None] * 14, [None] * 14]
    for i, lab in enumerate(labels):
        # bank b/s, DFI b/s, insurance b/s, MF b/s, NPS b/s, total b/s, net
        rows.append([lab, 10, 20, 1, 1, 30, 10, 100, 50, 5, 0, 146, 81, 65])
    return pd.DataFrame(rows)


def test_month_names_short_or_long_and_no_gap():
    h = cd.parse_history(_history(["July'24", "Aug'24", "September '24"]))
    assert list(h["period"]) == ["2024-07", "2024-08", "2024-09"]
    assert h["net"].iloc[0] == 65 and h["bim_net"].iloc[0] == (10 - 20) + (30 - 10) + (100 - 50)
    with pytest.raises(cd.Refused, match="not read"):
        cd.parse_history(_history(["July'24", "September'24"]))


def test_daily_rows_must_agree_with_the_month():
    h = cd.parse_history(_history(["October'26"]))
    days = pd.DataFrame({"period": ["2026-10-01", "2026-10-02"], "buy": [80.0, 60.0], "sell": [50.0, 30.0]})   # net 60 = bim_net
    out = cd.build(h, days, {"2026-10": 2})
    assert set(out["kind"]) == {"month", "day"}
    with pytest.raises(cd.Refused, match="2026-10"):
        cd.build(h, days.assign(sell=[50.0, 40.0]), {"2026-10": 2})
    cd.build(h, days.iloc[:1], {"2026-10": 2})          # a month not complete is not checked


def test_the_dashboard_reads_finished_months_whole_and_the_live_month_from_days():
    from src.ui.views.dashboard_home_view import _dii_months, _dii_now
    f = pd.DataFrame({"kind": ["month", "day", "day"], "period": ["2026-10", "2026-11-02", "2026-11-03"],
                      "buy": [0, 0, 0], "sell": [0, 0, 0], "net": [47969.0, -421.0, -3503.0], "scope": ["", "", ""]})
    m = _dii_months(f)
    assert m[pd.Period("2026-10", "M")][0] == 47969.0 and m[pd.Period("2026-10", "M")][5]
    now = _dii_now(f)
    assert now[2] == -3924.0 and now[3] == 2 and now[4] == 2 and now[1] == pd.Timestamp("2026-11-03")


def test_a_month_collected_from_its_first_session_on_all_exchanges_replaces_nse(monkeypatch, tmp_path):
    import src.ui.views.dashboard_home_view as h
    days = pd.bdate_range("2026-12-01", "2026-12-04")
    f = tmp_path / "flows.csv"
    pd.DataFrame({"date": days.strftime("%Y-%m-%d"), "category": "DII", "buy": 0, "sell": 0, "net": [-1.0, -2.0, 3.0, -4.0],
                  "fetched_at": ""}).to_csv(f, index=False)
    monkeypatch.setitem(h.FILES, "nse_flows", f)
    m = h._all_exchange_months()
    v = m[pd.Period("2026-12", "M")]
    assert v[0] == -4.0 and v[3] == 4 and v[6] == "all exchanges" and not v[5]
    # November started on 6 Nov in the file, so it is not taken
    pd.DataFrame({"date": ["2026-11-06"], "category": "DII", "buy": 0, "sell": 0, "net": [-1.0], "fetched_at": ""}).to_csv(f, index=False)
    assert h._all_exchange_months() == {}
