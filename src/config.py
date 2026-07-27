from __future__ import annotations
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

def _get(name: str, default: str | None = None) -> str:
    v = os.getenv(name, default)
    if v is None:
        raise ValueError(f"Missing env var: {name}")
    return v

def _get_bool(name: str, default: str = "0") -> bool:
    return _get(name, default).strip() not in ("0", "false", "False", "")

# Default search-term overrides — only for symbols Google News can't search
# meaningfully as-is (indices, forex, crypto tickers with punctuation).
# Ordinary equity tickers (AMZN, NVDA, GOOGL, NFLX, AMD, ORCL, ...) used to
# have "helpful" natural-language overrides here (e.g. AMZN -> "Amazon stock
# e-commerce"), but measured against the live feed on 2026-07-25 every one of
# them returned far FEWER trusted-source articles in the last 7 days than
# just searching the raw ticker: AMZN 0 vs 15, ORCL 0 vs 14, NVDA 3 vs 19,
# NFLX 8 vs 37, AMD 5 vs 19, GOOGL 34 vs 39. Removed rather than guessed at a
# better phrase — if this needs revisiting, re-measure before changing it,
# since Google News' ranking for a given query drifts over time.
_DEFAULT_TICKER_SEARCH_TERMS: dict[str, str] = {
    "GC=F":     "gold price USD futures",
    "CL=F":     "crude oil price futures WTI",
    "EURUSD=X": "euro dollar exchange rate",
    "THBUSD=X": "Thai baht USD exchange rate",
    "BTC-USD":  "Bitcoin USD price crypto",
    "ETH-USD":  "Ethereum USD price crypto",
    "EURUSD":   "euro dollar exchange rate",
    "^GSPC":    "S&P 500 stock market index",
    "^DJI":     "Dow Jones industrial average",
    "^IXIC":    "NASDAQ stock market index",
}

@dataclass(frozen=True)
class Settings:
    # DB
    pg_host: str = _get("POSTGRES_HOST", "localhost")
    pg_port: int = int(_get("POSTGRES_PORT", "5432"))
    pg_db: str = _get("POSTGRES_DB", "fin_dw")
    pg_user: str = _get("POSTGRES_USER", "fin")
    pg_password: str = _get("POSTGRES_PASSWORD", "fin")

    # Pipeline
    tickers: tuple[str, ...] = tuple([t.strip() for t in _get("TICKERS", "AAPL").split(",") if t.strip()])
    price_source: str = _get("PRICE_SOURCE", "stooq").strip().lower()  # yahoo|stooq
    news_rss_template: str = _get("NEWS_RSS_TEMPLATE", "https://news.google.com/rss/search?q={ticker}%20stock&hl=en-US&gl=US&ceid=US:en")
    trusted_news_sources: tuple[str, ...] = tuple([
        s.strip().lower() for s in _get(
            "TRUSTED_NEWS_SOURCES",
            "bloomberg,reuters,cnbc,financial times,wall street journal,yahoo finance,marketwatch,"
            "marketbeat,simply wall st,seeking alpha,investing.com,the globe and mail,barron,"
            "msn,business insider,motley fool,benzinga,the street,zacks,coindesk,cointelegraph,meyka,polymarket"
        ).split(",") if s.strip()
    ])
    lookback_hours: int = int(_get("LOOKBACK_HOURS", "168"))
    intraday_lookback_hours: int = int(_get("INTRADAY_LOOKBACK_HOURS", "3"))
    pipeline_tz: str = _get("PIPELINE_TZ", "Asia/Bangkok")
    news_debug: bool = _get_bool("NEWS_DEBUG", "1")
    email_sender: str = _get("EMAIL_SENDER", "")
    email_password: str = _get("EMAIL_PASSWORD", "")
    email_receiver: str = _get("EMAIL_RECEIVER", "")

    @property
    def ticker_search_terms(self) -> dict[str, str]:
        """Return per-ticker RSS search query overrides."""
        result = dict(_DEFAULT_TICKER_SEARCH_TERMS)
        # Support env-based overrides: TICKER_SEARCH_TERM_GCXF=gold futures USD
        for t in self.tickers:
            safe_key = "TICKER_SEARCH_TERM_" + t.replace("=", "X").replace("-", "_").upper()
            val = os.getenv(safe_key)
            if val:
                result[t] = val
        return result

    @property
    def sqlalchemy_url(self) -> str:
        if self.pg_host.startswith("/cloudsql"):
            return f"postgresql+psycopg2://{self.pg_user}:{self.pg_password}@/{self.pg_db}?host={self.pg_host}"
        return f"postgresql+psycopg2://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_db}"
