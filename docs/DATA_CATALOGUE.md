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
| `prices/yahoo` | **Retired 2026-10-02**: no longer published; Yahoo files live on the `data-latest` release only | — | — | — | — | Deleted whole by `r2_retention` |
| `prices/yahoo/raw`, `prices/yahoo/bootstrap` | **Retired** (Yahoo data removed from R2) | — | — | — | — | Deleted whole |
| `prices/screener/bootstrap` | Bootstrap load | file | as pulled | `screener_10y_bootstrap` | Rebuilds, audits | Never touched |
| `nse/prices_daily` | NSE bhav copy, unadjusted OHLC (index closes on bundle days), ~3,800 securities | security × day | **10 Jun 2010 to date** (Jan–Jun 2010 being collected) | `nse_collect` every 4 h; `daily_sync` collects the last 3 sessions; history imported 2 Oct 2026 from NSE's full bhavcopy via the GitHub mirror (`nse_history_import`) | NSE adjustment layer, three-source check, source checks | Full history |
| `nse/corporate_actions` | NSE Bc file: splits, bonuses, rights, demergers parsed to kind and price factor | action, per listing day | Oct 2023 to date | `nse_collect` | `src/loaders/nse_adjusted.py`, `src/engine/reconcile.py` | Full history |
| `nse/corporate_actions_history` | NSE's corporate-action list, with face values | action, one file per ex-date year | 2010 – 2026 | `nse_history_import` (one request a year) | `nse_history.read_r2` (with the daily files) | Full history |
| `nse/closed_days` | Weekdays with no NSE bundle a week later (holidays) | day | grows | `nse_collect` | `nse_collect` (asks each once) | Full history |
| `prices/ss` | The SS store: daily OHLCV, 1,216 stocks, 1,000 sessions each, one whole-history file | stock × day | from 2018 (most from Sep 2022) | `ss_sync` weekdays 22:02 IST | Three-source check; to become the app's primary source | 7 dates + month-ends |
| `nse/market_caps` | NSE market cap per security | security × day | 3 years | `nse_collect` | Nano Cap list, screener MCAP column | Full history |
| `nse/source_checks` | Disagreements between NSE and the other sources, newest day | check | newest day | `nse_compare`, `nse_sample_check` | Data-health review | Overwritten daily |
| `market_caps/nse_history` | Market-cap history used for universe cuts | security × day | grows daily | `r2_market_cap_history` 20:00 | Membership, Nano Cap | Full history |
| `indices/membership/nifty_total_market` | Point-in-time index membership | stock × effective date | from notices | `daily_sync`, membership notices | Backtester (`former_members`), Track Record | Full history |
| `indices/prices/research` | Index levels (Nifty 500, Nifty 50 …) | index × day | years | `r2_nse_index_prices` 20:30 | Benchmarks, RRG, Breadth | Full history |
| `trading_sessions/observed` | Sessions that actually traded | day | grows daily | `r2_observed_trading_sessions` | Continuity audit | Full history |
| `snapshots/rankings` | Daily ranking table (the rank history) | stock × day | grows daily | `r2_ranking_archive` 20:45 | Rank history, Track Record "Ranks by month" | Full history |
| `app/prices_snapshot`, `app/prices_extra` | **Retired 2026-10-02**: app reads these from the release only | — | — | — | — | Deleted whole |
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
| `nse_prices/closes.parquet`, `actions.parquet`, `notes.json` | Local NSE close and action copies (2 years) for the adjustment layer; `notes.json` holds one-off corrections and rename overrides | `sync_nse_prices` (monthly) |
| `benchmarks.csv` | Nifty 500 and Nifty 50 daily closes from 8 Oct 2015 (NSE rows win, then SS, then Screener) | `daily_sync` (`build_benchmarks.py --update`) |
| `reference/nse/symbolchange.csv`, `namechange.csv`, `equity_l.csv` | NSE's ticker changes (1999 on), name changes and today's listed equities with ISINs | `sync_nse_reference` daily |
| `reference/nse/isin_history.csv` | Every symbol–ISIN pair in NSE's bhavcopy, Jun 2011 – Jun 2021, first and last day | `build_isin_history.py`, once (history) |
| `nse_market_caps.csv`, `nse_all_time_highs.csv`, `nse_tv_classification.csv`, `nse_fo_symbols.json`, `nse_trading_days.json`, `screener_company_ids.json` | Reference tables: market cap, all-time highs, industry labels, F&O list, trading calendar, Screener ids | `daily_sync` / collectors |
| `track_record.json` | The frozen monthly Track Record ledger | `monthly_track_record`, 1st–5th of the month, 19:00 |

## Which source wins

**Today the app ranks on Screener, then NSE** for what Screener lacks
(`price_source.ranking_frames`). Yahoo is no longer a source (owner, 2 Oct
2026). SS is collected nightly and checked against the other two by the
three-source vote, with NSE's own record as judge; it is not yet wired into
the app. Rules, the nightly run and the vote: `docs/PRICE_PIPELINE.md`.

## Comparisons: where they stand

- 2026-09-25: NSE vs Screener closes agree for 749 of 750; NSE vs Yahoo moves
  agree for all 750. The one flag is HEG (demerger 2026-09-07, no price on
  either).
- Adjusted NSE vs Screener (third report): drift beyond 1% fell from 135 stocks
  to 58 after applying splits and bonuses; rank correlation 0.9993 / 0.9934 /
  0.9975, top-20 overlap 20/20, 19/20, 20/20.
- Fourth report (27 Sep): 1,117 of 1,167 stocks within 1% throughout, 50
  beyond; rank correlation 0.9997 / 0.9984 / 0.9991, top 20 in common 20/20,
  19/20, 20/20, top 50 50/50.
- Decision (owner, 2 Oct 2026): NSE becomes the middle source, skipping the
  ~50 stocks still beyond 1%. Wired in 2 Oct: gaps in Screener fill from NSE.
- SS vs Screener (2 Oct, a year of 192 stocks): identical to the paisa on 187;
  differences were a rights issue (ADANIENT), an SME migration (ADVAIT), a new
  listing (ARCIL) and one day (BLISSGVS). Screener's volume is NSE + BSE.
- Three-source vote (Aug–Sep 2026, 1,210 stocks, NSE for 1,207): SS outvoted 52
  times, Screener 18, 1 unresolved (HEG's demerger day). See
  `docs/PRICE_PIPELINE.md`.

## Freshness in the app

The header pill shows the price date. Configuration → Universe has a table of
every source's latest date, how many trading days behind it is, and whether it
is current, plus the manual refresh (one global refresh per cooldown).
