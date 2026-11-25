# Full data audit, part 1: the inventory and two cross-checks (S163, 24 Nov 2026)

> **Part 1 of S163** (section 1, and 2 (a) and (b)); (c)-(f) and section 3 to follow. **Checked by the coordinator, 24 Nov 2026:** gap 4 confirmed (7 NSE weekend sessions missing from `nse_total_market.csv`) and **fixed by rule** the same day (`collect_nse_total_market.py` asks for the weekend sessions NSE's index history holds; the 7 closes equal it); the `DATA_CATALOGUE.md` writer of `signal_tests.json` corrected. R2 content not checked (no keys in this container).

Draft by Claude, 24 Nov 2026, read from main `4048427` (24 Nov 08:56 UTC). It follows `docs/DATA_AUDIT_PLAN.md`
section 1 (one table per page, one row per element) and section 2 (a) and (b). It does not cover 2 (c) to (f).
`docs/FIGURE_INVENTORY.md` (S154) is reused as it stands: the figures it already lists are named here once, with the
columns it lacks (original source, where kept, writing job, end date). Nothing in the repository was changed.

**Counts:** 13 pages (11 menu pages + the stock page + the header strip), 193 element rows (9 of them are per-system notes, so 184 elements),
12 gaps under (a), 10 findings under (b) (rows b11 and b12 are checks that cleared), plus 7 other findings (section 4).

**What could not be checked, and why**

- **R2 content.** This container has no R2 credentials. Every R2 statement is **judged from code** (the writer's
  `r2_publish.py --dataset` line, the reader's dataset constant); revisions, history length and last-written dates are
  not checked.
- **The live page date.** The ranking (`rank_df`) and the price frames come from R2 (else the `data-latest` release)
  at run time, so the session each page shows was not read. `docs/FIGURE_INVENTORY.md` recorded 20 Nov on the live
  site on 24 Nov (S193 A); `data/backtest_reference.json` says the long file's last session was 20 Nov
  (`long_last_session`). The committed `data/` files end on 23 Nov (table below). Each row says "PD" for the page's
  data date where the figure follows it.
- **Run history** (last success, run time, minutes) is section 2 (c), not done here.
- **Release assets** were not listed (`gh release view` not run); named from the upload lines only.

## 0. Legends

### Jobs (cron from `.github/workflows/*.yml`, UTC)

| Key | Workflow | Schedule (file:line) |
|---|---|---|
| J-scr | `screener_sync.yml` | `7 17 * * *` (:30); also `weekly_full_sync.yml` `30 18 * * 5` (:6), `screener_catchup.yml` `37 23 * * *`, `37 1 * * *` (:19-20) |
| J-daily | `daily_sync.yml` | `30 17 * * 1-5` (:29), `0 2 * * *` (:64), and `workflow_run` after the Screener sync (:79-80) |
| J-long | `nse_long_prices.yml` | `workflow_run` after J-daily, only when that run was itself chained (:39-41, :62-66); `30 3 * * 6` (:44) |
| J-idx | `nse_indices.yml` | `10 14 * * *` (:24) |
| J-col | `nse_collect.yml` | `41 12 * * 1-5`, `41 14 * * 1-5`, `11 16 * * 1-5`, `41 3 * * *` (:27-30) |
| J-fii | `fii_dii.yml` | `47 14 * * 1-5`, `47 17 * * 1-5` (:8-9) |
| J-nsdl | `nsdl_fpi.yml` | `17 4 * * 1-6`, `17 13 * * 1-5` (:17-18) |
| J-mh | `momentum_health.yml` | `23 6 2-6 * *` (:8) |
| J-tr | `monthly_track_record.yml` | `0 19 1-5 * *` (:15) |
| J-rc | `results_calendar.yml` | `23 16 * * *` (:11) |
| J-ref | `nse_reference_sync.yml` | `45 2 * * *` (:11) |
| J-bt | `backtest_reference.yml` | `17 5 * * 0` (:10) |
| J-bse | `bse_daily.yml` | `30 20 * * 5` (:19) |
| J-ev | `r2-historical-evidence-bootstrap.yml` | `workflow_run` after J-daily (:16-17), `15 20 * * 0` (:35) |
| J-mcap | `r2_market_cap_history.yml` | `workflow_run` after J-daily (:19-20), `00 20 * * 0` (:7) |
| hand | no schedule | by hand or once |

### Upstream stores the pages read through (judged from code)

| Key | What | Kept | Written by |
|---|---|---|---|
| RANK | the published ranking, one per system | R2 `snapshots/rankings` (750), `snapshots/rankings_{nano,combined,1000}`; release `rankings.parquet`, `rankings_{sys}.parquet` (`ranking_store.py:197-205`, `:232-246`) | J-daily (`daily_sync.yml:287` `precompute_systems.py`, `:321-332` release, `:356-371` R2); J-scr weekly (`weekly_full_sync.yml:91`) |
| SCR | Screener's adjusted closes, ~1,167 stocks + extras (`price_source.fetch_screener_store`, `:102`) | R2 `prices/screener`; release `screener_prices.parquet` | J-scr (`screener_sync.yml:235`, `:256-258`) |
| NSE2Y | NSE's raw closes, two years, for the adjustment layer (`nse_prices.closes_path`, `:248`) | R2 `nse/closes_2y`; release `nse_closes.parquet`; not in git (`.gitignore:102`) | J-tr (`scripts/publish_nse_closes.sh:16-26`) |
| LONG | NSE's long adjusted file, 2008 to date (`nse_long.py:57-59`) | R2 `prices/nse_long_close`, `_value`, `_report`; release `nse_long_*.parquet` | J-long (`nse_long_prices.yml:159`, `:174`) |
| IDX | every NSE index, daily (`ui/indices_data.frames`, `:23`; `nse_indices.read_compact`, `:348`) | R2 `indices/nse_close_all`; repo `data/nse_indices_history.parquet` (to 20 Nov, frozen) + `data/nse_indices_recent.csv` | J-idx (`nse_indices.yml:56-81`) |
| BI | `data/benchmark_indices.csv` (`benchmark_indices.read`/`series`, `:69`, `:81`) | repo only | J-daily (`daily_sync.yml:200` `build_benchmark_indices.py`) |
| BM | `data/benchmarks.csv`, Nifty 500 and Nifty 50 (`benchmark_store.history`, `:75`; `price_loader.fetch_benchmark_history`, `:276`) | repo only | J-daily (`daily_sync.yml:190` `build_benchmarks.py`) |
| TR | track-record ledgers `data/track_record.json`, `_nano`, `_combined` (`_1000` not on disk) (`systems.ledger_path`, `:46-52`) | repo only | J-tr (`monthly_track_record.yml:134-213`) |
| MEM | `data/membership_history.json` (8 indices incl. `nifty_500`, `nifty_1000`) | repo; R2 holds the Total Market timeline only (see 2(a)) | J-daily (`daily_sync.yml:278`, `:420`) |

Derived at run time (kept nowhere; rebuilt from the stores above on each cold start): `record_run`
(`model_record.py:113`) → `canonical_book.current_book` (`:27`), `book_series.book_series` (`:39`),
`model_plan.model_plan` (`:16`), `rank_history.snapshots`, `daily_history.frame` (`:46`, SCR frame filled from LONG).

### Last rows of the committed files (read 24 Nov 2026)

| File | Ends | File | Ends |
|---|---|---|---|
| `benchmarks.csv` | 23 Nov | `nse_dii.csv` | day 19 Nov; month Oct 2026 |
| `benchmark_indices.csv` (11 series) | 23 Nov, all | `fii_dii_flows.csv` | 23 Nov (from 6 Nov) |
| `nse_total_market.csv` | 23 Nov | `nsdl_fpi_daily.csv` | 23 Nov |
| `nse_indices_history.parquet` | 20 Nov | `nse_indices_recent.csv` | 23 Nov (one session) |
| `breadth_history.csv` | 23 Nov (both universes) | `qualified_now.json` | `as_of` 23 Nov |
| `signal_tests.json` | `through` 2026-10 | `momentum_health.csv`, `_750`, `_nano` | month 2026-10; `_1000` absent |
| `momentum_health_latest.json` | 30 Oct | `book_exposure.csv` | rebalance 1 Oct |
| `track_record.json` | months Jan-Oct 2026 | `track_record_nano`/`_combined.json` | Oct 2026 only |
| `nse_market_caps.csv`, `nse_all_time_highs.csv` | AsOf 23 Nov | `results_calendar.csv` | 25 Sep - 5 Dec, fetched 24 Nov |
| `reference/nse/corporate_actions_recent.json` | ex-dates 9 Oct - 10 Dec | `backtest_reference.json` | built 22 Nov, long file to 20 Nov |
| `indices_sync_meta.json` | 24 Nov 04:43 | `indices/ind_nifty1000_list.csv` | 1,000 rows, on disk |

## 1. The inventory

Systems: 750, 1000, nano (> ₹2,000 Cr), combined (`src/engine/systems.py`). A row says how a figure differs by system
only where it does. System-wide rules, found in `app.py`: RANK, the price frames and the record are the chosen
system's (`app.py:748-795`, `systems.ledger_path`); under nano and combined `Industry` is replaced by TradingView's
sector from `data/nse_tv_classification.csv` (`app.py:1070-1079`); the members-of-the-day breadth history is joined
under the 750 only (`dashboard_home_view.py:224-226`, `market_view.py:101`).

### 1.1 Header strip (every page; `src/ui/components.py:138`, called at `app.py:1327-1337`)

| Element | Read / made by | Original source | Kept | Job | Ends on |
|---|---|---|---|---|---|
| Market dot and "Nifty Total Market x% above its 200D EMA" | `get_market_regime(TOTAL_MARKET_REGIME, end=last price)` `price_loader.py:309`, `_regime_close` `:299` (`mq.join_market`), called `app.py:1029` | NSE (Total Market from BI, Nifty 500 from BM before 14 Oct 2021); EMA computed by us | repo BI, BM | J-daily | cut at PD (`app.py:1026-1029`); BI 23 Nov |
| Index level (Nifty Total Market) | same, `RegimeData.current_price` | NSE via BI | repo BI | J-daily | PD |
| Universe (count) | `len(rank_df)` `app.py:1322` | computed by us from RANK | R2/release RANK | J-daily | PD (not checked) |
| Above 50D EMA, n (%) | `count_above_ema(rank_df)` `components.py:19`, column `Above 50 EMA` | computed by us (RANK from SCR + NSE2Y) | RANK | J-daily | PD |
| Near 52W high, n (%) | `count_above_ema(rank_df, "Near 52W High")` `app.py:1332` | computed by us (RANK) | RANK | J-daily | PD |
| Prices pill "closes of …" | `_status_pill_html` `components.py:95` from `data_freshness` (`price_as_of` = `pipeline.ranking_as_of(adj_close)`, `app.py:818-819`) | SCR / NSE2Y frame | R2/release SCR | J-scr | PD by definition |
| Market caps chip (in the pill when stale) | `data_freshness` `mcap_as_of`: seeded from `nse_market_caps.csv` AsOf (`app.py:213-218`), overwritten by `fetch_market_caps` `mcap_loader.py:181`: local cache, then **a live NSE PR-zip download at run time** (`:207-250`), then the repo file (`:252`) | NSE PR bhavcopy | repo `data/nse_market_caps.csv`; the live download only in the container's cache (`MCAP_PR_FILE`) | J-daily (file); none (live) | 23 Nov (file); live not checked |
| All-time highs chip | `ath_as_of` from `nse_all_time_highs.csv` AsOf (`app.py:219-224`) | computed by us from SCR + LONG (`sync_data.py:380-399`) | repo only | J-daily (`daily_sync.yml:277`) | 23 Nov |
| "Late:" notice | `stale_prices_notice` `components.py:482` | the prices' date against NSE's calendar | — | — | PD |
| Pending-history notice | `pending_history_notice` `components.py:456` reads `data/screener_pending_history.json` | Screener (members with no history) | repo only | J-scr (`screener_sync.yml:275`) | empty on 24 Nov |
| Shown or not | market line hidden on the Dashboard (`app.py:1336`) | — | — | — | — |

System: Universe, Above 50D EMA and Near 52W high count the chosen system's RANK; the regime line is the same for all.

### 1.2 Dashboard (`src/ui/views/dashboard_home_view.py`, `render_home_view` `:1130`)

Page date: `_fmt.session_of(adj_close)` (`:1146`), the deep SCR frame. Index figures end on `idx_end` = min(PD, Total
Market's last close) (`:1171`). Prices are the deep frame (`app.py:1125`).

| Element | Read / made by | Original source | Kept | Job | Ends on |
|---|---|---|---|---|---|
| Verdict paragraph (brief) | `_brief` `:1574` from the rows below | computed by us | nowhere | — | PD |
| §1 Since inception, after costs | `build_portfolio_history(record…)` `portfolio_view.py:270`, `strategy_total_return` (`:1155-1157`) | computed by us from TR + SCR | TR repo; prices SCR | J-tr, J-scr | PD |
| §1 Nifty Total Market since inception | `di.window_return(market, first_fill, as_of)` `dashboard_insights.py:58` (`:1181-1182`) | NSE via BI | repo BI | J-daily | idx_end; BI 23 Nov |
| §1 Month so far, book | `strategy_mtd` (`:1153-1154`) | computed (TR + SCR) | nowhere | — | PD |
| §1 Month so far, market and five NSE momentum indices | `di.book_month` `:116` on BI series `MOMENTUM_NAMES` (`:53-59`, `:1176-1178`) | NSE via BI (`nse_close_all` rows) | repo BI | J-daily | idx_end; "–" if no close (S148) |
| §1 Months ahead of Nifty Total Market; month bars | `di.book_month`; `_last_month` `:1367` on TR `months` | TR frozen months (Jan-Oct, against Nifty 500) + BI | repo TR, BI | J-tr, J-daily | Oct frozen; live month PD |
| §1 Frozen-span note | `_frozen_span` `:1357` | TR | repo TR | J-tr | Oct 2026 |
| §1 "index is late" sentence | `index_late_note` `:417` | BI's last date | repo BI | J-daily | idx_end |
| §2 Sell / Watch / Clear badges per holding | `exit_watch.assess` `:72` on RANK (`:1184`) | computed (RANK) | RANK | J-daily | PD |
| §2 Rank trail 3M · 1M · now | `_history_inputs` `:212` → `di.rank_trails` `:557`; now = `qualified_ranks` `exit_watch.py:50` | computed from SCR deep frame (`rank_history.snapshots`) and RANK | nowhere (RANK for now) | — | PD |
| §2 Industry status under each name | `mq.leaders_answer` `market_questions.py:504`, `di.industry_bucket` `:432` (`:1199-1207`) | computed from SCR + BM/BI (`join_market`) | nowhere | — | PD |
| §2 Next rebalance, sessions away, fill day | `actions_view.next_rebalance` `:69`, `_sessions_between` `:85` | NSE holidays `data/reference/nse/holidays.csv` (`nse_calendar.published_holidays`) | repo only | hand (catalogue: by hand / audit, 3 Oct) | last holiday 25 Dec 2026; no 2027 rows |
| §2 Sells, buys, holds, next in line | `model_plan` `model_plan.py:16` (`:1186`) | computed (TR book + RANK) | nowhere | — | PD |
| §2 Churn against an average month | `churn_line` `:1104` on `record["month_books"]` (`:1212-1214`) | computed from TR replay | nowhere | — | PD |
| §2 Results due before the check | `rc.for_book(rc.load())` `results_calendar.py:30,61` (`:1215-1219`) | NSE `api/event-calendar` + `api/corporate-board-meetings` | repo `data/results_calendar.csv` only, replaced each night | J-rc | fetched 24 Nov, to 5 Dec |
| §2 Leadership turnover in the top 40 | `di.leadership_turnover` `:498` on `rank_table` | computed (SCR snapshots) | nowhere | — | PD |
| §3 Momentum tiles (12M, 3M, last month, month so far) | `sm.read(system)` `system_momentum.py:90`, `sm.tiles` `:137` (`:1228-1231`); MTD `_month_so_far` `:255` | computed by us from members + SCR/LONG (`build_momentum_health.py:78`) | repo `momentum_health_{750,nano}.csv` | J-mh | Oct 2026; MTD PD |
| ↳ by system | 750: `momentum_health_750.csv` (from 2021); nano: `_nano.csv` (2 rows); 1000: no file → "being collected" (`record_note` `:168`); **combined reads the 750's file** (`:1228`, `sm.SYSTEMS` = 750/1000/nano, `system_momentum.py:32`) | | | | |
| §3 Losing streak, deepest fall | `di.losing_streak` `:200`, `di.momentum_lag` `:605` | same as tiles | same | J-mh | Oct 2026 |
| §3 Long-record line (Nifty 500 since 2010) | `_long_record(spreads)` `:247` on `momentum_health.csv` | computed (Nifty 500 PIT members + LONG) | repo only | J-mh | Oct 2026 |
| §3 Each signal: now, 1M, 3M, own history, flip, months like this | `_signals` `:1686` on BM Nifty 500, breadth, flows, `momentum_health_latest.json`, `qualified_now.json` (`_qualify_saved` `:1637`, else `_qualify_today` `:1649`) | NSE (BM), computed (breadth, qualified) | repo only | J-daily (BM), J-long (qualified, breadth), J-mh (latest) | idx_end; qualified 23 Nov |
| §3 Pass / Not confirmed, average | `_load_tests` `:1594` reads `data/signal_tests.json` | computed (`build_breadth_history.py`) from LONG + BM + momentum_health | repo only | **J-long** (`nse_long_prices.yml:187-193`; the catalogue says J-daily) | through Oct 2026 |
| Same under every system | `qualified_now.json`, `signal_tests.json` and `momentum_health.csv` are Nifty 500 readings shown under all four systems (S193 K3) | | | | |
| §4 Foreign investors this month, headline | `di.flows_summary` `:304` on `nsdl_fpi_daily.csv` cut at PD (`:1234-1235`) | NSDL FPI daily | repo only | J-nsdl | 23 Nov, cut at PD |
| §4 Foreign buying as share of the ranked stocks' value | `di.fpi_share_of_value` `:550`; caps `system_market_caps` (`extra_universe_loader.py`) on `nse_market_caps.csv` then the nano list's month-end figure (`:1246-1252`) | NSDL; NSE market caps | repo only | J-nsdl, J-daily | 23 Nov |
| §4 What heavy foreign buying meant (tested) | `di.flow_evidence` `:357` (NSDL + `momentum_health.csv` + BM) | computed | repo only | J-nsdl, J-mh | Oct 2026 |
| §4 Domestic institutions this month (tile, chart) | `_dii_months` `:1409`, `_dii_now` `:1470` on `nse_dii.csv` | NSE category-wise turnover workbooks | repo only | J-fii (`collect_nse_dii.py`) | day 19 Nov (2 sessions late by rule) |
| §4 DII days NSE's file lacks yet | `_dii_provisional_after` `:1434` on `fii_dii_flows.csv` | NSE provisional FII/DII report (no history at NSE) | repo only | J-fii | 23 Nov |
| §4 FPI bars; NSE-vs-NSDL comparison | `_fpi_bars` `:1480`, `_flow_compare` `:1513` (`fii_dii_flows.csv` against NSDL) | NSDL; NSE provisional | repo only | J-nsdl, J-fii | 23 Nov, cut at PD |
| §5 Size table against momentum indices, 1M 3M 6M | `di.size_table` `:412` on BI + Nifty 100 from IDX (`_nse_close("nifty_100")` `:1844`, `:1166`) | NSE (BI, IDX) | repo BI, IDX copy; R2 `indices/nse_close_all` | J-daily, J-idx | idx_end |
| §5 The book by size bar | `_book_sizes(risk)` `:1810`, `book_risk.book_risk` `:91` on today's weights | computed (book_series) with NSE size lists | nowhere | — | PD |
| §5 Is the rally shared (breadth by size, now/1M/3M) | `di.size_breadth` `:537` on `data/indices/ind_*.csv` today's members (`SIZE_LISTS` `:51-53`, `:1254-1269`) | NSE index lists (today's) + SCR | repo `data/indices/` | J-daily | PD |
| ↳ by system | "Nano Cap" row only when the system prices ≥ 90% of the Nifty 1000's other 250 (`:1265-1270`), i.e. under 1000 | | | | |
| §5 Typical stock: equal-weight and median vs Nifty Total Market | `di.typical_stock` `:514` on ranked SCR prices and BI | computed + NSE | nowhere / BI | J-daily | idx_end |
| §6 Where the book is strong and weak (sector cards, 6M and 1M) | `section_strong_weak` `:1035` on book weights (`book_series.table`) + `leaders_answer` sectors | computed (SCR, RANK industry) | nowhere | — | PD |
| ↳ by system | nano/combined group by TradingView sector (`app.py:1070-1079`) | `nse_tv_classification.csv` | repo; R2 `classifications/tv_history` (J-ev) | | |
| Glance: index moves on one date | `_glance` `:1866` on BI (`TOTAL_MARKET`, nifty50, midcap150, smallcap250, microcap250) | NSE via BI | repo BI | J-daily | idx_end |
| Glance: breadth chart, 200D, members of each date | `_breadth_spec` `:1526`; `pit_breadth.splice(mq._share_above_ema(…), past)` (`:224-233`) on `breadth_history.csv` + `daily_history.frame` | computed from LONG + MEM (history), SCR (live) | repo `breadth_history.csv` only | J-long | 23 Nov file; live part PD |
| Glance: the book's risk (volatility, beta, exit time) | `pr.risk(eq, market)` `portfolio_report.py:172`; `book_risk` (volume from SCR) | computed (book_series, BI) | nowhere | — | PD |
| Glance: Valuation and styles (P/E percentile now/1M/3M; styles' 12M lead) | `indices_glance_rows` `:1827`, `_indices_glance` `:1854` → `indices_page.valuation` `:119`, `styles` `:207`, `Frames.until(idx_end)` | NSE all-indices file (P/E, closes) | R2 `indices/nse_close_all`; repo IDX copy | J-idx | idx_end; IDX 23 Nov |
| Footer "Data to …" | `_fmt.data_to(as_of)` (`:1338`) | PD | — | — | PD |

### 1.3 Actions (`actions_view.render_actions_view` `:249` → `actions_page.render` / `gather` `:360`)

| Element | Read / made by | Original source | Kept | Job | Ends on |
|---|---|---|---|---|---|
| Title and "if today's prices hold" | `actions_page.header` `:132` | computed | — | — | PD |
| Model book / My holdings switch | `render` `:480`, `holdings_store` | the reader's own list or Kite CSV (`actions_view._edit_holdings` `:157`, `pd.read_csv(up)` `:177`) | browser only | — | — |
| Counts: sell, buy, hold, close to a rule | `model_plan` (`:384`) or `plan_rebalance` (my holdings, `:421-422`); `assess` | computed (TR book + RANK) | nowhere | — | PD |
| Next rebalance, sessions away, fill; holiday caveat | `next_rebalance` `actions_view.py:69`, `holiday_caveat` (`:434`) | NSE holidays file | repo `reference/nse/holidays.csv` | hand | 2026 |
| Kite basket: capital, orders, share counts, CSV | `basket` `:90`; value and shares from `book_series` (`:386-391`) | computed (TR + SCR) | nowhere | — | PD |
| Sell rows: industry, rule broken, held since, return since entry | `sell_rows` `:80`, `sells_html`; `Entry Date`, `Return %` from the book | TR replay + RANK | nowhere | — | PD |
| Buy rows: qualified rank, price, 3M, 6M, from 52W high, amount, shares | `buy_rows` `:68`, `qualified_ranks`, `_price` `:64` (RANK `CMP`) | RANK | RANK | J-daily | PD |
| Buy-size limit sentence | `gather` `:411-416` on `TRACK_RECORD_CONFIG` | code (`track_record.py`) | — | — | — |
| Next in line | `plan.next_in_line` | computed (RANK) | nowhere | — | PD |
| Hold rows: rank buffer, 50D EMA and 52W cushions, closest rule, return | `assess` (`EMA cushion`, `High cushion`), `nearest_rule` | RANK (`% 50 EMA`, `% High`) | RANK | J-daily | PD |
| Hold rank trail 3M · 1M · now | `di.rank_trails` (`:433`) | computed (SCR snapshots) + RANK | nowhere | — | PD |
| What could still change: board meetings due before the fill | `_events` `:453` → `rc.load()` | NSE event calendar | repo `results_calendar.csv` (rolling 60 days, replaced nightly) | J-rc | to 5 Dec |
| ↳ ex-dates due before the fill | `_events` reads `data/reference/nse/corporate_actions_recent.json` (`:471`) | NSE corporate-actions feed | repo only | J-ref | ex-dates to 10 Dec |
| The book after the trades: sector and size | `section_after` `:185`; `_sizes` `:442` (`bx.size_of` on MEM) | MEM (NSE lists) + RANK industry | repo MEM | J-daily | PD |
| Evidence: what swaps have added (1M, 3M vs Total Market) | `swap_evidence.from_record` `:103` on TR history, SCR, BI, `former_members.load()` (`:402-409`) | computed from TR + SCR + `former_member_prices.parquet` + BI | repo (TR, former members, BI) | J-tr, J-daily | PD / idx |
| Buy candidates (collapsed qualified list) | `render_qualified_view` `qualified_view.py:70` | RANK | RANK | J-daily | PD |
| Footer: data date, gap and short-history counts | `footer` `:329`, `gap_count` `components.py:585` | RANK flags | RANK | J-daily | PD |
| ↳ by system | before inception (nano/combined/1000) the model book is replaced by a note (`app.py:1097-1110`, `:1240`) | | | | |

### 1.4 Screener (`ranking_view.render_ranking_view` `:225`)

| Element | Read / made by | Original source | Kept | Job | Ends on |
|---|---|---|---|---|---|
| Title (count passing both filters) | `screener_title` `:710`, `_passes` `:706` | RANK filter columns | RANK | J-daily | PD |
| Lede ("book buys the top 20 … keeps … top 40") | `screener_lede` `:728`; numbers typed / `TRACK_RECORD_CONFIG` | code | — | — | — |
| Signal chips | `components.signal_chips_html` with `regime` | BI/BM regime | repo | J-daily | PD |
| Top-50 moves: in, out, biggest jumps | `top50_changes` `:638`, `biggest_jumps` `:655`, `render_top50_changes` `:862` | RANK (`Rank (-1M)`) | RANK | J-daily | PD vs one month back (`_month_ago` `:682`) |
| New-high counts | `_new_high_counts` `:634` on the SCR frame | computed (SCR) | nowhere | — | PD |
| Table: Rank, Price (`CMP`), 1/3/6/9/12M Return, Sharpe, falls, filters | `rank_df` columns via `render_screener_table` (`screener_table.py:58`, `:294-430`) | computed by us from SCR, filled from NSE2Y (`price_source.ranking_frames` `:289`) | RANK | J-daily | PD |
| Table: Rank 3M / 1M ago, Rank Δ 1M | `Rank (-3M)`, `Rank (-1M)`, `Rank Δ 1M` (`screener_table.py:309`, `:345`) | RANK | RANK | J-daily | PD |
| Table: Qualified #, Qualified 3M / 1M ago | `with_book_columns` `:762` (`qualified_ranks`), `qualified_trail` `:788` on the deep frame | RANK + computed (SCR) | nowhere for the trail | — | PD |
| Table: Held | `book_symbols` from `_screener_book` (`app.py:1129-1139`, `current_book`) | TR replay | nowhere | — | PD |
| Table: Market Cap (Cr) | `Market Cap (Cr)` (`screener_table.py:349`) | NSE PR bhavcopy (written into RANK at precompute; live NSE if the app computes) | RANK; repo `nse_market_caps.csv`; R2 `nse/market_caps` | J-daily, J-col | 23 Nov |
| Table: % 50 EMA, % High (52W) | `screener_table.py:365`, `:409-430` | computed (SCR; highs from `nse_all_time_highs.csv` for the all-time high) | RANK | J-daily | PD |
| Table: Sector / Industry | RANK `Industry` (NSE's list), `TV_Sector`/`TV_Industry` from `nse_tv_classification.csv` (`app.py:1049-1066`) | NSE index lists; TradingView labels | repo `data/indices/`, `nse_tv_classification.csv`; R2 `classifications/tv_history` | J-daily | — |
| Data line (behind, deferred session) | `data_line` `:813`, `behind_phrase` `:802` | metrics of the SCR frame | — | — | PD |
| System footnote (what is ranked, members not yet ranked) | `system_note` `:666` via `app._system_line` `:1083` | MEM / `ind_nifty1000_list.csv` / `ind_nanocap_list.csv` vs RANK | repo | J-daily | — |
| CSV download | `_rankings_csv` `:158`, `export_columns` `:215` | RANK | RANK | J-daily | PD |
| ↳ by system | each system its own RANK file; 1000's 250 extras from SCR extras (`sync_screener.py`) | | | | |

### 1.5 Stock page (`/screener?stock=`; `stock_view.render_stock_view` `:483`)

| Element | Read / made by | Original source | Kept | Job | Ends on |
|---|---|---|---|---|---|
| Kicker, title, lede (close, 12M vs market) | `head_html` `:261`, `stock_lines.kicker` `:121`, `title` `:134`, `lede` `:141` | RANK + BI | RANK, BI | J-daily | PD (`:511-513`, market cut at PD `:553`) |
| Tiles: close, 1M, 12M, rank, rank 3M ago, market cap | `stock_lines.tiles` `:167` on RANK | RANK | RANK | J-daily | PD |
| Place among the qualified "of N"; 3M / 1M ago | `qualified_ranks` (`:528-530`), `with_book_columns` (`:531-533`) | RANK + SCR deep frame | nowhere (trail) | — | PD |
| Rules: 50D EMA, 52W high, rank; ladder | `rules_html` `:309`, `stock_lines.rules` `:295`, `ladder` `:280`, `assess` (`:544`) | RANK + SCR | RANK | J-daily | PD |
| Results and ex-dates before the check | `_calendar` `:209` (`rc.load`), `_nse_action_list` `:177` (`data/nse_prices/actions.parquet`) | NSE event calendar; NSE corporate actions | repo `results_calendar.csv`; repo `nse_prices/actions.parquet` (from R2 `nse/corporate_actions`) | J-rc; J-tr (`monthly_track_record.yml:213`) | to 5 Dec; actions file not dated here |
| In the model book: return since entry, weight | `_holding` `:188` (`book_series` table) | TR + SCR | nowhere | — | PD |
| Returns by window vs Nifty Total Market and the typical stock | `returns_html` `:346`, `stock_lines.windows` `:466`, `market_return` `:456` | RANK `{m}M Return`; BI | RANK, BI | J-daily | PD |
| Price chart, volume, 50D EMA, relative strength | `render_price_chart` (`:592`); `daily_history.stock_close` `:69` (SCR filled from LONG); volume SCR | Screener (closes, NSE+BSE volume), NSE long file | R2/release SCR, LONG | J-scr, J-long | PD |
| Sessions above the EMA (price heading) | `sl.sessions_above` `:557` | computed | nowhere | — | PD |
| Industry peers | `industry_html` `:381`, `_peers_note` `:132` | RANK | RANK | J-daily | PD |
| Data checks | `data_html` `:415` (`sl.DataChecks`) | RANK flags | RANK | J-daily | PD |
| Ranks in the other systems | `_elsewhere_links` `:456`, `_other_ranks` `:469` (`app._other_rankings` `:1185`, same-session RANK of each other system) | RANK per system | R2/release | J-daily | same session only |
| Not ranked: why | `_render_not_ranked` `:427` (members, other rankings) | MEM lists + RANK | repo, RANK | J-daily | PD |

### 1.6 Portfolio (`portfolio_view.render_portfolio_view` `:468` → `portfolio_page.gather` `:125`)

Prices: the deep SCR frame (`app.py:1168-1174`). Index series cut at PD, Total Market and Momentum 50 not further
(`portfolio_page.py:133-139`).

| Element | Read / made by | Original source | Kept | Job | Ends on |
|---|---|---|---|---|---|
| Title, sub ("₹1 Cr was put in on …") | `header_title` `:350`, `header` `:365` | TR + SCR; BI | TR repo | J-tr | PD |
| Header KPIs: value, since start, vs Total Market, month so far, below peak | `header` `:365-405` from `book_series`, `pr.periods`, `metrics.drawdown` | computed (TR + SCR), NSE (BI) | TR, BI | J-tr, J-daily | PD |
| Provenance / reconstructed note (1000) | `_provenance` `:319`, `reconstructed_note` `:335` | MEM `nifty_1000` note | repo MEM | J-daily | — |
| Current book table: qty, entry price, price, value, weight, today, P&L from the fill, since entry | `holdings_spec` `:421` on `book_series.table` | TR + SCR | nowhere | — | PD |
| ↳ vs 50D EMA, from 52W high | RANK `% 50 EMA`, `% High` (`:433-434`) | RANK | RANK | J-daily | PD |
| ↳ Sector · size | `record_sector_map` `model_record.py:32`; `bx.size_of` on MEM (`:151-152`) | NSE lists | repo MEM | J-daily | PD |
| ↳ Rank 3M · 1M · now | `di.rank_trails(series.prices, …, now=qualified_ranks)` (`:142-143`) | SCR + RANK | nowhere | — | PD |
| Sector & size now, against the ranked stocks' weights | `section_exposure` `:504`; `_market_weights` `:176` (`system_market_caps` on `nse_market_caps.csv`) | NSE market caps | repo only | J-daily | 23 Nov |
| Sectors and size at every rebalance (heat table) | `data/book_exposure.csv` via `bx` (`:154-160`) | computed by us at each freeze (`update_track_record.py`) | repo only | J-tr | rebalance 1 Oct + live month computed |
| ↳ by system | `book_exposure.csv` is the 750's; other systems computed live from their tradebook (`:154-160`) | | | | |
| Returns by period: book, Total Market, lead, Momentum 50 | `section_returns` `:566`, `pr.periods` `portfolio_report.py:50` | TR + SCR; BI (`nifty_total_market`, `nifty500_mom50`) | TR, BI | J-tr, J-daily | PD; Total Market may end earlier (note `:599-603`) |
| This year: book, YTD indices, size mix | `pr.ret` `:38`, `pr.size_mix` `:263` on `book_exposure` + BI (`YTD_ROWS`, `SIZE_INDEX`) | NSE via BI | repo BI | J-daily | idx end |
| Growth of ₹100: book, Momentum 50, Total Market | `section_equity` `:691` | computed + BI | nowhere / BI | — | PD |
| Drawdown, max drawdown | `metrics.drawdown`, `max_drawdown` | computed | nowhere | — | PD |
| Volatility, beta | `pr.risk` `:172` | computed vs BI | nowhere | — | PD |
| Calendar returns: month bars and grid | `month_bars_spec` `:848`, `pr.calendar` `:235` | TR frozen months + live | repo TR | J-tr | Oct frozen + live |
| Day by day vs Total Market, last 20 sessions | `:862-881` | computed + BI | nowhere | — | PD |
| Trades: closed, open, rebalances; history chart | `section_trades_top` `:940`, `history_spec` `:982` | TR replay (`record_run`) | nowhere | — | PD |
| Systems side by side | `section_systems` `:1028`, `_systems` `:221` (each ledger `load_ledger(ledger_path(sid))`, prices `track_record_view._comparison_price_frame` `:19`, SCR per system) | TR files + SCR | repo TR | J-tr | PD; 1000 has no ledger yet |
| Rule numbers in notes (20, 40, 20%, 50D) | `TRACK_RECORD_CONFIG` | code | — | — | — |

### 1.7 Market (`market_view.render_market_view` `:88` → `market_questions_view.render_market_page_questions` `:513`)

Prices: `daily_history.frame(adj_close)` (SCR filled from LONG, `app.py:1156-1160`). The market line is Nifty Total
Market joined to the Nifty 500 before 14 Oct 2021 (`market_view.py:105-110`, `market_close` `:105`).

| Element | Read / made by | Original source | Kept | Job | Ends on |
|---|---|---|---|---|---|
| Title answering both questions | `render_market_page_questions` `:513` | computed | — | — | PD |
| Trend: Total Market vs 200D EMA, now and 1M ago | `mq.ema_gap` `market_questions.py:380`, `trend_answer` `:431` | NSE (BI joined to BM) | repo BI, BM | J-daily | PD |
| Trend: vs 10-month average; month-end reading | `ten_month_today` `:337`, `ten_month_gap` `:317`, `last_month_end` `:359` | same | same | J-daily | PD |
| From the 52W high: market and size indices | `mq.from_high` `:391`; sizes `size_closes` `market_questions_view.py:145` (BI) | NSE (BI) | repo BI | J-daily | PD |
| Size trend table | `size_trend_html` `:291` | NSE (BI) | repo BI | J-daily | PD; late names said |
| Participation: share above 200D / 50D EMA, net new highs (history + live) | `_answers` `:83`, `pit_breadth.splice(mq._share_above_ema` `:172`, `_net_new_highs` `:183`) | computed: LONG + MEM (history, `breadth_history.csv`), SCR (live) | repo `breadth_history.csv` | J-long | 23 Nov file; live PD |
| ↳ by system | history spliced only under 750 (`market_view.py:101`, `:153-154`) | | | | |
| Share beating Nifty Total Market over 12M; median stock | `mq._beat_index_12m` `:225` on `total_market()` `market_questions_view.py:128` (`nse_total_market.csv`, then BI after its last row) | NSE all-index archive; NSE via BI | repo `nse_total_market.csv`, BI | J-daily (`daily_sync.yml:432`) | 23 Nov; misses 7 weekend sessions (FIGURE_INVENTORY difference 5) |
| Which sectors lead | `mq.leaders_answer` `:504` | computed (SCR, RANK industry) vs market | nowhere | — | PD |
| Breadth charts (share above 200D, weekly, net new highs) | `_chart_series` `:350`, `_breadth_charts` `:386` | same as participation | repo `breadth_history.csv` | J-long | PD |
| "Joined" note | `joined_note` `:114` | BI first date | repo BI | J-daily | — |
| Today's charts: participation above each MA | `compute_ma_breadth` (`market_view.py:142-144`) on `adj_close` | computed (SCR) | nowhere | — | PD |
| Participation by index (Nifty 50 … Microcap 250, NANO250) | `index_members(rank_df, …)` `:30` on RANK tags (`:162-190`) | NSE lists via RANK | RANK | J-daily | PD |
| New highs against new lows | `compute_hl_timeseries` (`:145`) | computed (SCR) | nowhere | — | PD |
| Stocks making new highs and lows, 20 sessions | `get_recent_hl_events` (`:196`) | computed (SCR + RANK) | nowhere | — | PD |
| Footer: data date, ranked, gaps, short histories | `:211-214` | RANK | RANK | J-daily | PD |

### 1.8 Indices (`indices_view.render_indices_view` `:369`; system-independent)

All figures read IDX through `indices_data.frames()` (`indices_data.py:23`): `data/nse_indices_history.parquet` +
`data/nse_indices_recent.csv`, with `data/reference/nse_index_{aliases,corrections,groups,missing_sessions}.csv`
(`nse_indices.py:36-41`). Original source: NSE's daily all-indices file (`ind_close_all_DDMMYYYY.csv`). Kept: R2
`indices/nse_close_all` + the repo copy. Job: J-idx. Ends: 23 Nov (recent file).

| Element | Read / made by | Original source | Kept | Job | Ends on |
|---|---|---|---|---|---|
| Head: Nifty 500 P/E and its percentile since 31 Mar 2021 | `head` `:68`, `indices_page.valuation` `:119`, `percentile` `:96` | NSE (P/E column) | IDX | J-idx | 23 Nov |
| Valuation table: P/E, P/B, yield, now / 1M / 3M; young-index rows | `section_valuation` `:105`, `young_valuation` `:149` | NSE | IDX | J-idx | 23 Nov |
| "Derived" sessions marked | `derived` column, `nse_index_missing_sessions.csv` | NSE next-day points change (11 of 12 days) | repo reference | hand (#587) | — |
| Styles leading/trailing parents, 12M | `section_styles` `:162`, `styles` `:207`, `lead_12m` `:192` | NSE | IDX | J-idx | 23 Nov |
| How long a style can lag | `section_lag` `:190`, `years_led` `:238` | NSE | IDX | J-idx | 23 Nov |
| Calendar years | `section_years` `:229`, `calendar_lead` `:197` | NSE | IDX | J-idx | year to date 23 Nov |
| Size year by year | `section_size` `:255`, `size_years` `:253` | NSE | IDX | J-idx | 23 Nov |
| Every index: 1/3/6/9/12M, from 12M high, P/E (112 indices) | `section_every` `:304`, `every_index` `:292`, `ret` `:81`; late names `late_names` `:329` | NSE | IDX | J-idx | each index's last session |
| Index groups (Broad, Sector, Theme, Strategy, not a stock index) | `nse_index_groups.csv` (`nse_indices.groups` `:312`) | by hand with evidence | repo only | hand | — |

### 1.9 Sectors (`sector_view.render_sector_view` `:650`, `_model` `:179`)

Prices: `daily_history.frame` cut at PD (`:664-668`); the market line `total_market()` (`:672`).

| Element | Read / made by | Original source | Kept | Job | Ends on |
|---|---|---|---|---|---|
| Head and lede ("Nifty Total Market rose x%") | `head` `:216`, `peer_index.size_gap` | NSE (`nse_total_market.csv`, BI after it) | repo | J-daily | 23 Nov; weekend sessions missing (difference 5) |
| Each sector's lead over the ranked stocks, 6M and 1M (now, 1M, 3M ago) | `section_lead` `:251`, `sectors_page.leads` `:107` | computed (SCR/LONG + RANK industry), equal-weighted | nowhere | — | PD (`ld.when`) |
| The ranked stocks equal-weighted, 1/3/6/12M | `sectors_page.ew_return` `:48` | computed | nowhere | — | PD |
| Share above 200D EMA, all and per sector, now/1M/3M | `sectors_page.ema_shares` `:257` (today's members) | computed | nowhere | — | PD |
| NSE sector indices: returns, from 12M high, P/E | `section_indices` `:375`, `sector_indices` `:176`, `from_high` `:54`; map `data/reference/nse_sector_index_map.csv` (`sector_map` `:34`) | NSE (IDX); map by hand (#593) | IDX; repo map | J-idx; hand | `f.until(ld.when)` |
| Broad or narrow (sector index vs its ranked stocks) | `section_broad` `:333`, `broad_or_narrow` `:211`, `pair_series` `:229` | NSE + computed | IDX | J-idx | PD |
| Month by month, each sector less the 750 | `section_months` `:428`, `mq.industry_months` `:626` | computed | nowhere | — | PD |
| Leadership map | `section_map` `:500`, `leadership_views` `:278` | computed | nowhere | — | PD |
| Inside a sector (board, shares) | `section_inside` `:523`, `industry_board` `:94` | RANK + computed | RANK | J-daily | PD |
| Stocks in a sector: table with Qualified # | `render_screener_table` on RANK (`:693-697`) | RANK | RANK | J-daily | PD |
| Footer | `:699-701` | RANK | RANK | J-daily | `ld.when` |
| ↳ by system | nano/combined: TradingView groupings, no NSE-index sections (`tv_sectors` `:50`, `section_only_nse` `:423`) | `nse_tv_classification.csv` | repo | J-daily | |

### 1.10 Watchlist (`watchlist_view.render_watchlist_view` `:123`)

| Element | Read / made by | Original source | Kept | Job | Ends on |
|---|---|---|---|---|---|
| The saved names | `watchlist_store` (browser) | the reader | browser only | — | — |
| Search options (every NSE equity) | `search_options` `:52`, `_nse_lists` `:83` (`nse_identity`: `equity_l.csv`, `symbolchange.csv`) | NSE listed equities | repo `reference/nse/` | J-ref | 23 Nov copy |
| Screener table for the saved names | `with_book_columns` + `render_screener_table` (every Screener column, 1.4) | RANK + SCR | RANK | J-daily | PD |
| Plan lines (buy, sell, hold, next in line) | `_lines_section` `:240`, `watchlist_lines.lines()`, `model_plan` | computed | nowhere | — | PD |
| Not ranked here; ranked in another system | `_not_ranked_section` `:272` (`other_rankings`) | RANK per system | R2/release | J-daily | same session |
| Results due before the fill | `_fill_section` `:314` (`rc.load()` `:326`) | NSE calendar | repo `results_calendar.csv` | J-rc | to 5 Dec |
| Footer | `_foot` `:335`, `render_data_quality_footer` | RANK | RANK | J-daily | PD |

### 1.11 Backtest (`backtest_view.render_backtest_view`, page code `:1089-1135`; system-independent, `app.py:1221-1232`)

| Element | Read / made by | Original source | Kept | Job | Ends on |
|---|---|---|---|---|---|
| Settings line ("tested …") | `tested_line` `:490`, `_settings_form` `:300` | code defaults (`TRACK_RECORD_CONFIG`, app weights) | — | — | — |
| History bounds, universe membership | `_history_bounds` `:221`; `iu.index_history(key)` (`:250`) on MEM | NSE lists (MEM) | repo MEM | J-daily | — |
| Prices for the run | `_long_file` `:162` → `nse_long.load` (R2 first, release fallback) | NSE bhavcopy, adjusted; BSE fills NSE-only gaps (S38) | R2 LONG, release | J-long | 20 Nov (`backtest_reference.json`) |
| Liquidity floor (traded value) | `_long_value` `:170`, `nse_long.average_value` (`:206-208`) | NSE traded value | R2 `prices/nse_long_value`, release | J-long | same |
| §1 Ahead of the Nifty 500: a year, the Nifty 500's, lead pts | `head` `:496`, `section_lead` `:520`, `bp.summary` | computed vs BM (`fetch_benchmark_history(period="max")` `:1103`) | repo BM | J-daily | the run's last month-end |
| §1 Growth of ₹100 (log) chart | `bp.weekly_chart` (`:947`) | computed vs BM | nowhere | — | month-end |
| §1 Universe index row (e.g. Nifty 500's own index; Nifty 50 from BM) | `gather` `:885-899` (IDX `close[ikey]`) | NSE | IDX, BM | J-idx, J-daily | month-end |
| §1 Since Nifty200 Momentum 30 / Total Market went live | `bp.window` (`:915-930`) on IDX `nifty200_momentum_30`, `nifty_total_market` | NSE | IDX | J-idx | month-end |
| §1 Month so far | `meta["strategy_mtd"]` (`:932-937`) | computed | nowhere | — | PD of LONG |
| §1 Dividend yield of the Nifty 500 | `store.dy["nifty_500"].mean()` (`:938-941`) | NSE all-indices file | IDX | J-idx | 23 Nov |
| §2 Falls from a peak; below peak now | `section_falls` `:584`, `bp.falls`, `below_peak_now` | computed vs BM | nowhere | — | month-end |
| §3 Year by year (rule, Nifty 500, Total Market, universe index) | `section_years` `:635`, `bp.years_table` (`:909`) | computed + BM + IDX | nowhere | — | month-end |
| §4 What it depends on: costs, monthly reset, after tax | `section_depends` `:724` on `data/backtest_reference.json` (`_reference` `:214`) | computed by us (`build_backtest_reference.py`) from LONG | repo only | J-bt | built 22 Nov, window to 30 Oct |
| ↳ "This rule, Nifty Total Market" row | `reference["total_market_universe"]` (`:924-926`) | same | repo | J-bt | 30 Oct |
| §5 Can it be trusted (stale exits, short books) | `section_trust` `:792`, `bp.stale_exits`, `short_books` | computed | nowhere | — | month-end |
| §6 Trades; trade log; ZIP download | `section_trades_head` `:841`, `_download` `:1024` | computed | nowhere (download) | — | month-end |
| Footer | `foot` `:861` (`long_last`, `indices_as_of`) | LONG, IDX dates | — | — | 20 Nov / 23 Nov |

### 1.12 Configuration (`config_view.render_config_view` `:651`)

| Element | Read / made by | Original source | Kept | Job | Ends on |
|---|---|---|---|---|---|
| Index sync: last synced, stocks in the files, ranked now | `_section_data_sync` `:239`; `get_sync_metadata` (`indices_loader.py:207`) reads `data/indices_sync_meta.json`; `len(rank_df)` | NSE index lists | repo only | J-daily | 24 Nov 04:43 |
| Freshness table (prices, market caps, all-time highs) | `_freshness_table` `:122`, `data_freshness` (`components.py`) | as header | | | PD |
| File dates table (11 files, rule, status) | `file_dates` `:208` on `FILE_RULES` `:152-174` | each file's last row | repo | per file | per file |
| ↳ row "NSE closes for gaps" | `nse_prices/closes.parquet` (`:171`) — **gitignored** (`.gitignore:102`), so a fresh server reads "Not on this server" (`:217-218`) unless a loader has cached it there | NSE | R2 NSE2Y, release | J-tr | not checked live |
| System chooser and its captions | `:278-300`; `membership_summary` (`extra_universe_loader`) on `nanocap_membership.json`, `NIFTY_1000_PATH` | our month-end list; NSE's Nifty 1000 | repo only | J-daily | — |
| Momentum score weights (sliders, pill) | `_section_momentum_signal` `:409`, `DEFAULT_LOOKBACK_WEIGHTS` | code | — | — | — |
| Backtest caps (sector, stock) | `_section_portfolio_risk` `:509`, `DEFAULT_SECTOR_CAP`, `DEFAULT_STOCK_CAP` | code | — | — | — |
| Data health: corporate actions adjusted, missed splits, demergers | `_section_data_health` `:566`, `load_events()` (`corporate_actions.py:171`, `data/corporate_actions_log.json`) | Screener vs NSE action checks | repo; R2 `corporate_actions/evidence` (J-ev) | J-scr, J-daily | — |
| Data-quality footer | `render_data_quality_footer` | RANK | RANK | J-daily | PD |

### 1.13 Guide (`guide_view.render_guide_view` `:239`, `_body` `:46`)

| Element | Read / made by | Original source | Kept | Job | Ends on |
|---|---|---|---|---|---|
| Book size, keep rank, weights, caps, cost, EMA, warm-up dates | `_body` `:47-76` from `TRACK_RECORD_CONFIG` | code | — | — | — |
| "within 20%" and the worked example (+20.0% vs +5.0%) | typed in `_body` | text | — | — | — |
| High basis sentence | `_body` `:70` (`high_basis` from metrics) | SCR frame | — | — | PD |
| Data-quality footer: ranked, gaps, short histories | `:245-248` | RANK | RANK | J-daily | PD |

## 2. Across all rows

### (a) Inputs we could not download again that are not in R2 (R2 content not checked; judged from code)

Method: every `r2_publish.py --dataset` in `.github/workflows/` and `scripts/` was listed (datasets: `prices/screener`,
`snapshots/rankings*`, `prices/nse_long_*`, `nse/*` via `nse_collect.py:49-55`, `nse/closes_2y`, `indices/nse_close_all`,
`bse/daily`, `prices/ss`, `trading_sessions/*`, `market_caps/*`, the J-ev set). None of the files below is a source or
an input of those publishes, except where the row says so. "Git only" means the repository's history is the only
copy (GitHub, not R2).

| # | Item | Why it cannot be fetched again | Where it is now | Evidence |
|---|---|---|---|---|
| a1 | NSE provisional FII/DII, `data/fii_dii_flows.csv` | NSE keeps no history; the file is the history from 6 Nov 2026, first reading kept | git only | `collect_fii_dii.py:7-12`; `fii_dii.yml:61` commits it; no `r2_publish` names it (grep of workflows) |
| a2 | Track-record ledgers `data/track_record.json`, `_nano`, `_combined` (and `_1000`, `track_record_shadow*` and `data/record_books.json` when written; neither is on disk on 24 Nov) | frozen months are a record, not a recomputation: Jan and Feb 2026 replay differently and the owner accepted the drift (`src/engine/parity_accepted_drift.json`) | git only | `monthly_track_record.yml:213`, `:233` (git add); no R2 publish of `track_record` (grep `.github/workflows/r2*.yml`, `scripts/r2_*.py`: none) |
| a3 | `data/book_exposure.csv` | rows "once written are never rewritten" (catalogue); size by the lists of that date | git only | `monthly_track_record.yml:213`; no R2 publish |
| a4 | Point-in-time membership other than the Total Market: `membership_history.json` `indices.nifty_500`, `nifty_1000` (and the five size indices' own entries) | Nifty 1000 is point in time from the first nightly list (S175); a missed night is lost | git only. R2 gets the top-level Total Market timeline (`r2_historical_evidence_bootstrap.py:149-153`, `_membership_intervals` reads only `baseline`/`changes` `:74-86`) and five size lists rebuilt from their CSVs' git history (`:155-166`) | `TRACKED_INDEX_PATHS` (`build_membership_history.py:36-43`) has no Nifty 1000 or Nifty 500 |
| a5 | NSE's Nifty 1000 list `data/indices/ind_nifty1000_list.csv` | NSE publishes only today's list | git only | not in `TRACKED_INDEX_PATHS` (above), so not in R2 `indices/constituents/*` |
| a6 | Our > ₹2,000 Cr month-end lists `data/nanocap_membership.json`, `data/indices/ind_nanocap_list.csv` | built from that month's NSE caps and equity list; reproducible only while those inputs are kept | git only | same; `daily_sync.yml:215` (`build_extra_universe.py`); no R2 publish |
| a7 | NSE board-meeting calendar as announced, `data/results_calendar.csv` | NSE's API serves ~4 weeks ahead and 60 days back; the file is **replaced** each night (`collect_results_calendar.py:200` `new.to_csv`), so dates as first announced survive only in git | git only | `results_calendar.yml:39` |
| a8 | NSE feeds as of each day: `data/reference/nse/corporate_actions_recent.json`, `equity_l.csv`, `symbolchange.csv`, `namechange.csv` | NSE serves today's lists | git only (daily commits, `nse_reference_sync.yml:61`) | not a publish input; Actions reads the actions file (`actions_page.py:471`) |
| a9 | `data/reference/nse/nifty1000_notices.json`, `anchor_checks.jsonl` | records of what NSE published on a day | git only | `nse_reference_sync.yml:61`; catalogue: records for people |
| a10 | Hand corrections `data/nse_prices/notes.json`; `data/reference/*` evidence tables (`nse_index_*`, `nse_sector_index_map.csv`, `historical_industries.csv`, `tejhq_actions.csv`) | hand work with evidence | git only | not publish inputs (grep) |
| a11 | The long file's BSE fills (`bse_fill_*.csv`) | the audit zip `long_price_audit_latest.zip` goes to the release with `--clobber` | release only, overwritten each build | `nse_long_prices.yml:232` |
| a12 | Live NSE market caps fetched by the app at run time (`mcap_loader.py:207-250`) | not kept beyond the container's cache file; the header chip may report its date | container only | the committed `nse_market_caps.csv` is in R2 (`market_caps/nse_history`, J-mcap), so the value is kept, not the app's own reading |

Lower risk, also not in R2 but re-downloadable or recomputable (named so they are not missed): `nse_dii.csv` (NSE
archives each session's workbook, `collect_nse_dii.py:4-6`); `nsdl_fpi_daily.csv` (`nsdl_fpi.py --backfill`,
`:154`); `breadth_history.csv`, `signal_tests.json`, `qualified_now.json` (J-long from LONG + MEM); `momentum_health*`
(J-mh); `backtest_reference.json` (J-bt); `benchmarks.csv` and `benchmark_indices.csv` (from R2
`indices/nse_close_all`, except their Kaggle/SS/Screener rows before 21 Feb 2012 and the Screener rows after the
store's last day: **those older rows are not in R2**, judged from `DATA_CATALOGUE.md:62-63`).

### (b) Stored twice, or never read

Reader counts come from a grep of each `data/` file's base name across `src`, `app.py`, `scripts`, `r2`, `agent`,
`nse_index_rebuild`, `.github` and `tests` (run 24 Nov). A file read only through a built name is noted.

| # | Item | Finding | Evidence |
|---|---|---|---|
| b1 | Nifty Total Market close, four copies | `data/nse_total_market.csv`, BI rows `nifty_total_market`, IDX parquet/recent, R2 `indices/nse_close_all`. They differ: the CSV lacks NSE's 7 weekend sessions, so Market and Sectors read the session before (FIGURE_INVENTORY difference 5) | `market_questions_view.py:128-143`; catalogue `:63`, `:71` |
| b2 | Index store twice (already in the checklist) | R2 `indices/nse_close_all` and the repo copy; S172 open | `nse_indices.yml:60-81` |
| b3 | Nifty 500 / Nifty 50 closes twice | `data/benchmarks.csv` NSE rows from 21 Feb 2012 are a copy of IDX (`--nse-history`, S168) | catalogue `:62` |
| b4 | Market caps four ways, two with no reader | `data/nse_market_caps.csv` (read), R2 `nse/market_caps` (read by `build_extra_universe.py`), R2 `market_caps/nse_history` (no app reader; catalogue `:30`), R2 `market_caps/nse_snapshot` (no reader; catalogue `:32`) | `r2_market_cap_history.yml`; `r2-historical-evidence-bootstrap.yml:131` |
| b5 | Membership three ways in R2 with no app reader | `indices/membership/*`, `indices/constituents/*`, `universes/point_in_time` (≈8 MiB) | catalogue `:31-32` (S195 grep); `r2-historical-evidence-bootstrap.yml:80-110` |
| b6 | R2 `prices/ss` | no reader of the R2 copy; the jobs read the release's `ss_*` | catalogue `:25`; `ss_sync.yml:126`, `screener_sync.yml:180` |
| b7 | R2 `nse/source_checks` | no code reads the tables | catalogue `:29` |
| b8 | `data/reference/nse/CHANGES.json`, `MANIFEST.json`, `anchor_checks.jsonl`, `namechange.csv`, `nifty1000_notices.json` | src=0 readers; scripts read only as their writer's previous state or not at all | grep counts (src=0); catalogue `:53`, `:55` |
| b9 | `data/reference/tejhq_actions.csv` | read only by the long-file build | src=0, scripts=2 (`build_nse_long_prices.py:88`, its builder) |
| b10 | `data/membership_notices.json` | read by scripts only (the membership build); no page | src=0, scripts=2, tests=3 |
| b11 | Release and R2 pairs kept on purpose (not a gap; named so they are not counted twice) | RANK, SCR, LONG, NSE2Y each in R2 and the release (R2 first, release fallback) | `app_source.py:1-19`; `nse_long.py:20-22` |
| b12 | `data/momentum_health_750.csv`, `_nano.csv` | src=0 by literal name but read through `system_momentum.path` (`:40`): **read** | `system_momentum.py:40`, `:90` |

## 3. The five most important gaps

1. **The track record is in git only** (a2, a3). The frozen ledgers, `record_books.json` and `book_exposure.csv` have
   no R2 copy, and the frozen months cannot be recomputed to the same numbers (accepted drift, Jan and Feb 2026).
   Evidence: `monthly_track_record.yml:213`; no `r2_publish` names them.
2. **Point-in-time membership beyond the Total Market is in git only** (a4, a5, a6): the Nifty 500 and Nifty 1000
   timelines in `membership_history.json`, NSE's Nifty 1000 list and our > ₹2,000 Cr lists. The R2 evidence job
   publishes only the top-level Total Market timeline and five size lists. A missed night of the Nifty 1000 list is lost.
3. **NSE's provisional FII/DII and the announced board-meeting calendar** (a1, a7): NSE keeps no history of the
   first, and the second is replaced nightly; both read by the Dashboard and Actions, both git only.
4. **Nifty Total Market is kept four ways and the copies disagree** (b1): the 7 weekend sessions missing from
   `nse_total_market.csv` move Market's and Sectors' windows by a session against the Dashboard, Indices and
   Portfolio.
5. **R2 pays for datasets nothing reads while the record is missing** (b4-b7): `market_caps/nse_history`,
   `market_caps/nse_snapshot`, the membership/constituents/universe set, `prices/ss`, `nse/source_checks`.

## 4. Other findings while reading (not under (a) or (b); for routing)

1. **Combined's Dashboard momentum tiles are the 750's** (`dashboard_home_view.py:1228`: `system if system in sm.SYSTEMS
   else SYSTEM_750`; `system_momentum.py:32` lists 750, 1000, nano). The page does not say so (not checked on the live page).
2. **Nifty 1000 has no `momentum_health_1000.csv` and no `track_record_1000.json`** on 24 Nov: its tiles read "being
   collected" and Portfolio's "systems side by side" has no ledger for it (expected until the December freeze, S175).
3. **The catalogue names the wrong writer for `signal_tests.json`** (`DATA_CATALOGUE.md:79` says `daily_sync`); the
   code runs `build_breadth_history.py` in `nse_long_prices.yml:187-193`.
4. **Configuration's file-date table lists `nse_prices/closes.parquet`**, which is gitignored (`.gitignore:102`,
   `config_view.py:171`), so on a fresh server that row reads "Not on this server" unless a loader has cached the file
   there. Not checked live.
5. **The app downloads NSE's market caps live** (`mcap_loader.py:207-250`, submitted on every cold start at `app.py:790`)
   and the header's "Market caps" date can come from that download, not from the committed file. A reachability item
   (checklist section 3).
6. **Configuration's "Read by" column is incomplete**: `benchmarks.csv` is listed for "Dashboard, Market"
   (`config_view.py:153`) but Backtest, Sectors' lede and the header also read it.
7. **NSE holidays (`reference/nse/holidays.csv`) are written by hand** (catalogue `:80`) and end on 25 Dec 2026
   ("fetched 2026-10-03"); every "sessions away" figure on the Dashboard and Actions depends on it. A check day or
   fill in 2027 relies on the caveat (`actions_page.py:434`). 24 Nov 2026 is in the file as a holiday (Guru Nanak),
   which is why the committed data end on 23 Nov.

## 5. Every outside address (section 3 of the plan; read from the code 24 Nov 2026)

Hosts named in `src/`, `scripts/`, `app.py` and the workflows. When each last answered is in the pipelines review (2 (c)), from the jobs' run history; this container reaches none of them directly except through its proxy.

| Host | Called by | What it gives | If it stops |
|---|---|---|---|
| `www.nseindia.com`, `www.nseindia.in` | `src/core/nse_web.py`; `scripts/collect_fii_dii.py`, `sync_nse_holidays.py`, `collect_results_calendar.py`, `fetch_nse_bhavcopy.py`, `sync_nse_reference.py`; `src/loaders/nse_backfill.py` | FII/DII flows, holidays, results calendar, bhavcopy, reference lists | Flows, holidays and results go stale; the committed files stay (the jobs keep the last file) |
| `nsearchives.nseindia.com`, `archives.nseindia.com` | `src/loaders/nse_indices.py`, `nse_backfill.py`, `nse_bundle.py`, `mcap_loader.py`; `scripts/collect_nse_dii.py`, `collect_nse_total_market.py`, `sync_fo_symbols.py`, `check_index_anchor.py` | Index closes, daily bhavcopy and corporate actions, market caps (PR zip), DII | Prices and indices stop at the last stored session; market caps fall back to the committed snapshot (the app's normal path: NSE refuses the cloud host) |
| `niftyindices.com` | `src/core/config.py` | Index constituent lists | Membership stops at the committed lists |
| `www.screener.in` | `src/loaders/screener_loader.py`; `scripts/classify_missing.py` | The deep weekly price history and gap fill | No new deep history; NSE fills gaps (S167) |
| `www.bseindia.com` | `scripts/bse_bhavcopy.py` | BSE's bhavcopy, the second source for halts and gaps | Gaps cannot be told from halts (CLAUDE.md rule) |
| `www.fpi.nsdl.co.in` | `scripts/nsdl_fpi.py`, `fii_dii.yml` | NSDL's FPI flows | Dashboard flows go stale |
| `scanner.tradingview.com` | `scripts/classify_missing.py` | Sector labels for stocks outside NSE's files (Nano, the 1000) | New stocks stay unlabelled |
| `github.com` (releases) | `src/loaders/ranking_store.py`, `src/core/config.py`; `scripts/build_isin_history.py`; `nse_history_import.yml` | The published ranking and the long price file (`data-latest`) | The app ranks live instead of reading the published ranking (slower; S210) |
| `cdn.jsdelivr.net` | `src/ui/lw_chart.py` | The chart library, **fallback only**: `static/` is served first | Nothing while `static/` holds the file |
| `fonts.googleapis.com` | `scripts/build_fonts.py` (build time) | IBM Plex, then self-hosted in `static/fonts` | Nothing at run time |
| `huggingface.co` | `scripts/build_tejhq_actions.py` (one-off build) | A corporate-actions dataset | Nothing at run time |
| `web.archive.org` | `scripts/check_nifty500_against_wayback.py` (a check) | Dated copies of NSE pages | One check cannot run |
| `faculty.iima.ac.in` | `scripts/research/residual_momentum.py` (research) | IIMA's factor data | Research only |
| R2 (Cloudflare; endpoint from secrets) | the app and most jobs (`src/storage`) | The stores | See section 0 |

Two callers the table above missed: the price endpoint kept in a secret (`SS_BASE_URL`, `src/loaders/ss_prices.py`, `ss_sync.yml`, Fridays) and, from 25 Nov, `scripts/screener_earnings.py` (`screener_earnings.yml`, Saturdays) on `www.screener.in`.

**When each last answered** (25 Nov 2026, the last successful run of the job that calls it, from GitHub's run history):

| Job | Hosts | Last success (UTC) | Run |
|---|---|---|---|
| `daily_sync` | NSE archives, niftyindices.com, TradingView scanner, R2 | 25 Nov 02:06 | 45530515349 |
| `fii_dii` | NSE, NSE archives (DII), NSDL | 25 Nov 01:38 | 45527201421 |
| `nsdl_fpi` | NSDL | 24 Nov 22:59 | 45505998029 |
| `nse_reference_sync` | NSE, NSE archives, niftyindices.com | 25 Nov 11:44 | 45607165352 |
| `results_calendar` | NSE | 25 Nov 00:52 | 45521484883 |
| `nse_indices` | NSE archives, R2 | 24 Nov 23:27 | 45510179408 |
| `nse_collect`, `nse_long_prices` | NSE archives, R2 | 25 Nov 00:37, 02:09 | 45519579787, 45530868619 |
| `screener_sync` | Screener, R2 | 25 Nov 01:23 | 45525359771 |
| `bse_daily` (weekly) | BSE | 21 Nov 01:37 | 44851245582 |
| `ss_sync` (Fridays) | the secret endpoint | 20 Nov 22:46 | 44831607703 |
| `nse_classification` (manual so far) | NSE | 24 Nov 17:59 | 45454637779 |
| `screener_earnings` (Saturdays) | Screener, R2 | first run 28 Nov | - |

Every host answered within its job's schedule. Not checked: hosts built from variables other than `SS_BASE_URL`; the app's own calls (R2, GitHub releases as fallback, jsDelivr as fallback, niftyindices.com only from the Configuration page's sync button), which no job records.


## 6. Pipelines (section 2 (c) of the plan; 24 Nov 2026)

Run figures for 25 Oct to 24 Nov 2026 read by a second agent from GitHub's API (`list workflow runs`, branch main); median = updated_at − run_started_at. All 30 scheduled workflows are on the alert's watched list (`scheduled_failure_alert.yml:21-52`), and every commit step checks `git diff --staged --quiet` first. The coordinator checked findings 1, 2 and 7 in the files; the run counts are the agent's.

| workflow | schedule UTC | runs/fails/median min | re-downloads | guard | alert | writes only changes |
|---|---|---|---|---|---|---|
| daily_sync | 17:30 Mon-Fri, 02:00 daily, +after Screener | 86/0/1.7 | 3 runs a day; the 02:00 slot was for Yahoo, now retired | only empty universe (`sync_data.py:234`); `git add -A data/` after 14 `\|\| echo` steps | yes, warnings via the green scan | git yes; release and R2 rankings 3x a day, no skip |
| screener_sync | 17:07 daily | 31/1/40.4 | 365 days per stock every night (`config.py:85`) | rows (`:225`), rank (`:149`), vote (`:188`) | yes | git yes; R2 no `--skip-if-published` (`:256`) |
| ss_sync | 16:32 Fri | 17/1/277.9 (daily until 17 Nov; ~87 min a run since) | stale >12 h only | rows (`:120`) | refusal is a `::warning` (`sync_ss.py:212`) | release and R2 every run |
| nse_collect | 12:41, 14:41, 16:11 Mon-Fri; 03:41 daily | 91/0/1.2 | no, skips what R2 holds (`nse_collect.py:332`); Screener store cached | `--check` | refusal is a warning (#585 open) | R2 new days |
| nse_long_prices | Sat 03:30 full; nightly after daily_sync | 15/2/4.1 | Saturday re-reads all of R2 by design; nightly uses the packs | `check_long_publish.py` (`:141`) **before**; audits **after** publish | yes | release re-uploaded every build; R2 skips |
| nse_indices | 14:10 daily | 4/0/0.8 (new 21 Nov) | new sessions only | `collect_nse_indices.py:122-140` | yes | git yes; R2 no skip (`:60`) |
| weekly_full_sync | 18:30 Fri | 4/0/0.8 | nothing: FORCE_FULL unused | as daily | yes | release rankings |
| monthly_track_record | 19:00 1st-5th | 5/0/3.9 | – | freeze refuses (`:122`) | yes | yes |
| fii_dii | 14:47, 17:47 Mon-Fri | 22/0/0.7 | – | `collect_fii_dii.py:71`, `collect_nse_dii.py:137` | yes | appends new rows |
| nsdl_fpi | 04:17 Mon-Sat, 13:17 Mon-Fri | 24/0/0.3 | latest page | `nsdl_fpi.py:179` | yes | yes |
| results_calendar | 16:23 daily | 18/4/0.4 | – | `collect_results_calendar.py:141,198` | yes | yes |
| nse_reference_sync | 02:45 daily | 30/1/0.4 | – | `sync_nse_reference.py:80` | yes (#541) | yes |
| bse_daily | 20:30 Fri | 4/0/1.1 | after the last date only | `bse_daily.yml:110-118` | yes | release weekly; R2 monthly |
| backtest_reference / momentum_health | Sun 05:17 / 06:23 2nd-6th | 2/0/1.8 / 4/0/1.1 | not read | "build and check" (script not read) | yes | yes |
| r2 bootstrap / market_cap / observed sessions | weekly + chained | 116/0/1.8; 111/0/0.7; 31/0/1.0 | rebuilt from repo | `--skip-if-published` | yes | yes (skip) |
| r2 inventory / continuity / recovery / retention | daily / daily / 1st / Sun | 40/7/2.1; 30/0/0.6; 9/0/28.1; 17/2/2.8 | audits | – | yes (#612 open) | – |
| nse_compare / history_audit / history_import | Sun / 3rd / 2nd | 6/0/15.9 (2 timed out at 45 min); 1/0/10.2; 1/0/0.9 | release files | – | yes | report only |
| v1-full-validation / v1-production-qa | 23:23 / 03:17 + push | 189/11/3.7; 245/53/2.7 | – | – | schedule only; 7 and 33 push failures not alerted | – |
| keep_awake, schedule_watchdog, screener_catchup | 4-hourly, 05:41, 23:37+01:37 | 3/0/0.5, 13/0/0.6, 0 runs (merged 24 Nov, #663) | – | – | yes | – |

Unwatched manual writers (`nse_prices_backfill`, `owner_cleanup`, `nse_sample_check`, `investigate_raw`, `r2_publish_release_asset`) are dispatch-only.

**Findings** (routed in S225):

1. **The long file is published before its audit limits run** (`nse_long_prices.yml:142-172` publish, `:242-255` limits). This is a recorded choice (PRICE_PIPELINE.md, "Audit limits": "fails the job **after** the file is published"; the alert opens an issue), so it is the owner's: whether a limit breach should hold the file back.
2. **`weekly_full_sync` repeats the daily sync.** `FORCE_FULL` is read (`sync_data.py:11`) but no longer changes anything since Yahoo left; the job re-uploads rankings. Retiring a job needs the owner's yes.
3. **daily_sync commits after 14 steps that end `|| echo ::warning`**, with no whole-run check before `git add -A data/` (`daily_sync.yml:451`), and on a rebase conflict keeps this run's copy of every conflicting file (`:475`).
4. **The green scan reads only each workflow's latest green run** (`alert_green_scan.py:44`), so a warning in an earlier run of a job that runs 3-4 times a day can be missed (inferred from the code).
5. **A push-to-main failure raises no alert** (`scheduled_failure_alert.yml:81-83`): the agent counts 33 Production QA and 7 Full Validation failures on push in 30 days (Production QA's 33 checked by the coordinator from the API: 10 on 15 Nov, 3 each on 22 and 23 Nov; the latest, run 45271454528 on 23 Nov 21:36, failed on 15 console 404s with the deploy matching; every push run on 24 Nov is green). The coordinator reads Production QA after each merge it makes; other pushes are not covered.
6. **Screener sync is the largest cost**: 1,288 minutes in 30 days; it asks 365 days per stock every night (`sync_screener.py:154`). Whether a shorter window saves time (the 1.2 s pause may set the pace) needs one measured run.
7. **Fixed 24 Nov:** `--skip-if-published` added to the five `r2_publish.py` calls that lacked it (`daily_sync.yml` ×2, `screener_sync.yml`, `ss_sync.yml`, `nse_indices.yml`), as the bootstrap job already does; a re-run after a fix changes the bytes, so nothing real is skipped. A stale comment corrected (`r2_market_cap_history.yml:2`, "daily" → weekly).
8. **daily_sync's 02:00 UTC slot** was there for Yahoo; dropping it saves about 2 minutes a day (owner).
9. **18 scheduled workflows install packages without a pip cache** (about 22 s a run).
10. **Failures open or unexplained:** r2_retention (#612), results_calendar (4 scheduled runs, 12-22 Nov), r2_archive_inventory (7), the 24 Nov scheduled Full Validation.

Not checked: R2 operation counts; the scripts behind backtest_reference and momentum_health; the causes in finding 10.

## 7. Costs (section 2 (f) of the plan; 24 Nov 2026)

Measured from the Actions API (`/actions/workflows/{id}/runs`, completed runs, `updated_at − run_started_at`), all events and
branches, 25 Oct – 24 Nov and 17–24 Nov. Wall time per run, which is close to billed time for one-job workflows and below it
for jobs that run in parallel or for under a minute: GitHub bills each job rounded up to the minute, so the "≤ billed" column
counts every run as at least one minute, an upper bound (a job skipped by its `if:`, which most alert runs are, bills nothing).

| | 30 days | ≤ billed | last 7 days | x 30/7 |
|---|---|---|---|---|
| All workflows | 12,784 min, 5,020 runs | 15,690 | 5,396 min, 2,468 runs | ~23,100 |
| V1 Full Validation | 4,204 (750 runs) | 4,580 | 3,176 (422 runs: 302 on PRs, 99 of them cancelled; 114 pushes to main; 8 scheduled) | ~13,600 |
| SS price sync | 3,423 (17 runs, 201 min each) | 3,431 | 175 (2) | weekly since 17 Nov (owner): ~4 x 200 = ~860 |
| Screener daily sync | 1,288 (31) | 1,303 | 423 (9) | ~1,800 |
| V1 Production QA | 834 (246) | 966 | 401 (128) | ~1,700 |
| Canonical parity | 636 (827) | 866 | 330 (440) | ~1,400 |
| Everything else | ~2,400 | | ~890 | ~3,800 |

Read:
1. **Full Validation is 59% of the last week**: about 60 runs a day, 9 minutes for a push to main and 6.3 for a PR run. Its
   count follows the number of pushes: 109 of the 114 main pushes in the week were merges. S199 (docs-only PRs skip it) and
   the batching rule (one PR per decision round) are the levers; the merge cadence of 24 Nov (16 merges a day) is what costs.
2. **The private-plan allowance** (S142): GitHub Free gives 2,000 minutes a month, Pro and Team 3,000 (GitHub's billing page,
   not re-read today). The last week runs at ~23,000 a month, 8-11 times either. Even without Full Validation (~9,500 a month),
   it is over. Going private needs Full Validation cut to a few runs a day, and Parity and Production QA on push only.
3. **SS sync fell from 3,423 to ~860 a month** with the weekly schedule (17 Nov); already done.
4. **R2:** 1.68 GB in 27,025 objects (r2_archive_inventory, run 45396914100, 24 Nov), down from 3.49 GB on 14 Nov (run
   43579606312) after the retention rules of 17-22 Nov. Cloudflare's free tier is 10 GB of storage; operation counts are not
   in the inventory and were not measured (left open).
5. **Streamlit memory:** not measured here (the Community Cloud host's figures are not readable from a runner or this
   container); left open.

Not checked: billed minutes as GitHub reports them (the billing API needs the owner's token); R2 operations; Streamlit memory.
