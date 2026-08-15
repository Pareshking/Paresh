"""
Quantitative Strategy & Factor Architecture Handbook (Comprehensive Institutional Reference).
Unified typography system with exact mathematical formulations, equations,
parameter lookbacks, weight dependencies, trade execution protocols, and market regime playbooks.
"""

import pandas as pd
import streamlit as st

from src.ui.components import render_data_quality_footer
from src.ui.theme import render_saas_table


def render_guide_view(rank_df: pd.DataFrame) -> None:
    """Renders the comprehensive Strategy Architecture & Factor Handbook with standardized typography."""
    st.markdown(
        """
        <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.15rem; font-weight: 800; color: #0f172a; margin-bottom: 2px;">
            Quantitative Strategy & Factor Architecture Handbook
        </div>
        <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 13px; color: #64748b; margin-bottom: 14px;">
            Institutional reference detailing mathematical formulations, parameter lookbacks, weight dependencies, risk engines, and regime playbooks.
        </div>
        """,
        unsafe_allow_html=True,
    )

    section_tab = st.segmented_control(
        "Handbook Sections",
        ["Methodology Framework", "Strategy Comparison Matrix", "Mathematical Deep Dives", "Market Regime Playbooks", "Execution & FAQ"],
        default="Methodology Framework",
        key="guide_main_nav",
        label_visibility="collapsed",
    )
    if not section_tab:
        section_tab = "Methodology Framework"

    st.markdown(" ")

    # ── TAB 1: Methodology Framework ─────────────────────────────────────────
    if section_tab == "Methodology Framework":
        # 1. Visual 5-Step Pipeline Card
        pipeline_html = """
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:18px; box-shadow:0 1px 3px rgba(0,0,0,0.02); margin-bottom:16px; font-family:'Plus Jakarta Sans',sans-serif;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px; border-bottom:1px solid #f1f5f9; padding-bottom:10px;">
                <div style="font-size:14px; font-weight:700; color:#0f172a;">
                    End-to-End Quantitative Investment Pipeline
                </div>
                <span style="font-family:'JetBrains Mono',monospace; font-size:12px; color:#059669; background:#ecfdf5; border:1px solid #a7f3d0; padding:3px 10px; border-radius:6px; font-weight:700;">
                    44.4% CAGR · 1.74 Sharpe · 30 bps Friction Drag Tested
                </span>
            </div>

            <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:10px;">
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px;">
                    <div style="font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700; color:#4f46e5;">STEP 01</div>
                    <div style="font-weight:600; font-size:13px; color:#0f172a; margin-top:2px;">Universe Ingestion</div>
                    <div style="font-size:13px; color:#64748b; line-height:1.5; margin-top:4px;">750 liquid stocks from Nifty Total Market with daily Bhavcopy ingestion and corporate action adjustments.</div>
                </div>
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px;">
                    <div style="font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700; color:#059669;">STEP 02</div>
                    <div style="font-weight:600; font-size:13px; color:#0f172a; margin-top:2px;">Trend Gating</div>
                    <div style="font-size:13px; color:#64748b; line-height:1.5; margin-top:4px;">CMP &gt; 50 EMA and within 20% of 52W High to eliminate stage-4 downtrends and structural laggards.</div>
                </div>
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px;">
                    <div style="font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700; color:#d97706;">STEP 03</div>
                    <div style="font-weight:600; font-size:13px; color:#0f172a; margin-top:2px;">Factor Scoring</div>
                    <div style="font-size:13px; color:#64748b; line-height:1.5; margin-top:4px;">Sharpe × R² multi-window (1M/3M/6M/9M/12M) normalized via ±3σ Winsorized Gaussian Z-scores.</div>
                </div>
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px;">
                    <div style="font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700; color:#7c3aed;">STEP 04</div>
                    <div style="font-weight:600; font-size:13px; color:#0f172a; margin-top:2px;">Portfolio Sizing</div>
                    <div style="font-size:13px; color:#64748b; line-height:1.5; margin-top:4px;">Top 20 equal/inv-vol weighting with 2.0× buffer (hold to rank 40) cutting annual turnover to ~39.5%.</div>
                </div>
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px;">
                    <div style="font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700; color:#0284c7;">STEP 05</div>
                    <div style="font-weight:600; font-size:13px; color:#0f172a; margin-top:2px;">Execution & Stops</div>
                    <div style="font-size:13px; color:#64748b; line-height:1.5; margin-top:4px;">2×ATR initial stop & 3×ATR Chandelier trailing exit + 1-Click Zerodha Kite Basket CSV export.</div>
                </div>
            </div>
        </div>
        """
        st.html(pipeline_html)

        # 2. Key Architecture Comparison: Composite (Config Weights) vs Single-Window
        comparison_card_html = """
        <div style="padding:18px; background-color:#ffffff; border:1px solid #e2e8f0; border-radius:12px; font-family:'Plus Jakarta Sans',sans-serif; font-size:13px; color:#475569; line-height:1.65; box-shadow:0 1px 3px rgba(0,0,0,0.02); margin-bottom:16px;">
            <div style="font-size:14px; font-weight:700; color:#0f172a; margin-bottom:10px;">
                Architecture Comparison: Composite Sharpe × R² (Config Weights) vs Single-Window Sharpe × R²
            </div>
            <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:16px;">
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:14px;">
                    <div style="font-weight:700; font-size:13px; color:#4f46e5; margin-bottom:6px;">
                        👑 Composite Sharpe × R² (Config Weights) — [RECOMMENDED FOR CORE PORTFOLIOS]
                    </div>
                    <div style="font-size:13px; color:#475569; line-height:1.6;">
                        • <strong>Multi-Horizon Blend</strong>: Combines 5 distinct lookback windows: 1M (10%), 3M (30%), 6M (30%), 9M (20%), and 12M (10%).<br>
                        • <strong>Anti-Whipsaw Filter</strong>: Eliminates short-term "pump-and-dump" traps. A stock with a 2-week speculative spike will score high on 1M, but will be filtered out because its 6M/12M base is weak.<br>
                        • <strong>Customizable Sliders</strong>: Fully adjustable in the <em>Configuration</em> tab to emphasize shorter or longer horizons based on market cycles.<br>
                        • <strong>Turnover Efficiency</strong>: Generates stable, high-conviction signals with lower portfolio churn (~39.5% annual turnover).
                    </div>
                </div>
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:14px;">
                    <div style="font-weight:700; font-size:13px; color:#0284c7; margin-bottom:6px;">
                        🎯 Sharpe × R² (Single-Window Horizon) — [TACTICAL SWING DISCOVERY]
                    </div>
                    <div style="font-size:13px; color:#475569; line-height:1.6;">
                        • <strong>Single Lookback Window</strong>: Evaluates purely 1 isolated timeframe (e.g. only 3M / 63 days or only 6M / 126 days).<br>
                        • <strong>Higher Responsiveness</strong>: Reacts faster to emerging short-term trends, but has higher whipsaw risk if a single month experiences a sharp drawdown.<br>
                        • <strong>Fixed Horizon</strong>: Does not blend across horizons; scores reflect only price action within that exact lookback window.<br>
                        • <strong>Best Used For</strong>: Tactical swing screening and comparing relative performance within a specific quarterly holding period.
                    </div>
                </div>
            </div>
        </div>
        """
        st.html(comparison_card_html)

        # 3. Detailed 4-Pillar Mathematical Breakdown (100% Standardized 13px/14px Typography)
        methodology_html = """
        <div style="padding:20px; background-color:#ffffff; border:1px solid #e2e8f0; border-radius:12px; font-family:'Plus Jakarta Sans',sans-serif; font-size:13px; color:#475569; line-height:1.65; box-shadow:0 1px 3px rgba(0,0,0,0.02); margin-bottom:16px;">
            <div style="font-size:14px; font-weight:700; color:#0f172a; margin-bottom:14px;">
                Quantitative Mathematical Formulations & Parameter Dependencies
            </div>
            <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:16px;">
                <div>
                    <div style="color:#0f172a; font-weight:600; font-size:13px; margin-bottom:4px;">
                        1. Multi-Window Sharpe × R² Factor (10/30/30/20/10)
                    </div>
                    <div style="color:#475569; font-size:13px; line-height:1.6;">
                        Combines 5 rolling lookbacks: <strong>1M (10%)</strong>, <strong>3M (30%)</strong>, <strong>6M (30%)</strong>, <strong>9M (20%)</strong>, and <strong>12M (10%)</strong>. Each window calculates annualized log-Sharpe multiplied by Pearson R² regression score (Sharpe × R²) to reward persistent geometric compounding over erratic single-day spike noise.
                    </div>
                </div>
                <div>
                    <div style="color:#0f172a; font-weight:600; font-size:13px; margin-bottom:4px;">
                        2. ±3σ Winsorized Z-Score Normalization
                    </div>
                    <div style="color:#475569; font-size:13px; line-height:1.6;">
                        Raw factor metrics across the universe are Winsorized at ±3σ to neutralize extreme distribution outliers before Gaussian standardization (Z ~ N(0, 1)):
                        <div style="font-family:'JetBrains Mono',monospace; font-size:12px; background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:6px 10px; margin-top:8px; font-weight:600; color:#1e293b;">
                            Score = 0.10·Z(1M) + 0.30·Z(3M) + 0.30·Z(6M) + 0.20·Z(9M) + 0.10·Z(12M)
                        </div>
                    </div>
                </div>
                <div>
                    <div style="color:#0f172a; font-weight:600; font-size:13px; margin-bottom:4px;">
                        3. Trend & Liquidity Gating
                    </div>
                    <div style="color:#475569; font-size:13px; line-height:1.6;">
                        Stocks must satisfy strict quantitative criteria to enter qualified model portfolios:
                        <ul style="margin:6px 0 0 16px; padding:0; line-height:1.6; font-size:13px;">
                            <li><strong>CMP &gt; 50 EMA</strong> (Primary medium-term uptrend regime filter)</li>
                            <li><strong>CMP &ge; 80% of 52W High</strong> (Within 20% of 52-week High)</li>
                            <li>Microstructure liquidity gating to eliminate friction slippage</li>
                        </ul>
                    </div>
                </div>
                <div>
                    <div style="color:#0f172a; font-weight:600; font-size:13px; margin-bottom:4px;">
                        4. Turnover Buffer & Execution Framework
                    </div>
                    <div style="color:#475569; font-size:13px; line-height:1.6;">
                        Walk-forward monthly (21D) rebalancing with causal execution (Rank at T → Trade at T+1):
                        <ul style="margin:6px 0 0 16px; padding:0; line-height:1.6; font-size:13px;">
                            <li><strong>Top 20 Holdings</strong> (Equal-Weighted or Inverse-Vol Sizing)</li>
                            <li><strong>2.0× Buffer Zone (Top 40)</strong>: Retains existing positions if rank &le; 40, cutting turnover to 39.5%</li>
                            <li><strong>Risk Limits</strong>: 30 bps round-trip friction, 2×ATR stop loss & 3×ATR Chandelier trailing exit</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
        """
        st.html(methodology_html)

        # 4. Position Sizing & Risk Management Architecture Card
        sizing_risk_html = """
        <div style="padding:20px; background-color:#ffffff; border:1px solid #e2e8f0; border-radius:12px; font-family:'Plus Jakarta Sans',sans-serif; font-size:13px; color:#475569; line-height:1.65; box-shadow:0 1px 3px rgba(0,0,0,0.02); margin-bottom:16px;">
            <div style="font-size:14px; font-weight:700; color:#0f172a; margin-bottom:14px;">
                Position Sizing Models & Risk Management Architecture
            </div>
            <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(300px, 1fr)); gap:16px;">
                <div>
                    <div style="color:#0f172a; font-weight:600; font-size:13px; margin-bottom:4px;">
                        Equal Weighting Allocation ($w_i = 1/N$)
                    </div>
                    <div style="color:#475569; font-size:13px; line-height:1.6;">
                        Allocates a uniform 5.00% capital weight across the Top 20 qualified holdings. Maximizes gross upside in broad-based bull markets where momentum breadth is strong and uniform across sectors.
                    </div>
                </div>
                <div>
                    <div style="color:#0f172a; font-weight:600; font-size:13px; margin-bottom:4px;">
                        Inverse-Volatility Parity ($w_i \\propto 1/\\sigma_i$)
                    </div>
                    <div style="color:#475569; font-size:13px; line-height:1.6;">
                        Weights each asset inversely proportional to its annualized 60-day standard deviation:
                        <div style="font-family:'JetBrains Mono',monospace; font-size:12px; background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:6px 10px; margin-top:8px; font-weight:600; color:#1e293b;">
                            w_i = (1 / &sigma;_i) / &sum;(1 / &sigma;_j)
                        </div>
                        Reduces overall portfolio volatility and minimizes maximum drawdowns during choppy or high-VIX environments.
                    </div>
                </div>
                <div>
                    <div style="color:#0f172a; font-weight:600; font-size:13px; margin-bottom:4px;">
                        2×ATR Initial Stop Loss
                    </div>
                    <div style="color:#475569; font-size:13px; line-height:1.6;">
                        Sets an immediate volatility-calibrated stop loss upon entry:
                        <div style="font-family:'JetBrains Mono',monospace; font-size:12px; background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:6px 10px; margin-top:8px; font-weight:600; color:#1e293b;">
                            Stop Loss = Entry Price - 2.0 &times; ATR(14)
                        </div>
                        Prevents catastrophic single-stock gap-down losses while accommodating normal market noise.
                    </div>
                </div>
                <div>
                    <div style="color:#0f172a; font-weight:600; font-size:13px; margin-bottom:4px;">
                        3×ATR Chandelier Trailing Exit
                    </div>
                    <div style="color:#475569; font-size:13px; line-height:1.6;">
                        Ratchets profit stops higher as the stock trends, protecting accumulated compounding gains:
                        <div style="font-family:'JetBrains Mono',monospace; font-size:12px; background-color:#f8fafc; border:1px solid #e2e8f0; border-radius:6px; padding:6px 10px; margin-top:8px; font-weight:600; color:#1e293b;">
                            Chandelier Exit = Highest High(22D) - 3.0 &times; ATR(14)
                        </div>
                        Allows multi-bagger runners to breathe while triggering prompt exits when the trend breaks.
                    </div>
                </div>
            </div>
        </div>
        """
        st.html(sizing_risk_html)

    # ── TAB 2: Strategy Comparison Matrix ────────────────────────────────────
    elif section_tab == "Strategy Comparison Matrix":
        st.markdown(
            """
            <div style="font-family:'Plus Jakarta Sans',sans-serif; font-size:14px; font-weight:700; color:#0f172a; margin-bottom:8px;">
                Full Multi-Model Strategy Comparison Matrix
            </div>
            """,
            unsafe_allow_html=True,
        )
        matrix_data = [
            {
                "Strategy Model": "Composite Sharpe × R²",
                "Lookback Windows": "1M, 3M, 6M, 9M, 12M",
                "Config Weights": "YES (Customizable)",
                "Risk Adjustment": "Vol + R² Smoothness",
                "Market Beta": "Included",
                "Best Regime": "Steady Secular Bull Runs",
                "Primary Objective": "Low-whipsaw persistent geometric compounding",
            },
            {
                "Strategy Model": "Sharpe × R² (Single Window)",
                "Lookback Windows": "Single (3M or 6M)",
                "Config Weights": "NO (Fixed Window)",
                "Risk Adjustment": "Vol + R² Smoothness",
                "Market Beta": "Included",
                "Best Regime": "Quarterly Swing Cycles",
                "Primary Objective": "Tactical horizon ranking without multi-window smoothing",
            },
            {
                "Strategy Model": "Multi-Window Pure Sharpe",
                "Lookback Windows": "1M, 3M, 6M, 9M, 12M",
                "Config Weights": "YES (Customizable)",
                "Risk Adjustment": "Annualized Volatility",
                "Market Beta": "Included",
                "Best Regime": "High-Beta Parabolic Expansions",
                "Primary Objective": "Captures maximum gross upside without R² penalty",
            },
            {
                "Strategy Model": "Residual (α) Momentum",
                "Lookback Windows": "126 Trading Days (6M)",
                "Config Weights": "NO (Independent CAPM)",
                "Risk Adjustment": "Stripped Market Beta (β)",
                "Market Beta": "Excluded (Idiosyncratic)",
                "Best Regime": "Narrow Rallies, Choppy Range",
                "Primary Objective": "Isolates company-specific fundamental alpha",
            },
            {
                "Strategy Model": "Industry-Relative",
                "Lookback Windows": "Multi-Window (1M–12M)",
                "Config Weights": "Partial (Uses Composite)",
                "Risk Adjustment": "Sector Group Mean",
                "Market Beta": "Sector-Neutralized",
                "Best Regime": "Active Sector Rotation",
                "Primary Objective": "Picks #1 outperformer within every peer group",
            },
            {
                "Strategy Model": "Momentum Acceleration",
                "Lookback Windows": "1M+3M+6M vs 9M+12M",
                "Config Weights": "NO (Fixed Derivatives)",
                "Risk Adjustment": "Short vs Long Differential",
                "Market Beta": "Velocity Trend",
                "Best Regime": "Early Bull & Inflection Points",
                "Primary Objective": "Detects early stage-2 fresh breakout momentum",
            },
            {
                "Strategy Model": "Consensus Ensemble",
                "Lookback Windows": "Multi-Engine Overlap",
                "Config Weights": "NO (Borda Rank Sum)",
                "Risk Adjustment": "Multi-Factor Cross-Validation",
                "Market Beta": "Balanced",
                "Best Regime": "All-Weather Core Portfolio",
                "Primary Objective": "Minimizes drawdowns & eliminates false breakouts",
            },
            {
                "Strategy Model": "Exp Regression (R²)",
                "Lookback Windows": "126 Trading Days (6M)",
                "Config Weights": "NO (Direct Regression)",
                "Risk Adjustment": "R² Goodness of Fit",
                "Market Beta": "Slope-driven",
                "Best Regime": "Linear Exponential Trends",
                "Primary Objective": "Fits log-linear compounding slope directly",
            },
            {
                "Strategy Model": "Relative Rotation (RRG)",
                "Lookback Windows": "12W RS / 6W Tail",
                "Config Weights": "NO (JdK Algorithm)",
                "Risk Adjustment": "RS-Ratio vs RS-Momentum",
                "Market Beta": "Benchmark Relative",
                "Best Regime": "Sector & Asset Allocation",
                "Primary Objective": "Visualizes clockwise quadrant rotational cycles",
            },
            {
                "Strategy Model": "Institutional Delivery",
                "Lookback Windows": "Daily vs 20-Day Mean",
                "Config Weights": "NO (Volume Factor)",
                "Risk Adjustment": "Volume Threshold Surge",
                "Market Beta": "Volume-driven",
                "Best Regime": "Accumulation Breakouts",
                "Primary Objective": "Confirms big-money institutional buying footprint",
            },
        ]
        comp_df = pd.DataFrame(matrix_data)
        render_saas_table(comp_df, key="guide_matrix_table", max_height=450)

    # ── TAB 3: Mathematical Deep Dives ───────────────────────────────────────
    elif section_tab == "Mathematical Deep Dives":
        strat_choice = st.pills(
            "Select Engine to Inspect",
            [
                "Composite Sharpe × R²",
                "Single-Window Sharpe × R²",
                "Multi-Window Pure Sharpe",
                "Residual (α) Momentum",
                "Industry-Relative Momentum",
                "Momentum Acceleration",
                "Consensus Ensemble",
                "Relative Rotation Graph",
                "Delivery Surge Factor",
                "Risk & Stop-Loss Engine",
            ],
            default="Composite Sharpe × R²",
            key="guide_strat_choice_pill",
            label_visibility="collapsed",
        )

        if strat_choice == "Composite Sharpe × R²":
            st.markdown(
                r"""
                ##### 1. Composite Multi-Window Momentum ($\text{Sharpe} \times R^2$)
                
                **Mathematical Formulation:**
                For each momentum window $w \in \{21\text{D}, 63\text{D}, 126\text{D}, 189\text{D}, 252\text{D}\}$:
                $$\text{Log Return}_w = \ln\left(\frac{P_t}{P_{t-w}}\right)$$
                $$\text{Daily Volatility}_w = \text{StdDev}(\ln(P / P_{-1})) \times \sqrt{w}$$
                $$\text{Sharpe}_w = \frac{\text{Log Return}_w}{\text{Daily Volatility}_w}$$
                $$R^2_w = \left(\text{Corr}\left(\ln(P), \text{Time}\right)\right)^2$$
                $$\text{Raw Momentum}_w = \text{Sharpe}_w \times R^2_w$$
                $$\text{Composite Score} = \sum_{w} \text{Weight}_w \times z\text{-Score}\left(\text{Raw Momentum}_w\right)$$

                * **Config Weights Integration**: Uses active weights configured in the **Configuration** tab (e.g. 10/30/30/20/10).
                * **Multi-Horizon Defense**: Requires consistent compounding across both short-term (1M/3M) and long-term (6M/9M/12M) horizons, preventing speculative short-term whipsaws.
                * **Optimal Regime**: Steady secular bull runs and core compounder portfolios.
                """
            )

        elif strat_choice == "Single-Window Sharpe × R²":
            st.markdown(
                r"""
                ##### 2. Single-Window Momentum ($\text{Sharpe} \times R^2$)
                
                **Mathematical Formulation:**
                Evaluates purely one isolated time window $w$ (e.g., $w = 63\text{D}$ for 3-Month or $w = 126\text{D}$ for 6-Month):
                $$\text{Sharpe}_w = \frac{\ln(P_t / P_{t-w})}{\sigma_w \sqrt{w}}$$
                $$R^2_w = \left(\text{Corr}\left(\ln(P), \text{Time}\right)\right)^2$$
                $$\text{Single Window Score} = z\text{-Score}\left(\text{Sharpe}_w \times R^2_w\right)$$

                * **Key Difference vs Composite**: Does not blend other horizons. Evaluates performance strictly within the specified window.
                * **Sensitivity & Trade-off**: Higher responsiveness to quarterly moves, but more sensitive to single-month reversals.
                * **Optimal Regime**: Quarterly tactical rebalancing and short-to-medium term swing trading.
                """
            )

        elif strat_choice == "Multi-Window Pure Sharpe":
            st.markdown(
                r"""
                ##### 3. Multi-Window Pure Sharpe Momentum (No $R^2$)
                
                **Mathematical Formulation:**
                Evaluates pure risk-adjusted annualized velocity across all multi-windows without penalizing parabolic curves:
                $$\text{Sharpe}_w = \frac{\ln(P_t / P_{t-w})}{\sigma_w \sqrt{w}}$$
                $$\text{Score} = \sum_{w} \text{Weight}_w \times z\text{-Score}(\text{Sharpe}_w)$$

                * **Config Weights Integration**: Uses custom factor weights across 1M, 3M, 6M, 9M, 12M windows.
                * **Difference vs $\text{Sharpe} \times R^2$**: Allows explosive, high-curvature parabolic winners to score at the top without penalty.
                * **Optimal Regime**: Aggressive expansion bull markets where leaders accelerate rapidly.
                """
            )

        elif strat_choice == "Residual (α) Momentum":
            st.markdown(
                r"""
                ##### 4. Residual ($\alpha$) Idiosyncratic Momentum
                
                **Mathematical Formulation:**
                Performs a rolling **126-Trading Day (6-Month)** single-factor CAPM regression against the broad market index ($R_m$):
                $$R_{i, t} = \alpha_i + \beta_i \cdot R_{m, t} + \epsilon_{i, t}$$
                $$\beta_i = \frac{\operatorname{Cov}(R_i, R_m)}{\operatorname{Var}(R_m)}$$
                $$\alpha_i = \left(\mu_{\text{stock}, i} - \beta_i \cdot \mu_{\text{market}}\right) \times 252$$

                * **Config Weights Integration**: Independent CAPM regression engine.
                * **Why it works**: Strips out broad market beta, isolating stocks with genuine company-specific outperformance.
                * **Optimal Regime**: Narrow rallies, choppy indices, and consolidation phases.
                """
            )

        elif strat_choice == "Industry-Relative Momentum":
            st.markdown(
                r"""
                ##### 5. Industry-Relative Momentum
                
                **Mathematical Formulation:**
                Evaluates a stock's momentum relative to its own industry peer group:
                $$\text{RelScore}_i = \text{Score}_i - \overline{\text{Score}}_{\text{Industry}}$$
                where $\overline{\text{Score}}_{\text{Industry}} = \frac{1}{N_{\text{grp}}} \sum_{j \in \text{Industry}} \text{Score}_j$.

                * **Config Weights Integration**: Uses the multi-window composite score as the base.
                * **Why it works**: Isolates the single strongest leader inside every sector, providing sector-neutral alpha regardless of macro cycles.
                * **Optimal Regime**: Active sector rotation environments and market inflections.
                """
            )

        elif strat_choice == "Momentum Acceleration":
            st.markdown(
                r"""
                ##### 6. Momentum Acceleration (Velocity Derivative)
                
                **Mathematical Formulation:**
                Measures the difference between recent short-term velocity and long-term trend baseline:
                $$\text{Short Term} = 0.10 \cdot z(1\text{M}) + 0.35 \cdot z(3\text{M}) + 0.55 \cdot z(6\text{M})$$
                $$\text{Long Term} = 0.45 \cdot z(9\text{M}) + 0.55 \cdot z(12\text{M})$$
                $$\text{Acceleration} = \text{Short Term} - \text{Long Term}$$

                * **Config Weights Integration**: Fixed derivative weights.
                * **Why it works**: Detects early-stage breakouts weeks before they show up in 12M tables.
                * **Optimal Regime**: Market regime turning points and early bull market recoveries.
                """
            )

        elif strat_choice == "Consensus Ensemble":
            st.markdown(
                r"""
                ##### 7. Multi-Strategy Consensus Ensemble
                
                **Mathematical Formulation:**
                Combines independent ranking dimensions using Borda Count rank aggregation:
                $$\text{Consensus Rank} = \operatorname{Rank}\left(\text{Rank}_{\text{Residual }\alpha} + \text{Rank}_{\text{IndRel}} + \text{Rank}_{\text{Accel}} + \text{Rank}_{\text{Composite}}\right)$$

                * **Config Weights Integration**: Ensemble cross-validation.
                * **Why it works**: Requires multiple orthogonal models to agree, filtering out high-volatility false breakouts and lowering maximum drawdowns.
                * **Optimal Regime**: Core capital allocation where capital preservation is paramount.
                """
            )

        elif strat_choice == "Relative Rotation Graph":
            st.markdown(
                r"""
                ##### 8. Relative Rotation Graph (RRG)
                
                **Mathematical Formulation (Julius de Kempenaer Algorithm):**
                1. **Relative Strength Line**: $\text{RS}(t) = \frac{P_{\text{Sector}}(t)}{P_{\text{Benchmark}}(t)} \times 100$
                2. **JdK RS-Ratio (Trend)**: Exponential smoothing normalized around 100:
                   $$\text{RS-Ratio} = 100 + 6.5 \times z\text{-Score}\left(\frac{\text{EMA}(\text{RS}, 6)}{\text{SMA}(\text{EMA}(\text{RS}, 6), 12)}\right)$$
                3. **JdK RS-Momentum (Velocity)**: Rate of change of RS-Ratio:
                   $$\text{RS-Momentum} = 100 + 6.5 \times z\text{-Score}\left(\frac{\text{RS-Ratio}(t)}{\text{RS-Ratio}(t-5)}\right)$$

                * **Quadrant Lifecycle**:
                  * **Leading (>100, >100)**: Strong relative strength and momentum.
                  * **Weakening (>100, <100)**: Relative strength remains high, but momentum is fading.
                  * **Lagging (<100, <100)**: Underperforming the benchmark.
                  * **Improving (<100, >100)**: Momentum inflecting upward; watchlist for early entry.
                """
            )

        elif strat_choice == "Delivery Surge Factor":
            st.markdown(
                r"""
                ##### 9. Institutional Delivery Volume Surge Factor
                
                **Mathematical Formulation:**
                Tracks true institutional accumulation by analyzing delivery volume percentage and absolute delivery surges:
                $$\text{Del \%} = \frac{\text{Delivery Quantity}}{\text{Traded Quantity}} \times 100$$
                $$\text{Del Surge Daily} = \frac{\text{Delivery Quantity}}{\text{20-Day SMA}(\text{Delivery Quantity})}$$
                $$\text{Del Surge 20D} = \frac{\text{20-Day SMA}(\text{Delivery Quantity})}{\text{Previous 20-Day SMA}(\text{Delivery Quantity})}$$

                * **Threshold Rules**: High delivery flagged at $\text{Del \%} \ge 50\%$ with $\text{Delivery Surge} \ge 1.5\times$.
                * **Optimal Regime**: Validating that price momentum is backed by genuine long-term institutional buying.
                """
            )

        elif strat_choice == "Risk & Stop-Loss Engine":
            st.markdown(
                r"""
                ##### 10. Quantitative Risk, Volatility & Stop-Loss Engine
                
                **Mathematical Formulation:**
                1. **True Range (TR)**:
                   $$\text{TR}_t = \max\left(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|\right)$$
                2. **Average True Range (ATR)**:
                   $$\text{ATR}_{14, t} = \frac{\text{ATR}_{14, t-1} \times 13 + \text{TR}_t}{14}$$
                3. **2.0× Initial Stop Loss**:
                   $$\text{Initial Stop} = P_{\text{Entry}} - 2.0 \times \text{ATR}_{14}$$
                4. **3.0× Chandelier Trailing Exit**:
                   $$\text{Chandelier Exit}_t = \max_{i \in [0, 21]} \left(H_{t-i}\right) - 3.0 \times \text{ATR}_{14, t}$$

                * **Execution Rule**: If current market price breaches the Chandelier trailing stop, exit the position at next open ($T+1$) with 0 hesitation.
                """
            )

    # ── TAB 4: Market Regime Playbooks ───────────────────────────────────────
    elif section_tab == "Market Regime Playbooks":
        playbook_html = """
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:16px; margin-bottom:16px; font-family:'Plus Jakarta Sans',sans-serif;">
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-top:3px solid #16a34a; border-radius:10px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,0.02);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <span style="font-weight:700; font-size:14px; color:#15803d;">BULLISH EXPANSION</span>
                    <span style="font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700; color:#15803d; background:#ecfdf5; padding:2px 7px; border-radius:4px;">NIFTY &gt; 50 EMA</span>
                </div>
                <div style="font-size:13px; color:#475569; line-height:1.6;">
                    <div><strong>#1 Model:</strong> Multi-Window Pure Sharpe</div>
                    <div><strong>#2 Model:</strong> Momentum Acceleration</div>
                    <div><strong>Target Allocation:</strong> 100% Equity (0% Cash)</div>
                    <div style="margin-top:6px; color:#64748b;">
                        Strategy focuses on high-beta momentum breakouts, aggressive compounding, and unconstrained upside capture.
                    </div>
                </div>
            </div>

            <div style="background:#ffffff; border:1px solid #e2e8f0; border-top:3px solid #0284c7; border-radius:10px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,0.02);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <span style="font-weight:700; font-size:14px; color:#0284c7;">RANGE-BOUND / NEUTRAL</span>
                    <span style="font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700; color:#0284c7; background:#f0f9ff; padding:2px 7px; border-radius:4px;">BREADTH 40–55%</span>
                </div>
                <div style="font-size:13px; color:#475569; line-height:1.6;">
                    <div><strong>#1 Model:</strong> Residual (α) Momentum</div>
                    <div><strong>#2 Model:</strong> Industry-Relative</div>
                    <div><strong>Target Allocation:</strong> 85% Equity (15% Cash)</div>
                    <div style="margin-top:6px; color:#64748b;">
                        Strategy strips out market beta to isolate idiosyncratic, stock-specific fundamental outperformance.
                    </div>
                </div>
            </div>

            <div style="background:#ffffff; border:1px solid #e2e8f0; border-top:3px solid #d97706; border-radius:10px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,0.02);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <span style="font-weight:700; font-size:14px; color:#d97706;">VOLATILE / HIGH VIX</span>
                    <span style="font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700; color:#d97706; background:#fffbeb; padding:2px 7px; border-radius:4px;">VIX &gt; 18</span>
                </div>
                <div style="font-size:13px; color:#475569; line-height:1.6;">
                    <div><strong>#1 Model:</strong> Consensus Ensemble (Borda)</div>
                    <div><strong>#2 Model:</strong> Composite Sharpe × R²</div>
                    <div><strong>Target Allocation:</strong> 70% Equity (30% Cash)</div>
                    <div style="margin-top:6px; color:#64748b;">
                        Enable Inverse-Volatility Parity weighting in Portfolio tab to limit drawdown exposure.
                    </div>
                </div>
            </div>

            <div style="background:#ffffff; border:1px solid #e2e8f0; border-top:3px solid #dc2626; border-radius:10px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,0.02);">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <span style="font-weight:700; font-size:14px; color:#dc2626;">BEARISH DEFENSIVE</span>
                    <span style="font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700; color:#dc2626; background:#fef2f2; padding:2px 7px; border-radius:4px;">NIFTY &lt; 50 EMA</span>
                </div>
                <div style="font-size:13px; color:#475569; line-height:1.6;">
                    <div><strong>#1 Model:</strong> Capital Protection Mode</div>
                    <div><strong>#2 Model:</strong> Cash Preservation</div>
                    <div><strong>Target Allocation:</strong> 40% Equity (60% Cash)</div>
                    <div style="margin-top:6px; color:#64748b;">
                        Exit all stocks that violate trailing stops. Do not add new positions until Nifty closes above 50 EMA.
                    </div>
                </div>
            </div>
        </div>
        """
        st.html(playbook_html)

    # ── TAB 5: Execution & FAQ ───────────────────────────────────────────────
    else:
        # Step-by-Step Zerodha Kite Execution Card
        zerodha_guide_html = """
        <div style="padding:18px; background-color:#ffffff; border:1px solid #e2e8f0; border-radius:12px; font-family:'Plus Jakarta Sans',sans-serif; font-size:13px; color:#475569; line-height:1.65; box-shadow:0 1px 3px rgba(0,0,0,0.02); margin-bottom:16px;">
            <div style="font-size:14px; font-weight:700; color:#0f172a; margin-bottom:12px;">
                🚀 Zerodha Kite 1-Click Basket Execution Playbook
            </div>
            <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:12px;">
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px;">
                    <div style="font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700; color:#4f46e5;">STEP 1: EXPORT BASKET</div>
                    <div style="font-size:13px; color:#475569; margin-top:4px;">Navigate to the <strong>Portfolio</strong> tab, review target weights, and click <strong>Download Zerodha Kite Basket CSV</strong>.</div>
                </div>
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px;">
                    <div style="font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700; color:#059669;">STEP 2: IMPORT TO KITE</div>
                    <div style="font-size:13px; color:#475569; margin-top:4px;">Open <strong>Zerodha Kite Web</strong> $\to$ Navigate to <em>Orders &gt; Baskets</em> $\to$ Click <em>New Basket</em> $\to$ Click <strong>Import CSV</strong>.</div>
                </div>
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px;">
                    <div style="font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700; color:#d97706;">STEP 3: EXECUTE IN 1-CLICK</div>
                    <div style="font-size:13px; color:#475569; margin-top:4px;">Execute the entire basket between 09:20 AM and 09:30 AM on the 1st trading day of the month using Market/Limit orders.</div>
                </div>
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:12px;">
                    <div style="font-family:'JetBrains Mono',monospace; font-size:11px; font-weight:700; color:#7c3aed;">STEP 4: SET GTT STOPS</div>
                    <div style="font-size:13px; color:#475569; margin-top:4px;">Place Zerodha GTT (Good-Till-Triggered) OCO stop loss orders matching the table's 2×ATR Initial Stop and 3×ATR Chandelier values.</div>
                </div>
            </div>
        </div>
        """
        st.html(zerodha_guide_html)

        faq_html = """
        <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(320px, 1fr)); gap:12px; margin-bottom:16px; font-family:'Plus Jakarta Sans',sans-serif;">
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-weight:700; font-size:14px; color:#0f172a; margin-bottom:6px;">
                    What is the difference between Composite Sharpe × R² and Single-Window Sharpe × R²?
                </div>
                <div style="font-size:13px; color:#475569; line-height:1.6;">
                    <strong>Composite Sharpe × R²</strong> blends 5 rolling horizons (1M/3M/6M/9M/12M) with custom configuration weights to eliminate short-term whipsaws and false breakouts. <strong>Single-Window</strong> calculates Sharpe × R² on strictly 1 isolated period (e.g. 3M), making it more responsive to short-term momentum but subject to higher turnover and volatility.
                </div>
            </div>

            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-weight:700; font-size:14px; color:#0f172a; margin-bottom:6px;">
                    When should I rebalance my portfolio?
                </div>
                <div style="font-size:13px; color:#475569; line-height:1.6;">
                    Rebalance on the <strong>first trading day of every calendar month</strong> (or every 21 trading days). Avoid intra-month knee-jerk changes unless a holding breaches its 2×ATR Stop Loss or Chandelier Trailing Exit.
                </div>
            </div>

            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-weight:700; font-size:14px; color:#0f172a; margin-bottom:6px;">
                    Why is stock #14 not in the Top 20 Portfolio?
                </div>
                <div style="font-size:13px; color:#475569; line-height:1.6;">
                    The system enforces the <strong>2.0× Turnover Buffer Rule</strong>. Existing holdings are retained as long as they stay within Rank #40. This prevents excessive brokerage friction, impact slippage, and capital gains taxes.
                </div>
            </div>

            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-weight:700; font-size:14px; color:#0f172a; margin-bottom:6px;">
                    How does JdK Relative Rotation Graph (RRG ®) work?
                </div>
                <div style="font-size:13px; color:#475569; line-height:1.6;">
                    RRG tracks clockwise rotation across 4 quadrants: <strong>Improving (Blue)</strong> $\to$ <strong>Leading (Green)</strong> $\to$ <strong>Weakening (Yellow)</strong> $\to$ <strong>Lagging (Red)</strong>. Sectors rotating into <em>Leading</em> offer the strongest multi-month tailwinds.
                </div>
            </div>

            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-weight:700; font-size:14px; color:#0f172a; margin-bottom:6px;">
                    What is the difference between Equal Weighting and Inverse-Volatility Parity?
                </div>
                <div style="font-size:13px; color:#475569; line-height:1.6;">
                    <strong>Equal Weighting</strong> gives each stock a flat 5.0% allocation (ideal for strong bull markets). <strong>Inverse-Volatility Parity</strong> weights stocks by $1/\\sigma$, allocating smaller sizes to high-beta volatile stocks and larger sizes to low-volatility compounders, cutting portfolio drawdown.
                </div>
            </div>

            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:16px; box-shadow:0 1px 2px rgba(0,0,0,0.02);">
                <div style="font-weight:700; font-size:14px; color:#0f172a; margin-bottom:6px;">
                    How does the 30 bps Friction Drag model work in Backtesting?
                </div>
                <div style="font-size:13px; color:#475569; line-height:1.6;">
                    Every simulated trade deducts a realistic <strong>30 basis points (0.30%) round-trip cost</strong> covering STT (Securities Transaction Tax), exchange turnover charges, SEBI turnover fees, GST, stamp duty, and bid-ask slippage drag.
                </div>
            </div>
        </div>
        """
        st.html(faq_html)

    render_data_quality_footer(
        total_stocks=len(rank_df),
        gap_count=int((rank_df.get("Data Gap", pd.Series()) == "🔴").sum()),
        short_count=int((rank_df.get("Short History", pd.Series()) == "Yes").sum()),
    )
