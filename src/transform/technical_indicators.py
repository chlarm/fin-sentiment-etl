from __future__ import annotations
import pandas as pd


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def add_technical_indicators(price_df: pd.DataFrame) -> pd.DataFrame:
    """Input columns: ticker, d, close, return_1d (as produced by price_features.add_return_features).
    Output adds one row per (ticker, d) with the indicator columns for fact_technical_daily."""
    if price_df.empty:
        return price_df

    df = price_df.copy().sort_values(["ticker", "d"])
    g = df.groupby("ticker")["close"]

    df["sma_20"] = g.transform(lambda s: s.rolling(20, min_periods=20).mean())
    df["sma_50"] = g.transform(lambda s: s.rolling(50, min_periods=50).mean())
    df["sma_200"] = g.transform(lambda s: s.rolling(200, min_periods=200).mean())

    df["ema_12"] = g.transform(lambda s: s.ewm(span=12, min_periods=12, adjust=False).mean())
    df["ema_26"] = g.transform(lambda s: s.ewm(span=26, min_periods=26, adjust=False).mean())
    df["macd"] = df["ema_12"] - df["ema_26"]
    df["macd_signal"] = df.groupby("ticker")["macd"].transform(
        lambda s: s.ewm(span=9, min_periods=9, adjust=False).mean()
    )
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    df["rsi_14"] = g.transform(lambda s: _rsi(s, 14))

    df["volatility_20"] = df.groupby("ticker")["return_1d"].transform(
        lambda s: s.rolling(20, min_periods=20).std()
    )

    df["momentum_5"] = g.transform(lambda s: s.pct_change(5))
    df["momentum_21"] = g.transform(lambda s: s.pct_change(21))
    df["momentum_63"] = g.transform(lambda s: s.pct_change(63))

    cols = [
        "ticker", "d", "sma_20", "sma_50", "sma_200", "ema_12", "ema_26",
        "macd", "macd_signal", "macd_hist", "rsi_14", "volatility_20",
        "momentum_5", "momentum_21", "momentum_63",
    ]
    return df[cols]
