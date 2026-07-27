from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import feedparser
import pendulum
import requests


@dataclass
class NewsItem:
    ticker: str
    source_name: str
    base_url: str
    published_at_utc: datetime
    title: str
    url: str | None

def _guess_source(feed_url: str) -> tuple[str, str]:
    parsed = urlparse(feed_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    name = parsed.netloc.replace("www.", "")
    return name, base

def _entry_datetime_utc(entry) -> datetime | None:
    t = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if t:
        dt = datetime(*t[:6])
        return pendulum.instance(dt, tz="UTC")
    s = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if not s:
        return None
    try:
        dt2 = parsedate_to_datetime(s)
        if dt2.tzinfo is None:
            return pendulum.instance(dt2, tz="UTC")
        return pendulum.instance(dt2).in_timezone("UTC")
    except Exception:
        return None

def fetch_news_rss_for_ticker(
    ticker: str,
    rss_template: str,
    lookback_hours: int,
    now_utc: datetime,
    trusted_sources: tuple[str, ...] | None = None,
    debug: bool = False,
) -> list[NewsItem]:
    # If the template is already a fully-built URL (no {ticker}), use it as-is
    if "{ticker}" in rss_template or "{ticker_lower}" in rss_template:
        feed_url = rss_template.format(ticker=ticker, ticker_lower=ticker.lower())
    else:
        feed_url = rss_template
    headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari",
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
}
    resp = requests.get(feed_url, headers=headers, timeout=20)
    status = resp.status_code
    content_type = resp.headers.get("Content-Type")

    source_name, base_url = _guess_source(feed_url)

    parsed = feedparser.parse(resp.content)
    cutoff = now_utc - timedelta(hours=lookback_hours)

    entries = getattr(parsed, "entries", []) or []
    kept: list[NewsItem] = []

    for e in entries:
        title = getattr(e, "title", "") or ""
        link = getattr(e, "link", None)
        published_utc = _entry_datetime_utc(e)
        if not published_utc:
            continue
        if published_utc < cutoff:
            continue
        
        entry_source = getattr(e, "source", {})
        pub_title = entry_source.get("title", "")
        pub_url = entry_source.get("href", "")

        if trusted_sources:
            is_trusted = any(ts in pub_title.lower() for ts in trusted_sources)
            if not is_trusted:
                continue

        actual_source_name = pub_title if pub_title else source_name
        actual_base_url = pub_url if pub_url else base_url

        kept.append(NewsItem(
            ticker=ticker,
            source_name=actual_source_name,
            base_url=actual_base_url,
            published_at_utc=published_utc,
            title=title,
            url=link,
        ))

    if debug:
        status = getattr(parsed, "status", None)
        bozo = getattr(parsed, "bozo", None)
        exc = getattr(parsed, "bozo_exception", None)
        print(f"[news][{ticker}] url={feed_url}")
        print(f"[news][{ticker}] status={status} bozo={bozo} entries={len(entries)} kept={len(kept)}")
        print(f"[news][{ticker}] http_status={status} content_type={content_type} bytes={len(resp.content)}")
        if exc:
            print(f"[news][{ticker}] bozo_exception={exc}")

    return kept
