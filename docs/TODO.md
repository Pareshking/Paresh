# To do

The one list of what is still open. Tick an item when it is done and verified,
with the date and the PR or run that proves it; move it to **Done** at the
bottom. Add anything promised in a conversation here the same day.

_Last updated: 2026-09-30_

## Now

| # | What | How we know it is done | Status |
|---|---|---|---|
| 1 | Merge PR #255: Production QA waits for the page's run before judging the ☰ menu | #255 merged; post-merge V1 Production QA green | [ ] |
| 2 | Read the 4th NSE comparison (run on b1cb342: demergers and month-first ex-dates handled) | Report read, results given to the owner: drift beyond 1% (was 58), Spearman and top 20/50 per system | [ ] |
| 3 | Decide: NSE as the middle price source (Screener → NSE → Yahoo) | Owner says yes or no after item 2 | [ ] |
| 4 | If yes: switch the price order in the app | PR merged; precompute accepted in production; docs updated | [ ] |

## Dated

| # | When | What | How we know it is done | Status |
|---|---|---|---|---|
| 5 | 30 Sep 2026, evening (check 18:30 UTC) | October Nano Cap list built; Nano Cap and Combined rankings published | `data/nanocap_membership.json` gains `2026-09-30`; `rankings_nano` / `rankings_combined` published and accepted | [ ] |
| 6 | 1 Oct 2026 | First Nano Cap and Combined model books; their backtest shows September | Actions and Backtest with `?sys=nano` / `?sys=combined` | [ ] |
| 7 | 2–5 Nov 2026 | October frozen in all three ledgers | Track Record's "Three systems, side by side" shows Oct 2026 | [ ] |

## Ongoing

| # | What | Cadence |
|---|---|---|
| 8 | Read the weekly NSE comparison; collect any missing session it lists (`nse_collect.yml` → dates); look at new unconfirmed actions and unexplained jumps | Sundays 06:40 UTC |
| 9 | Weekly R2 retention and recovery audit green (audit now reads 10 at a time, 40-min limit) | Weekly |

## Later

| # | What |
|---|---|
| 10 | All three price sources (NSE, Yahoo, Screener) in before 06:00 IST. Screener's nightly run for 1,167 stocks takes about 37 minutes |
| 11 | Delete merged remote branches (owner, by hand): `docs/BRANCH_CLEANUP_TODO.md` |

## Done (27 Sep 2026)

- System picker restyled; Combined no longer reverts after a stock page (#242)
- Industries for Nano Cap stocks from TradingView and Screener.in (#249; Value Research blocks scripts)
- Four flagged stocks in the production log resolved (#251)
- Top bar gains "Within 20% of 52W high"; repeated figures removed from every page; treemap and unused code removed (#252)
- Screener header on one row, so the table starts higher (#254)
- R2 recovery audit no longer times out (#252: 7.5 and 15.5 min runs)
- NSE adjusted prices: splits and bonuses from the Bc file, confirmed by the price (#253); month-first ex-dates and demergers (#254); five missing sessions collected


## Done (30 Sep 2026)

- Dynamic point-in-time membership history for all six production NSE indices merged in PR #258 (merge commit `73b095a49b52ab1a4a968e21e364610e94ed02a5`); pre-merge Lint, V1 Full Validation, R2 Focused Validation and R2 Streamlit read-path gates were green.
- Post-merge R2 historical evidence bootstrap run `36646326268` completed green: index constituent snapshots, point-in-time membership histories, combined universe, historical sector/industry classification, confirmed trading sessions, historical market caps and corporate-action evidence all published successfully.
- Post-merge R2 ranking calculation archive run `36646326289` completed green: canonical ranking artifact validated, published immutably and audited successfully.
