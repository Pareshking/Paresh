"""
Portfolio construction and optimization engine.
Weighting schemes: Equal Weight, Inverse Volatility, Equal Risk Contribution (Risk Parity).
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


def apply_caps(
    weights: pd.Series,
    sector_map: dict[str, str] | None,
    *,
    sector_cap: float = 0.30,
    stock_cap: float = 0.10,
) -> pd.Series:
    """Project weights onto the stock and sector caps. Both are actually binding.

    Two callers need this and only one had it. ``run_backtest`` accepted
    ``stock_cap`` and ``sector_cap``, put them in its cache key, and never
    applied them: a 1% stock cap with a 2% sector cap produced byte-identical
    statistics to 100%/100%, and the "Current Holdings" book the Backtest tab
    tells you to trade came out 75% in one industry while the Portfolio tab, on
    the same ranking and the same settings, held the cap. A control that does
    nothing is worse than no control, because the user believes the limit is on.

    The projection itself was also wrong, in the shipped Portfolio tab, in the
    direction that matters. It clipped to the caps and then renormalised the
    whole vector back to 1.0 -- and scaling everything up lifts the clipped
    names straight back through the cap they were just clipped to. Twenty equal
    weights under a 6% stock cap and a 40% sector cap came out with a 6.98%
    position and 58.1% in one sector, against a docstring promising both were
    "strictly satisfied" and a UI captioned "Cap: 40%".

    So the deficit left by clipping is redistributed to HEADROOM instead of
    scaled into everyone: each name may absorb at most what its own cap allows,
    and at most its share of what its sector's cap allows. Every step therefore
    stays inside the feasible set, and the result satisfies both caps or says it
    could not.

    Caps are made feasible before they are applied: a cap below 1/n (or below
    1/num_sectors) cannot be met by any portfolio of n names, so it is raised to
    the tightest achievable value rather than iterated against forever.
    """
    if stock_cap <= 0 or sector_cap <= 0:
        raise ValueError("Caps must be > 0")

    w = weights.copy().fillna(0.0).astype(float)
    n = len(w)
    if n == 0:
        return w
    if n == 1:
        return pd.Series([1.0], index=w.index)

    sec_groups: dict[str, list[str]] = {}
    if sector_map:
        for sym in w.index:
            sec_groups.setdefault(sector_map.get(sym, "Other"), []).append(sym)
    num_sec = max(len(sec_groups), 1)

    # Feasibility. Bumping each cap to its own floor is not enough: the two
    # interact. Seventeen names split 15/2 across two sectors, under a 5.9%
    # stock cap and a 50% sector cap, can hold at most 50% + 2x5.9% = 61.8% --
    # both caps individually "feasible", jointly impossible, and the projection
    # below would then hand back a fully-invested book that breaches them.
    #
    # Total capacity is sum_sectors min(sector_cap, n_i x stock_cap), which is
    # exactly linear in a common scale factor, so the smallest relaxation that
    # admits a fully-invested portfolio is 1/capacity applied to both caps.
    eff_stock_cap = max(stock_cap, 1.0 / n + 1e-9)
    eff_sector_cap = max(sector_cap, 1.0 / num_sec + 1e-9)
    capacity = sum(
        min(eff_sector_cap, len(syms) * eff_stock_cap)
        for syms in (sec_groups.values() or [list(w.index)])
    ) or 1.0
    relaxed = capacity < 1.0 - 1e-12
    if relaxed:
        eff_stock_cap /= capacity
        eff_sector_cap /= capacity
        logger.warning(
            "Concentration caps were jointly infeasible for %d names across %d "
            "sectors (capacity %.3f); relaxed to stock %.2f%% / sector %.2f%%.",
            n, num_sec, capacity, eff_stock_cap * 100, eff_sector_cap * 100,
        )

    if float(w.sum()) <= 0:
        w = pd.Series(1.0 / n, index=w.index)

    for _ in range(200):
        # 1. Clip to the individual cap.
        w = w.clip(upper=eff_stock_cap)

        # 2. Scale each over-weight sector down to its cap. Scaling DOWN can
        #    never breach the stock cap, so this leaves step 1 intact.
        for syms in sec_groups.values():
            total = float(w[syms].sum())
            if total > eff_sector_cap:
                w[syms] *= eff_sector_cap / total

        total = float(w.sum())
        if total > 1.0 + 1e-12:
            w /= total          # pure down-scale: still inside both caps
            continue
        deficit = 1.0 - total
        if deficit <= 1e-12:
            break

        # 3. Hand the deficit to headroom, never to everyone. A name can take
        #    at most (stock cap - its weight), and a sector's names can take at
        #    most (sector cap - the sector's weight) between them.
        room = (eff_stock_cap - w).clip(lower=0.0)
        for syms in sec_groups.values():
            sector_room = eff_sector_cap - float(w[syms].sum())
            wanted = float(room[syms].sum())
            if sector_room <= 0:
                room[syms] = 0.0
            elif wanted > sector_room:
                room[syms] *= sector_room / wanted
        available = float(room.sum())
        if available <= 1e-15:
            break               # caps jointly leave nowhere to put the rest
        w = w + room * min(1.0, deficit / available)

    total = float(w.sum())
    out = w / total if total > 0 else pd.Series(1.0 / n, index=w.index)
    # What was ACTUALLY enforced, so a caller showing "Cap: 30%" can show the
    # relaxation instead of the number the user typed.
    out.attrs["effective_stock_cap"] = eff_stock_cap
    out.attrs["effective_sector_cap"] = eff_sector_cap
    out.attrs["caps_relaxed"] = bool(relaxed)
    return out


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

        NOT REACHABLE FROM THE UI. Nothing calls this: the Portfolio tab offers
        Equal Weight and Inverse Volatility only. It is kept because the method
        is sound, and it is annotated because of what it does when it fails --
        four separate paths return a DIFFERENT weighting scheme, and three of
        them used to do so in silence. That is the failure mode Mean-Variance
        Optimisation was removed for (audit F1: it degraded to Equal Weight on
        any exception while still reporting itself as MVO).

        Every fallback now logs what it returned and why. A caller that wires
        this up must surface that to the user rather than labelling the result
        "Equal Risk Contribution" -- a book built by inverse volatility and
        captioned ERC is a false claim about how the money is allocated.
        """
        valid = [s for s in symbols if s in self.returns.columns]
        n = len(valid)
        if n < 2:
            logger.warning("ERC: %d usable name(s); returning Equal Weight, not ERC.", n)
            return self.equal_weight(symbols)

        ret_sub = self.returns[valid].iloc[-window:].dropna(how="any")
        if len(ret_sub) < 30:
            logger.warning(
                "ERC: only %d complete observations in a %d-session window; "
                "returning Inverse Volatility, not ERC.", len(ret_sub), window,
            )
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
            logger.warning(
                "ERC: SLSQP did not converge (%s); returning Inverse Volatility, "
                "not ERC.", res.message,
            )
            return self.inverse_volatility(valid)
        except Exception as e:
            logger.warning(f"Risk Parity solver error: {e} — fallback to inverse vol")
            return self.inverse_volatility(valid)


    def apply_constraints(
        self,
        weights: pd.Series,
        sector_cap: float = 0.30,
        stock_cap: float = 0.10,
    ) -> pd.Series:
        """Project weights onto the stock and sector caps. See ``apply_caps``."""
        return apply_caps(
            weights, self.sector_map, sector_cap=sector_cap, stock_cap=stock_cap
        )

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
