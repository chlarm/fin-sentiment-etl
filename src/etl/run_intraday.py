"""
run_intraday.py — Near-realtime news sentiment ETL
===================================================
• Run every 30 minutes via Cloud Scheduler → Cloud Run Job
• Fetches only the last N hours of news (default 3h)
• Uses VADER scorer only — no FinBERT/PyTorch (fast, lightweight)
• Skips price fetch (Yahoo Finance is EOD only; prices come from daily run)
• Updates fact_news and fact_sentiment_daily
"""
from __future__ import annotations
import argparse
from datetime import timedelta
import pendulum
import pandas as pd

from src.config import Settings
from src.common.db import get_engine
from src.common.hashing import build_news_hash
from src.extract.news_rss import fetch_news_rss_for_ticker
from src.transform.sentiment import VaderScorer
from src.transform.sentiment_index import build_daily_sentiment_index
from src.load.dim import ensure_assets, ensure_source, ensure_dim_dates
from src.load.facts import insert_news, upsert_daily_sentiment


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Near-realtime intraday news ETL (VADER only)")
    p.add_argument("--lookback-hours", type=int, default=None,
                   help="Override lookback window in hours (default: INTRADAY_LOOKBACK_HOURS from env)")
    return p.parse_args()


def main() -> None:
    settings = Settings()
    args = _parse_args()

    tz = pendulum.timezone(settings.pipeline_tz)
    now_utc = pendulum.now("UTC")
    run_d = pendulum.now(tz).date()

    lookback_hours = args.lookback_hours or settings.intraday_lookback_hours

    print(f"[intraday] Starting near-realtime ETL run")
    print(f"[intraday] run_date={run_d}  lookback={lookback_hours}h  tickers={len(settings.tickers)}")

    # VADER scorer — instant load, no GPU, ~1ms per article
    scorer = VaderScorer()

    engine = get_engine(settings)

    # Build news URL per ticker (same logic as daily run)
    search_terms = settings.ticker_search_terms

    def _news_url(ticker: str) -> str:
        search_q = search_terms.get(ticker, ticker)
        q_encoded = search_q.replace(" ", "%20")
        return (
            "https://news.google.com/rss/search"
            f"?q={q_encoded}%20market&hl=en-US&gl=US&ceid=US:en"
        )

    # Fetch news for all tickers
    news_items = []
    for t in settings.tickers:
        feed_url = _news_url(t)
        items = fetch_news_rss_for_ticker(
            ticker=t,
            rss_template=feed_url,
            lookback_hours=lookback_hours,
            now_utc=now_utc,
            trusted_sources=settings.trusted_news_sources,
            debug=settings.news_debug,
        )
        news_items.extend(items)

    print(f"[intraday] Fetched {len(news_items)} news items across all tickers")

    if not news_items:
        print("[intraday] No new articles found — exiting cleanly")
        return

    # Ensure dim_date covers today
    with engine.begin() as conn:
        ensure_dim_dates(conn, run_d, run_d)
        asset_map = ensure_assets(conn, list(settings.tickers))

        news_rows = []
        for item in news_items:
            asset_id = asset_map.get(item.ticker)
            if not asset_id:
                continue

            source_id = ensure_source(conn, item.source_name, "rss", item.base_url)
            s = scorer.score(item.title)

            published_d = pendulum.instance(item.published_at_utc).date()
            ensure_dim_dates(conn, published_d, published_d)

            published_iso = pendulum.instance(item.published_at_utc).to_iso8601_string()
            nh = build_news_hash(item.ticker, published_iso, item.title, item.url)

            news_rows.append({
                "asset_id": asset_id,
                "source_id": source_id,
                "published_at": item.published_at_utc,
                "published_d": published_d,
                "title": item.title,
                "url": item.url,
                "news_hash": nh,
                "sentiment_score": s.score,
                "sentiment_label": s.label,
            })

        news_attempted = insert_news(conn, news_rows)

        # Refresh sentiment index for today and yesterday
        window_start = run_d - timedelta(days=2)
        df_news = pd.read_sql(
            """
            SELECT asset_id, published_d, sentiment_score, sentiment_label
            FROM fact_news
            WHERE published_d BETWEEN %(s)s AND %(e)s
            """,
            conn,
            params={"s": window_start, "e": run_d},
        )
        si = build_daily_sentiment_index(df_news)
        si_cnt = upsert_daily_sentiment(conn, si)

    print(f"\n=== INTRADAY ETL DONE ===")
    print(f"run_date={run_d}  lookback={lookback_hours}h")
    print(f"news_attempted_inserts={news_attempted} (dedup by news_hash in DB)")
    print(f"sentiment_daily_upsert_rows={si_cnt}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[intraday] FATAL ERROR: {e}")
        from src.alerting import send_email_alert
        send_email_alert("❌ INTRADAY ETL FAILED ❌", f"Error: {e}")
        raise
