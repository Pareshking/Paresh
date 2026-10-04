# 2010 PIT monthly ranking audit

This manual workflow is isolated. It does not modify the production engine, R2 objects, releases, or canonical ranking data.

## Inputs required before running

The workflow requires a verified Nifty 500 point-in-time history JSON with this shape:

```json
{"baseline":{"date":"2010-01-01","symbols":["SYMBOL1","SYMBOL2"]},"changes":[{"date":"2010-02-24","added":["NEW"],"removed":["OLD"]}]}
```

A wrapped form `{"indices":{"nifty_500":{...}}}` is also accepted. The JSON must provide actual dated changes; current constituents are not a valid substitute for 2010.

For tradebook reconciliation, provide an HTTPS URL to a CSV with `Stock Name` and `Entry Date` columns. Leave blank for rankings only. Do not use a public URL for private trade records; workflow inputs may be visible to repository users who can view runs.

## Calculation convention

- Each month's decision date is the prior available price session before that month's first price session, avoiding look-ahead from that month's close.
- 12-month ROC = close[t] / close[t-252] - 1.
- Annualized volatility = sample standard deviation of the last 252 daily simple returns × sqrt(252).
- Score = 12-month ROC / annualized volatility.
- Missing price history is flagged; missing PIT membership coverage fails closed.
- Ties are broken by symbol. All eligible names are output with Top 20/25/30 flags.

## Outputs

- `2010_monthly_top30_and_coverage.csv`
- `2010_monthly_audit_summary.csv`
- `2010_tradebook_rank_reconciliation.csv` (when tradebook URL is provided)
- `validation_report.json`

This is a research audit, not production certification. Membership authenticity, corporate-action adjustment and ticker lineage remain separate evidence gates.
