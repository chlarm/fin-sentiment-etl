from __future__ import annotations
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

def upsert_price_daily(conn: Connection, asset_map: dict[str, int], df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    rows = []
    for r in df.itertuples(index=False):
        asset_id = asset_map.get(r.ticker)
        if not asset_id:
            continue
        rows.append({
            "asset_id": asset_id,
            "d": r.d,
            "open": None if pd.isna(r.open) else float(r.open),
            "high": None if pd.isna(r.high) else float(r.high),
            "low": None if pd.isna(r.low) else float(r.low),
            "close": None if pd.isna(r.close) else float(r.close),
            "adj_close": None if pd.isna(getattr(r, "adj_close", None)) else float(r.adj_close),
            "volume": None if pd.isna(r.volume) else int(r.volume),
            "return_1d": None if pd.isna(getattr(r, "return_1d", None)) else float(r.return_1d),
            "pct_change": None if pd.isna(getattr(r, "pct_change", None)) else float(r.pct_change),
        })

    if not rows:
        return 0

    conn.execute(
        text("""
        INSERT INTO fact_price_daily
          (asset_id, d, open, high, low, close, adj_close, volume, return_1d, pct_change)
        VALUES
          (:asset_id, :d, :open, :high, :low, :close, :adj_close, :volume, :return_1d, :pct_change)
        ON CONFLICT (asset_id, d)
        DO UPDATE SET
          open=EXCLUDED.open,
          high=EXCLUDED.high,
          low=EXCLUDED.low,
          close=EXCLUDED.close,
          adj_close=EXCLUDED.adj_close,
          volume=EXCLUDED.volume,
          return_1d=EXCLUDED.return_1d,
          pct_change=EXCLUDED.pct_change,
          updated_at=now()
        """),
        rows,
    )
    return len(rows)

def insert_news(conn: Connection, rows: list[dict]) -> int:
    if not rows:
        return 0

    conn.execute(
        text("""
        INSERT INTO fact_news
          (asset_id, source_id, published_at, published_d, title, url, news_hash, sentiment_score, sentiment_label)
        VALUES
          (:asset_id, :source_id, :published_at, :published_d, :title, :url, :news_hash, :sentiment_score, :sentiment_label)
        ON CONFLICT (news_hash) DO NOTHING
        """),
        rows,
    )
    return len(rows)

def upsert_daily_sentiment(conn: Connection, df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    rows = []
    for r in df.itertuples(index=False):
        rows.append({
            "asset_id": int(r.asset_id),
            "d": r.d,
            "news_count": int(r.news_count),
            "sentiment_mean": None if pd.isna(r.sentiment_mean) else float(r.sentiment_mean),
            "sentiment_median": None if pd.isna(r.sentiment_median) else float(r.sentiment_median),
            "pos_count": int(r.pos_count),
            "neu_count": int(r.neu_count),
            "neg_count": int(r.neg_count),
        })

    conn.execute(
        text("""
        INSERT INTO fact_sentiment_daily
          (asset_id, d, news_count, sentiment_mean, sentiment_median, pos_count, neu_count, neg_count)
        VALUES
          (:asset_id, :d, :news_count, :sentiment_mean, :sentiment_median, :pos_count, :neu_count, :neg_count)
        ON CONFLICT (asset_id, d)
        DO UPDATE SET
          news_count=EXCLUDED.news_count,
          sentiment_mean=EXCLUDED.sentiment_mean,
          sentiment_median=EXCLUDED.sentiment_median,
          pos_count=EXCLUDED.pos_count,
          neu_count=EXCLUDED.neu_count,
          neg_count=EXCLUDED.neg_count,
          updated_at=now()
        """),
        rows,
    )
    return len(rows)
