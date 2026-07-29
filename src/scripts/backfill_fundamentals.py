#!/usr/bin/env python3
"""
Backfill quarterly company fundamentals (revenue, EPS, margins, debt, FCF)
from yfinance, anchored to the real earnings-announcement date so later
modeling doesn't leak future information (see fact_fundamentals_quarterly's
announced_d column).

Only stocks file financial statements — indices, forex, commodities, and
crypto tickers are skipped automatically (yfinance returns no statement data
for them), not filled with fake values.

Usage:
    python -m src.scripts.backfill_fundamentals
    python -m src.scripts.backfill_fundamentals --tickers AAPL,MSFT
"""
from __future__ import annotations
import argparse
import time

from src.config import Settings
from src.common.db import get_engine
from src.extract.fundamentals_yahoo import fetch_quarterly_fundamentals
from src.load.dim import ensure_assets
from src.load.facts import upsert_fundamentals_quarterly


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--tickers", type=str, default=None, help="Comma-separated override; defaults to Settings.tickers")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    settings = Settings()
    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else list(settings.tickers)

    engine = get_engine(settings)
    with engine.begin() as conn:
        asset_map = ensure_assets(conn, tickers)

    print(f"Fetching quarterly fundamentals for {len(tickers)} tickers...")
    total_rows = 0
    skipped: list[str] = []

    for t in tickers:
        rows = fetch_quarterly_fundamentals(t)
        if not rows:
            skipped.append(t)
            print(f"  {t:10s} no statement data (likely index/forex/commodity/crypto) — skipped")
        else:
            for r in rows:
                r["source"] = "yfinance"
            with engine.begin() as conn:
                n = upsert_fundamentals_quarterly(conn, asset_map, rows)
            total_rows += n
            periods = sorted(r["fiscal_period_end"] for r in rows)
            print(f"  {t:10s} {len(rows)} quarters ({periods[0]} -> {periods[-1]})")
        time.sleep(0.5)  # be polite to the Yahoo endpoint

    print(f"\nDone: upserted {total_rows} rows into fact_fundamentals_quarterly")
    if skipped:
        print(f"Skipped (no fundamentals — not stocks): {skipped}")


if __name__ == "__main__":
    main()
