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

from scripts.build_membership_history import RESEARCH_INDEXES, TRACKED_INDEX_PATHS, build_history
from src.core.tickers import is_tradeable_symbol


ROOT = Path(__file__).resolve().parents[1]
MEMBERSHIP_AS_OF = "2026-09-18"
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


def _validate_index_sources() -> None:
    missing = [str(path) for path in INDEX_FILES.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "historical evidence index source file(s) missing: " + ", ".join(missing)
        )


def build_constituents(output_dir: Path) -> list[Path]:
    _validate_index_sources()
    evidence_date = _sync_date()
    out: list[Path] = []
    for index, path in INDEX_FILES.items():
        frame = pd.read_csv(path)
        symbol_col = next(
            (c for c in frame.columns if str(c).strip().lower() == "symbol"), None
        )
        if symbol_col is None:
            raise RuntimeError(f"{path}: missing Symbol column")
        symbols = frame[symbol_col].astype(str).str.strip().str.upper()
        symbols = symbols[symbols.map(is_tradeable_symbol)].drop_duplicates().sort_values()
        result = pd.DataFrame(
            {
                "index": index,
                "symbol": symbols.to_list(),
                "as_of": evidence_date,
                "evidence_date": evidence_date,
                "source": "NSE index constituent snapshot",
            }
        )
        path_out = output_dir / f"constituents_{index}.parquet"
        result.to_parquet(path_out, index=False)
        out.append(path_out)
    return out


def _membership_intervals(history: dict[str, Any], index_name: str | None = None, as_of: str = MEMBERSHIP_AS_OF) -> pd.DataFrame:
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
                    "index": index_name or "nifty_total_market",
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
                "index": index_name or "nifty_total_market",
                "symbol": symbol,
                "effective_from": starts[symbol].isoformat(),
                "effective_to": None,
                "source": "repository membership history",
                "evidence_date": last_evidence.isoformat(),
            }
        )

    frame = pd.DataFrame(rows).sort_values(["index", "symbol", "effective_from"])
    frame["as_of"] = as_of
    return frame


def build_membership(output_dir: Path) -> list[Path]:
    """Build PIT membership intervals for all five research indices.

    The legacy Total Market timeline is intentionally retained as a compatibility
    artifact because existing V1 consumers use it. The five research indices are
    reconstructed independently from their own committed NSE snapshots so an
    index reclassification is represented by the actual index timelines rather
    than inferred from today's universe.
    """
    paths: list[Path] = []

    as_of = _sync_date()
    legacy = json.loads((ROOT / "data/membership_history.json").read_text())
    frame = _membership_intervals(legacy, as_of=as_of)
    path = output_dir / "membership_nifty_total_market.parquet"
    frame.to_parquet(path, index=False)
    paths.append(path)

    for index in RESEARCH_INDEXES:
        summary = build_history(
            TRACKED_INDEX_PATHS[index],
            ROOT / "data" / "membership" / f"{index}.json",
            index_name=index,
            include_working_tree=True,
            write=False,
        )
        frame = _membership_intervals(summary["history"], index_name=index, as_of=as_of)
        path = output_dir / f"membership_{index}.parquet"
        frame.to_parquet(path, index=False)
        paths.append(path)

    return paths


def build_point_in_time_universe(output_dir: Path) -> Path:
    frames = []
    for index in (*RESEARCH_INDEXES, "nifty_total_market"):
        path = output_dir / f"membership_{index}.parquet"
        frame = pd.read_parquet(path)
        frames.append(frame)
    result = pd.concat(frames, ignore_index=True).sort_values(["effective_from", "index", "symbol"])
    path = output_dir / "point_in_time_universe.parquet"
    result.to_parquet(path, index=False)
    return path

def build_classification(output_dir: Path) -> Path:
    from scripts.build_classification_history import build
    path = output_dir / "classification_history.parquet"
    build(path)
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
    paths.extend(build_membership(output_dir))
    paths.append(build_classification(output_dir))
    paths.append(build_point_in_time_universe(output_dir))
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
    # Every Parquet file is written and closed inside main(). On 2026-09-25 the
    # CI run built all of them, printed every BUILT line, then aborted during
    # interpreter teardown ("terminate called without an active exception",
    # exit 134) -- a native thread-pool shutdown race, not a data error, and
    # not reproducible locally in 30 runs. Skipping teardown once the output is
    # flushed makes the step's exit code reflect the work actually done.
    import os
    import sys

    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
