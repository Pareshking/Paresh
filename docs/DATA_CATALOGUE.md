# Data catalogue

One page that says what data exists, where it lives, who writes it and who
reads it. Detail lives in the linked docs; this page is the index.

Times are UTC. R2 is Cloudflare R2 (the research archive, immutable
content-addressed revisions plus a `current` pointer per dataset). `data/` is
the repo copy the app reads at run time.

## R2 datasets

| Dataset (R2 prefix) | What it is | Grain | History | Writer (workflow, UTC) | Readers | Retention |
|---|---|---|---|---|---|---|
| `prices/screener` | Screener.in adjusted daily closes, ~1,167 stocks | stock × day | 10 years (bootstrap) | `screener_sync` 18:45 daily; `weekly_full_sync` Fri 18:30 | App price loader, backtests | Full history |
| `prices/yahoo` | Yahoo adjusted closes, whole universe | stock × day | 10 years | `daily_sync` Mon–Fri 17:30 | App fallback, comparison reports | Last 7 dates + month-end of every month (policy 2026-09-25) |
| `prices/yahoo/raw`, `prices/yahoo/bootstrap`, `prices/screener/bootstrap` | Source-faithful raw pulls and bootstrap loads | file | as pulled | `r2_yahoo_raw_build`, `screener_10y_bootstrap` | Rebuilds, audits | Never touched |
| `nse/prices_daily` | NSE bhav copy, unadjusted OHLC and index closes, ~3,800 securities | security × day | back to 2023-10-03 (3 years) | `nse_collect` every 4 h; `daily_sync` collects the last 3 sessions | NSE adjustment layer, source checks | Full history |
| `nse/corporate_actions` | NSE Bc file: splits, bonuses, demergers parsed to kind and price factor | action | 3 years | `nse_collect` | `src/loaders/nse_adjusted.py` | Full history |
| `nse/market_caps` | NSE market cap per security | security × day | 3 years | `nse_collect` | Nano Cap list, screener MCAP column | Full history |
| `nse/source_checks` | Disagreements between NSE and the other sources, newest day | check | newest day | `nse_compare`, `nse_sample_check` | Data-health review | Overwritten daily |
| `market_caps/nse_history` | Market-cap history used for universe cuts | security × day | grows daily | `r2_market_cap_history` 20:00 | Membership, Nano Cap | Full history |
| `indices/membership/nifty_total_market` | Point-in-time index membership | stock × effective date | from notices | `daily_sync`, membership notices | Backtester (`former_members`), Track Record | Full history |
| `indices/prices/research` | Index levels (Nifty 500, Nifty 50 …) | index × day | years | `r2_nse_index_prices` 20:30 | Benchmarks, RRG, Breadth | Full history |
| `trading_sessions/observed` | Sessions that actually traded | day | grows daily | `r2_observed_trading_sessions` | Continuity audit | Full history |
| `snapshots/rankings` | Daily ranking table (the rank history) | stock × day | grows daily | `r2_ranking_archive` 20:45 | Rank history, Track Record "Ranks by month" | Full history |
| `snapshots/app_prices`, `snapshots/app_prices_extra` | App price bundle | file | latest | `daily_sync` | App cold start | Latest + month-end |
| `snapshots/application` | Retired. No longer published (2026-09-25) | | | | | Existing copies follow the 7 + month-end rule |

Policy and recovery: `docs/R2_RECOVERY_AND_RETENTION.md`. Layout and rules
(never splice sources, preserve departed stocks, manifests, checksums):
`docs/MARKET_DATA_ARCHIVE_R2_SPEC.md`.

## Repo files the app reads (`data/`)

| File | What it is | Written by |
|---|---|---|
| `indices/ind_*.csv` | Current NSE index constituent lists (Total Market, Nifty 50, Next 50, Midcap 150, Smallcap 250, Microcap 250, Nano Cap) | `daily_sync` |
| `membership_history.json`, `membership_notices.json` | Point-in-time membership and the notices it is built from | membership scripts (`docs/MEMBERSHIP_FROM_NOTICES.md`) |
| `nanocap_membership.json` | Month-end Nano Cap list | `daily_sync` (builds on the last session of the month) |
| `corporate_actions_log.json` | Corporate actions applied | `daily_sync` |
| `former_member_prices.parquet/.json` | Prices for stocks that left the universe, so past months replay faithfully | `daily_sync` |
| `nse_prices/closes.parquet`, `actions.parquet` | Local NSE close and action copies for the adjustment layer | `nse_collect` |
| `nse_market_caps.csv`, `nse_all_time_highs.csv`, `nse_tv_classification.csv`, `nse_fo_symbols.json`, `nse_trading_days.json`, `screener_company_ids.json` | Reference tables: market cap, all-time highs, industry labels, F&O list, trading calendar, Screener ids | `daily_sync` / collectors |
| `track_record.json` | The frozen monthly Track Record ledger | `monthly_track_record`, 2nd–5th of the month, 19:00 |

## Which source wins (decision D3)

Prices: **Screener → NSE → Yahoo.** Screener is the primary adjusted series.
NSE is the middle source once its adjustment layer is accepted
(`docs/NSE_DATA_LEDGER.md`, to-do 3 and 4). Yahoo is the last fallback. Sources
are never spliced inside one series (spec §10); a stock uses one source for its
whole window and the app labels which.

## NSE vs Yahoo vs Screener: where the comparison stands

- 2026-09-25: NSE vs Screener closes agree for 749 of 750; NSE vs Yahoo moves
  agree for all 750. The one flag is HEG (demerger 2026-09-07, no price on
  either).
- Adjusted NSE vs Screener (third report): drift beyond 1% fell from 135 stocks
  to 58 after applying splits and bonuses; rank correlation 0.9993 / 0.9934 /
  0.9975, top-20 overlap 20/20, 19/20, 20/20.
- Left: ex-dates Bc prints month-first (E2E, MCX, VGL, SILVERTUC) and demergers
  (VEDL, HEG, SIEMENS, RAYMOND, ABFRL). The fourth report decides whether NSE
  becomes the middle source.

## Freshness in the app

The header pill shows the price date. Configuration lists which constituent
lists are on disk and how fresh they are, and has the manual refresh (rate
limited to one global refresh per cooldown). A single compact table of every
dataset's latest date against its expected cadence (the Writer column above)
is still to do; it replaces the long Data section in Configuration (TODO U5).
