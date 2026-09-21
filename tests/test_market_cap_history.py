"""Executable contracts for the dated market-cap evidence builder."""

from pathlib import Path

import pandas as pd


def test_market_cap_history_keeps_latest_revision_per_evidence_date(monkeypatch, tmp_path: Path):
    from scripts import build_market_cap_history as mod

    commits = ["a" * 40, "b" * 40, "c" * 40]
    frames = {
        commits[0]: pd.DataFrame(
            {"symbol": ["AAA"], "market_cap": [10], "date": pd.to_datetime(["2026-01-01"]), "source": ["nse"]}
        ),
        commits[1]: pd.DataFrame(
            {"symbol": ["AAA"], "market_cap": [11], "date": pd.to_datetime(["2026-01-01"]), "source": ["nse"]}
        ),
        commits[2]: pd.DataFrame(
            {"symbol": ["AAA"], "market_cap": [12], "date": pd.to_datetime(["2026-02-01"]), "source": ["nse"]}
        ),
    }

    monkeypatch.setattr(
        mod,
        "_git",
        lambda *args: "\n".join(commits) if args[:1] == ("log",) else "",
    )
    monkeypatch.setattr(mod, "_snapshot", lambda commit, path: frames[commit])

    out = tmp_path / "market_caps.parquet"
    summary = mod.build(out, mod.DEFAULT_PATH)
    result = pd.read_parquet(out)

    assert summary["snapshot_count"] == 2
    assert result["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-01-01", "2026-02-01"
    ]
    assert result.loc[result["date"].eq(pd.Timestamp("2026-01-01")), "market_cap"].iloc[0] == 11
    assert result.loc[result["date"].eq(pd.Timestamp("2026-01-01")), "evidence_commit"].iloc[0] == commits[1]


def test_market_cap_history_rejects_duplicate_symbols(monkeypatch):
    from scripts import build_market_cap_history as mod
    import pytest

    csv_text = """Symbol,MarketCap,AsOf,Source
AAA,10,2026-01-01,nse
AAA,11,2026-01-01,nse
"""
    monkeypatch.setattr(mod, "_git", lambda *args: csv_text)
    with pytest.raises(RuntimeError, match="duplicate symbols"):
        mod._snapshot("a" * 40, "data/nse_market_caps.csv")
