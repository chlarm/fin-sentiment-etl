from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def _get(name: str, default: str | None = None) -> str:
    v = os.getenv(name, default)
    if v is None:
        raise ValueError(f"Missing env var: {name}")
    return v

def _get_bool(name: str, default: str = "0") -> bool:
    return _get(name, default).strip() not in ("0", "false", "False", "")

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
    lookback_hours: int = int(_get("LOOKBACK_HOURS", "168"))
    pipeline_tz: str = _get("PIPELINE_TZ", "Asia/Bangkok")
    news_debug: bool = _get_bool("NEWS_DEBUG", "1")

    @property
    def sqlalchemy_url(self) -> str:
        return f"postgresql+psycopg2://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_db}"
