#!/usr/bin/env python3
"""
Compute technical indicators (SMA/EMA/MACD/RSI/volatility/momentum) from the
price history already in fact_price_daily and store them in
fact_technical_daily. Pure derived computation — no external network calls.

Usage:
    python -m src.scripts.backfill_technical_indicators
    python -m src.scripts.backfill_technical_indicators --tickers AAPL,MSFT
"""
from __future__ import annotations
import argparse
import pandas as pd
from sqlalchemy import text

from src.config import Settings
from src.common.db import get_engine
from src.transform.technical_indicators import add_technical_indicators
from src.load.dim import ensure_assets
from src.load.facts import upsert_technical_daily


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--tickers", type=str, default=None, help="Comma-separated override; defaults to Settings.tickers")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    settings = Settings()
    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else list(settings.tickers)

    engine = get_engine(settings)
    with engine.connect() as conn:
        price_df = pd.read_sql(
            text("""
                SELECT a.ticker, p.d, p.close, p.return_1d
                FROM fact_price_daily p
                JOIN dim_asset a ON a.asset_id = p.asset_id
                WHERE a.ticker = ANY(:tickers)
                ORDER BY a.ticker, p.d
            """),
            conn,
            params={"tickers": tickers},
        )

    if price_df.empty:
        print("No price data found for the given tickers. Run the price backfill first.")
        return

    print(f"Computing indicators for {price_df['ticker'].nunique()} tickers, {len(price_df)} price rows...")
    tech_df = add_technical_indicators(price_df)

    with engine.begin() as conn:
        asset_map = ensure_assets(conn, tickers)
        rows = upsert_technical_daily(conn, asset_map, tech_df)

    print(f"Done: upserted {rows} rows into fact_technical_daily")
    for t in tickers:
        sub = tech_df[tech_df["ticker"] == t].dropna(subset=["rsi_14"])
        if sub.empty:
            print(f"  {t:10s} no rows with a full RSI window yet")
        else:
            print(f"  {t:10s} indicators available from {sub['d'].min()} -> {sub['d'].max()} ({len(sub)} rows)")


if __name__ == "__main__":
    main()
