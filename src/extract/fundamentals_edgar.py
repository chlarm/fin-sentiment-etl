"""
Quarterly fundamentals from SEC EDGAR's XBRL `companyfacts` API.

Why this exists alongside fundamentals_yahoo.py: Yahoo only returns 5-7
quarters per ticker (a limit of their API, not of our code), which left
Track B with ~106 rows total — too thin for the panel regression it wants.
EDGAR carries the full filing history: 35-67 distinct period-ends per ticker
across our 21 equities, going back to 2007-2017 depending on the company.
It's free and needs no API key.

Two things make EDGAR fiddly, both handled below:

1. **Concept names vary by company AND over time.** JPM, TSLA and XOM tag
   revenue as plain Revenues, while Apple used SalesRevenueNet until 2018 and
   RevenueFromContractWithCustomerExcludingAssessedTax after it (the ASC 606
   changeover). Rather than maintain a per-ticker mapping, we pull
   `companyfacts` once (all ~400 concepts in one request) and merge every
   candidate tag — picking only the single richest one drops whole eras.

2. **10-Q filings tag year-to-date figures as well as three-month ones.**
   Summing blindly would double-count. Duration facts are therefore filtered
   to those spanning roughly one quarter (see QUARTER_MIN_DAYS/MAX_DAYS);
   YTD facts (~180/270/365 days) are dropped.

Point-in-time correctness: a period can be reported more than once (original
filing, then restatements). For backtesting, what matters is the number as it
was FIRST known, so we keep the earliest `filed` date and the value reported
with it — using a later restatement would leak information that wasn't
available on the day. `announced_d` is that filing date, which is a real
improvement over fundamentals_yahoo.py, where it is approximated from
earnings-calendar dates.

Usage:
    python -m src.extract.fundamentals_edgar --tickers AAPL,MSFT
"""
from __future__ import annotations

import argparse
import os
import time
from datetime import date, datetime

import requests

CIK_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# SEC asks that automated clients identify themselves with a real contact.
# Kept in an env var so a contact address isn't baked into the repository.
DEFAULT_USER_AGENT = "fin-sentiment-etl academic research (set SEC_USER_AGENT)"

# SEC's published guidance is max 10 requests/second; we go far below that.
REQUEST_DELAY_SECONDS = 0.2

# A "quarter" duration in XBRL is rarely exactly 91 days — 13-week retail
# quarters, 52/53-week fiscal years and leap years all shift it. This window
# accepts single quarters while excluding half-year (~180) and YTD (~270+).
QUARTER_MIN_DAYS = 80
QUARTER_MAX_DAYS = 100

# Candidate us-gaap tags per field, richest/most specific first. The chosen
# tag is whichever has the most usable facts for that particular company.
DURATION_CONCEPTS: dict[str, list[str]] = {
    "revenue": [
        # Order matters — see _series_by_priority(). Banks first: for JPM the
        # meaningful top line is revenue net of interest expense, and plain
        # Revenues only covers 2008-2014 for them.
        "RevenuesNetOfInterestExpense",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueNet",
        "Revenues",
    ],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "gross_profit": ["GrossProfit"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
}
EPS_CONCEPTS = ["EarningsPerShareDiluted"]

# Balance-sheet items are instants (a value AT a date), not durations.
INSTANT_CONCEPTS: dict[str, list[str]] = {
    "stockholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "short_term_debt": ["LongTermDebtCurrent", "ShortTermBorrowings", "DebtCurrent"],
}


def _user_agent() -> str:
    return os.getenv("SEC_USER_AGENT", DEFAULT_USER_AGENT)


def _get_json(session: requests.Session, url: str) -> dict | None:
    try:
        resp = session.get(url, headers={"User-Agent": _user_agent()}, timeout=60)
    except requests.RequestException as e:
        print(f"[edgar] request failed for {url}: {e}")
        return None
    time.sleep(REQUEST_DELAY_SECONDS)
    if resp.status_code != 200:
        # Surfaced rather than swallowed: a silent failure here looks
        # identical to "this company has no data", which is a very different
        # conclusion.
        print(f"[edgar] HTTP {resp.status_code} for {url}")
        return None
    return resp.json()


# SEC's ticker file maps a ticker to whichever registrant currently uses it,
# which is not always the entity that holds the financial history. XOM points
# at CIK 0002115436 ("EXXON MOBIL CORP"), a registrant whose companyfacts
# payload contains only the `ffd` taxonomy — no us-gaap at all — while the
# entire 2009-2026 statement history sits under the predecessor CIK
# 0000034088 ("Exxon Mobil Corporation"). Without this override XOM silently
# looks like a company that has never filed financials.
CIK_OVERRIDES: dict[str, str] = {
    "XOM": "0000034088",
}


def fetch_cik_map(session: requests.Session) -> dict[str, str]:
    """ticker -> zero-padded 10-digit CIK, with known overrides applied."""
    data = _get_json(session, CIK_MAP_URL)
    if not data:
        return {}
    mapping = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in data.values()}
    mapping.update(CIK_OVERRIDES)
    return mapping


def _parse(d: str) -> date:
    return datetime.strptime(d, "%Y-%m-%d").date()


def _first_reported(rows: list[dict], quarterly_only: bool) -> dict[date, tuple[float, date]]:
    """Collapse one tag's raw facts to {period_end: (value, first_filed_date)}.

    Keeps the EARLIEST filing for each period end — the value as first known,
    which is what a point-in-time backtest is allowed to see. Later
    restatements are deliberately ignored.
    """
    out: dict[date, tuple[float, date]] = {}
    for r in rows:
        if r.get("val") is None or not r.get("end") or not r.get("filed"):
            continue
        end = _parse(r["end"])
        filed = _parse(r["filed"])

        if quarterly_only:
            start = r.get("start")
            if not start:
                continue
            days = (end - _parse(start)).days
            if not (QUARTER_MIN_DAYS <= days <= QUARTER_MAX_DAYS):
                continue

        prev = out.get(end)
        if prev is None or filed < prev[1]:
            out[end] = (float(r["val"]), filed)
    return out


def _series_by_priority(
    facts: dict, candidates: list[str], unit: str, quarterly_only: bool
) -> tuple[dict[date, tuple[float, date]], list[str]]:
    """Build one series from candidate tags in PRIORITY order: for each period
    end, the first candidate that reports it wins.

    Not a blind merge, because candidate tags are not always synonyms.
    Apple's SalesRevenueNet -> RevenueFromContractWithCustomerExcludingAssessedTax
    really is the same line under a new name (the ASC 606 changeover), so
    filling gaps from the older tag is correct. But JPMorgan reports both
    Revenues and RevenuesNetOfInterestExpense, which are different measures —
    for a bank the net-of-interest figure is the meaningful top line, and
    mixing the two by "whichever was filed first" would splice two
    definitions into one series. Ordering the candidates encodes that choice
    explicitly; later tags only ever fill periods the preferred one lacks.

    Returns the series plus which tags actually contributed, so the caller can
    report the provenance rather than leaving it implicit.
    """
    series: dict[date, tuple[float, date]] = {}
    used: list[str] = []
    for name in candidates:
        entry = facts.get(name)
        if not entry:
            continue
        rows = entry.get("units", {}).get(unit)
        if not rows:
            continue
        contributed = False
        for end, val in _first_reported(rows, quarterly_only).items():
            if end not in series:
                series[end] = val
                contributed = True
        if contributed:
            used.append(name)
    return series, used


def fetch_quarterly_fundamentals_edgar(
    ticker: str,
    session: requests.Session | None = None,
    cik_map: dict[str, str] | None = None,
) -> list[dict]:
    """Real quarterly fundamentals from EDGAR. Returns [] (never fabricated
    rows) for anything EDGAR has no filings for — indices, forex, commodities
    and crypto don't file with the SEC."""
    session = session or requests.Session()
    cik_map = cik_map if cik_map is not None else fetch_cik_map(session)

    cik = cik_map.get(ticker.upper())
    if not cik:
        return []

    payload = _get_json(session, COMPANYFACTS_URL.format(cik=cik))
    if not payload:
        return []
    gaap = payload.get("facts", {}).get("us-gaap", {})
    if not gaap:
        print(f"[edgar] {ticker}: CIK {cik} has no us-gaap facts "
              f"(taxonomies: {list(payload.get('facts', {}).keys())}) — likely the wrong registrant")
        return []

    dur: dict[str, dict[date, tuple[float, date]]] = {}
    tags_used: dict[str, list[str]] = {}
    for field, candidates in DURATION_CONCEPTS.items():
        dur[field], tags_used[field] = _series_by_priority(gaap, candidates, "USD", quarterly_only=True)

    eps, tags_used["eps_diluted"] = _series_by_priority(gaap, EPS_CONCEPTS, "USD/shares", quarterly_only=True)

    inst: dict[str, dict[date, tuple[float, date]]] = {}
    for field, candidates in INSTANT_CONCEPTS.items():
        inst[field], tags_used[field] = _series_by_priority(gaap, candidates, "USD", quarterly_only=False)

    # Revenue anchors a period: without it there's no meaningful quarter.
    period_ends = sorted(dur["revenue"].keys())

    out: list[dict] = []
    for pe in period_ends:
        revenue, filed = dur["revenue"][pe]
        net_income = dur["net_income"].get(pe, (None, None))[0]
        gross_profit = dur["gross_profit"].get(pe, (None, None))[0]
        ocf = dur["operating_cash_flow"].get(pe, (None, None))[0]
        capex = dur["capex"].get(pe, (None, None))[0]

        equity = inst["stockholders_equity"].get(pe, (None, None))[0]
        ltd = inst["long_term_debt"].get(pe, (None, None))[0]
        std = inst["short_term_debt"].get(pe, (None, None))[0]

        total_debt = None
        if ltd is not None or std is not None:
            total_debt = (ltd or 0.0) + (std or 0.0)

        free_cash_flow = None
        if ocf is not None and capex is not None:
            # capex is reported as a positive outflow in the cash-flow tags
            free_cash_flow = ocf - abs(capex)

        out.append({
            "_revenue_tags": tags_used.get("revenue", []),
            "ticker": ticker,
            "fiscal_period_end": pe,
            "announced_d": filed,
            "revenue": revenue,
            "net_income": net_income,
            "eps_diluted": eps.get(pe, (None, None))[0],
            "gross_margin": (gross_profit / revenue) if (gross_profit is not None and revenue) else None,
            "net_margin": (net_income / revenue) if (net_income is not None and revenue) else None,
            "total_debt": total_debt,
            "stockholders_equity": equity,
            "free_cash_flow": free_cash_flow,
        })

    return out


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--tickers", type=str, default=None, help="Comma-separated; defaults to Settings.tickers")
    return p.parse_args()


def main() -> None:
    from src.config import Settings

    args = _parse_args()
    settings = Settings()
    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else list(settings.tickers)

    session = requests.Session()
    cik_map = fetch_cik_map(session)
    if not cik_map:
        print("Could not fetch the SEC ticker->CIK map; aborting.")
        return

    total = 0
    for t in tickers:
        rows = fetch_quarterly_fundamentals_edgar(t, session=session, cik_map=cik_map)
        total += len(rows)
        if not rows:
            print(f"  {t:10s} no EDGAR filings (expected for indices/forex/commodities/crypto)")
            continue
        ends = [r["fiscal_period_end"] for r in rows]
        filled = sum(1 for r in rows if r["net_income"] is not None)
        src = ",".join(rows[0].get("_revenue_tags", [])) or "?"
        print(f"  {t:10s} {len(rows):3d} quarters  {min(ends)} -> {max(ends)}  "
              f"(net_income: {filled})  revenue via {src}")
    print(f"\nTotal quarterly rows available from EDGAR: {total}")


if __name__ == "__main__":
    main()
