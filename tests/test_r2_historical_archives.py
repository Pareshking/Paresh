"""Tests for historical session and market-cap archive builders."""

from pathlib import Path

import pandas as pd


def test_observed_sessions_builder(tmp_path: Path):
    from scripts.build_observed_sessions_parquet import build

    src = tmp_path / "prices.parquet"
    out = tmp_path / "sessions.parquet"
    pd.DataFrame(
        {"AAA": [1, 2, 3]},
        index=pd.to_datetime(["2026-09-18", "2026-09-21", "2026-09-21"]),
    ).to_parquet(src)
    result = build(src, out)
    frame = pd.read_parquet(out)

    assert result["session_count"] == 2
    assert frame["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-09-18", "2026-09-21"]
    assert frame["is_session"].all()
    assert frame["source"].eq("observed_production_price_archive").all()


def test_market_cap_history_uses_latest_snapshot_per_asof(monkeypatch, tmp_path: Path):
    from scripts import build_market_cap_history as mod

    commits = ["a" * 40, "b" * 40, "c" * 40]
    frames = {
        commits[0]: pd.DataFrame(
            {"Symbol": ["AAA"], "MarketCap": [10], "AsOf": ["2026-01-01"], "Source": ["nse"]}
        ),
        commits[1]: pd.DataFrame(
            {"Symbol": ["AAA"], "MarketCap": [11], "AsOf": ["2026-01-01"], "Source": ["nse"]}
        ),
        commits[2]: pd.DataFrame(
            {"Symbol": ["AAA"], "MarketCap": [12], "AsOf": ["2026-02-01"], "Source": ["nse"]}
        ),
    }

    monkeypatch.setattr(mod, "_git", lambda *args: "\n".join(commits) if args[:1] == ("log",) else "")
    monkeypatch.setattr(mod, "_snapshot", lambda commit, path: frames[commit].assign(
        symbol=frames[commit]["Symbol"],
        market_cap=frames[commit]["MarketCap"],
        date=pd.to_datetime(frames[commit]["AsOf"]),
        source=frames[commit]["Source"],
    )[["symbol", "market_cap", "date", "source"]])

    out = tmp_path / "market_caps.parquet"
    result = mod.build(out, mod.DEFAULT_PATH)
    frame = pd.read_parquet(out)

    assert result["snapshot_count"] == 2
    assert frame["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-01-01", "2026-02-01"]
    assert frame.loc[frame["date"].eq(pd.Timestamp("2026-01-01")), "market_cap"].iloc[0] == 11
