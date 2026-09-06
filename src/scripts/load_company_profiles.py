#!/usr/bin/env python3
"""
Load SEC EDGAR company profiles into dim_company_profile.

Run occasionally rather than daily: registrant facts change rarely, and the
business description only changes when a new 10-K is filed — once a year per
company. Re-running is safe and idempotent.

Usage:
    python -m src.scripts.load_company_profiles            # dry run
    python -m src.scripts.load_company_profiles --apply
    python -m src.scripts.load_company_profiles --apply --tickers AAPL,MSFT
"""
from __future__ import annotations
import argparse
import json

import requests
from sqlalchemy import text

from src.common.db import get_engine
from src.config import Settings
from src.extract.company_profile_edgar import fetch_company_profile
from src.extract.fundamentals_edgar import fetch_cik_map
from src.load.dim import ensure_assets

UPSERT = text("""
INSERT INTO dim_company_profile
  (asset_id, cik, legal_name, sic, sic_description, entity_type,
   state_of_incorporation, fiscal_year_end, exchanges, ein, filer_category,
   phone, hq_street, hq_city, hq_state, former_names, business_description,
   latest_10k_filed, latest_10k_accession, latest_10k_url, recent_filings,
   fetched_at)
VALUES
  (:asset_id, :cik, :legal_name, :sic, :sic_description, :entity_type,
   :state_of_incorporation, :fiscal_year_end, :exchanges, :ein, :filer_category,
   :phone, :hq_street, :hq_city, :hq_state, :former_names, :business_description,
   :latest_10k_filed, :latest_10k_accession, :latest_10k_url,
   CAST(:recent_filings AS jsonb), now())
ON CONFLICT (asset_id) DO UPDATE SET
  cik=EXCLUDED.cik, legal_name=EXCLUDED.legal_name, sic=EXCLUDED.sic,
  sic_description=EXCLUDED.sic_description, entity_type=EXCLUDED.entity_type,
  state_of_incorporation=EXCLUDED.state_of_incorporation,
  fiscal_year_end=EXCLUDED.fiscal_year_end, exchanges=EXCLUDED.exchanges,
  ein=EXCLUDED.ein, filer_category=EXCLUDED.filer_category, phone=EXCLUDED.phone,
  hq_street=EXCLUDED.hq_street, hq_city=EXCLUDED.hq_city, hq_state=EXCLUDED.hq_state,
  former_names=EXCLUDED.former_names,
  -- Keep an existing description if this run could not extract one. A 10-K
  -- that reformats its headings should not silently erase a good description
  -- captured from the previous filing.
  business_description=COALESCE(EXCLUDED.business_description,
                                dim_company_profile.business_description),
  latest_10k_filed=EXCLUDED.latest_10k_filed,
  latest_10k_accession=EXCLUDED.latest_10k_accession,
  latest_10k_url=EXCLUDED.latest_10k_url,
  recent_filings=EXCLUDED.recent_filings,
  fetched_at=now()
""")


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Write. Without it, nothing is modified.")
    p.add_argument("--tickers", type=str, default=None)
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    settings = Settings()
    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else list(settings.tickers)
    engine = get_engine(settings)

    session = requests.Session()
    cik_map = fetch_cik_map(session)
    if not cik_map:
        print("Could not fetch the SEC ticker->CIK map; aborting without changes.")
        return

    profiles, no_registrant = [], []
    for t in tickers:
        p = fetch_company_profile(t, session=session, cik_map=cik_map)
        if not p:
            no_registrant.append(t)
            continue
        profiles.append(p)
        desc = p["business_description"]
        print(f"  {t:10s} {(p['legal_name'] or '?')[:32]:34s} "
              f"{(p['sic_description'] or '?')[:28]:30s} "
              f"{f'{len(desc):,} chars' if desc else 'no business text'}")

    with_desc = sum(1 for p in profiles if p["business_description"])
    print(f"\n{len(profiles)} profiles, {with_desc} with a business description")
    if no_registrant:
        print(f"No SEC registrant (expected): {no_registrant}")

    if not profiles:
        print("Nothing fetched — aborting without changes.")
        return
    if not args.apply:
        print("\nDry run. Re-run with --apply to write.")
        return

    with engine.begin() as conn:
        asset_map = ensure_assets(conn, tickers)
        rows = []
        for p in profiles:
            asset_id = asset_map.get(p["ticker"])
            if not asset_id:
                continue
            row = {k: v for k, v in p.items() if k not in ("ticker", "recent_filings")}
            row["asset_id"] = asset_id
            row["recent_filings"] = json.dumps(p["recent_filings"])
            rows.append(row)
        conn.execute(UPSERT, rows)
    print(f"Upserted {len(rows)} rows into dim_company_profile")


if __name__ == "__main__":
    main()
