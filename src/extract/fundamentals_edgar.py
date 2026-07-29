"""
Quarterly fundamentals from SEC EDGAR's XBRL `companyfacts` API.

Why this exists alongside fundamentals_yahoo.py: Yahoo only returns 5-7
quarters per ticker (a limit of their API, not of our code), which left
Track B with ~106 rows total — too thin for the panel regression it wants.
EDGAR carries the full filing history: 35-67 distinct period-ends per ticker
across our 21 equities, going back to 2007-2017 depending on the company.
It's free and needs no API key.

Four things make EDGAR fiddly, all handled below:

1. **Concept names vary by company AND over time.** JPM, TSLA and XOM tag
   revenue as plain Revenues, while Apple used SalesRevenueNet until 2018 and
   RevenueFromContractWithCustomerExcludingAssessedTax after it (the ASC 606
   changeover). Rather than maintain a per-ticker mapping, we pull
   `companyfacts` once (all ~400 concepts in one request) and fill each period
   from the first candidate tag that reports it — see _series_by_priority for
   why the order matters and why this is not a blind merge.

2. **10-Q filings tag year-to-date figures as well as three-month ones.**
   Summing blindly would double-count. Duration facts are therefore filtered
   to those spanning roughly one quarter (see QUARTER_MIN_DAYS/MAX_DAYS);
   YTD facts (~180/270/365 days) are dropped.

3. **Filers get their own tags wrong.** Oracle's 10-Ks label the full-year
   revenue figure with a 91-day start/end for five separate years; the dates
   are valid so only the magnitude betrays it (_drop_mistagged_quarters).

4. **Per-share figures are not comparable across a stock split.** See
   _first_reported — this is why eps_diluted alone uses the latest filing.

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

# Full-year durations, needed only to derive Q4 (see _derive_q4_rows). 52/53-week
# fiscal years and leap years mean this is not always 365.
ANNUAL_MIN_DAYS = 340
ANNUAL_MAX_DAYS = 380

SPAN_WINDOWS = {
    "quarter": (QUARTER_MIN_DAYS, QUARTER_MAX_DAYS),
    "annual": (ANNUAL_MIN_DAYS, ANNUAL_MAX_DAYS),
}

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


def _first_reported(
    rows: list[dict], span: str | None, prefer: str = "earliest"
) -> dict[date, tuple[float, date, date | None]]:
    """Collapse one tag's raw facts to {period_end: (value, first_filed, start)}.

    `span` selects a duration window from SPAN_WINDOWS ("quarter" or
    "annual"); None means the fact is an instant and has no duration to check.

    `prefer` picks which filing's VALUE wins when a period was reported more
    than once. The reported filing date is always the earliest one either way,
    since that is when the market first learned the figure.

    - "earliest" (dollar amounts): the value as first known, which is what a
      point-in-time backtest is allowed to see. Later restatements are
      deliberately ignored.
    - "latest" (per-share amounts): stock splits force this. Apple tagged
      diluted EPS of 14.50 for the quarter ending 2013-12-28 when it was
      filed, then re-tagged the same quarter as 2.07 after the 7:1 split in
      June 2014. Taking the earliest filing per period splices pre- and
      post-split figures into one series, putting a 7x cliff in the middle of
      FY2014 that no company event corresponds to. A split is a presentational
      change, not news, so the split-adjusted (latest) value is the honest one
      — and it matches our price history, which is also split-adjusted. The
      cost is that a genuine restatement of EPS is absorbed too; that is the
      lesser distortion, and it is recorded in DATA_DECISIONS.md.
    """
    # value_filed tracks the filing the chosen VALUE came from, separately from
    # the earliest filing that dates the period. Collapsing the two makes
    # prefer="latest" silently pick whichever fact happened to come last in the
    # payload, since the running minimum is never a valid comparison point.
    chosen: dict[date, tuple[float, date]] = {}
    first_filed: dict[date, date] = {}
    starts: dict[date, date | None] = {}

    for r in rows:
        if r.get("val") is None or not r.get("end") or not r.get("filed"):
            continue
        end = _parse(r["end"])
        filed = _parse(r["filed"])
        start: date | None = None

        if span is not None:
            if not r.get("start"):
                continue
            start = _parse(r["start"])
            lo, hi = SPAN_WINDOWS[span]
            if not (lo <= (end - start).days <= hi):
                continue

        prev = chosen.get(end)
        if prev is None or (filed < prev[1] if prefer == "earliest" else filed > prev[1]):
            chosen[end] = (float(r["val"]), filed)
        known = first_filed.get(end)
        first_filed[end] = filed if known is None else min(known, filed)
        if starts.get(end) is None:
            starts[end] = start

    return {end: (v, first_filed[end], starts[end]) for end, (v, _) in chosen.items()}


def _series_by_priority(
    facts: dict, candidates: list[str], unit: str, span: str | None, prefer: str = "earliest"
) -> tuple[dict[date, tuple[float, date, date | None]], list[str]]:
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
        for end, val in _first_reported(rows, span, prefer).items():
            if end not in series:
                series[end] = val
                contributed = True
        if contributed:
            used.append(name)
    return series, used


# Deliberately near 1.0 rather than "implausibly large". A first pass at 0.6
# flagged Tesla's quarter ending 2012-12-31 as bogus — 306M against a 413M
# fiscal year, 74% — but that one is real: the Model S ramp genuinely put most
# of Tesla's 2012 revenue in the final quarter. What actually identifies the
# mis-tag is that the quarter EQUALS the year, so only that is caught. A YTD
# nine-month figure mis-tagged as a quarter would land near 75% and is
# indistinguishable from Tesla; this check does not claim to find those.
MISTAGGED_QUARTER_SHARE = 0.95

# How far the two independent Q4 reconstructions may differ and still be
# treated as the same number. Filers round to the nearest million, so a little
# slack is needed; real disagreements in testing were 2% or larger.
RECONCILE_TOLERANCE = 0.005


def _drop_mistagged_quarters(
    ticker: str,
    quarterly: dict[date, tuple[float, date, date | None]],
    annual: dict[date, tuple[float, date, date | None]],
) -> int:
    """Remove "quarterly" revenue facts that actually carry a full-year figure.

    The duration filter trusts the filer's own start/end dates, and filers get
    them wrong. Oracle's 10-K tags Revenues with start 2020-03-01, end
    2020-05-31 — a legitimate 91-day quarter — but the value attached is
    39,068,000,000, their entire fiscal year. The dates pass every check;
    only the magnitude gives it away, so it is checked against the fiscal year
    that contains it. Left in place, this both inflates that quarter ~3.5x and
    makes the derived Q4 wrong for every affected Oracle year.
    """
    dropped = 0
    for fy_end, (fy_val, _f, fy_start) in annual.items():
        if fy_start is None or not fy_val:
            continue
        limit = abs(fy_val) * MISTAGGED_QUARTER_SHARE
        for q_end in [d for d in quarterly if fy_start < d <= fy_end]:
            if abs(quarterly[q_end][0]) > limit:
                print(f"[edgar] {ticker}: dropping revenue for quarter ending {q_end} — "
                      f"{quarterly[q_end][0]:,.0f} is {quarterly[q_end][0] / fy_val:.0%} of "
                      f"FY{fy_end.year} ({fy_val:,.0f}); mis-tagged annual figure")
                del quarterly[q_end]
                dropped += 1
    return dropped


def _margins(revenue: float | None, gross_profit: float | None, net_income: float | None) -> tuple[float | None, float | None]:
    gm = (gross_profit / revenue) if (gross_profit is not None and revenue) else None
    nm = (net_income / revenue) if (net_income is not None and revenue) else None
    return gm, nm


def _consistent_remainder(
    facts: dict, candidates: list[str], fy_end: date, fy_filed: date, inner: list[date]
) -> float | None:
    """FY minus the three inner quarters, taken from ONE tag in ONE filing.

    Both conditions matter. Same filing, because a 10-K that restates its
    interim quarters reports them on the basis the annual total uses. Same tag,
    because candidate tags are not interchangeable: a filing may state the year
    under SalesRevenueNet while stating the quarters under Revenues, and
    subtracting across those two definitions produced a 75% error on Amazon's
    FY2012 in testing — worse than not using the snapshot at all.

    Returns None when no single tag covers all four periods in that filing, so
    the caller can fall back rather than silently mixing bases.
    """
    for name in candidates:
        rows = (facts.get(name) or {}).get("units", {}).get("USD") or []
        quarters: dict[date, float] = {}
        annual: float | None = None
        for r in rows:
            if r.get("val") is None or not r.get("start") or not r.get("filed"):
                continue
            if _parse(r["filed"]) != fy_filed:
                continue
            end = _parse(r["end"])
            days = (end - _parse(r["start"])).days
            if QUARTER_MIN_DAYS <= days <= QUARTER_MAX_DAYS:
                quarters.setdefault(end, float(r["val"]))
            elif end == fy_end and ANNUAL_MIN_DAYS <= days <= ANNUAL_MAX_DAYS:
                annual = float(r["val"])
        if annual is not None and all(d in quarters for d in inner):
            return annual - sum(quarters[d] for d in inner)
    return None


def _derive_q4_rows(
    ticker: str,
    gaap: dict,
    dur: dict[str, dict[date, tuple[float, date, date | None]]],
    ann: dict[str, dict[date, tuple[float, date, date | None]]],
    inst: dict[str, dict[date, tuple[float, date, date | None]]],
) -> list[dict]:
    """Reconstruct the missing fourth quarter as FY minus Q1+Q2+Q3.

    OFF BY DEFAULT, and the measurements below are the reason. The idea was
    sound and the implementation is correct where it can be checked, but it
    cannot be checked where it would actually be used.

    Most filers never tag a standalone Q4: the 10-K reports the full year, and
    the fourth quarter only exists as the remainder. Across our 21 equities
    that leaves 178 of ~334 ticker-years with just three quarters — a gap that
    is systematic rather than random, and it removes the quarter that carries
    the annual results and next-year guidance.

    This is arithmetic on figures the company actually reported, not an
    estimate, but it is still a derived number: a restated interim quarter or
    a tagging inconsistency lands entirely in Q4. Rows are therefore returned
    with source='edgar_derived' so they can be excluded from analysis.

    Both sides of the subtraction are taken from the SAME filing wherever the
    10-K restates its interim quarters. Mixing bases is what produced the worst
    errors in testing: Johnson & Johnson's FY2023 total excludes the Kenvue
    consumer business as a discontinued operation while the quarters as first
    filed still include it, so subtracting one from the other overstated the
    revenue drop by 37%. Years where the 10-K does not repeat its quarters fall
    back to the as-first-filed series and are counted separately by the caller.

    eps_diluted is deliberately never derived, and derived rows leave it NULL.
    Stock splits make per-share figures non-additive across the archive: Apple's
    FY2012 quarters are only ever tagged in pre-split units (35.49 for Q1-Q3
    combined), while FY2012's annual EPS was re-tagged at 6.31 after the 2014
    7:1 split, because the later 10-K restates annual comparatives but not the
    individual quarters of a year that old. No choice of filing reconciles them.

    Only emitted when the fiscal year has exactly three tagged quarters inside
    it and none already ends on the year end; anything else is left alone
    rather than guessed at.

    Why it stays off. Graded against the 131 ticker-years where EDGAR does tag
    a real Q4, the two-method rule agreed with the filed figure 106 times out
    of 106 on revenue and 101 out of 101 on net income — no errors at all. That
    result is worthless here, because agreement is only possible when the 10-K
    restates its quarters, and a 10-K that restates its quarters is a 10-K that
    tags Q4. Of the 181 ticker-years that actually lack a Q4, zero can be
    verified this way.

    Grading the only method those 181 years could use — the year minus the
    quarters as first filed in each 10-Q — on the 20 comparable years where a
    real Q4 exists to check against: 15 correct, 5 wrong by 2.4% to 40.7%. A
    25% error rate, invisible at load time, spread across the quarter that
    carries the annual results. Adding ~180 such rows to Track B buys coverage
    at the price of not knowing which rows are true, so the gap is left open
    and documented instead. Pass derive_q4=True only with that understood.
    """
    rows: list[dict] = []
    rev_q = dur["revenue"]

    for fy_end in sorted(ann["revenue"].keys()):
        fy_rev, fy_filed, fy_start = ann["revenue"][fy_end]
        if fy_start is None or fy_end in rev_q:
            continue  # already have a real standalone Q4

        inner = [q for q in rev_q if fy_start < q < fy_end]
        if len(inner) != 3:
            continue

        def remainder(field: str) -> float | None:
            """Q4 for one field, or None when the filings do not agree.

            Computed twice from independent sources — once inside the 10-K
            (one tag, one filing) and once from the quarters as they were
            first filed in each 10-Q — and only kept when the two agree.

            Both methods can be wrong on their own. Amazon's FY2012 10-K tags
            its four 2012 quarters with values that sum to 48,077,000,000,
            which is not FY2012 (61,093,000,000) but FY2011: the comparative
            year's quarters were filed against the current year's dates. That
            filing is internally inconsistent, so being self-consistent proves
            nothing. Conversely the as-first-filed quarters go stale whenever a
            year is genuinely restated, as with Johnson & Johnson's FY2023
            after the Kenvue separation.

            Where the two disagree there is no basis for choosing, and a
            fabricated quarter is worse than a missing one, so the field is
            dropped instead of guessed.
            """
            same_filing = _consistent_remainder(
                gaap, DURATION_CONCEPTS[field], fy_end, fy_filed, inner)

            total = ann[field].get(fy_end)
            parts = [dur[field][q][0] for q in inner if q in dur[field]]
            as_filed = total[0] - sum(parts) if (total is not None and len(parts) == 3) else None

            if same_filing is None or as_filed is None:
                return None
            scale = max(abs(same_filing), abs(as_filed))
            if scale and abs(same_filing - as_filed) / scale > RECONCILE_TOLERANCE:
                return None
            return same_filing

        revenue = remainder("revenue")
        if revenue is None:
            continue
        net_income = remainder("net_income")
        gross_profit = remainder("gross_profit")
        ocf = remainder("operating_cash_flow")
        capex = remainder("capex")

        gross_margin, net_margin = _margins(revenue, gross_profit, net_income)

        # Balance-sheet items are instants at the year end, so they are read
        # directly rather than derived — no subtraction involved.
        equity = inst["stockholders_equity"].get(fy_end, (None,))[0]
        ltd = inst["long_term_debt"].get(fy_end, (None,))[0]
        std = inst["short_term_debt"].get(fy_end, (None,))[0]
        total_debt = (ltd or 0.0) + (std or 0.0) if (ltd is not None or std is not None) else None

        rows.append({
            "ticker": ticker,
            "fiscal_period_end": fy_end,
            "announced_d": fy_filed,
            "revenue": revenue,
            "net_income": net_income,
            "eps_diluted": None,  # never derived — see the docstring on splits
            "gross_margin": gross_margin,
            "net_margin": net_margin,
            "total_debt": total_debt,
            "stockholders_equity": equity,
            "free_cash_flow": (ocf - abs(capex)) if (ocf is not None and capex is not None) else None,
            "source": "edgar_derived",
        })
    return rows


def fetch_quarterly_fundamentals_edgar(
    ticker: str,
    session: requests.Session | None = None,
    cik_map: dict[str, str] | None = None,
    derive_q4: bool = False,
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

    dur: dict[str, dict[date, tuple[float, date, date | None]]] = {}
    ann: dict[str, dict[date, tuple[float, date, date | None]]] = {}
    tags_used: dict[str, list[str]] = {}
    for field, candidates in DURATION_CONCEPTS.items():
        dur[field], tags_used[field] = _series_by_priority(gaap, candidates, "USD", span="quarter")
        ann[field], _ = _series_by_priority(gaap, candidates, "USD", span="annual")

    # prefer="latest" only for per-share figures — see _first_reported.
    eps, tags_used["eps_diluted"] = _series_by_priority(
        gaap, EPS_CONCEPTS, "USD/shares", span="quarter", prefer="latest")
    _drop_mistagged_quarters(ticker, dur["revenue"], ann["revenue"])

    inst: dict[str, dict[date, tuple[float, date, date | None]]] = {}
    for field, candidates in INSTANT_CONCEPTS.items():
        inst[field], tags_used[field] = _series_by_priority(gaap, candidates, "USD", span=None)

    # Revenue anchors a period: without it there's no meaningful quarter.
    period_ends = sorted(dur["revenue"].keys())

    out: list[dict] = []
    for pe in period_ends:
        revenue, filed, _ = dur["revenue"][pe]
        net_income = dur["net_income"].get(pe, (None,))[0]
        gross_profit = dur["gross_profit"].get(pe, (None,))[0]
        ocf = dur["operating_cash_flow"].get(pe, (None,))[0]
        capex = dur["capex"].get(pe, (None,))[0]

        equity = inst["stockholders_equity"].get(pe, (None,))[0]
        ltd = inst["long_term_debt"].get(pe, (None,))[0]
        std = inst["short_term_debt"].get(pe, (None,))[0]

        total_debt = None
        if ltd is not None or std is not None:
            total_debt = (ltd or 0.0) + (std or 0.0)

        free_cash_flow = None
        if ocf is not None and capex is not None:
            # capex is reported as a positive outflow in the cash-flow tags
            free_cash_flow = ocf - abs(capex)

        gross_margin, net_margin = _margins(revenue, gross_profit, net_income)

        out.append({
            "_revenue_tags": tags_used.get("revenue", []),
            "ticker": ticker,
            "fiscal_period_end": pe,
            "announced_d": filed,
            "revenue": revenue,
            "net_income": net_income,
            "eps_diluted": eps.get(pe, (None,))[0],
            "gross_margin": gross_margin,
            "net_margin": net_margin,
            "total_debt": total_debt,
            "stockholders_equity": equity,
            "free_cash_flow": free_cash_flow,
            "source": "edgar",
        })

    if derive_q4:
        out.extend(_derive_q4_rows(ticker, gaap, dur, ann, inst))
        out.sort(key=lambda r: r["fiscal_period_end"])

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
    total_derived = 0
    for t in tickers:
        rows = fetch_quarterly_fundamentals_edgar(t, session=session, cik_map=cik_map)
        total += len(rows)
        if not rows:
            print(f"  {t:10s} no EDGAR filings (expected for indices/forex/commodities/crypto)")
            continue
        ends = [r["fiscal_period_end"] for r in rows]
        filled = sum(1 for r in rows if r["net_income"] is not None)
        derived = sum(1 for r in rows if r["source"] == "edgar_derived")
        total_derived += derived
        src = ",".join(next((r["_revenue_tags"] for r in rows if r.get("_revenue_tags")), [])) or "?"
        print(f"  {t:10s} {len(rows):3d} quarters (+{derived:2d} derived Q4)  {min(ends)} -> {max(ends)}  "
              f"(net_income: {filled})  revenue via {src}")
    print(f"\nTotal quarterly rows available from EDGAR: {total} "
          f"({total - total_derived} as-filed, {total_derived} derived Q4)")


if __name__ == "__main__":
    main()
