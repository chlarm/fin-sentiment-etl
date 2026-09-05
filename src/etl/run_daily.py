"""
Daily ETL, split into independent stages.

Why stages. Everything used to run inside one transaction and one Airflow
task, which coupled failures that have nothing to do with each other: loading
FinBERT and fetching 30 RSS feeds is slow and flaky, price ingestion is fast
and reliable, and yet a stall in the former rolled back the latter.

News is still the more valuable half to protect — its density depends on how
often we actually run, since each RSS query returns a capped ~100 entries —
but the stronger claim this docstring used to make, that a day not fetched is
"gone permanently", was wrong and is corrected in DATA_DECISIONS.md: the feed
reaches back ~140 days, so a run after a gap does recover much of it.

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
import math
from datetime import timedelta
import pendulum
import pandas as pd
from sqlalchemy import text

from src.config import Settings
from src.common.db import get_engine
from src.common.hashing import build_news_hash
from src.extract.prices_yahoo import fetch_daily_prices_yahoo
from src.extract.prices_stooq import fetch_daily_prices_stooq
from src.extract.news_rss import fetch_news_rss_for_ticker, google_news_rss_url
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

# Floor: enough to re-confirm recent days and cover a long weekend.
# Ceiling: a bound on how much one run will try to repair, so a fresh database
# or a badly stale one doesn't turn into an unbounded download.
PRICE_LOOKBACK_FLOOR_DAYS = 14
PRICE_LOOKBACK_CEILING_DAYS = 400


def _price_lookback_days(engine, settings: Settings, run_d) -> int:
    """How far back to fetch prices: far enough to close whatever gap exists.

    This used to be hardcoded at 14 days, which silently made gaps permanent.
    When the machine was off from 2026-08-12 to 2026-08-21, the next run's
    14-day window started after the hole, so it filled the recent days and left
    ten calendar days missing that no later run would ever reach — the window
    only ever moves forward. Prices, unlike news, are fully re-fetchable, so
    there is no reason to lose them.

    Two different kinds of gap have to be looked for, and checking only the
    first is what let the August hole survive a run that "succeeded":

    * trailing — the newest stored day is behind today. Caught by max(d).
    * interior — days missing in the middle, with data on both sides, so
      max(d) is perfectly current and reports nothing wrong.

    Interior gaps are found by looking for calendar dates inside the stored
    range that have no price row at all. That is unambiguous here because the
    crypto tickers trade every day, weekends included: BTC-USD has a row for
    3,693 of the 3,705 calendar days it spans, and the 12 it lacks are these
    outage days. A date with zero rows is therefore a gap, never a holiday.
    """
    tickers = list(settings.tickers)
    horizon_start = run_d - timedelta(days=PRICE_LOOKBACK_CEILING_DAYS)

    with engine.connect() as conn:
        latest_per_ticker = conn.execute(
            text("""
                SELECT a.ticker, max(p.d) AS latest
                FROM fact_price_daily p
                JOIN dim_asset a ON a.asset_id = p.asset_id
                WHERE a.ticker = ANY(:tickers)
                GROUP BY a.ticker
            """),
            {"tickers": tickers},
        ).all()

        earliest_gap = conn.execute(
            text("""
                WITH bounds AS (
                    SELECT greatest(min(d), :horizon_start) AS lo, max(d) AS hi
                    FROM fact_price_daily
                )
                SELECT min(gs)::date
                FROM bounds,
                     generate_series(bounds.lo, bounds.hi, interval '1 day') gs
                LEFT JOIN (SELECT DISTINCT d FROM fact_price_daily) p
                       ON p.d = gs::date
                WHERE p.d IS NULL
            """),
            {"horizon_start": horizon_start},
        ).scalar()

    lookback, reason = choose_price_lookback(
        run_d, latest_per_ticker, earliest_gap, expected_tickers=len(tickers))
    if reason:
        print(f"[price] {reason} — widening lookback to {lookback} days")
    return lookback


def choose_price_lookback(
    run_d, latest_per_ticker: list, earliest_gap, expected_tickers: int
) -> tuple[int, str | None]:
    """Pure decision half of _price_lookback_days, split out so the rule can be
    tested without a database. Returns (lookback_days, reason) where reason is
    None when nothing needed repairing.

    `latest_per_ticker` is [(ticker, latest_date), ...]; `earliest_gap` is the
    oldest date inside the stored range with no price row, or None.
    """
    if len(latest_per_ticker) < expected_tickers:
        missing = expected_tickers - len(latest_per_ticker)
        return PRICE_LOOKBACK_CEILING_DAYS, f"{missing} ticker(s) have no price history yet"

    stalest_ticker, stalest_date = min(latest_per_ticker, key=lambda r: r[1])
    needed = (run_d - stalest_date).days
    reason = f"{stalest_ticker} latest {stalest_date}"

    if earliest_gap is not None:
        gap_days = (run_d - earliest_gap).days
        if gap_days > needed:
            needed = gap_days
            reason = f"missing price days from {earliest_gap}"

    # +5 so the fetch starts before the last stored day rather than exactly on
    # it, which also lets recompute_returns_from_db see a prior close.
    lookback = max(PRICE_LOOKBACK_FLOOR_DAYS,
                   min(PRICE_LOOKBACK_CEILING_DAYS, needed + 5))
    return lookback, (reason if lookback > PRICE_LOOKBACK_FLOOR_DAYS else None)


def _fetch_prices(settings: Settings, run_d, lookback_days: int):
    tickers = list(settings.tickers)

    # --- Try Yahoo first (if configured) ---
    if settings.price_source == "yahoo":
        try:
            df = fetch_daily_prices_yahoo(tickers, end_d=run_d, lookback_days=lookback_days)
            if not df.empty:
                return df
            print("[price] yahoo returned empty; fallback to stooq")
        except Exception as e:
            print(f"[price] yahoo failed: {e} -> fallback to stooq")

    # --- Fallback to Stooq (also wrapped in try/except) ---
    try:
        df = fetch_daily_prices_stooq(tickers, end_d=run_d, lookback_days=max(lookback_days, 60))
        if not df.empty:
            return df
        print("[price] stooq also returned empty — continuing ETL with no price data")
    except Exception as e:
        print(f"[price] stooq fallback also failed: {e} — continuing ETL with no price data")

    return pd.DataFrame()


def stage_prices(settings: Settings, engine, run_d) -> None:
    """Prices, return repair and technical indicators. No model needed."""
    lookback_days = _price_lookback_days(engine, settings, run_d)
    price_raw = _fetch_prices(settings, run_d, lookback_days)
    price_feat = add_return_features(price_raw)

    with engine.begin() as conn:
        # dim_date must span the fetch window, not a fixed 60 days, or a
        # gap-closing run would insert prices on dates dim_date lacks.
        ensure_dim_dates(conn, run_d - timedelta(days=max(60, lookback_days)), run_d)
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
    load alone can stall on a Hugging Face hub call.

    It is NOT, as this docstring claimed until 2026-09-05, the half whose data
    cannot be recovered. A Google News RSS query returns ~100 entries reaching
    back roughly 140 days, so a run that happens after a gap can still pick up
    what it missed; what threw the older entries away was our own
    LOOKBACK_HOURS filter, not the feed. See DATA_DECISIONS.md.

    Two things have to hold for a wide lookback to actually be useful, and
    neither did before:

    1. Articles already in fact_news must not be re-scored. Every run re-fetches
       the same back-catalogue, and FinBERT is the expensive step; deduplicating
       by news_hash *before* scoring (rather than relying on the INSERT's
       ON CONFLICT afterwards) is what keeps the cost proportional to genuinely
       new articles instead of to the window width.
    2. The daily sentiment index must be rebuilt across the whole window. It
       used to rebuild only the last 7 days, so anything older would land in
       fact_news and never reach fact_sentiment_daily — the table the model and
       dashboard actually read. Widening the fetch without this would have
       looked like it worked and changed nothing.
    """
    print("Loading FinBERT Model...")
    scorer = FinbertScorer()
    print("Model Loaded!")

    now_utc = pendulum.now("UTC")
    search_terms = settings.ticker_search_terms

    news_items = []
    for t in settings.tickers:
        items = fetch_news_rss_for_ticker(
            ticker=t,
            rss_template=google_news_rss_url(search_terms.get(t, t)),
            lookback_hours=settings.lookback_hours,
            now_utc=now_utc,
            trusted_sources=settings.trusted_news_sources,
            debug=settings.news_debug,
        )
        news_items.extend(items)
    print(f"[news] fetched {len(news_items)} items across {len(settings.tickers)} tickers")

    # The rebuild window has to span everything the fetch could have returned,
    # or older articles reach fact_news but never fact_sentiment_daily. Rounded
    # UP to whole days: date arithmetic drops the sub-day remainder, so a
    # lookback that isn't a multiple of 24 would otherwise leave the oldest day
    # partly outside the window it was fetched under.
    window_start = run_d - timedelta(days=math.ceil(settings.lookback_hours / 24))

    with engine.begin() as conn:
        asset_map = ensure_assets(conn, list(settings.tickers))

        # Identify every candidate first, WITHOUT scoring: the hash depends
        # only on the article, so it can be computed before FinBERT runs.
        candidates = []
        for item in news_items:
            asset_id = asset_map.get(item.ticker)
            if not asset_id:
                continue
            published_at = pendulum.instance(item.published_at_utc)
            candidates.append({
                "item": item,
                "asset_id": asset_id,
                "published_d": published_at.date(),
                "news_hash": build_news_hash(
                    item.ticker, published_at.to_iso8601_string(), item.title, item.url),
            })

        already_stored = set()
        if candidates:
            already_stored = {
                r[0] for r in conn.execute(
                    text("SELECT news_hash FROM fact_news WHERE news_hash = ANY(:hashes)"),
                    {"hashes": [c["news_hash"] for c in candidates]},
                )
            }
        fresh = [c for c in candidates if c["news_hash"] not in already_stored]
        print(f"[news] {len(candidates)} candidates, {len(already_stored)} already stored, "
              f"{len(fresh)} to score")

        if fresh:
            dates = [c["published_d"] for c in fresh]
            ensure_dim_dates(conn, min(dates), max(dates))
        # dim_date must also cover the index window even when nothing is new,
        # since the rebuild below joins against it.
        ensure_dim_dates(conn, window_start, run_d)

        news_rows = []
        for c in fresh:
            item = c["item"]
            s = scorer.score(item.title)
            news_rows.append({
                "asset_id": c["asset_id"],
                "source_id": ensure_source(conn, item.source_name, "rss", item.base_url),
                "published_at": item.published_at_utc,
                "published_d": c["published_d"],
                "title": item.title,
                "url": item.url,
                "news_hash": c["news_hash"],
                "sentiment_score": s.score,
                "sentiment_label": s.label,
            })

        news_attempted = insert_news(conn, news_rows)

        # Rebuild the daily sentiment index across the whole fetch window.
        df_news = pd.read_sql(
            """
            SELECT asset_id, published_d, sentiment_score, sentiment_label
            FROM fact_news
            WHERE published_d BETWEEN %(s)s AND %(e)s
            """,
            conn,
            params={"s": window_start, "e": run_d},
        )
        si_cnt = upsert_daily_sentiment(conn, build_daily_sentiment_index(df_news))

    print(f"[news] inserted {news_attempted} new articles, "
          f"rebuilt {si_cnt} sentiment-index rows since {window_start}")


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
