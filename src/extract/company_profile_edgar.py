"""
Company profiles from SEC EDGAR: who the registrant is, and what it says it
does — in its own words, from a document it filed under legal obligation.

Why EDGAR rather than a web source. Everything here is citable to a specific
filing with an accession number and a permanent SEC URL, and the business
description is the company's own statutory account of its operations, not a
third party's summary. That matters for a thesis: a claim about what Apple
does can be traced to Apple's 10-K rather than to an encyclopedia edit.

Two endpoints are used:

  submissions/CIK##########.json   registrant facts — legal name, SIC industry
                                   classification, state of incorporation,
                                   fiscal year end, exchanges, former names,
                                   and the full filing index
  the 10-K primary document        Item 1 "Business", the narrative section

**Item 1 extraction is not universally reliable, and the failure is
structural rather than a parsing bug.** Measured across the 21 equities, 19
extract cleanly. The two that do not:

  MSFT   "Item 1. Business" appears exactly once in the whole document — in
         the index. The body section is headed differently.
  INTC   uses a "Form 10-K Cross-Reference Index" that maps items to page
         numbers, so no Item 1 heading exists in the body at all.

No regex fixes those, because the text being searched for is genuinely
absent. Rather than return a fragment that looks like a business description
and is not, extraction returns None and the caller stores NULL — the profile
and the link to the filing are still shown, so the reader can go to the
source. A wrong description would be worse than none.
"""
from __future__ import annotations

import argparse
import html as html_lib
import re
import time
from datetime import date, datetime

import requests

from src.extract.fundamentals_edgar import (
    REQUEST_DELAY_SECONDS,
    _get_json,
    _user_agent,
    fetch_cik_map,
)

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{document}"

# Item 1 sections outside this range are almost certainly a mis-parse: a few
# hundred characters means the table of contents was matched, and hundreds of
# thousands means the end marker was missed and most of the document was
# swallowed. Observed genuine range across the 21 equities: 5.6k - 92.8k.
MIN_BUSINESS_CHARS = 3_000
MAX_BUSINESS_CHARS = 150_000

FILING_FORMS = ("10-K", "10-Q", "8-K")
RECENT_FILINGS_KEPT = 8


def _html_to_text(raw: str) -> str:
    """Strip markup to a single whitespace-normalised string.

    Script and style bodies are removed first — leaving them in injects
    JavaScript into what is meant to be prose, and their braces confuse the
    heading search.
    """
    raw = re.sub(r"<(script|style)\b.*?</\1>", " ", raw, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html_lib.unescape(text)
    # Non-breaking spaces survive unescape as U+00A0 and break word matching.
    text = text.replace(" ", " ")
    return re.sub(r"\s+", " ", text).strip()


def extract_business_section(text: str) -> str | None:
    """The Item 1 "Business" narrative, or None when it cannot be located.

    Each candidate start is paired with the FIRST "Item 1A Risk Factors" that
    follows it, then the longest such span wins. Pairing every start with
    every end instead lets a table-of-contents entry pair with the last risk
    factors mention and swallow the document — that produced a 214,000
    character "business description" for Coca-Cola before it was fixed.
    """
    starts = [m.start() for m in re.finditer(r"Item\s*1\.?\s*[—–\-]?\s*Business", text, re.I)]
    ends = [m.start() for m in re.finditer(r"Item\s*1A\.?\s*[—–\-]?\s*Risk\s*Factors", text, re.I)]
    if not starts or not ends:
        return None

    best: tuple[int, int] | None = None
    for a in starts:
        following = next((b for b in ends if b > a), None)
        if following and (best is None or following - a > best[1] - best[0]):
            best = (a, following)
    if best is None:
        return None

    section = text[best[0]:best[1]].strip()
    if not (MIN_BUSINESS_CHARS <= len(section) <= MAX_BUSINESS_CHARS):
        return None
    return section


def _parse_date(value: str | None) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() if value else None
    except ValueError:
        return None


def fetch_company_profile(
    ticker: str,
    session: requests.Session | None = None,
    cik_map: dict[str, str] | None = None,
    with_business: bool = True,
) -> dict | None:
    """Registrant profile plus, where extractable, the Item 1 business text.

    Returns None for anything with no SEC registrant — indices, forex,
    commodities and crypto do not file, which is a fact about the asset and
    not an error.
    """
    session = session or requests.Session()
    cik_map = cik_map if cik_map is not None else fetch_cik_map(session)
    cik = cik_map.get(ticker.upper())
    if not cik:
        return None

    data = _get_json(session, SUBMISSIONS_URL.format(cik=cik))
    if not data:
        return None

    business_addr = (data.get("addresses") or {}).get("business") or {}
    recent = (data.get("filings") or {}).get("recent") or {}

    filings: list[dict] = []
    latest_10k: dict | None = None
    forms = recent.get("form", [])
    for i, form in enumerate(forms):
        if form not in FILING_FORMS:
            continue
        accession = recent["accessionNumber"][i]
        entry = {
            "form": form,
            "filed": recent["filingDate"][i],
            "accession": accession,
            "url": ARCHIVE_URL.format(
                cik_int=int(cik),
                accession=accession.replace("-", ""),
                document=recent["primaryDocument"][i],
            ),
        }
        if form == "10-K" and latest_10k is None:
            latest_10k = entry
        if len(filings) < RECENT_FILINGS_KEPT:
            filings.append(entry)
        if latest_10k and len(filings) >= RECENT_FILINGS_KEPT:
            break

    profile = {
        "ticker": ticker.upper(),
        "cik": cik,
        "legal_name": data.get("name"),
        "sic": data.get("sic") or None,
        "sic_description": data.get("sicDescription") or None,
        "entity_type": data.get("entityType") or None,
        "state_of_incorporation": data.get("stateOfIncorporation") or None,
        "fiscal_year_end": data.get("fiscalYearEnd") or None,
        "exchanges": ", ".join(data.get("exchanges") or []) or None,
        "ein": data.get("ein") or None,
        "filer_category": data.get("category") or None,
        "phone": data.get("phone") or None,
        "hq_city": business_addr.get("city") or None,
        "hq_state": business_addr.get("stateOrCountry") or None,
        "hq_street": business_addr.get("street1") or None,
        "former_names": ", ".join(
            f["name"] for f in (data.get("formerNames") or []) if f.get("name")
        ) or None,
        "recent_filings": filings,
        "latest_10k_filed": _parse_date(latest_10k["filed"]) if latest_10k else None,
        "latest_10k_accession": latest_10k["accession"] if latest_10k else None,
        "latest_10k_url": latest_10k["url"] if latest_10k else None,
        "business_description": None,
    }

    if with_business and latest_10k:
        try:
            resp = session.get(
                latest_10k["url"], headers={"User-Agent": _user_agent()}, timeout=120
            )
            time.sleep(REQUEST_DELAY_SECONDS)
            if resp.status_code == 200:
                profile["business_description"] = extract_business_section(
                    _html_to_text(resp.text)
                )
            else:
                print(f"[profile] {ticker}: HTTP {resp.status_code} fetching 10-K")
        except requests.RequestException as exc:
            print(f"[profile] {ticker}: could not fetch 10-K: {exc}")

    return profile


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--tickers", type=str, default=None)
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

    with_desc = 0
    for t in tickers:
        p = fetch_company_profile(t, session=session, cik_map=cik_map)
        if not p:
            print(f"  {t:10s} no SEC registrant (expected for indices/forex/commodities/crypto)")
            continue
        desc = p["business_description"]
        with_desc += bool(desc)
        print(f"  {t:10s} {(p['legal_name'] or '')[:34]:36s} {p['sic_description'] or '':30s} "
              f"business: {len(desc):,} chars" if desc else
              f"  {t:10s} {(p['legal_name'] or '')[:34]:36s} {p['sic_description'] or '':30s} "
              f"business: not extractable")
    print(f"\nBusiness description extracted for {with_desc} of {len(tickers)} requested")


if __name__ == "__main__":
    main()
