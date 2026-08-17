import numpy as np
import pandas as pd

def paired_alpha(stock, benchmark):
    pair = pd.concat([stock, benchmark], axis=1).dropna()
    if len(pair) < 30:
        return np.nan
    y, x = pair.iloc[:, 0], pair.iloc[:, 1]
    var = float(x.var())
    if var <= 0:
        return np.nan
    beta = float(y.cov(x)) / var
    return (float(y.mean()) - beta * float(x.mean())) * 252

def test_missing_stock_observations_are_excluded_from_both_beta_and_mean():
    idx = pd.bdate_range("2025-01-01", periods=80)
    benchmark = pd.Series(np.linspace(0.001, 0.003, len(idx)), index=idx)
    stock = 0.5 * benchmark + 0.001
    stock = pd.Series(stock, index=idx)
    stock.iloc[[10, 20, 21, 45]] = np.nan
    got = paired_alpha(stock, benchmark)
    expected = paired_alpha(stock.dropna(), benchmark.loc[stock.dropna().index])
    assert np.isclose(got, expected, equal_nan=True)

def test_insufficient_paired_observations_returns_nan():
    idx = pd.bdate_range("2025-01-01", periods=40)
    benchmark = pd.Series(0.002, index=idx)
    stock = pd.Series(0.003, index=idx)
    stock.iloc[:15] = np.nan
    assert np.isnan(paired_alpha(stock, benchmark))
