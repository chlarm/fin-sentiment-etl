"""
Daily ETL, split into independent stages.

Why stages. Everything used to run inside one transaction and one Airflow
task, which coupled failures that have nothing to do with each other: loading
FinBERT and fetching 30 RSS feeds is slow and flaky, price ingestion is fast
and reliable, and yet a stall in the former rolled back the latter. Worse, the
one thing that must never be lost is news — Google News RSS has no archive, so
a day not fetched is gone permanently — while prices and technical indicators
can always be recomputed from history.

Each stage now commits on its own and can run as its own Airflow task:

    prices  fetch OHLCV, repair return_1d from full history, rebuild
            technical indicators. No model, no network beyond the price feed.
    news    fetch RSS, score with FinBERT, rebuild the daily sentiment index.
    dq      run the data-quality checks against whatever is in the DB and
            email the summary.

Running with no --stage does all three in order, so local use is unchanged.

Usage:
    python -m src.etl.run_daily
    python -m src.etl.run_daily --stage prices
    python -m src.etl.run_daily --stage news --date 2026-07-29
"""
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

STAGES = ("prices", "news", "dq")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--date", type=str, default=None, help="Run date in YYYY-MM-DD (default: today in PIPELINE_TZ)")
    p.add_argument("--stage", choices=STAGES, default=None,
                   help="Run a single stage. Default: all of them, in order.")
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


def stage_prices(settings: Settings, engine, run_d) -> None:
    """Prices, return repair and technical indicators. No model needed."""
    price_raw = _fetch_prices(settings, run_d)
    price_feat = add_return_features(price_raw)

    with engine.begin() as conn:
        ensure_dim_dates(conn, run_d - timedelta(days=60), run_d)
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

    print(f"[prices] upserted {prices_cnt} price rows, {technical_cnt} technical rows")


def stage_news(settings: Settings, engine, run_d) -> None:
    """RSS, FinBERT scoring and the daily sentiment index.

    Kept apart from prices because this is the slow, fragile half — the model
    load alone can stall on a Hugging Face hub call — and because it is the
    half whose data cannot be recovered if a day is missed.
    """
    print("Loading FinBERT Model...")
    scorer = FinbertScorer()
    print("Model Loaded!")

    now_utc = pendulum.now("UTC")
    search_terms = settings.ticker_search_terms

    def _news_url(ticker: str) -> str:
        """Return the RSS URL for a ticker, using override search terms when available."""
        search_q = search_terms.get(ticker, ticker)
        q_encoded = search_q.replace(" ", "%20")
        return (
            "https://news.google.com/rss/search"
            f"?q={q_encoded}%20market&hl=en-US&gl=US&ceid=US:en"
        )

    news_items = []
    for t in settings.tickers:
        items = fetch_news_rss_for_ticker(
            ticker=t,
            rss_template=_news_url(t),
            lookback_hours=settings.lookback_hours,
            now_utc=now_utc,
            trusted_sources=settings.trusted_news_sources,
            debug=settings.news_debug,
        )
        news_items.extend(items)
    print(f"[news] fetched {len(news_items)} items across {len(settings.tickers)} tickers")

    with engine.begin() as conn:
        ensure_dim_dates(conn, run_d - timedelta(days=60), run_d)
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

        # Build daily sentiment index from DB (last 7 days)
        df_news = pd.read_sql(
            """
            SELECT asset_id, published_d, sentiment_score, sentiment_label
            FROM fact_news
            WHERE published_d BETWEEN %(s)s AND %(e)s
            """,
            conn,
            params={"s": run_d - timedelta(days=7), "e": run_d},
        )
        si_cnt = upsert_daily_sentiment(conn, build_daily_sentiment_index(df_news))

    print(f"[news] attempted {news_attempted} inserts (dedup by news_hash), "
          f"{si_cnt} sentiment-index rows")


def stage_dq(settings: Settings, engine, run_d) -> None:
    """Checks and the summary email.

    Reports what is actually in the database rather than what this process
    just did, so the summary stays truthful when a stage was skipped, failed,
    or ran in a separate Airflow task.
    """
    with engine.begin() as conn:
        checks = run_basic_checks(conn)
        coverage = run_coverage_check(conn, window_days=7)
        technical_gaps = run_technical_gap_check(conn, window_days=30)
        freshness = pd.read_sql(
            """
            SELECT (SELECT max(d) FROM fact_price_daily)       AS latest_price,
                   (SELECT max(published_d) FROM fact_news)    AS latest_news,
                   (SELECT max(d) FROM fact_sentiment_daily)   AS latest_sentiment,
                   (SELECT max(d) FROM fact_technical_daily)   AS latest_technical
            """,
            conn,
        ).iloc[0]

    checks_passed = all(v == 0 for v in checks.values())
    thin_coverage = coverage[coverage["zero_news_days"] >= coverage["trading_days"]] if not coverage.empty else coverage

    print("\n=== ETL DONE ===")
    print(f"run_date={run_d} tz={settings.pipeline_tz}")
    print(f"latest in DB: {freshness.to_dict()}")
    print(f"dq_checks={checks} ({'Pass' if checks_passed else 'Fail'})")
    if not thin_coverage.empty:
        print(f"news_coverage: {len(thin_coverage)} ticker(s) with ZERO real news in the last 7 days: "
              f"{thin_coverage['ticker'].tolist()}")
    if not technical_gaps.empty:
        print(f"technical_indicator_gaps (last 30d): {technical_gaps.set_index('ticker')['missing_technical_days'].to_dict()}")

    stale_price = freshness["latest_price"] is None or (run_d - freshness["latest_price"]).days > 4
    status = "⚠️ ETL STALE" if (stale_price or not checks_passed) else "✅ ETL SUCCESS ✅"

    send_email_alert(status, (
        f"Date: {run_d}\n"
        f"Latest price: {freshness['latest_price']}\n"
        f"Latest news: {freshness['latest_news']}\n"
        f"Latest sentiment: {freshness['latest_sentiment']}\n"
        f"Latest technical: {freshness['latest_technical']}\n"
        f"DQ Checks: {'Pass' if checks_passed else 'Fail'} ({checks})\n"
        f"Tickers with zero real news (last 7d): "
        f"{thin_coverage['ticker'].tolist() if not thin_coverage.empty else 'none'}\n"
        f"Technical indicator gaps (last 30d): "
        f"{technical_gaps['ticker'].tolist() if not technical_gaps.empty else 'none'}"
    ))


def main() -> None:
    settings = Settings()
    args = _parse_args()

    tz = pendulum.timezone(settings.pipeline_tz)
    run_d = pendulum.parse(args.date).date() if args.date else pendulum.now(tz).date()
    engine = get_engine(settings)

    runners = {"prices": stage_prices, "news": stage_news, "dq": stage_dq}
    for name in ([args.stage] if args.stage else STAGES):
        print(f"\n>>> stage: {name}")
        runners[name](settings, engine, run_d)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        from src.alerting import send_email_alert
        send_email_alert("❌ ETL FAILED ❌", f"Error: {e}")
        raise
