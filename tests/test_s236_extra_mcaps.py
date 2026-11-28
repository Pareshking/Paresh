"""S236: the > ₹2,000 Cr list's stocks take NSE's daily market cap, not the month-end list's.

The live stock page read JLHL at ₹8,430 Cr (the list of 30 Oct) beside its 27 Nov close, while NSE's
file and Screener both had ₹11,320 Cr (site audit, 28 Nov 2026).
"""

from pathlib import Path

import pandas as pd

from src.loaders import extra_universe_loader as xl

ROOT = Path(__file__).resolve().parents[1]


def test_nse_daily_value_wins_over_the_month_end_list(tmp_path):
    nse = tmp_path / "nse_market_caps.csv"
    pd.DataFrame({"Symbol": ["JLHL"], "MarketCap": [113199736983.0], "AsOf": ["2026-11-27"],
                  "Source": ["pr_live_zip"]}).to_csv(nse, index=False)
    lst = tmp_path / "ind_nanocap_list.csv"
    pd.DataFrame({"Company Name": ["A", "B"], "Industry": ["x", "y"], "Symbol": ["JLHL", "ONLYLIST"],
                  "Series": ["EQ", "EQ"], "ISIN Code": ["", ""], "MarketCapCr": [8430.0, 2500.0]}).to_csv(lst, index=False)
    caps = xl.system_market_caps(["JLHL", "ONLYLIST"], str(nse), str(lst))
    assert round(caps["JLHL"] / 1e7) == 11320          # NSE's 27 Nov value
    assert round(caps["ONLYLIST"] / 1e7) == 2500       # the list only where NSE has none


def test_the_app_and_the_precompute_do_not_read_the_list_directly():
    for f in ("app.py", "scripts/precompute_systems.py"):
        src = (ROOT / f).read_text()
        assert "list_market_caps(" not in src, f
        assert "system_market_caps(" in src, f
