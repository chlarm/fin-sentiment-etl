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
from src.transform.sentiment import FinbertScorer
from src.transform.sentiment_index import build_daily_sentiment_index
from src.load.dim import ensure_assets, ensure_source, ensure_dim_dates
from src.load.facts import upsert_price_daily, insert_news, upsert_daily_sentiment, upsert_technical_daily
from src.transform.technical_indicators import add_technical_indicators
from src.scripts.backfill_price_returns import recompute_returns_from_db
from src.dq.checks import run_basic_checks, run_coverage_check, run_technical_gap_check
from src.alerting import send_email_alert

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--date", type=str, default=None, help="Run date in YYYY-MM-DD (default: today in PIPELINE_TZ)")
    return p.parse_args()

def _fetch_prices(settings: Settings, run_d):
    tickers = list(settings.tickers)

    # --- Try Yahoo first (if configured) ---
    if settings.price_source == "yahoo":
        try:
            df = fetch_daily_prices_yahoo(tickers, end_d=run_d, lookback_days=14)
            if not df.empty:
                return df
            print("[price] yahoo returned empty; fallback to stooq")
        except Exception as e:
            print(f"[price] yahoo failed: {e} -> fallback to stooq")

    # --- Fallback to Stooq (also wrapped in try/except) ---
    try:
        df = fetch_daily_prices_stooq(tickers, end_d=run_d, lookback_days=60)
        if not df.empty:
            return df
        print("[price] stooq also returned empty — continuing ETL with no price data")
    except Exception as e:
        print(f"[price] stooq fallback also failed: {e} — continuing ETL with no price data")

    return pd.DataFrame()

def main() -> None:
    settings = Settings()
    args = _parse_args()

    tz = pendulum.timezone(settings.pipeline_tz)
    run_d = pendulum.parse(args.date).date() if args.date else pendulum.now(tz).date()

    # dim_date window
    start_d = run_d - timedelta(days=60)
    end_d = run_d

    engine = get_engine(settings)
    print("Loading FinBERT Model...")
    scorer = FinbertScorer()
    print("Model Loaded!")

    # 1) Extract prices
    price_raw = _fetch_prices(settings, run_d)
    price_feat = add_return_features(price_raw)

    # 2) Extract news (last N hours from now UTC)
    now_utc = pendulum.now("UTC")
    news_items = []
    search_terms = settings.ticker_search_terms

    # Build a custom RSS template that accepts a `search_q` param
    def _news_url(ticker: str) -> str:
        """Return the RSS URL for a ticker, using override search terms when available."""
        search_q = search_terms.get(ticker, ticker)
        # URL-encode spaces with %20
        q_encoded = search_q.replace(" ", "%20")
        # Use the configured template but override the search query
        return (
            "https://news.google.com/rss/search"
            f"?q={q_encoded}%20market&hl=en-US&gl=US&ceid=US:en"
        )

    for t in settings.tickers:
        feed_url = _news_url(t)
        items = fetch_news_rss_for_ticker(
            ticker=t,
            rss_template=feed_url,          # pass the resolved URL directly
            lookback_hours=settings.lookback_hours,
            now_utc=now_utc,
            trusted_sources=settings.trusted_news_sources,
            debug=settings.news_debug,
        )
        news_items.extend(items)

    with engine.begin() as conn:
        ensure_dim_dates(conn, start_d, end_d)
        asset_map = ensure_assets(conn, list(settings.tickers))

        prices_cnt = upsert_price_daily(conn, asset_map, price_feat)

        # Fix up return_1d/pct_change from the full stored close history —
        # add_return_features() above only saw this run's short lookback
        # batch, so its earliest row has no visible previous close and would
        # otherwise overwrite a previously-correct value with NULL. See
        # src/scripts/backfill_price_returns.py for the full story.
        recompute_returns_from_db(conn, list(settings.tickers))

        # Recompute technical indicators for every ticker from the full
        # price history now in the DB. Must run after price upsert; rolling
        # features (SMA200, momentum_63, ...) need long history, not just
        # today's batch, so this always reads back from the DB rather than
        # reusing price_feat.
        tech_price_df = pd.read_sql(
            """
            SELECT a.ticker, p.d, p.close, p.return_1d
            FROM fact_price_daily p
            JOIN dim_asset a ON a.asset_id = p.asset_id
            WHERE a.ticker = ANY(%(tickers)s)
            """,
            conn,
            params={"tickers": list(settings.tickers)},
        )
        tech_df = add_technical_indicators(tech_price_df)
        technical_cnt = upsert_technical_daily(conn, asset_map, tech_df)

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
        coverage = run_coverage_check(conn, window_days=7)
        technical_gaps = run_technical_gap_check(conn, window_days=30)

    checks_passed = all(v == 0 for v in checks.values())
    thin_coverage = coverage[coverage["zero_news_days"] >= coverage["trading_days"]] if not coverage.empty else coverage

    print("\n=== ETL DONE ===")
    print(f"run_date={run_d} tz={settings.pipeline_tz}")
    print(f"price_source={settings.price_source} tickers={list(settings.tickers)}")
    print(f"prices_upsert_rows={prices_cnt}")
    print(f"news_attempted_inserts={news_attempted} (dedup by news_hash in DB)")
    print(f"sentiment_daily_upsert_rows={si_cnt}")
    print(f"technical_indicator_upsert_rows={technical_cnt}")
    print(f"dq_checks={checks} ({'Pass' if checks_passed else 'Fail'})")
    if not thin_coverage.empty:
        print(f"news_coverage: {len(thin_coverage)} ticker(s) with ZERO real news in the last 7 days: "
              f"{thin_coverage['ticker'].tolist()}")
    if not technical_gaps.empty:
        print(f"technical_indicator_gaps (last 30d): {technical_gaps.set_index('ticker')['missing_technical_days'].to_dict()}")

    msg = (
        f"Date: {run_d}\n"
        f"Prices Rows: {prices_cnt}\n"
        f"News Rows: {news_attempted}\n"
        f"Indices Rows: {si_cnt}\n"
        f"DQ Checks: {'Pass' if checks_passed else 'Fail'} ({checks})\n"
        f"Tickers with zero real news (last 7d): {thin_coverage['ticker'].tolist() if not thin_coverage.empty else 'none'}\n"
        f"Technical indicator gaps (last 30d): {technical_gaps['ticker'].tolist() if not technical_gaps.empty else 'none'}"
    )
    send_email_alert("✅ ETL SUCCESS ✅", msg)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        from src.alerting import send_email_alert
        send_email_alert("❌ ETL FAILED ❌", f"Error: {e}")
        raise
