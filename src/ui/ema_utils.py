import pandas as pd


def count_above_ema(rank_df: pd.DataFrame) -> int:
    """Count stocks above 50 EMA without failing on duplicate/unexpected columns."""
    ema_col = rank_df.get("Above 50 EMA")
    if ema_col is None:
        return 0
    if isinstance(ema_col, pd.DataFrame):
        ema_col = ema_col.iloc[:, -1]
    if not isinstance(ema_col, pd.Series):
        ema_col = pd.Series(ema_col, index=rank_df.index)
    normalized = ema_col.astype("string").str.strip().str.casefold()
    return int(normalized.isin({"true", "1", "✅"}).sum())
