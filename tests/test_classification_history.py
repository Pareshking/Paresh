import pandas as pd

from scripts.build_classification_history import REQUIRED


def test_classification_contract():
    frame = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB"],
            "sector": ["Technology", "Finance"],
            "industry": ["Software", "Banks"],
            "effective_from": pd.to_datetime(["2026-01-01", "2026-01-01"]),
            "evidence_date": pd.to_datetime(["2026-01-01", "2026-01-01"]),
            "evidence_commit": ["a" * 40, "a" * 40],
            "source": ["repository TV classification snapshot"] * 2,
        }
    )
    assert {"symbol", "sector", "industry", "effective_from", "evidence_date", "evidence_commit", "source"} <= set(frame.columns)
    assert frame["symbol"].is_unique
    assert frame["sector"].notna().all()
    assert frame["industry"].notna().all()
