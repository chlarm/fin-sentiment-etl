from __future__ import annotations
import pandas as pd

def add_return_features(price_df: pd.DataFrame) -> pd.DataFrame:
    if price_df.empty:
        return price_df
    df = price_df.copy().sort_values(["ticker", "d"])
    df["prev_close"] = df.groupby("ticker")["close"].shift(1)
    df["return_1d"] = (df["close"] / df["prev_close"]) - 1
    df["pct_change"] = df["return_1d"] * 100
    return df.drop(columns=["prev_close"])
