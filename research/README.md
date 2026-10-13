# Research

Research-only scripts. Nothing here is imported by the app, and nothing here
feeds production ranking -- these exist to test whether the scoring model
actually predicts anything, against alternatives it could have been.

All are run by hand, never on a push. Both read a local price cache and refuse
the network outright, so they finish in seconds.

Two earlier scripts, `v1_hypothesis_backtest.py` (candidate scoring models over
monthly-start snapshots) and `v1_recent6m_monthstart.py` (rank IC at 1M/3M/6M
over the last six month starts), downloaded ten years from Yahoo and were
removed with it on 13 Oct 2026 (TODO S10). To ask those questions again, build
them on the long NSE file (`nse_long_close.parquet`, see
`docs/DATA_CATALOGUE.md`), not on a vendor download.

| Script | Question it asks |
|---|---|
| `evaluate_recent_horizons.py` | Over the last eight completed months, what do three horizon weighting profiles earn, and what does each cost in turnover to earn it? |
| `compare_existing_vs_profile2.py` | Does the earnings/acceleration tilt beat the weights the app actually ships, and how different is the book it would hold today? |

Output lands in `research/outputs/` as CSV (gitignored).

Read the numbers with the same caveats as the backtest tab: the universe is
today's index membership applied backwards, so survivorship is baked in, and a
few-month sample is small.
