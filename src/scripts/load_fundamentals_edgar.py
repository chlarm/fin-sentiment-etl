#!/usr/bin/env python3
"""
Replace the yfinance-sourced fundamentals with SEC EDGAR filings.

This is a replacement, not a merge, and the reason is the primary key. It is
(asset_id, fiscal_period_end), and the two providers date the same quarter
differently: yfinance rounds to month end (2026-03-31), EDGAR reports the
actual fiscal close (2026-03-28, a 13-week quarter). Inserted alongside each
other, one quarter becomes two rows under two keys, and every Track B
aggregate silently double-counts. Neither `ON CONFLICT` nor any date
comparison can separate them after the fact.

EDGAR is the better of the two on every axis that matters here: ~10.7x the
history (1,135 rows against 106), the real fiscal period ends rather than
rounded ones, and `announced_d` taken from the actual filing date instead of
approximated from an earnings calendar — which is what keeps Track B from
seeing figures before the market did.

Deletion is scoped by `source` (see MANAGED_SOURCES) and runs in the same
transaction as the insert, so a failure mid-load leaves the table as it was
rather than empty, and rows loaded by anything else are never touched.
Requires --apply; without it this only reports what it would do.

Usage:
    python -m src.scripts.load_fundamentals_edgar            # dry run
    python -m src.scripts.load_fundamentals_edgar --apply
"""
from __future__ import annotations
import argparse

import requests
from sqlalchemy import text

from src.common.db import get_engine
from src.config import Settings
from src.extract.fundamentals_edgar import (
    fetch_cik_map,
    fetch_quarterly_fundamentals_edgar,
)
from src.load.dim import ensure_assets
from src.load.facts import upsert_fundamentals_quarterly

SOURCE = "edgar"

# Cleared before every load, not just the provider being replaced. An upsert
# alone leaves behind rows that a later run no longer produces: the first load
# stored NVDA's quarter under both 2010-07-31 and 2010-08-01, and once the
# de-duplication was added the stray one simply stopped being written rather
# than being removed. Rebuilding the managed rows makes a re-run mean the same
# thing as a first run.
MANAGED_SOURCES = ("yfinance", "edgar", "edgar_derived")


def _counts(conn) -> dict[str, int]:
    return {
        (r[0] or "(null)"): r[1]
        for r in conn.execute(text(
            "SELECT source, count(*) FROM fact_fundamentals_quarterly GROUP BY 1"))
    }


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true",
                   help="Actually write. Without it, nothing is modified.")
    p.add_argument("--tickers", type=str, default=None)
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    settings = Settings()
    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else list(settings.tickers)
    engine = get_engine(settings)

    with engine.connect() as conn:
        print(f"Before: {_counts(conn)}")

    session = requests.Session()
    cik_map = fetch_cik_map(session)
    if not cik_map:
        print("Could not fetch the SEC ticker->CIK map; aborting without changes.")
        return

    print(f"\nFetching EDGAR fundamentals for {len(tickers)} tickers...")
    rows: list[dict] = []
    for t in tickers:
        got = fetch_quarterly_fundamentals_edgar(t, session=session, cik_map=cik_map)
        for r in got:
            r["source"] = SOURCE
        rows.extend(got)
        if got:
            ends = [r["fiscal_period_end"] for r in got]
            print(f"  {t:10s} {len(got):3d} quarters  {min(ends)} -> {max(ends)}")

    if not rows:
        # Refusing here matters: EDGAR returning nothing looks identical to a
        # rate-limited session, and deleting on that basis would empty the
        # table for a transient network problem.
        print("\nEDGAR returned no rows at all — aborting without changes.")
        return

    print(f"\nFetched {len(rows)} EDGAR rows across "
          f"{len({r['ticker'] for r in rows})} tickers.")

    if not args.apply:
        print(f"\nDry run. Re-run with --apply to replace rows from "
              f"{MANAGED_SOURCES} with these.")
        return

    with engine.begin() as conn:
        asset_map = ensure_assets(conn, tickers)
        deleted = conn.execute(
            text("DELETE FROM fact_fundamentals_quarterly WHERE source = ANY(:s)"),
            {"s": list(MANAGED_SOURCES)},
        ).rowcount
        inserted = upsert_fundamentals_quarterly(conn, asset_map, rows)
        print(f"\nDeleted {deleted} existing rows, upserted {inserted} '{SOURCE}' rows.")

    with engine.connect() as conn:
        print(f"After:  {_counts(conn)}")


if __name__ == "__main__":
    main()
