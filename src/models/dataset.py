from __future__ import annotations
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

TECHNICAL_FEATURES = [
    "rsi_14", "macd_hist", "volatility_20",
    "momentum_5", "momentum_21", "momentum_63",
    "price_vs_sma20", "price_vs_sma50",
]
SENTIMENT_FEATURES = ["sentiment_index", "sentiment_lag1", "sentiment_lag2", "news_count"]


def _add_targets(df: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    """Forward-looking direction targets. Computed per-ticker so horizons never
    cross a ticker boundary. NaN (can't see that far into the future yet) is
    left as-is — callers drop those rows before training, never fill them."""
    df = df.sort_values(["ticker", "d"]).copy()
    for h in horizons:
        fwd_close = df.groupby("ticker")["close"].shift(-h)
        fwd_return = (fwd_close / df["close"]) - 1
        df[f"target_ret_{h}d"] = fwd_return
        df[f"target_dir_{h}d"] = (fwd_return > 0).astype("Int64")
        df.loc[fwd_return.isna(), f"target_dir_{h}d"] = pd.NA
    return df


def build_technical_dataset(engine: Engine, tickers: list[str], horizons: list[int]) -> pd.DataFrame:
    """Price + technical-indicator features for every ticker, full history.
    No sentiment — this is the large, robust baseline dataset (10 years)."""
    sql = """
    SELECT a.ticker, p.d, p.close,
           t.rsi_14, t.macd_hist, t.volatility_20,
           t.momentum_5, t.momentum_21, t.momentum_63,
           t.sma_20, t.sma_50
    FROM fact_price_daily p
    JOIN dim_asset a ON a.asset_id = p.asset_id
    JOIN fact_technical_daily t ON t.asset_id = p.asset_id AND t.d = p.d
    WHERE a.ticker = ANY(:tickers)
    ORDER BY a.ticker, p.d
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn, params={"tickers": tickers})

    if df.empty:
        return df

    df["price_vs_sma20"] = (df["close"] / df["sma_20"]) - 1
    df["price_vs_sma50"] = (df["close"] / df["sma_50"]) - 1
    df = _add_targets(df, horizons)
    return df


def build_sentiment_dataset(engine: Engine, tickers: list[str], horizons: list[int]) -> pd.DataFrame:
    """Same as build_technical_dataset but joined with sentiment history too —
    only rows where sentiment actually exists for that ticker/day survive the
    join, which is why this naturally comes out much shorter than the
    technical-only dataset (sentiment coverage started ~Dec 2025)."""
    sql = """
    SELECT a.ticker, p.d, p.close,
           t.rsi_14, t.macd_hist, t.volatility_20,
           t.momentum_5, t.momentum_21, t.momentum_63,
           t.sma_20, t.sma_50,
           s.sentiment_mean AS sentiment_index, s.news_count
    FROM fact_price_daily p
    JOIN dim_asset a ON a.asset_id = p.asset_id
    JOIN fact_technical_daily t ON t.asset_id = p.asset_id AND t.d = p.d
    JOIN fact_sentiment_daily s ON s.asset_id = p.asset_id AND s.d = p.d
    WHERE a.ticker = ANY(:tickers)
    ORDER BY a.ticker, p.d
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn, params={"tickers": tickers})

    if df.empty:
        return df

    df["price_vs_sma20"] = (df["close"] / df["sma_20"]) - 1
    df["price_vs_sma50"] = (df["close"] / df["sma_50"]) - 1
    df["sentiment_lag1"] = df.groupby("ticker")["sentiment_index"].shift(1)
    df["sentiment_lag2"] = df.groupby("ticker")["sentiment_index"].shift(2)
    df = _add_targets(df, horizons)
    return df


def eligible_sentiment_tickers(engine: Engine, min_days: int = 30) -> list[str]:
    """Tickers with enough real sentiment history to be worth modeling —
    avoids training on a ticker that has 1-2 sentiment days total."""
    sql = """
    SELECT a.ticker, COUNT(*) AS n
    FROM fact_sentiment_daily s
    JOIN dim_asset a ON a.asset_id = s.asset_id
    GROUP BY a.ticker
    HAVING COUNT(*) >= :min_days
    ORDER BY n DESC
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn, params={"min_days": min_days})
    return df["ticker"].tolist()
