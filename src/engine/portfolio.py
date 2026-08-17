"""
Portfolio construction and optimization engine.
Weighting schemes: Equal Weight, Inverse Volatility, Equal Risk Contribution (Risk Parity), Mean-Variance (MVO with Ledoit-Wolf + SLSQP).
Constraints: Stock Cap, Sector Cap, Volatility Targeting.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from src.core.logger import logger


def _shrunk_cov(returns_df: pd.DataFrame) -> pd.DataFrame:
    """
    Pure NumPy analytical Ledoit-Wolf covariance shrinkage estimator with zero external dependencies.
    Shrinks sample covariance toward diagonal target matrix with equal average variance.
    """
    clean = returns_df.dropna(how="any")
    X = clean.values
    T, N = X.shape

    if T < 2 or N == 0:
        return pd.DataFrame(
            np.eye(max(N, 1)), index=clean.columns, columns=clean.columns
        )

    mean = np.mean(X, axis=0)
    X_c = X - mean
    sample_cov = (X_c.T @ X_c) / max(T - 1, 1)

    # Variance floor for zero-variance assets
    diag_var = np.diag(sample_cov)
    if np.any(diag_var < 1e-10):
        sample_cov += np.eye(N) * 1e-6
        diag_var = np.diag(sample_cov)

    # Shrinkage target: diagonal matrix with average variance
    var_mean = float(np.mean(diag_var))
    target = np.eye(N) * var_mean

    # Ledoit-Wolf optimal asymptotic shrinkage intensity (delta)
    y = X_c**2
    phi_mat = (y.T @ y) / max(T, 1) - sample_cov**2
    phi = float(np.sum(phi_mat))

    gamma = float(np.linalg.norm(sample_cov - target, "fro") ** 2)
    kappa = (phi / gamma) if gamma > 1e-12 else 0.0
    shrinkage = float(np.clip(kappa / max(T, 1), 0.05, 0.95))

    shrunk = shrinkage * target + (1.0 - shrinkage) * sample_cov
    eps = 1e-6 * max(float(np.trace(shrunk)) / max(N, 1), 1e-4)
    shrunk += np.eye(N) * eps

    return pd.DataFrame(shrunk, index=clean.columns, columns=clean.columns)


class PortfolioOptimizer:
    """Constructs and optimizes multi-asset portfolios with institutional risk management."""

    def __init__(
        self, log_returns_df: pd.DataFrame, sector_map: dict[str, str] | None = None
    ):
        self.returns: pd.DataFrame = log_returns_df
        self.sector_map: dict[str, str] = sector_map or {}

    def equal_weight(self, symbols: Sequence[str]) -> pd.Series:
        n = len(symbols)
        if n == 0:
            return pd.Series(dtype=float)
        return pd.Series(1.0 / n, index=list(symbols))

    def inverse_volatility(self, symbols: Sequence[str], window: int = 63) -> pd.Series:
        valid = [s for s in symbols if s in self.returns.columns]
        if not valid:
            return self.equal_weight(symbols)
        vol = self.returns[valid].iloc[-window:].std(ddof=0) * np.sqrt(252)
        inv = 1.0 / vol.replace(0, np.nan)
        inv = inv.fillna(0)
        total = float(inv.sum())
        return (inv / total) if total > 0 else self.equal_weight(valid)

    def equal_risk_contribution(
        self,
        symbols: Sequence[str],
        window: int = 126,
    ) -> pd.Series:
        """
        Computes Equal Risk Contribution (Risk Parity) weights such that
        each asset contributes equally to total portfolio risk.
        """
        valid = [s for s in symbols if s in self.returns.columns]
        n = len(valid)
        if n < 2:
            return self.equal_weight(symbols)

        ret_sub = self.returns[valid].iloc[-window:].dropna(how="any")
        if len(ret_sub) < 30:
            return self.inverse_volatility(valid)

        cov = _shrunk_cov(ret_sub).values * 252

        try:
            from scipy.optimize import minimize

            def risk_budget_obj(w):
                port_var = float(w @ cov @ w)
                if port_var <= 1e-12:
                    return 1e6
                port_vol = np.sqrt(port_var)
                mrc = (cov @ w) / port_vol
                rc = w * mrc
                target_rc = port_vol / n
                return float(np.sum((rc - target_rc) ** 2))

            bounds = [(0.005, 1.0)] * n
            constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}]
            x0 = np.ones(n) / n
            opts = {"ftol": 1e-9, "maxiter": 500}

            res = minimize(
                risk_budget_obj,
                x0=x0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options=opts,
            )
            if res.success:
                w = np.maximum(res.x, 0.0)
                tot = float(np.sum(w))
                return pd.Series(w / tot if tot > 0 else np.ones(n) / n, index=valid)
            else:
                return self.inverse_volatility(valid)
        except Exception as e:
            logger.warning(f"Risk Parity solver error: {e} — fallback to inverse vol")
            return self.inverse_volatility(valid)

    def mean_variance(
        self,
        symbols: Sequence[str],
        expected_returns: pd.Series,
        risk_aversion: float = 1.0,
        stock_cap: float = 0.10,
        sector_cap: float = 0.30,
    ) -> pd.Series:
        """
        Solves the quadratic Mean-Variance Optimization problem:
        min  0.5 * w'Σw - (1 / λ) * μ'w
        s.t. sum(w) = 1, 0 <= w_i <= eff_stock_cap, sum(w_sector) <= eff_sector_cap
        """
        valid = [
            s
            for s in symbols
            if s in self.returns.columns and s in expected_returns.index
        ]
        n = len(valid)
        if n == 0:
            return pd.Series(dtype=float)
        if n == 1:
            return pd.Series([1.0], index=valid)

        ret_sub = self.returns[valid].iloc[-126:].dropna(how="any")
        if len(ret_sub) < 30:
            return self.equal_weight(valid)

        daily_cov = _shrunk_cov(ret_sub)
        cov = daily_cov.values * 252

        # Expected returns normalization (scaled annualized spread)
        mu_raw = expected_returns[valid].values.astype(float)
        mu_std = float(np.std(mu_raw))
        if mu_std > 1e-8:
            mu = (mu_raw - np.mean(mu_raw)) / mu_std * 0.15 + 0.15
        else:
            mu = np.full(n, 0.15)

        eff_stock_cap = max(float(stock_cap), 1.25 / n, 0.06)

        sec_indices: dict[str, list[int]] = {}
        if self.sector_map:
            for idx, sym in enumerate(valid):
                sec = self.sector_map.get(sym, "Other")
                sec_indices.setdefault(sec, []).append(idx)
        num_sectors = max(len(sec_indices), 1)
        eff_sector_cap = max(float(sector_cap), 1.05 / num_sectors, 0.25)

        try:
            from scipy.optimize import minimize

            def objective(w):
                return float(
                    0.5 * (w @ cov @ w) - (1.0 / max(risk_aversion, 0.1)) * (mu @ w)
                )

            constraints = [{"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0)}]

            if sec_indices and eff_sector_cap < 1.0:
                for sec_idx_list in sec_indices.values():
                    a = np.zeros(n)
                    a[sec_idx_list] = 1.0
                    constraints.append(
                        {
                            "type": "ineq",
                            "fun": lambda w, _a=a, _c=eff_sector_cap: float(
                                _c - np.dot(_a, w)
                            ),
                        }
                    )

            bounds = [(0.005, eff_stock_cap)] * n
            x0 = np.ones(n) / n
            opts = {"ftol": 1e-9, "maxiter": 500}

            # Attempt 1: SLSQP with equal weight starting point
            res = minimize(
                objective,
                x0=x0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options=opts,
            )

            # Attempt 2: Inverse vol starting point if attempt 1 failed
            if not res.success:
                iv = self.inverse_volatility(valid)
                x0_iv = iv.reindex(valid).fillna(1.0 / n).values
                x0_iv = np.clip(x0_iv, 0.005, eff_stock_cap)
                x0_iv = x0_iv / np.sum(x0_iv)
                res = minimize(
                    objective,
                    x0=x0_iv,
                    method="SLSQP",
                    bounds=bounds,
                    constraints=constraints,
                    options=opts,
                )

            if res.success:
                w = np.maximum(res.x, 0.0)
                tot = float(np.sum(w))
                return pd.Series(w / tot if tot > 0 else np.ones(n) / n, index=valid)
            else:
                logger.debug(
                    "SLSQP didn't converge cleanly — using inverse volatility fallback"
                )
                return self.inverse_volatility(valid)
        except Exception as e:
            logger.warning(
                f"MVO solver exception: {e} — fallback to inverse volatility"
            )
            return self.inverse_volatility(valid)

    def apply_constraints(
        self,
        weights: pd.Series,
        sector_cap: float = 0.30,
        stock_cap: float = 0.10,
    ) -> pd.Series:
        """
        Iterative water-filling projection ensuring both individual stock and sector caps
        are strictly satisfied while guaranteeing total portfolio weight sums to exactly 1.0 (100%).
        """
        if stock_cap <= 0 or sector_cap <= 0:
            raise ValueError("Caps must be > 0")

        w = weights.copy().fillna(0.0)
        n = len(w)
        if n == 0:
            return w
        if n == 1:
            return pd.Series([1.0], index=w.index)

        # Feasibility adjustments
        eff_stock_cap = max(stock_cap, 1.0 / n + 1e-4)

        sec_groups: dict[str, list[str]] = {}
        if self.sector_map:
            for sym in w.index:
                sec = self.sector_map.get(sym, "Other")
                sec_groups.setdefault(sec, []).append(sym)
        num_sec = max(len(sec_groups), 1)
        eff_sector_cap = max(sector_cap, 1.0 / num_sec + 1e-4)

        for _ in range(100):
            prev_w = w.copy()

            # 1. Clip individual stock cap
            w = w.clip(upper=eff_stock_cap)

            # 2. Clip sector caps
            if sec_groups:
                for sec_syms in sec_groups.values():
                    sec_total = float(w[sec_syms].sum())
                    if sec_total > eff_sector_cap + 1e-8:
                        w[sec_syms] *= eff_sector_cap / sec_total

            # 3. Renormalize to 1.0
            tot = float(w.sum())
            if tot > 1e-8:
                w = w / tot

            if float((w - prev_w).abs().max()) < 1e-6:
                break

        tot_final = float(w.sum())
        return (w / tot_final) if tot_final > 0 else self.equal_weight(list(w.index))

    def volatility_target(
        self,
        weights: pd.Series,
        target_vol: float = 0.25,
        window: int = 63,
    ) -> tuple[pd.Series, float, float]:
        """Scales portfolio weights to meet target annualized volatility."""
        if target_vol <= 0:
            raise ValueError("target_vol must be > 0")
        valid = [s for s in weights.index if s in self.returns.columns]
        if not valid:
            return weights, 1.0, 0.0
        sub = self.returns[valid].iloc[-window:].dropna(how="any")
        port = (sub * weights[valid]).sum(axis=1)
        realised = float(port.std(ddof=0) * np.sqrt(252))
        scale = (
            float(np.clip(target_vol / realised, 0.10, 1.0)) if realised > 0 else 1.0
        )
        return weights * scale, scale, realised

    def summary(
        self, weights: pd.Series, rank_df: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        """Constructs human-readable portfolio allocation summary."""
        s = weights[weights > 1e-6].sort_values(ascending=False)
        tbl = pd.DataFrame({"Symbol": s.index, "Weight %": (s.values * 100).round(2)})
        if rank_df is not None and "Industry" in rank_df.columns:
            ind_map = rank_df.set_index("Symbol")["Industry"].to_dict()
            tbl["Industry"] = tbl["Symbol"].map(ind_map)
        return tbl.reset_index(drop=True)
