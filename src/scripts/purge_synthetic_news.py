#!/usr/bin/env python3
"""
Delete all synthetic/fabricated rows from fact_news (inserted by the now-removed
generate_demo_news.py demo generator) and rebuild fact_sentiment_daily for the
affected (asset_id, d) pairs from whatever REAL news remains.

Pairs that have no real news left after the purge correctly end up with no
fact_sentiment_daily row at all (not a zero/null placeholder), matching how the
table is populated elsewhere in the pipeline.

Idempotent: safe to re-run; if no synthetic source exists, it's a no-op.

Usage:
    python -m src.scripts.purge_synthetic_news
"""
from __future__ import annotations
import pandas as pd
from sqlalchemy import text

from src.config import Settings
from src.common.db import get_engine
from src.transform.sentiment_index import build_daily_sentiment_index
from src.load.facts import upsert_daily_sentiment


def main() -> None:
    settings = Settings()
    engine = get_engine(settings)

    with engine.begin() as conn:
        synthetic_ids = [
            row[0]
            for row in conn.execute(
                text("SELECT source_id FROM dim_source WHERE source_type = 'synthetic'")
            ).fetchall()
        ]
        if not synthetic_ids:
            print("No synthetic sources found in dim_source — nothing to purge.")
            return

        affected = conn.execute(
            text("""
                SELECT DISTINCT asset_id, published_d AS d
                FROM fact_news
                WHERE source_id = ANY(:ids)
            """),
            {"ids": synthetic_ids},
        ).fetchall()
        affected_pairs = pd.DataFrame(affected, columns=["asset_id", "d"])
        affected_pairs["d"] = pd.to_datetime(affected_pairs["d"]).dt.date

        deleted = conn.execute(
            text("DELETE FROM fact_news WHERE source_id = ANY(:ids)"),
            {"ids": synthetic_ids},
        ).rowcount

        rebuilt_pairs = 0
        if not affected_pairs.empty:
            conn.execute(
                text("DELETE FROM fact_sentiment_daily WHERE asset_id = :asset_id AND d = :d"),
                affected_pairs.to_dict("records"),
            )

            asset_ids = affected_pairs["asset_id"].unique().tolist()
            min_d, max_d = affected_pairs["d"].min(), affected_pairs["d"].max()
            remaining = pd.read_sql(
                text("""
                    SELECT asset_id, published_d, sentiment_score, sentiment_label
                    FROM fact_news
                    WHERE asset_id = ANY(:asset_ids) AND published_d BETWEEN :min_d AND :max_d
                """),
                conn,
                params={"asset_ids": asset_ids, "min_d": min_d, "max_d": max_d},
            )
            remaining["published_d"] = pd.to_datetime(remaining["published_d"]).dt.date

            # Restrict to exactly the affected pairs so we only touch what we deleted
            # (the wider asset/date-range pull above is just to fetch candidates cheaply).
            remaining = remaining.merge(
                affected_pairs.rename(columns={"d": "published_d"}),
                on=["asset_id", "published_d"],
                how="inner",
            )

            si = build_daily_sentiment_index(remaining)
            rebuilt_pairs = upsert_daily_sentiment(conn, si)

        zero_news_pairs = len(affected_pairs) - rebuilt_pairs

    print("=== Synthetic news purge complete ===")
    print(f"fact_news rows deleted: {deleted}")
    print(f"(asset_id, d) pairs affected: {len(affected_pairs)}")
    print(f"pairs rebuilt with remaining real news: {rebuilt_pairs}")
    print(f"pairs now with zero news (deleted, not rebuilt): {zero_news_pairs}")


if __name__ == "__main__":
    main()
