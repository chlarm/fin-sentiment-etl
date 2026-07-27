#!/usr/bin/env python3
"""
Bulk-load years of REAL daily price history for every ticker in Settings.tickers.

Unlike backfill.py (which reruns the whole daily ETL — FinBERT model + RSS news —
once per calendar day), this script only touches prices, in one/few batched
network calls, so pulling 10 years of history takes seconds instead of hours.

News/sentiment history cannot be backfilled the same way: Google News RSS only
ever returns *current* headlines, so historical sentiment can only accumulate
day by day from whenever the daily ETL starts running. This script intentionally
does not attempt to fake that.

Usage:
    python -m src.scripts.backfill_price_history
    python -m src.scripts.backfill_price_history --years 10
    python -m src.scripts.backfill_price_history --tickers AAPL,MSFT --years 5
"""
from __future__ import annotations
import argparse
from datetime import date, timedelta

import pendulum

from src.config import Settings
from src.common.db import get_engine
from src.extract.prices_yahoo import fetch_daily_prices_yahoo
from src.extract.prices_stooq import fetch_daily_prices_stooq
from src.transform.price_features import add_return_features
from src.load.dim import ensure_assets, ensure_dim_dates
from src.load.facts import upsert_price_daily


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--years", type=int, default=10, help="How many years of history to pull (default: 10)")
    p.add_argument("--tickers", type=str, default=None, help="Comma-separated override; defaults to Settings.tickers (.env TICKERS)")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    settings = Settings()
    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else list(settings.tickers)

    end_d = pendulum.now(settings.pipeline_tz).date()
    start_d = end_d - timedelta(days=365 * args.years)
    lookback_days = (end_d - start_d).days

    print(f"=== Bulk price history backfill ===")
    print(f"Tickers ({len(tickers)}): {tickers}")
    print(f"Range: {start_d} -> {end_d} ({args.years} years)")

    print("\n[1/3] Fetching from Yahoo Finance (batched)...")
    price_raw = fetch_daily_prices_yahoo(tickers, end_d=end_d, lookback_days=lookback_days)

    got = set(price_raw["ticker"].unique()) if not price_raw.empty else set()
    missing = [t for t in tickers if t not in got]
    if missing:
        print(f"  Yahoo missing/empty for: {missing} -> trying Stooq fallback")
        stooq_df = fetch_daily_prices_stooq(missing, end_d=end_d, lookback_days=lookback_days)
        if not stooq_df.empty:
            import pandas as pd
            price_raw = pd.concat([price_raw, stooq_df], ignore_index=True) if not price_raw.empty else stooq_df

    if price_raw.empty:
        print("No price data fetched from any source. Aborting.")
        return

    still_missing = [t for t in tickers if t not in set(price_raw["ticker"].unique())]
    if still_missing:
        print(f"  WARNING: no real data found anywhere for: {still_missing} (skipped, not faked)")

    print(f"\n[2/3] Computing return_1d / pct_change features...")
    price_feat = add_return_features(price_raw)
    print(f"  {len(price_feat)} rows across {price_feat['ticker'].nunique()} tickers")

    print(f"\n[3/3] Upserting into fact_price_daily...")
    engine = get_engine(settings)
    with engine.begin() as conn:
        ensure_dim_dates(conn, start_d, end_d)
        asset_map = ensure_assets(conn, tickers)
        rows = upsert_price_daily(conn, asset_map, price_feat)

    print(f"\n=== Done: upserted {rows} price rows ===")
    for t in tickers:
        sub = price_feat[price_feat["ticker"] == t]
        if sub.empty:
            print(f"  {t:10s} NO DATA")
        else:
            print(f"  {t:10s} {sub['d'].min()} -> {sub['d'].max()}  ({len(sub)} rows)")


if __name__ == "__main__":
    main()
