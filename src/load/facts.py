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
        if pd.isna(r.close):
            # Never write a hollow row over — or in place of — a real close price.
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

def upsert_technical_daily(conn: Connection, asset_map: dict[str, int], df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    cols = [
        "sma_20", "sma_50", "sma_200", "ema_12", "ema_26",
        "macd", "macd_signal", "macd_hist", "rsi_14", "volatility_20",
        "momentum_5", "momentum_21", "momentum_63",
    ]
    rows = []
    for r in df.itertuples(index=False):
        asset_id = asset_map.get(r.ticker)
        if not asset_id:
            continue
        row = {"asset_id": asset_id, "d": r.d}
        for c in cols:
            v = getattr(r, c)
            row[c] = None if pd.isna(v) else float(v)
        rows.append(row)

    if not rows:
        return 0

    set_clause = ", ".join(f"{c}=EXCLUDED.{c}" for c in cols)
    conn.execute(
        text(f"""
        INSERT INTO fact_technical_daily
          (asset_id, d, {", ".join(cols)})
        VALUES
          (:asset_id, :d, {", ".join(":" + c for c in cols)})
        ON CONFLICT (asset_id, d)
        DO UPDATE SET
          {set_clause},
          updated_at=now()
        """),
        rows,
    )
    return len(rows)

def upsert_fundamentals_quarterly(conn: Connection, asset_map: dict[str, int], rows_in: list[dict]) -> int:
    if not rows_in:
        return 0

    rows = []
    for r in rows_in:
        asset_id = asset_map.get(r["ticker"])
        if not asset_id:
            continue
        rows.append({
            "asset_id": asset_id,
            "fiscal_period_end": r["fiscal_period_end"],
            "announced_d": r.get("announced_d"),
            "revenue": r.get("revenue"),
            "net_income": r.get("net_income"),
            "eps_diluted": r.get("eps_diluted"),
            "gross_margin": r.get("gross_margin"),
            "net_margin": r.get("net_margin"),
            "total_debt": r.get("total_debt"),
            "stockholders_equity": r.get("stockholders_equity"),
            "free_cash_flow": r.get("free_cash_flow"),
            "source": r.get("source"),
        })

    if not rows:
        return 0

    conn.execute(
        text("""
        INSERT INTO fact_fundamentals_quarterly
          (asset_id, fiscal_period_end, announced_d, revenue, net_income, eps_diluted,
           gross_margin, net_margin, total_debt, stockholders_equity, free_cash_flow, source)
        VALUES
          (:asset_id, :fiscal_period_end, :announced_d, :revenue, :net_income, :eps_diluted,
           :gross_margin, :net_margin, :total_debt, :stockholders_equity, :free_cash_flow, :source)
        ON CONFLICT (asset_id, fiscal_period_end)
        DO UPDATE SET
          announced_d=EXCLUDED.announced_d,
          revenue=EXCLUDED.revenue,
          net_income=EXCLUDED.net_income,
          eps_diluted=EXCLUDED.eps_diluted,
          gross_margin=EXCLUDED.gross_margin,
          net_margin=EXCLUDED.net_margin,
          total_debt=EXCLUDED.total_debt,
          stockholders_equity=EXCLUDED.stockholders_equity,
          free_cash_flow=EXCLUDED.free_cash_flow,
          source=EXCLUDED.source,
          updated_at=now()
        """),
        rows,
    )
    return len(rows)
