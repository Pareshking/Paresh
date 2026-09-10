# Multi-Agent Adversarial Audit — 2026-09-10

Governing rule: **assume the system is wrong until it survives adversarial
verification.** Nothing below is asserted from reading code alone. Every
confirmed defect was reproduced with a counterexample that runs, and every
allegation the evidence did not support is recorded as rejected.

Scope: `src/engine`, `src/ui/views`, `src/core/config.py`, `src/loaders`,
`tests/`, `.github/workflows/`, `data/*.json`, `README.md`, the in-app Guide.

**Second pass (same day): the Screener tab.** The first pass covered the
Backtest, Portfolio and Track Record tabs and left tab 1 — the one people
actually use — unaudited. Findings S1-S4 below come from that second pass.

**Third pass: the remaining tabs and the loaders.** Qualified, Sectors,
RRG, Watchlist, Market Breadth, Configuration, and `src/loaders`. Findings
T1-T5. Every tab has now been audited.

**Fourth pass: INDEPENDENT review.** Passes 1-3 were written and graded by
the same author — the exact conflict a council structure exists to break.
Four independent agents were then given the merged work and told not to
trust this document. Findings R1-R8 are theirs, verified here before being
accepted. Three of the four agents were killed by a session rate limit
before reporting; what follows is what the two that produced work found.

Baseline commit: `0ce4a86`. Test suite at baseline: **651 passed, 1 failed.**
After this audit: **720 passed, 0 failed.**

---

## Verdict

The engine is **causal** — the strongest allegation against a backtest, that it
can see the future, was tested and failed. Scrambling every price after a
decision date left that date's holdings bit-identical. The corporate-action
back-adjustment is return-neutral before the event and cannot leak either. The
walk-forward skeleton, the T-close/T+1-fill separation, the append-only ledger
and the parameter sweep's overfitting guards are genuinely well built, and
several of them are better than the norm for this kind of project.

What failed was everything *around* that skeleton: the backtest simulated a
different signal from the one the screener displays, silently ignored the risk
limits the user configured, scored five of its six reported months against
today's index constituents while the machinery to avoid that sat unused, and
labelled four of its eight headline statistics as quantities they were not.

The Screener tab, audited in a second pass, failed in the same way and closer
to the user: six of its eleven index filters returned an empty table, its Nifty
50 filter returned a hundred stocks, its 52-week-high gate was easier to pass
the less history a stock had, and its rank-change column did not sum to zero.

The third pass found the same signature once more — a substring test standing
in for an identity, and a colour or a label asserting something the number
does not. The RRG benchmark selector was inert: all three of its options
contained "50", so all three produced one series. Market Breadth counted every
stock that failed to print as a stock below its moving average.

**Judge decision: REWORK REQUIRED at audit time — now APPROVED WITH CONDITIONS**
after the corrections in this branch. The conditions are in *Remaining Risks*;
the first of them is that the reported track record is still 7/8 reconstruction
and cannot yet support a performance claim.

---

## Confirmed problems

| # | Severity | Problem | Evidence | Fix |
|---|---|---|---|---|
| **F1** | **Critical** | Every in-app backtest scored history against **today's** index constituents. `run_backtest` has a `_membership` parameter and `_index_mask` to prevent exactly this; **3 of its 4 call sites never passed it** (`backtest_view.py`, `track_record_view.py`, `parameter_sweep.py`). Only the offline `update_track_record.py` did. | `stats["pit_periods"] == 0` on every in-app run. `data/membership_history.json` has baseline `2026-08-19` and **zero** recorded changes, so `members_on()` returns `None` for 5 of the 6 reported months. Index additions skew to recent winners; a momentum screen buys precisely those. | `load_history_or_none()` added and wired into all three call sites. |
| **F2** | **Critical** | The backtest **did not score the strategy the screener shows.** Two independent implementations of one statistic, diverging on real data. (a) The screener carries a window's opening price forward up to 5 sessions; the backtester read one exact row, so a single holed session scored a stock NaN in the backtest and a real number on screen. (b) The screener winsorises at ±3σ *then* z-scores; the backtester z-scored *then* clipped — a different transform. | (a) One-session gap on the 1M anchor: screener `1.826378`, backtester `NaN`. (b) 200-name cross-section with five leaders: **149 names moved by >0.05**, max |Δz| **0.5252**, **2 of the top 20 changed**, 126/200 displaced ≥3 ranks. Because the composite sums five windows, a fat-tailed window carried less than its configured weight in the backtest and all of it on screen. | `period_sharpe_at()` and `winsorised_z()` are now the single definitions in `calendar_momentum.py`; the backtester delegates. |
| **F3** | **High** | `stock_cap` and `sector_cap` were accepted by `run_backtest`, put in its cache key, and **never read**. The Configuration tab showed limits in force; the simulation and the "Current Holdings" book the tab tells you to trade had none. | `stock_cap=0.01, sector_cap=0.02` produced **byte-identical statistics** to `1.00/1.00`. Resulting book: **75% in one industry** under a 30% configured cap. The Portfolio tab, same ranking, same settings, enforced the cap — the two tabs disagreed. | Caps projected in `_compute_weights` via the shared `apply_caps()`. |
| **F4** | **High** | `apply_caps` (shipped as `PortfolioOptimizer.apply_constraints`, live in the Portfolio tab) **did not satisfy the caps its docstring promised were "strictly satisfied".** It clipped, then renormalised the whole vector to 1.0 — which lifts clipped names straight back through the cap. It also had no notion of *joint* feasibility. | 20 equal weights, 6% stock cap, 40% sector cap → **6.98% position, 58.1% sector**. Randomised property test found violations in 20/300 shapes even after a first fix, all of them jointly-infeasible cap pairs. | Deficit is redistributed to **headroom**, never scaled into everyone. Joint capacity `Σ min(sector_cap, n_i·stock_cap)` is computed and the pair relaxed by exactly `1/capacity` when infeasible, logged and reported via `.attrs`, and surfaced in the Portfolio tab. **1000/1000** randomised shapes now respect the enforced caps. |
| **F5** | **High** | **"Win Rate — Profitable Periods"** displayed the share of months that beat the benchmark, not the share that made money. | Audit fixture: card showed **67%**; months actually profitable: **100%**. A month can lose money and beat a worse index. | `win_rate` is now profitable periods; `beat_rate` added and shown beside it. |
| **F6** | **High** | **Sharpe was not a Sharpe ratio.** It divided an annualised-from-six-months CAGR by annualised volatility — a geometric numerator extrapolated from half a year over an arithmetic denominator. The risk-free hurdle was a bare `0.065` inline, invisible and unchangeable. | Fixture: shown **6.294**, mean-excess Sharpe **5.028** — a 26% overstatement of the headline risk-adjusted figure. | Sharpe = annualised mean excess ÷ annualised vol. `RISK_FREE_RATE` moved to `config.py`. `sharpe_stderr` (≈`√((1+S²/2)/n)`) added and displayed, because a Sharpe from 126 sessions printed to two decimals invites a precision it does not have. |
| **F7** | **Medium** | **Sortino's denominator was `std(negative returns)`** — divided by the count of losing days rather than all days, and measured about the mean of the losses rather than about zero. It matches no published Sortino and its error has no fixed sign. | Fixture: shown **12.221**; with target semideviation **10.394**. | Target semideviation `√(mean(min(r,0)²))·√252`. |
| **F8** | **Medium** | **Turnover had two definitions.** Establishment was hard-coded to `1.0`; every later period used `Σ|Δw|/2`. The same `cost_bps` therefore priced full notional on day one and half notional afterwards, and the "Avg Period Turnover" KPI averaged terms that did not measure the same thing. | Series was `100, 20, 20, 25, 15, 15`. `cost_bps` is documented as a *round-trip* cost; establishing a book buys 100% and sells nothing — half a round trip. NSE delivery is ~11-13 bps per side against ~25-35 bps for the pair, so 30 bps on establishment over-charged ~2.5×. | One definition everywhere. Establishment is now 50% / 15 bps; the avg-turnover KPI fell from an incoherent 32.5% to 24.2%. |
| **F9** | **Medium** | The **"Provenance"** table on the Track Record tab contained **no provenance** — the same four numbers as the Returns grid. The ledger carries `origin`, `config`, `finalized_on` and `data_as_of` for every month, and `summary_stats` already counted `backfilled`/`recorded`. Nothing displayed any of it. | Shipped ledger: **7 of 8 months are `origin: "backfill"`**, all frozen `2026-09-03`, while the header reads "Strategy since inception **+38.7%**" against a benchmark of −1.8%. | Provenance table now shows origin, universe, freeze date, price date and config fingerprint; a warning states how much of the record is reconstruction. |
| **F10** | **Medium** | The backtester computes `pit_periods` / `current_universe_periods` with a comment saying *"a caller reporting the return without reporting this overstates the result"* — and **no caller reported it**. | Grep: zero references in `src/ui/`. | Survivorship coverage warning added to the Backtest tab. |
| **F11** | **Medium** | **The in-app Guide contradicted the code and the README.** A hardcoded **"44.4% CAGR · 1.74 Sharpe"** badge attached to no window, universe or date. Two selectable "engines" (*Single-Window Sharpe*, *Multi-Window Pure Sharpe*) that do not exist. Momentum windows documented as `{21D, 63D, 126D, 189D, 252D}` — the definition the README says was **removed**. "Daily Bhavcopy ingestion" (it is Yahoo Finance). "60-day standard deviation" (the code uses 63). Two mutually inconsistent Sharpe formulas on adjacent pages. | See the claim-vs-implementation table below. | All corrected; the removed engines are documented as removed, with the reason. |
| **F12** | **High** (revised up from Medium) | `tests/test_card_symbol_links_to_the_stock_page` patched `st.html` while the renderer moved to `st.markdown` in **16206a4 (2026-09-04)**. It captured nothing and asserted against `""`. `v1-full-validation.yml` runs on every push to main, and its steps are sequential — so the failing test at step 5 **skipped steps 6-10**: *Compile application and source*, *Full current-universe quantitative integration*, *Enforce deprecated Streamlit HTML cleanup*, *Headless Streamlit runtime smoke test* and the validation artifact upload. For six days main did not merely have a red test; it had **no runtime or integration validation running at all.** | Reproduced locally: patching `st.markdown` instead, the `href` is present and the feature works — the test, not the product, was broken. Confirmed independently from the job logs of runs **156 and 157** (2026-09-04), both `failure` at step 5 with steps 6-10 `skipped`. | Both sinks patched, so moving the sink again cannot silently blind it. Run **158** on the merge commit is the first fully green validation on main since at least 2026-09-04: all 12 steps `success`, including the 64-second current-universe quantitative integration and the headless Streamlit smoke test. |
| **F13** | **Low** | `PortfolioOptimizer.equal_risk_contribution` is **unreachable** (nothing calls it) and has **four** paths that return a different weighting scheme, three of them silent. This is the exact failure mode Mean-Variance Optimisation was removed for (audit F1: "degraded to Equal Weight on any exception while still reporting itself as MVO"). | Grep: no call sites. Silent paths: `n < 2`, `len(ret_sub) < 30`, `res.success == False`. | Every fallback logs what it returned and why; the docstring records the constraint for whoever wires it up. |
| **F14** | **Low** | **Every return in the application is pre-tax and nothing says so.** "Strategy Return (Net)" means net of modelled transaction costs only. Monthly rebalancing realises gains inside twelve months, so in India essentially all of them are short-term. | No tax logic exists anywhere in `src/` or `scripts/`. | Disclosure added to the Guide FAQ and the buffer note. **No tax model was built** — see *Remaining Risks*. |
| **F15** | **Low / informational** | **Unescaped external data reaches an HTML sink.** `render_saas_table` and `render_master_screener_table` interpolate DataFrame cell values into `unsafe_allow_html=True` markup with no escaping. Values originate in `niftyindices.com` CSVs and Yahoo Finance. | No live exploit: NSE symbols and industry names are alphanumeric today, and the one user-controlled path (`?stock=`) is guarded — see *Rejected allegations*. The exposure is a compromised or merely `&`-containing upstream field. | **Reported, not fixed.** Recommended: `html.escape(str(val))` at each cell interpolation in `src/ui/theme.py`. Same argument applies to CSV export (`=`/`+`/`-`/`@`-prefixed fields). |

---

## Confirmed problems — Screener tab (second pass)

| # | Severity | Problem | Evidence | Fix |
|---|---|---|---|---|
| **S1** | **High** | **The `[INDEX]` filter offered 11 options, 6 of which returned an empty screener.** `indices_loader` writes SHORT FORMS into the `Indices` column (`N50`, `NN50`, `MID150`, `SMALL250`, `MICRO250`); the option list added the long names on top of them — including a `NIFTY 500` the app does not load as a constituent index at all — and filtered by substring. | On the shipped 750-symbol universe: `[INDEX] NIFTY 50` → **0 stocks**. Same for `NIFTY MIDCAP 150`, `NIFTY SMALLCAP 250`, `NIFTY MICROCAP 250`, `NIFTY TOTAL MARKET`, `NIFTY 500`. | One option per tag actually present, labelled with the index's real name and carrying the tag for an exact match. **5 options, 0 dead.** |
| **S2** | **High** | **The Nifty 50 filter also returned the whole Nifty Next 50**, because `"NN50"` contains `"N50"` and the filter used `str.contains`. | `[INDEX] N50` → **100 stocks**; Nifty 50 has 50. The extra 50 were `ABB, ADANIENSOL, ADANIGREEN, ADANIPOWER, AMBUJACEM, BAJAJHLDNG, BANKBARODA, BOSCHLTD, …` | Exact tag membership against the comma-split list. Nifty 50 now returns 50. |
| **S3** | **High** | **The 52-week-high gate got EASIER the less history a stock had.** The screener took `max()` over the trailing 252 rows with no minimum observation count, while the backtester has always used `rolling(252, min_periods=126)`. Two definitions of one named filter, disagreeing precisely on recent listings — which a momentum screen already over-selects. | A stock listed 70 sessions ago: screener quoted a "52W High" of 150.0 from those 70 sessions, `% High` **0.0%**, `Near 52W High` **True**, **Rank #1**. The backtester's high for the same name is `NaN` and it fails the gate. On a 750-name frame, **18 short-history names were passing the gate**. The Portfolio tab filters on exactly this column and does not exclude `Short History`. | `HIGH_52W_MIN_OBSERVATIONS = 126` in config, applied in **both** copies of the rule in `momentum.py`. Short-history names passing the gate: **18 → 0**. |
| **S4** | **Medium** | **`Rank Δ 1M` / `Rank Δ 3M` were differences between ranks over two different populations**, so they did not sum to zero — the defining property of a rank change. `Rank` is ranked among the rows surviving the score `dropna`; `Rank (-1M)` was ranked over every price column. Compounding it, the historical rank was qualified by **today's** observation count, so a stock with 27 prints three months ago — not rankable then — still received a `Rank (-3M)`. | The bias has **no fixed sign**: it depends on which kind of churn dominates. A 40-name universe with 5 names gone dark gave a mean "improvement" of **+3.17 places**; a 750-name universe with 30 recent listings gave **−1643** total (mean −2.2). This column drives the rank-delta badge on every row and card, the "Momentum Movers" preset (`|Δ| ≥ 15`), and the Rank Movers section. | Both sides ranked over the **paired** set — names scored *and rankable* on both dates, with the past judged by the history that existed then. Deltas now sum to **exactly 0**; a name rankable on only one date shows "—" instead of a fabricated jump. |

**Cost.** A 750×500 screener pass runs in **760 ms against a 741 ms baseline (+2.6%)**, the price of one extra `notna()` sum per horizon and the observation gate.

**Behaviour change worth stating.** S3 means a price frame shorter than 126
sessions yields no 52-week high for anyone, so `Near 52W High` is False across
the board and the Portfolio tab reports that nothing passes. That is the honest
answer — a 52-week high cannot be quoted from four months of data — but it is a
visible change on thin data. Production loads `PRICE_HISTORY_PERIOD = "2y"`, so
only genuine recent listings are affected, and they are already flagged
`Short History: Yes` in the footer count.

---

## Confirmed problems — remaining tabs and loaders (third pass)

| # | Severity | Problem | Evidence | Fix |
|---|---|---|---|---|
| **T1** | **High** | **Market Breadth counted a missing print as a stock below its moving average.** `_prices > ma` is False wherever either side is NaN, and `mean(axis=1)` then divided by the **full** column count. | A 100-stock frame with every stock above its 50D MA reads **100%**; hole 15 symbols on that session and it reads **85%** — 15% of the market reported as failing when those stocks simply did not trade. The README records a median of 33 holed symbols per session and 135 on 2026-07-21, so a number read as a market-regime signal was biased down ~4% on an ordinary day and ~18% on a bad one. | Unobserved cells masked to NaN; `mean(axis=1)` skips them, dividing by the stocks that actually have both a price and an MA. A genuine failure still counts: 40 below + 10 absent out of 100 now reads 50/90 = **55.6%**. |
| **T2** | **High** | **The RRG benchmark selector did nothing.** The dispatch was `if "50" in benchmark_choice`, and **all three option labels contain "50"** — `Nifty 500 (Universe Equal-Weighted)`, `Nifty 50 (Large-Cap 50)`, `Nifty Midcap 150`. The first branch always won, so the other two were unreachable and the three benchmarks were one series. | All three options produced byte-identical RS-Ratio output. Same defect class as S2 — a substring test standing in for an identity. | Dispatch on named constants with exact equality. The three options now produce three distinct series. |
| **T3** | **Medium** | **The RRG benchmark labels named NSE indices the code does not compute.** None of the three is an index: each is an *equal-weighted* proxy built from whatever universe the Configuration tab has loaded. The README requires `^CRSLDX` wherever a V1 module needs a market benchmark "unless a module has an explicitly documented reason not to", and no reason was documented. | `daily_ret[top50].mean(axis=1)` is not the Nifty 50 (free-float cap-weighted, fixed constituents); `iloc[100:250]` of today's cap ranking is not the Nifty Midcap 150. | Renamed to what they are — *Loaded universe / Top 50 by market cap / Market-cap ranks 101-250, equal-weighted* — with the deviation from the `^CRSLDX` convention documented in code and in the selector's help text. |
| **T4** | **Medium** | **Qualified tab: a loss printed green.** The *Avg 3M Return* and *Avg 6M Return* KPIs hard-coded `color: #059669` regardless of sign. | A −15.4% average rendered in emerald. Colour that contradicts the number is worse than no colour: the reader takes the colour first. | Colour follows the sign. |
| **T5** | **Low** | **Qualified tab: `corr_val and corr_val < 0.70` is a truthiness test, and `0.0` is falsy.** A perfectly uncorrelated book fell through to "High Correlation", and so did a single-name book where `corr_val` is `None` — labelling an unknown as a bad state beside a "—". The sublabels also read *"Trailing 63 Days"* / *"Trailing 126 Days"* on returns that are calendar-month by construction, restating the definition the README says was removed. | `classify(0.0)` → "High Correlation"; `classify(None)` → "High Correlation". | Explicit `None` test and numeric comparison; "Not measurable" is its own state. Sublabels corrected to *Calendar 3 / 6 months*. |

**Rejected in this pass.** The market-cap pipeline was checked for a unit
mismatch between its two sources (NSE PR archive and the yfinance fallback) —
a plausible 10⁷ error in the `Market Cap (Cr)` column. The shipped
`data/nse_market_caps.csv` stores rupees and `/1e7` yields crores correctly:
RELIANCE ₹17.3 lakh crore, TCS ₹7.99 lakh crore, HDFCBANK ₹10.6 lakh crore.
**False alarm** — both sources agree.

---

## Confirmed problems — independent review (fourth pass)

These were found by reviewers who did not write the code and were instructed to
distrust this report. Each was verified against the source before acceptance.

| # | Severity | Problem | Evidence | Fix |
|---|---|---|---|---|
| **R1** | **Critical** | **The live month-to-date was GROSS while every frozen month is NET, and the two are compounded into one headline.** Frozen months come off `eq_strat_net`, which charges `turnover × cost_bps` at each fill. The MTD block accrued `acc += w * r` with no friction term anywhere, and `summary_stats` splices that figure into the same series as the frozen months. "Strategy since inception" therefore mixed a gross month with net ones. | `src/engine/backtester.py`, MTD block: no `friction_drag` term. When `mtd_basis == "rebalanced book"` the month's turnover — up to a full 100% establishment — was carried for free. | MTD now charges the same `turnover × cost_bps` the loop does; `mtd_cost` and `strategy_mtd_gross` exposed in `live_meta`. |
| **R2** | **High** | **Track Record's "Annualised" extrapolates 8 months to a year with no caveat** — the identical defect F6 fixed on the Backtest tab, left standing on the tab users trust as the *real record*. | `track_record_view.py`: `c1.metric("Annualised", …)`; `track_record.py`: `(1 + total_s) ** (12.0 / n) - 1` with n = 8. Backtest says "scaled up from 0.51y" and "Not a CAGR"; this said nothing. | Label carries the elapsed window below one year, with the same "not a CAGR" explanation. |
| **R3** | **High** | **The Screener's breadth reading and BULL/BEAR regime verdict reintroduced the exact NaN-denominator bug T1 had just fixed**, through a different code path. `Above 50 EMA` is False wherever the close or EMA is missing (correct for a per-stock gate), and the strip divided by *every* row. The reading was also hardcoded emerald, so 12% breadth printed green. | `ranking_view.py`: `breadth_pct = round(n_ema / n_total * 100)` driving a four-state regime call; `<span style="color:#34d399">` regardless of value. **T1's fix was therefore incomplete.** | Denominator is the stocks that could answer (`% 50 EMA` non-null); colour follows the value; the priced count is shown. |
| **R4** | **High** | **"Alpha" books the constituents' dividend yield as skill.** The strategy compounds `auto_adjust=True` prices (total return, dividends reinvested); `^CRSLDX` is the Nifty 500 **price** index, which excludes them. Roughly 1-1.5% a year of the reported gap is yield. It is also a simple difference of cumulative returns, not beta-adjusted alpha. | `price_loader.py` pins `auto_adjust=True` on every download; `alpha = total_s - total_b`. | Relabelled "Excess vs Nifty 500" with the asymmetry stated. *Switching to a TRI series remains open — see Remaining Risks.* |
| **R5** | **High** | **The Configuration tab claimed a skip-month momentum convention the engine does not implement — three times, two of them contradicting each other.** One line said only the 12M window skips; another said all five do; `grep -rn "skip" src/engine/` returns no such logic. A user weighting the sliders believed they were buying 12-1 momentum and were buying 12-0. | `config_view.py` lines 204 / 217 / 222 vs `calendar_start_positions`, which runs `as_of - DateOffset(months=months)` straight to the latest observation. | All three corrected; the window table now leads with the calendar period and marks session counts approximate. |
| **R6** | **High** | **F15 was rated Low on a false premise — raised to High.** I judged unescaped third-party data in the HTML tables "Low: NSE symbols are alphanumeric today". The sandbox makes that wrong: these tables render in an `st.iframe` srcdoc with **`allow-same-origin` AND `allow-scripts`**, so markup in a cell executes on the app's own origin. | The decisive evidence was a **pre-existing comment in the very file I audited** — `theme.py:1341-1343` lists the sandbox flags. I read past it. | Escaped at the sink in `render_saas_table` and `render_master_screener_table`; URL-quoted hrefs; 9 tests parse the rendered markup with `HTMLParser` and assert no tag or attribute is created. |
| **R7** | **High** | **Chart payloads were `json.dumps`'d straight into `<script>` blocks.** `json.dumps` escapes quotes and backslashes but **not `</`**, and the HTML parser finds `</script` before JavaScript sees the string. An Industry name or ticker containing `</script>…` closes the block and injects markup — into the same `allow-same-origin` iframe as R6. | `charts.py`: treemap, RRG, breadth, H/L, equity and correlation payloads. | `_script_json()` escapes `</` → `<\/` plus U+2028/U+2029, applied at all seven sinks. |
| **R8** | **Medium** | **Workflow script injection**, and a correction to this report: pass 1 examined workflow *permissions*, found them correctly scoped, and recorded "FALSE ALARM". It never checked `${{ }}` interpolation into `run:` bodies. `v1-cold-start-probe.yml` spliced a `workflow_dispatch` input directly into a shell command. | `run: sleep "${{ github.event.inputs.preroll_seconds }}"` — attacker-controllable text the moment anyone holds write access, expanded before bash sees a quote. | Passed via `env:` and validated as digits, failing loudly otherwise. **The "workflows are correctly scoped" verdict in *Rejected allegations* was scoped too narrowly and is corrected here.** |

**What this pass says about passes 1-3.** Two of these eight (R3, R6) are cases
where my own fix or my own severity call was wrong, and one (R8) corrects a
"false alarm" I issued. R1 and R4 are quantitative defects three passes of my
own review did not find. That is the argument for independence, made against
this audit rather than by it.

---

## Claim vs implementation

| Claim | Source | Implementation | Evidence | Verdict |
|---|---|---|---|---|
| "The backtester must use the same canonical System-1 calendar-period engine as the live screener" | README | Two separate implementations, diverging on holed anchors and on outlier control | screener `1.826378` vs backtester `NaN`; 149/200 z-scores differed | **CONFIRMED DEFECT** → fixed (F2) |
| "raw factor → winsorization → Z-score → final clipping"; "must not describe simple Z-score clipping as raw-score winsorization" | README | The backtester did precisely the thing the README warns against | `_composite_z_score` z-scored then clipped | **CONFIRMED DEFECT** → fixed (F2) |
| "44.4% CAGR · 1.74 Sharpe · 30 bps Friction Drag Tested" | Guide, hero badge | Computed from nothing; no window, universe or date | Hardcoded string literal | **CONFIRMED DEFECT** → removed (F11) |
| "momentum window w ∈ {21D, 63D, 126D, 189D, 252D}" | Guide, deep dive | Calendar months; README says this definition was removed | `MOMENTUM_MONTHS = [1,3,6,9,12]` | **DOCUMENTATION DEFECT** → fixed (F11) |
| "System-1 is the **only** ranking system" | README | Guide offered *Single-Window Sharpe* and *Multi-Window Pure Sharpe* as selectable engines with formulas and a comparison matrix | Guide pills + matrix rows | **DOCUMENTATION DEFECT** → fixed (F11) |
| "daily Bhavcopy ingestion" | Guide | `yfinance` adjusted closes | `src/loaders/price_loader.py` | **DOCUMENTATION DEFECT** → fixed (F11) |
| "annualized 60-day standard deviation" | Guide | 63 sessions, in both the optimizer and the backtester | `window: int = 63`, `start_idx - 63` | **DOCUMENTATION DEFECT** → fixed (F11) |
| "ensuring both individual stock and sector caps are strictly satisfied" | `apply_constraints` docstring | Neither was | 6% → 6.98%, 40% → 58.1% | **CONFIRMED DEFECT** → fixed (F4) |
| "Win Rate / Profitable Periods" | Backtest KPI card | Share of months beating the benchmark | 67% shown, 100% profitable | **CONFIRMED DEFECT** → fixed (F5) |
| "CAGR (Annualized)" | Backtest KPI card | A ~0.51-year result raised to the power of ~2 | `(1+r)^(252/129)` | **MISLEADING LABEL** → relabelled with the window (F6) |
| "Never silently fall back to another portfolio methodology while displaying the original methodology name" | README | `equal_risk_contribution` has three silent fallbacks | `n<2`, `<30 obs`, `not res.success` | **DESIGN WEAKNESS** → logged (F13) |
| "This module detects and classifies. It deliberately does NOT rewrite prices" | `corporate_actions.py` module docstring | `adjust_prices()`, in the same module, rewrites prices in memory | Called from `run_backtest` | **DOCUMENTATION DEFECT** — the function's own docstring is accurate and explains why; the module header is stale |
| "a caller reporting the return without reporting this overstates the result" | `backtester.py`, on `pit_periods` | No caller reported it | Zero references in `src/ui/` | **CONFIRMED DEFECT** → fixed (F10) |

---

## Rejected allegations

The prosecution pursued these and the defence carried them on evidence.

| Allegation | Test performed | Verdict |
|---|---|---|
| **Look-ahead bias in the backtest** | Scrambled every price after the first fill date by `exp(N(0, 0.06))` and re-ran. First-period holdings identical (`{S0,S1,S3,S12,S21,S24,S26,S29,S32,S38}` both runs); `_composite_z_score` at T bit-identical. | **FALSE ALARM.** The engine is causal. |
| **Corporate-action back-adjustment leaks future information into past rankings** | `adjust_prices` scales all pre-event prices by the split ratio. A uniform scale factor cancels in every ratio the engine takes — returns, `P > EMA`, `P ≥ 0.8 × 52wk high`. | **FALSE ALARM.** Return-neutral before the event. |
| **Reflected XSS via `?stock=<payload>`** | `render_stock_view` matches the parameter against `rank_df["Symbol"]` and returns via `st.warning` (escaped) before any HTML is built; the hero interpolates `row["Symbol"]` from the frame, never the raw parameter. | **FALSE ALARM.** (The unescaped-cell exposure in F15 is a different, upstream-data path.) |
| **Over-permissioned GitHub workflows** | All seven audited. `contents: write` only on `daily_sync` and `monthly_track_record`, both of which commit. Five are `contents: read`. No `pull_request_target`. No secrets beyond `GITHUB_TOKEN`. | **FALSE ALARM.** Correctly scoped. |
| **Missing-window dilution shrinks a stock's composite toward the mean** | Already fixed before this audit; renormalisation over available weight is present in both engines and tested. | **FALSE ALARM** (previously corrected). |
| **Population vs sample SD mismatch between engines** | Both use `ddof=0`; the existing parity test covers it. | **FALSE ALARM** (previously corrected). |
| **`_fill_price` fabricates 0% round trips on holed sessions** | Carries the last real print forward, returns `NaN` when there is none, and `_round_trip_return` refuses to manufacture a zero. | **FALSE ALARM.** Correct as written. |
| **The parameter sweep presents a data-mined winner as a finding** | It reports the full distribution, an `overfitting_risk` classification against the spread, a holdout split and a rank correlation, and it counts *and diagnoses* failed combinations. | **FALSE ALARM** — better than the norm. But see *Remaining Risks*: it optimises objectives that were themselves mis-specified until F6/F7. |

---

## Remaining risks

These are **not fixed** and are the conditions on the verdict.

1. **The track record is not yet evidence.** 7 of 8 months are `origin: "backfill"`, all frozen in one pass on 2026-09-03 from today's universe and today's prices. The headline reads **+38.7% since inception vs −1.8%**; only **August 2026 (+12.6%)** was frozen as it closed. The record now says so on screen, but the number itself does not become out-of-sample by being labelled. **One honest month of live record exists.**

2. **Point-in-time membership reaches back to 2026-08-19 and no further, with zero recorded changes.** Wiring `_membership` in fixes the *mechanism*; it cannot manufacture history. Until the daily sync accumulates several NSE reconstitutions, 5 of every 6 reported months will still be scored on the current list and the Backtest tab will keep saying so. The *direction* of that bias is known and the *magnitude* is not — which is the reason to display it rather than estimate it.

3. **The equity curve rebalances daily, for free.** Within each period the engine applies fixed target weights to every day's returns, which is daily rebalancing to target; the blotter prices the same positions buy-and-hold. Measured on the audit fixture: **+60.4 bps over six months** of uncosted rebalancing return that the tradebook does not contain. Not fixed here — it changes the accrual model, and that is a methodology decision, not a bug fix. It also means the equity curve and the closed-trade table can never be reconciled exactly.

4. **Six months of daily data cannot support the ratios computed from it.** With the corrected Sharpe the fixture still prints **5.03 ± 0.44** (one standard error). Calmar over a half-year window has a numerator scaled to a year and a denominator that cannot contain a year's drawdown. The standard error is now shown; the underlying problem is the window, not the arithmetic. **These figures should not be quoted outside the app.**

5. **No tax model, and monthly rebalancing is the worst case for one.** Turnover of ~24%/month realises essentially everything as short-term gains in India. The gap between the displayed pre-tax return and an after-tax outcome is large and is not modelled. Building one would need current-law verification against authoritative sources, which was out of scope; the app now states the absence rather than implying "Net" means net of tax.

6. **Unescaped external data in HTML sinks (F15)** — reported with a concrete patch, not applied, because it touches the hottest rendering path and deserves its own change with its own tests.

7. **`sector_map` is today's classification applied to past rebalances.** Now that the sector cap binds, industry drift feeds the historical book. This is the same assumption the Portfolio tab already makes, and it is second-order beside F1, but it is a real point-in-time gap.

8. **`latest_as_of_date` has a discontinuity at 7 days.** Beyond a 7-day gap the as-of date snaps from today back to the last observation, shifting every calendar horizon by the size of the gap. A long exchange closure crosses that boundary. Not observed to misfire; flagged as a design weakness.

---

## Jury

| Juror | Verdict | Reasoning |
|---|---|---|
| Software Engineer | ACCEPT WITH CONDITIONS | Two implementations of one statistic, and the parity test happened to place its NaNs where both returned NaN. Now one definition. The `.attrs` channel for reporting cap relaxation is a seam to watch. |
| Quantitative Analyst | REWORK → ACCEPT WITH CONDITIONS | The signal was never the problem; the labels and the universe were. Sharpe, Sortino and win rate now mean what they say. Six months still cannot support a Sharpe quoted to two decimals. |
| QA Engineer | ACCEPT WITH CONDITIONS | Main was red for six days behind a workflow that runs on every push, and the red test was checking a sink the code had stopped using. 14 new regressions added, each reproducing a real counterexample. |
| End User | ACCEPT WITH CONDITIONS | Setting a sector cap and getting a 75% single-industry book is the failure that would have cost real money. "Win Rate 67%" beside six profitable months out of six is the one that erodes trust. |
| Skeptical Investor | **REWORK REQUIRED** | +38.7% since inception, 7 of 8 months reconstructed after the fact, 5 of 6 backtest months on today's constituent list, one month of genuine record. The disclosures are now honest and the number still is not evidence. Ask again in six months of recorded track. |
| Product Designer | ACCEPT | Disclosures land above the numbers rather than in tooltips. The "Provenance" table now contains provenance. |

**Jury: ACCEPT WITH CONDITIONS (5), REWORK REQUIRED (1).** The dissent is
recorded rather than averaged away: it is about evidence, and no amount of code
correction supplies it.

---

## Changes made

| File | Change |
|---|---|
| `src/engine/calendar_momentum.py` | `period_sharpe_at()` and `winsorised_z()` — the single canonical definitions of the per-row statistic and the cross-sectional normalisation. |
| `src/engine/backtester.py` | Delegates scoring to those; caps applied in `_compute_weights`; one turnover definition; Sharpe from mean excess; Sortino from target semideviation; `win_rate` vs `beat_rate` separated; `beat_rate`, `sharpe_stderr`, `risk_free_rate`, `window_years` added to `stats`. |
| `src/engine/portfolio.py` | `apply_caps()` extracted to module level and rewritten (headroom redistribution, joint feasibility, relaxation reported via `.attrs`); ERC fallbacks logged. |
| `src/engine/membership.py` | `load_history_or_none()`. |
| `src/engine/parameter_sweep.py` | Passes `_membership` so the grid is not ranked on survivorship. |
| `src/core/config.py` | `RISK_FREE_RATE`. |
| `src/ui/views/backtest_view.py` | `_membership` wired; survivorship coverage warning; four KPI cards relabelled to what they measure. |
| `src/ui/views/track_record_view.py` | `_membership` wired; backfill warning; Provenance table now carries provenance. |
| `src/ui/views/portfolio_view.py` | Cap relaxation surfaced in the KPI and as a warning. |
| `src/ui/views/guide_view.py` | Hardcoded performance badge removed; two non-existent engines removed; formulation corrected to the calendar-period, winsorise-then-z pipeline; Bhavcopy, 60-day and turnover claims corrected; pre-tax disclosure added. |
| `tests/test_adversarial_audit_2026_09.py` | **New.** 22 regressions covering the confirmed defects (F15 is reported, not fixed, so it carries no test). |
| `src/engine/breadth.py` | Unobserved cells masked out of the moving-average breadth denominator. |
| `src/ui/views/rrg_view.py` | Benchmark dispatch on named constants instead of a substring; options renamed to the proxies they actually compute. |
| `src/ui/views/qualified_view.py` | Average-return colour follows its sign; correlation status handles 0.0 and None; calendar-period sublabels. |
| `src/engine/momentum.py` | 52-week high gated on `HIGH_52W_MIN_OBSERVATIONS` in both code paths; rank deltas computed over the paired, historically-qualified population; `MIN_OBSERVATIONS` named. |
| `src/ui/views/ranking_view.py` | `[INDEX]` options built from tags actually present, labelled with real index names, matched exactly rather than by substring. |
| `tests/test_backtest_trade_returns.py` | Establishment-cost assertion corrected — it had pinned the bug. |
| `tests/test_stock_page_and_navigation.py` | Patches both render sinks; red since 2026-09-04. |

---

## Verification

Same fixture, before and after:

```
                                    BEFORE                AFTER
1  holed 1M anchor       screener 1.826378 / bt NaN    both 1.826378
2  caps 100/100 vs 6/30  22.631722% == 22.631722%      22.815701% vs 23.544356%
   top industry weight   75.0% vs 75.0%                75.0% vs 62.5%
3  "Profitable Periods"  67%  (actually 100%)          100%  (beat index 67%)
4  Sharpe                6.294 (mean-excess: 4.982)    5.028 == 5.028
   Sortino               12.221                        10.394
5  establishment         100% turnover / 0.30%         50% turnover / 0.15%
   avg turnover KPI      32.5%                         24.2%
```

- Full suite: **674 passed, 0 failed** (from 651 passed, 1 failed).
- **CI on `main` (run 158) is green end to end** — the first time since at
  least 2026-09-04. This matters beyond the test count: the five validation
  steps that F12 had been silently skipping now actually run, and the
  current-universe quantitative integration and headless Streamlit smoke
  test both pass against the corrected engines on Python 3.14, which is a
  different environment from the one this audit was developed in.
- `apply_caps`: **1000/1000** randomised shapes respect the enforced caps, sum
  to 1.0 within 1e-9, and carry no negative weight.
- Scoring parity: backtester and screener agree to `rtol=1e-9` across all five
  horizons, including on a holed anchor.
- Causality re-tested after every change: scrambling the post-decision future
  leaves the decision unchanged.
- Reproduction scripts for each counterexample are described inline in the
  regression tests, so each finding can be re-derived from this repository.

Third pass, same fixture before and after:

```
                                            BEFORE          AFTER
breadth, 15 of 100 symbols holed              85.0%          100.0%
breadth, 40 below + 10 absent of 100          50.0%           55.6%   (50 of 90 observed)
RRG: distinct series across 3 benchmarks          1               3
Qualified: -15.4% average rendered             green             red
Qualified: classify(corr = 0.00)      High Correlation    Diversified
```

Screener pass, same fixture before and after:

```
                                        BEFORE          AFTER
[INDEX] NIFTY 50                    0 stocks        50 stocks
[INDEX] N50 / Nifty 50            100 stocks        50 stocks
52-week highs quoted (of 740)             740              720
short-history names passing the gate       18                0
Rank Δ 1M, total across the book        -1643             +0.0
750x500 screener pass                  741 ms           760 ms
```

**Cost of the corrections.** A production-shaped backtest (750 symbols x 500
sessions, 0.4% holed) runs in **498 ms against a 479 ms baseline — +4%**. The
first cut was +70% (815 ms): the stale-anchor rule re-`ffill`ed the whole frame
35 times per run, and `winsorised_z` round-tripped through a one-row DataFrame,
rebuilding a 750-label index twice per call. The anchor frame is now computed
once per run and threaded down, and both normalisation paths call one numpy
kernel (`_winsorise_z_matrix`) rather than one wrapping the other. The residual
4% is the genuine cost of the anchor lookup and the cap projection.

## Judge decision

**APPROVED WITH CONDITIONS.**

The corrections are evidence-backed and tested. The conditions are the eight
Remaining Risks, and the binding one is the first: the strategy's reported
record is one month of evidence and seven months of reconstruction. The system
may now be trusted to *describe itself accurately*. It cannot yet be trusted to
*have proven anything*, and those are different claims.
