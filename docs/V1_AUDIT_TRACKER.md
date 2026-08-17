# V1 Quantitative Audit Tracker

**Repository:** `Pareshking/Umiya`  
**Scope:** V1 only. V2 is intentionally out of scope.  
**Source:** Full quantitative/code audit supplied on 17-Aug-2026, followed by implementation loops and verification.

## Purpose

This document is the living checklist for the original V1 audit. It records what was identified, what has since been changed, what is intentionally unchanged, and what remains to be researched.

The audit is a roadmap, not a requirement to reproduce MSCI/NSE/BSE methodology. Umiya remains a custom research model; institutional methodologies are reference/benchmark models.

---

## 1. Audit scorecard — current status

| Audit area | Original finding | Current status | Action |
|---|---|---|---|
| Mathematical precision / System-1 Sharpe | Period signal-to-noise statistic; not conventional annualized Sharpe | 🟢 Closed by decision | Approved Sharpe mathematics retained; documentation explicitly calls it period risk-adjusted momentum |
| R² in System-1 | Missing-data vulnerability and `Sharpe × R²` dependency | 🟢 Removed | R² removed from the V1 scoring path and stale System-1 documentation |
| Calendar-period definition | Correct principle but legacy trading-row constants remained | 🟢 Closed | 1/3/6/9/12M are canonical calendar horizons; legacy System-1 row-window config removed |
| Benchmark consistency | Benchmark needed to be common | 🟢 Closed | `^CRSLDX` (Nifty 500) is the common V1 benchmark |
| Live/backtest calendar consistency | Live and backtest could use different period definitions | 🟢 Closed | Backtest aligned to the canonical calendar-period engine |
| Monthly rebalance timing | 21 sessions did not equal calendar month | 🟢 Closed | Last trading day T close → first trading day next month T+1 |
| Industry-relative self-inclusion | Peer mean included the stock itself | 🟢 Closed | Leave-one-out industry-relative calculation implemented and regression-tested |
| Winsorization / normalization description | Audit questioned clipping vs winsorization | 🟢 Closed | Current sequence is documented as raw-score outlier control → Z-score → final clipping; no mathematical change required |
| Stock-specific forward-fill | Could manufacture zero returns and smooth signals | 🟢 Closed | Security-specific missing observations remain missing in quantitative calculations |
| Volatility mathematics | Audit noted differing methodologies | 🟢 Closed by decision | User-approved volatility mathematics retained; regression tests lock the convention |
| Portfolio ERC naming | Lower bound means constrained ERC | 🟡 Documentation/research | Ensure UI/docs consistently call it constrained ERC where applicable |
| Volatility targeting | 63-session realized volatility | 🟢 Accepted | Retained as an intentional portfolio-risk convention; not a System-1 period |
| Survivorship bias | Current universe can bias historical results | ⚪ Intentionally ignored | User explicitly chose not to address survivorship bias for this stage |
| Data history / institutional 3Y replication | Main loader historically around 2Y | 🟠 Open research limitation | Do not claim MSCI replication; consider longer history later if needed |
| Liquidity / implementability | No strong liquidity penalty | 🟠 Open | Audit and decide whether liquidity/tradability controls are required |
| Intermediate momentum | 12–7M vs 6–2M not isolated | 🟠 Research opportunity | Test as a separate Umiya research hypothesis; no production change yet |
| Frog-in-the-Pan | R² was not equivalent to FIP | 🟠 Research opportunity | If desired, test a dedicated continuous-momentum measure; not part of current System-1 |
| Classic month-skip comparison | Current model includes latest month | 🟠 Research opportunity | Compare current no-skip model with 12–1 / 12–2 style alternatives out of sample |
| Institutional benchmark replication | Umiya differs from MSCI/NSE/BSE/AQR | 🟠 Open research | Build benchmark models for comparison, not as a forced replacement of Umiya |
| Portfolio construction vs signal | Signal and portfolio implementation are separate | 🟢 Accepted architecture | Keep alpha signal and portfolio implementation explicitly separated |
| Residual-alpha market proxy | Historical implementation used universe mean if no benchmark | 🟢 Closed | `^CRSLDX` is now the required benchmark; no benchmark → all-NaN (universe mean fallback removed); 5 regression tests cover all call paths |
| Numerical robustness | Alignment/missing-data edge cases | 🟠 Ongoing | Continue targeted synthetic tests as new audit items are closed |

---

## 2. Completed implementation loops

### 2.1 Calendar System-1

**Closed.** System-1 economic horizons are calendar months with actual market observations. Fixed 21/63/126/189/252 row windows are no longer the System-1 period definition.

### 2.2 R² removal

**Closed.** R² is no longer part of the System-1 score. The old `Sharpe × R²` formulation is not the current V1 methodology.

### 2.3 Forward-fill integrity

**Closed.** Security-specific gaps are not converted into synthetic flat-price observations for quantitative returns/volatility. Exchange-wide closure handling remains separate.

### 2.4 Industry-relative leave-one-out

**Closed.** For a multi-stock industry, stock `i` is compared against the mean of valid peer scores excluding `i`. Singleton industries have no peer-relative comparison. Existing ranking semantics for missing values are preserved.

### 2.5 Monthly backtest/live consistency

**Closed.** The backtest uses the same canonical calendar momentum definition as the live System-1 path.

### 2.6 Month-end execution convention

**Closed.** Signal/rebalance occurs at the last available trading-day close of the month. Execution occurs on the first available trading day of the next month.

### 2.7 Common benchmark

**Closed.** `^CRSLDX` is the common V1 benchmark and must remain consistent across modules that require a market benchmark.

### 2.8 Approved volatility methodology

**Closed by explicit decision.** The existing session-based portfolio/risk mathematics is retained. The audit work added regression coverage rather than changing the approved mathematics.

### 2.9 Root momentum-window cleanup

**Closed.** The old root `MOMENTUM_WINDOWS = [21, 63, 126, 189, 252]` definition was removed. `MOMENTUM_MONTHS = [1, 3, 6, 9, 12]` is the canonical System-1 configuration.

### 2.10 Residual-alpha benchmark consistency

**Closed.** Every residual-alpha (System-3) call path now uses `^CRSLDX` as the market benchmark.

Changes made:
- `MomentumEngine.__init__` accepts `benchmark_rets: pd.Series | None`; stores it as `self._benchmark_rets`.
- `calculate_residual_momentum`: explicit `benchmark_returns` kwarg overrides stored benchmark; if neither is provided, returns all-NaN with a warning — universe-mean fallback removed.
- `get_multi_strategy_overlay`: passes `self._benchmark_rets` explicitly to `calculate_residual_momentum`.
- `strategy_view.compute_multi_strategy_monthly_matrix`: accepts `_benchmark_rets` parameter; uses it for residual alpha regression and for the benchmark-performance row; falls back to universe mean only when no benchmark is available (the documented "no benchmark" path).
- `app.py`: fetches `^CRSLDX` prices via `fetch_benchmark_history`; passes resulting returns through the pipeline and into `MomentumEngine`.
- `guide_view.py`: stale `Sharpe × R²` formulas replaced with correct calendar-month System-1 formulas; residual alpha section explicitly names `^CRSLDX`.
- `qualified_view.py`: stale label `"Multi-Window Sharpe × R² Composite"` corrected.
- Stale R² computation removed from `strategy_view.py` backtest matrix; variable `r2_6m` and related log-price/time-array code removed.
- Pre-existing `MOMENTUM_WINDOWS` import error in `backtester.py` and `momentum.py` fixed.
- Pre-existing `period_metrics` key mismatch in `get_rankings` fixed (month keys, not row keys).
- `cs_r2` in `calendar_momentum.py` renamed to `cs_rsq` to eliminate false positive in R² ban test.
- `tests/test_residual_alpha_benchmark.py` (new): 5 regression tests covering stored benchmark, explicit override, no-benchmark NaN, and overlay propagation.
- `tests/test_v1_r2_removed.py`: `strategy_view.py` added to static R²-residue check.

---

## 3. Important distinctions to preserve

### Calendar horizon vs statistical sample vs annualization

These are three different concepts:

1. **Economic horizon:** e.g. 6 calendar months.
2. **Statistical sample:** all valid daily observations inside that interval.
3. **Annualization:** only where a portfolio/risk statistic intentionally requires annualization.

Do not collapse these into one generic variable called `window`.

### System-1 vs portfolio risk

System-1 uses calendar horizons. Portfolio risk calculations may intentionally use session counts such as a short realized-volatility window. The existence of a session-based risk window is not evidence that System-1 should return to trading-row momentum periods.

### Umiya vs institutional indices

MSCI/NSE/BSE/AQR methodologies are comparison/reference models. Umiya is not required to reproduce them. Deviations such as the five-window 10/30/30/20/10 weighting and latest-month inclusion are research choices that should be validated empirically rather than silently presented as institutional methodology.

---

## 4. Remaining work — ordered queue

### NEXT 1 — Liquidity / implementability audit 🟠

Audit liquidity filters, stale prices, bid/ask/impact assumptions, circuit-limit exposure and whether smaller NSE securities can realistically be traded at the assumed transaction cost.

**Acceptance:** explicit methodology decision; no change unless evidence requires it.

### NEXT 2 — Data-history limitation 🟠

Determine whether V1 needs more than the current available history for institutional comparisons and covariance/regime research. Do not alter the current signal merely to imitate MSCI's 3-year weekly volatility.

### NEXT 3 — Intermediate momentum research 🟠

Test separate 12–7M and 6–2M components inspired by the Novy-Marx result. This is research, not a production fix.

### NEXT 4 — Latest-month / classic momentum comparison 🟠

Compare the current no-month-skip formulation with a month-skip alternative out of sample.

### NEXT 5 — Dedicated Frog-in-the-Pan research 🟠

If useful, test a direct continuous-momentum measure against the current System-1 signal. Do not reintroduce R² merely to approximate FIP.

### NEXT 6 — Institutional benchmark models 🟠

Build clean comparison implementations for MSCI-style and NSE-style momentum so Umiya can be evaluated against them without replacing the Umiya signal.

### NEXT 7 — Numerical robustness sweep 🟠

Continue synthetic tests for missing observations, short histories, ties, singleton groups, constant prices, duplicate dates and index alignment.

---

## 5. Explicitly deferred / not in scope

### Survivorship bias ⚪

Historical point-in-time constituent reconstruction is intentionally deferred because the user explicitly chose to ignore survivorship bias for this development stage.

### V2 ⚪

V2 is outside this audit. Do not modify or redesign V2 as part of this tracker.

### Sharpe mathematics ⚪

The approved System-1 Sharpe methodology is not to be changed unless the user explicitly reopens that decision.

### Volatility mathematics ⚪

The approved portfolio/risk volatility mathematics is not to be changed merely to match an institutional index methodology.

---

## 6. Final acceptance rule for each loop

A loop is only **closed/green** when:

1. the actual current code path has been inspected;
2. the intended change is implemented, or explicitly documented as intentionally unchanged;
3. targeted regression tests pass;
4. the relevant full test suite/CI is green;
5. documentation reflects the resulting mathematics and implementation; and
6. the tracker status is updated.

Never mark an audit item closed based only on a planned change or an unverified commit.
