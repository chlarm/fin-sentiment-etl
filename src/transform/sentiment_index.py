from __future__ import annotations
import pandas as pd

def build_daily_sentiment_index(news_df: pd.DataFrame) -> pd.DataFrame:
    """Input columns: asset_id, published_d, sentiment_score, sentiment_label"""
    if news_df.empty:
        return news_df

    df = news_df.copy()
    df["pos"] = (df["sentiment_label"] == "pos").astype(int)
    df["neu"] = (df["sentiment_label"] == "neu").astype(int)
    df["neg"] = (df["sentiment_label"] == "neg").astype(int)

    g = df.groupby(["asset_id", "published_d"], as_index=False)
    out = g.agg(
        news_count=("sentiment_score", "count"),
        sentiment_mean=("sentiment_score", "mean"),
        sentiment_median=("sentiment_score", "median"),
        pos_count=("pos", "sum"),
        neu_count=("neu", "sum"),
        neg_count=("neg", "sum"),
    )
    return out.rename(columns={"published_d": "d"})
