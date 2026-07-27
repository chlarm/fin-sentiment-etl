#!/usr/bin/env python3
"""
Delete fact_news rows whose publisher is NOT in TRUSTED_NEWS_SOURCES, and
rebuild fact_sentiment_daily for the affected (asset_id, d) pairs from the
trusted news that remains.

Why these rows exist at all: the Airflow DAG loads .env.airflow with
`set -a && source .env.airflow`, and TRUSTED_NEWS_SOURCES was unquoted while
containing spaces — so bash truncated the assignment, the variable came out
empty, and src/config.py turned that into an empty tuple, which
src/extract/news_rss.py treats as falsy and skips filtering entirely. Fixed in
.env.airflow (the value is now quoted); this script cleans up what got in.

IMPORTANT — legacy placeholder sources are deliberately NOT purged:
before per-article source extraction worked, news_rss.py's _guess_source()
fell back to the *feed* domain, so ~1.5k early rows are recorded as
"news.google.com" rather than their real publisher. Those rows may well have
passed the trusted filter at ingest time; we simply can't tell the publisher
from what was stored. They are the bulk of the earliest (and longest)
sentiment history, so deleting them on a technicality would destroy far more
real signal than the contamination it's meant to remove. They are excluded by
name below rather than by a date cutoff, so the rule stays explicit.

Matching mirrors news_rss.py exactly: a source is trusted if any configured
trusted substring appears in the lowercased source name.

Usage:
    python -m src.scripts.purge_untrusted_news --dry-run   # report only
    python -m src.scripts.purge_untrusted_news             # apply
"""
from __future__ import annotations
import argparse
import pandas as pd
from sqlalchemy import text

from src.config import Settings
from src.common.db import get_engine
from src.transform.sentiment_index import build_daily_sentiment_index
from src.load.facts import upsert_daily_sentiment

# Feed-level fallback names recorded before per-article source extraction
# worked — not real publishers, and not evidence the filter was bypassed.
LEGACY_PLACEHOLDER_SOURCES = {"news.google.com"}


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="Report what would be deleted, change nothing")
    return p.parse_args()


def find_untrusted_source_ids(conn, trusted: tuple[str, ...]) -> list[tuple[int, str, int]]:
    """Return (source_id, source_name, row_count) for every source that fails
    the trusted-substring test and isn't a legacy placeholder."""
    rows = conn.execute(
        text("""
            SELECT s.source_id, s.source_name, COUNT(fn.news_id) AS n
            FROM dim_source s
            JOIN fact_news fn ON fn.source_id = s.source_id
            GROUP BY s.source_id, s.source_name
        """)
    ).fetchall()

    out = []
    for source_id, source_name, n in rows:
        name = (source_name or "").lower()
        if name in LEGACY_PLACEHOLDER_SOURCES:
            continue
        if any(t in name for t in trusted):
            continue
        out.append((source_id, source_name, n))
    return sorted(out, key=lambda r: -r[2])


def main() -> None:
    args = _parse_args()
    settings = Settings()
    engine = get_engine(settings)
    trusted = settings.trusted_news_sources

    if not trusted:
        print("TRUSTED_NEWS_SOURCES is empty — refusing to run (that would flag every source).")
        return

    with engine.begin() as conn:
        untrusted = find_untrusted_source_ids(conn, trusted)
        if not untrusted:
            print("No untrusted-source rows found — nothing to purge.")
            return

        ids = [r[0] for r in untrusted]
        total = sum(r[2] for r in untrusted)

        print(f"=== Untrusted sources found: {len(untrusted)} ({total} rows) ===")
        for _, name, n in untrusted[:15]:
            print(f"  {name:<32} {n}")
        if len(untrusted) > 15:
            print(f"  ... and {len(untrusted) - 15} more")
        print(f"(excluded as legacy placeholders: {sorted(LEGACY_PLACEHOLDER_SOURCES)})")

        affected = conn.execute(
            text("SELECT DISTINCT asset_id, published_d AS d FROM fact_news WHERE source_id = ANY(:ids)"),
            {"ids": ids},
        ).fetchall()
        affected_pairs = pd.DataFrame(affected, columns=["asset_id", "d"])
        affected_pairs["d"] = pd.to_datetime(affected_pairs["d"]).dt.date

        if args.dry_run:
            print(f"\n[dry-run] would delete {total} fact_news rows")
            print(f"[dry-run] would rebuild {len(affected_pairs)} (asset_id, d) sentiment pairs")
            return

        deleted = conn.execute(
            text("DELETE FROM fact_news WHERE source_id = ANY(:ids)"),
            {"ids": ids},
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

            # Restrict to exactly the affected pairs so we only touch what we deleted.
            remaining = remaining.merge(
                affected_pairs.rename(columns={"d": "published_d"}),
                on=["asset_id", "published_d"],
                how="inner",
            )

            si = build_daily_sentiment_index(remaining)
            rebuilt_pairs = upsert_daily_sentiment(conn, si)

        zero_news_pairs = len(affected_pairs) - rebuilt_pairs

    print("\n=== Untrusted news purge complete ===")
    print(f"fact_news rows deleted: {deleted}")
    print(f"(asset_id, d) pairs affected: {len(affected_pairs)}")
    print(f"pairs rebuilt from remaining trusted news: {rebuilt_pairs}")
    print(f"pairs now with zero news (removed, not rebuilt): {zero_news_pairs}")


if __name__ == "__main__":
    main()
