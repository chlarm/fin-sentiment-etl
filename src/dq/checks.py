from __future__ import annotations
from sqlalchemy import text
from sqlalchemy.engine import Connection

def run_basic_checks(conn: Connection) -> dict[str, int]:
    dup = conn.execute(text("SELECT COUNT(*) - COUNT(DISTINCT news_hash) FROM fact_news")).scalar()
    null_close = conn.execute(text("SELECT COUNT(*) FROM fact_price_daily WHERE close IS NULL")).scalar()
    out_of_range = conn.execute(text("""
        SELECT COUNT(*)
        FROM fact_news
        WHERE sentiment_score IS NOT NULL AND (sentiment_score < -1.0 OR sentiment_score > 1.0)
    """)).scalar()
    return {
        "news_duplicates": int(dup or 0),
        "price_null_close": int(null_close or 0),
        "sentiment_out_of_range": int(out_of_range or 0),
    }
