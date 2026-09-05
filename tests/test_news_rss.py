"""
Tests for the Google News RSS URL builder.

Worth testing because the bug it replaced was completely silent: an
unescaped '&' in a search term ended the q= parameter, so ^GSPC spent months
searching Google News for the letter "S" and still returned a plausible-looking
feed of ~100 entries. Nothing errored; the coverage was just quietly wrong.
"""
from __future__ import annotations
from urllib.parse import parse_qs, urlparse

from src.extract.news_rss import google_news_rss_url


def _q(url: str) -> str:
    """The single q= value Google actually receives."""
    values = parse_qs(urlparse(url).query)["q"]
    assert len(values) == 1, f"expected exactly one q= parameter, got {values}"
    return values[0]


def test_ampersand_stays_inside_the_query():
    """'S&P 500 stock market index' must not truncate to 'S'."""
    assert _q(google_news_rss_url("S&P 500 stock market index")) == \
        "S&P 500 stock market index market"


def test_spaces_are_encoded():
    assert " " not in urlparse(google_news_rss_url("gold price USD futures")).query
    assert _q(google_news_rss_url("gold price USD futures")) == "gold price USD futures market"


def test_plain_ticker_is_unchanged_apart_from_the_market_suffix():
    assert _q(google_news_rss_url("AAPL stock")) == "AAPL stock market"


def test_other_query_parameters_survive():
    params = parse_qs(urlparse(google_news_rss_url("S&P 500")).query)
    assert params["hl"] == ["en-US"]
    assert params["gl"] == ["US"]
    assert params["ceid"] == ["US:en"]


def test_characters_that_would_break_a_url_are_escaped():
    """Tickers and terms carrying '=', '?', '#' or '&' must not leak into the
    URL structure — several of ours contain '=' (GC=F, EURUSD=X)."""
    for term in ["GC=F", "EURUSD=X", "a?b", "a#b", "a&b=c"]:
        params = parse_qs(urlparse(google_news_rss_url(term)).query)
        assert set(params) == {"q", "hl", "gl", "ceid"}, f"{term} leaked extra params: {params}"
        assert params["q"] == [f"{term} market"]
