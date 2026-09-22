"""Build normalized historical-evidence Parquet datasets for R2 bootstrap.

This consumes evidence already maintained by the repository. It does not fetch
new market data and therefore does not compete with the long Screener run.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
INDEX_FILES = {
    "nifty50": ROOT / "data/indices/ind_nifty50list.csv",
    "nifty_next50": ROOT / "data/indices/ind_niftynext50list.csv",
    "nifty_midcap150": ROOT / "data/indices/ind_niftymidcap150list.csv",
    "nifty_smallcap250": ROOT / "data/indices/ind_niftysmallcap250list.csv",
    "nifty_microcap250": ROOT / "data/indices/ind_niftymicrocap250_list.csv",
    "nifty_total_market": ROOT / "data/indices/ind_niftytotalmarket_list.csv",
}


def _sync_date() -> str:
    meta = json.loads((ROOT / "data/indices_sync_meta.json").read_text())
    return str(pd.Timestamp(meta["timestamp"]).date())


def build_constituents(output_dir: Path) -> list[Path]:
    evidence_date = _sync_date()
    out: list[Path] = []
    for index, path in INDEX_FILES.items():
        frame = pd.read_csv(path)
        symbol_col = next(
            (c for c in frame.columns if str(c).strip().lower() == "symbol"), None
        )
        if symbol_col is None:
            raise RuntimeError(f"{path}: missing Symbol column")
        symbols = (
            frame[symbol_col].astype(str).str.strip().str.upper()
        )
        symbols = symbols[symbols.ne("")].drop_duplicates().sort_values()
        result = pd.DataFrame(
            {
                "index": index,
                "symbol": symbols.to_list(),
                "evidence_date": evidence_date,
                "source": "NSE index constituent snapshot",
            }
        )
        path_out = output_dir / f"constituents_{index}.parquet"
        result.to_parquet(path_out, index=False)
        out.append(path_out)
    return out


def _membership_intervals(history: dict[str, Any]) -> pd.DataFrame:
    baseline = history.get("baseline")
    if not baseline:
        raise RuntimeError("membership history has no baseline")

    state = set(baseline["symbols"])
    starts: dict[str, date] = {
        symbol: pd.Timestamp(baseline["date"]).date() for symbol in state
    }
    rows: list[dict[str, Any]] = []
    last_evidence = pd.Timestamp(baseline["date"]).date()

    for change in history.get("changes", []):
        effective = pd.Timestamp(change["date"]).date()
        last_evidence = effective
        for symbol in sorted(change.get("removed", [])):
            start = starts.pop(symbol, None)
            if start is None:
                raise RuntimeError(f"membership removal without active start: {symbol}")
            rows.append(
                {
                    "index": history["index"],
                    "symbol": symbol,
                    "effective_from": start.isoformat(),
                    "effective_to": (effective - timedelta(days=1)).isoformat(),
                    "source": "repository membership history",
                    "evidence_date": effective.isoformat(),
                }
            )
            state.discard(symbol)
        for symbol in sorted(change.get("added", [])):
            if symbol in starts:
                raise RuntimeError(f"membership addition already active: {symbol}")
            starts[symbol] = effective
            state.add(symbol)

    last_evidence = max(
        [pd.Timestamp(baseline["date"]).date()]
        + [pd.Timestamp(change["date"]).date() for change in history.get("changes", [])]
    )

    for symbol in sorted(state):
        rows.append(
            {
                "index": history["index"],
                "symbol": symbol,
                "effective_from": starts[symbol].isoformat(),
                "effective_to": None,
                "source": "repository membership history",
                "evidence_date": last_evidence.isoformat(),
            }
        )

    return pd.DataFrame(rows).sort_values(["index", "symbol", "effective_from"])


def build_membership(output_dir: Path) -> Path:
    history = json.loads((ROOT / "data/membership_history.json").read_text())
    frame = _membership_intervals(history)
    path = output_dir / "membership_nifty_total_market.parquet"
    frame.to_parquet(path, index=False)
    return path


def build_trading_sessions(output_dir: Path) -> Path:
    payload = json.loads((ROOT / "data/nse_trading_days.json").read_text())
    dates = sorted(set(payload.get("trading_days", [])))
    if not dates:
        raise RuntimeError("no confirmed NSE trading sessions")
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "market": "NSE",
            "is_session": True,
            "source": payload.get("source", "NSE"),
            "evidence_date": _sync_date(),
        }
    )
    path = output_dir / "trading_sessions_confirmed.parquet"
    frame.to_parquet(path, index=False)
    return path


def build_market_caps(output_dir: Path) -> Path:
    frame = pd.read_csv(ROOT / "data/nse_market_caps.csv")
    required = {"Symbol", "MarketCap", "AsOf", "Source"}
    if not required.issubset(frame.columns):
        raise RuntimeError(f"market cap file missing columns: {sorted(required - set(frame.columns))}")
    frame = frame.rename(
        columns={
            "Symbol": "symbol",
            "MarketCap": "market_cap",
            "AsOf": "date",
            "Source": "source",
        }
    )
    frame["symbol"] = frame["symbol"].astype(str).str.strip().str.upper()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["evidence_date"] = frame["date"]
    path = output_dir / "market_caps_nse.parquet"
    frame.to_parquet(path, index=False)
    return path


def build_corporate_actions(output_dir: Path) -> Path:
    payload = json.loads((ROOT / "data/corporate_actions_log.json").read_text())
    rows = list(payload.get("events", {}).values())
    if not rows:
        raise RuntimeError("corporate-action log is empty")
    frame = pd.DataFrame(rows)
    frame["event_date"] = pd.to_datetime(frame["date"])
    frame["source"] = "repository-derived corporate-action anomaly log"
    frame["evidence_date"] = pd.to_datetime(frame["first_seen"])
    frame["evidence_uri"] = "repo://Pareshking/Paresh/data/corporate_actions_log.json"
    path = output_dir / "corporate_actions_evidence.parquet"
    frame.to_parquet(path, index=False)
    return path


def build_all(output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = build_constituents(output_dir)
    paths.append(build_membership(output_dir))
    paths.append(build_trading_sessions(output_dir))
    paths.append(build_market_caps(output_dir))
    paths.append(build_corporate_actions(output_dir))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    paths = build_all(args.output_dir)
    for path in paths:
        frame = pd.read_parquet(path)
        print(f"BUILT {path.name} rows={len(frame)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
