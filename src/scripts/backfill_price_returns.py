#!/usr/bin/env python3
"""
Recompute return_1d/pct_change for fact_price_daily rows from the close
prices already stored there. Pure derived arithmetic on real data already in
the table — not fabricating anything, just re-running the same transform
(src/transform/price_features.add_return_features) that should have produced
these values in the first place.

Root cause this fixes: src/etl/run_daily.py only fetches a short lookback
window (14 days on Yahoo, 60 on Stooq) each run and computes return_1d via
shift(1) *within that small batch* — so the earliest row of every day's batch
has no visible previous close and gets return_1d = NULL, even though a
correct value already existed in the DB from a prior run. Because the upsert
does ON CONFLICT DO UPDATE, this **overwrites** the previously-correct value
with NULL on every single run. That NULL then breaks any rolling feature
downstream — see volatility_20 in src/transform/technical_indicators.py,
which needs 20 consecutive non-null return_1d values and produces NULL for
the next 20 rows after a single gap.

The real fix is recompute_returns_from_db(), which always derives return_1d
from the full stored close history (via SQL LAG, not a fetch-window shift),
so a batch boundary can never corrupt it. run_daily.py calls this after every
price upsert. This module's CLI is for one-off repair of already-corrupted
rows.

Usage:
    python -m src.scripts.backfill_price_returns
    python -m src.scripts.backfill_price_returns --tickers AAPL,MSFT
"""
from __future__ import annotations
import argparse
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


def recompute_returns_from_db(conn: Connection, tickers: list[str]) -> int:
    """Recompute return_1d/pct_change in-place from each ticker's own stored
    close-price history, using SQL LAG over the full series (not a small
    fetch-window shift) so a batch boundary can never null out an
    already-correct value. Safe to call every ETL run."""
    result = conn.execute(
        text("""
            WITH ordered AS (
                SELECT p.asset_id, p.d, p.close,
                       LAG(p.close) OVER (PARTITION BY p.asset_id ORDER BY p.d) AS prev_close
                FROM fact_price_daily p
                JOIN dim_asset a ON a.asset_id = p.asset_id
                WHERE a.ticker = ANY(:tickers)
            )
            UPDATE fact_price_daily f
            SET return_1d = (o.close / o.prev_close) - 1,
                pct_change = ((o.close / o.prev_close) - 1) * 100,
                updated_at = now()
            FROM ordered o
            WHERE f.asset_id = o.asset_id AND f.d = o.d
              AND o.prev_close IS NOT NULL
              AND f.close IS NOT NULL
              AND f.return_1d IS DISTINCT FROM (o.close / o.prev_close) - 1
        """),
        {"tickers": tickers},
    )
    return result.rowcount


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--tickers", type=str, default=None, help="Comma-separated override; defaults to Settings.tickers")
    return p.parse_args()


def main() -> None:
    from src.config import Settings
    from src.common.db import get_engine

    args = _parse_args()
    settings = Settings()
    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else list(settings.tickers)

    engine = get_engine(settings)
    with engine.begin() as conn:
        rows = recompute_returns_from_db(conn, tickers)

    print(f"Recomputed return_1d/pct_change for {rows} rows across {len(tickers)} tickers.")


if __name__ == "__main__":
    main()
