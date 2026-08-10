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

# Default search-term overrides.
#
# History here matters because it explains why this isn't a single rule.
# Ordinary equity tickers used to have "helpful" natural-language overrides
# (e.g. AMZN -> "Amazon stock e-commerce"), but measured on 2026-07-25 every
# one of them returned far FEWER trusted-source articles in 7 days than just
# the raw ticker: AMZN 0 vs 15, ORCL 0 vs 14, NVDA 3 vs 19, NFLX 8 vs 37,
# AMD 5 vs 19, GOOGL 34 vs 39. So they were removed — extra qualifying words
# ("e-commerce") over-narrow Google News' full-text match.
#
# That is not the same claim as "bare ticker is always best." Re-measured on
# 2026-07-29 against 21 equities, appending the single word "stock" (not a
# phrase) won 20/21 head-to-head on trusted-source count — often by a lot for
# tickers that collide with common English words and can't function as a
# search term on their own (KO 0->10, HD 0->14, DIS 0->23, BA 0->5, V 1->10,
# PG 2->13, JNJ 1->13, INTC 1->13, WMT 1->16, JPM 4->18, XOM 9->32). The one
# loser was NFLX (14 -> 12), left on the bare ticker for that reason. If this
# needs revisiting, re-measure before changing it — Google News' ranking for
# a given query drifts over time, which is exactly what happened here.
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
    # Equities: "<ticker> stock", except NFLX (measured worse — see above).
    "AAPL": "AAPL stock",
    "MSFT": "MSFT stock",
    "GOOGL": "GOOGL stock",
    "AMZN": "AMZN stock",
    "NVDA": "NVDA stock",
    "META": "META stock",
    "TSLA": "TSLA stock",
    "AMD": "AMD stock",
    "ORCL": "ORCL stock",
    "INTC": "INTC stock",
    "JPM": "JPM stock",
    "V": "V stock",
    "JNJ": "JNJ stock",
    "XOM": "XOM stock",
    "PG": "PG stock",
    "KO": "KO stock",
    "WMT": "WMT stock",
    "HD": "HD stock",
    "DIS": "DIS stock",
    "BA": "BA stock",
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
