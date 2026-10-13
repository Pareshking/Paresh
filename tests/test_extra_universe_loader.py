"""The app's extra-universe loaders: member list and membership summary."""
import json

import pandas as pd

from src.loaders import extra_universe_loader as xl


def test_members_come_back_in_the_index_loaders_shape(tmp_path):
    p = tmp_path / "list.csv"
    pd.DataFrame({"Company Name": ["Abc Ltd", None, "Dummy"], "Industry": ["Finance", None, "X"],
                  "Symbol": ["abc", "XYZ", "DUMMYQ"], "Series": "EQ", "ISIN Code": "",
                  "MarketCapCr": [3000, 2500, 2100]}).to_csv(p, index=False)
    m = xl.members(str(p))
    assert list(m.columns) == ["Symbol", "Company Name", "Industry", "Indices"]
    assert list(m["Symbol"]) == ["ABC", "XYZ"]
    assert m.loc[1, "Company Name"] == "XYZ" and m.loc[1, "Industry"] == "Unclassified"
    assert set(m["Indices"]) == {"NANO"}
    assert xl.members(str(tmp_path / "missing.csv")).empty


def test_membership_summary_names_the_newest_month(tmp_path):
    p = tmp_path / "h.json"
    p.write_text(json.dumps({"months": {
        "2026-08-31": {"effective_from": "2026-09-01", "count": 417, "symbols": []},
        "2026-07-31": {"effective_from": "2026-08-01", "count": 400, "symbols": []}}}))
    assert xl.membership_summary(str(p)) == {
        "as_of": "2026-08-31", "effective_from": "2026-09-01", "count": 417}
    assert xl.membership_summary(str(tmp_path / "none.json")) == {}


def test_the_extra_universe_loader_downloads_nothing_from_yahoo():
    from pathlib import Path

    text = Path(xl.__file__).read_text(encoding="utf-8")
    assert "yfinance" not in text and "yf.download" not in text
    assert not hasattr(xl, "download") and not hasattr(xl, "load_prices")
