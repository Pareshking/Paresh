# Research

Research-only scripts. Nothing here is imported by the app, and nothing here
feeds production ranking -- these exist to test whether the scoring model
actually predicts anything, against alternatives it could have been.

All are run by hand (or via their workflow), never on a push. The first two
each download the full NSE Total Market universe and years of daily prices from
Yahoo, which takes up to 90 minutes and is not something to fire automatically.
The third reads the local price cache and refuses the network outright, so it
finishes in seconds.

| Script | Question it asks |
|---|---|
| `v1_hypothesis_backtest.py` | How do the candidate scoring models rank against each other over monthly-start snapshots? |
| `v1_recent6m_monthstart.py` | Over the last six month-start snapshots, what is the rank IC of each model at 1M/3M/6M forward horizons -- including classic 12M-1M momentum as a baseline? |
| `evaluate_recent_horizons.py` | Over the last eight completed months, what do three horizon weighting profiles earn, and what does each cost in turnover to earn it? |

Output lands in `research/outputs/` as CSV (gitignored). The workflow uploads
it as a build artifact with 14-day retention.

Read the numbers with the same caveats as the backtest tab: the universe is
today's index membership applied backwards, so survivorship is baked in, and a
six-snapshot sample is small.
