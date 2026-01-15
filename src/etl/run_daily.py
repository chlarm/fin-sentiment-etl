from __future__ import annotations
import argparse
from datetime import timedelta
import pendulum
import pandas as pd

from src.config import Settings
from src.common.db import get_engine
from src.common.hashing import build_news_hash
from src.extract.prices_yahoo import fetch_daily_prices_yahoo
from src.extract.prices_stooq import fetch_daily_prices_stooq
from src.extract.news_rss import fetch_news_rss_for_ticker
from src.transform.price_features import add_return_features
from src.transform.sentiment import VaderScorer
from src.transform.sentiment_index import build_daily_sentiment_index
from src.load.dim import ensure_assets, ensure_source, ensure_dim_dates
from src.load.facts import upsert_price_daily, insert_news, upsert_daily_sentiment
from src.dq.checks import run_basic_checks

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--date", type=str, default=None, help="Run date in YYYY-MM-DD (default: today in PIPELINE_TZ)")
    return p.parse_args()

def _fetch_prices(settings: Settings, run_d):
    tickers = list(settings.tickers)
    if settings.price_source == "yahoo":
        try:
            df = fetch_daily_prices_yahoo(tickers, end_d=run_d, lookback_days=14)
            if df.empty:
                print("[price] yahoo returned empty; fallback to stooq")
                return fetch_daily_prices_stooq(tickers, end_d=run_d, lookback_days=60)
            return df
        except Exception as e:
            print(f"[price] yahoo failed: {e} -> fallback to stooq")
            return fetch_daily_prices_stooq(tickers, end_d=run_d, lookback_days=60)

    return fetch_daily_prices_stooq(tickers, end_d=run_d, lookback_days=60)

def main() -> None:
    settings = Settings()
    args = _parse_args()

    tz = pendulum.timezone(settings.pipeline_tz)
    run_d = pendulum.parse(args.date).date() if args.date else pendulum.now(tz).date()

    # dim_date window
    start_d = run_d - timedelta(days=60)
    end_d = run_d

    engine = get_engine(settings)
    scorer = VaderScorer(finance_lexicon=None)

    # 1) Extract prices
    price_raw = _fetch_prices(settings, run_d)
    price_feat = add_return_features(price_raw)

    # 2) Extract news (last N hours from now UTC)
    now_utc = pendulum.now("UTC")
    news_items = []
    for t in settings.tickers:
        news_items.extend(fetch_news_rss_for_ticker(
            ticker=t,
            rss_template=settings.news_rss_template,
            lookback_hours=settings.lookback_hours,
            now_utc=now_utc,
            debug=settings.news_debug,
        ))

    with engine.begin() as conn:
        ensure_dim_dates(conn, start_d, end_d)
        asset_map = ensure_assets(conn, list(settings.tickers))

        prices_cnt = upsert_price_daily(conn, asset_map, price_feat)

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

        # Build daily sentiment index from DB (last 7 days)
        window_start = run_d - timedelta(days=7)
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

        checks = run_basic_checks(conn)

    print("\n=== ETL DONE ===")
    print(f"run_date={run_d} tz={settings.pipeline_tz}")
    print(f"price_source={settings.price_source} tickers={list(settings.tickers)}")
    print(f"prices_upsert_rows={prices_cnt}")
    print(f"news_attempted_inserts={news_attempted} (dedup by news_hash in DB)")
    print(f"sentiment_daily_upsert_rows={si_cnt}")
    print(f"dq_checks={checks}")

if __name__ == "__main__":
    main()
