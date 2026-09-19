"""Foundation runner for the research-agent pipeline.

This intentionally performs no web research and no ranking. It validates the
quantitative hand-off contract and emits a deterministic execution plan. Later
stages can replace individual steps with real adapters without changing the
contract.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from agent.contracts import QuantSnapshot, validate_snapshot
from agent.fingerprint import config_fingerprint


def build_plan(as_of: date, model: str, universe: str, benchmark: str) -> dict[str, object]:
    snapshot = QuantSnapshot(
        as_of=as_of,
        benchmark=benchmark,
        universe=universe,
        model=model,
        config_fingerprint=config_fingerprint(),
    )
    validate_snapshot(snapshot)
    return {
        "status": "foundation-ready",
        "as_of": as_of.isoformat(),
        "model": model,
        "universe": universe,
        "benchmark": benchmark,
        "stages": [
            "quant_snapshot",
            "market_context",
            "sector_context",
            "industry_context",
            "peer_context",
            "company_evidence",
            "adversarial_challenge",
            "review",
            "weekly_report",
        ],
        "ranking_mutation_allowed": False,
        "provenance": {"config_fingerprint": snapshot.config_fingerprint},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--model", default="System-1")
    parser.add_argument("--universe", default="NIFTY TOTAL MARKET")
    parser.add_argument("--benchmark", default="^CRSLDX")
    args = parser.parse_args()

    result = build_plan(
        as_of=date.fromisoformat(args.as_of),
        model=args.model,
        universe=args.universe,
        benchmark=args.benchmark,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
