-- Star schema for finance price + news sentiment (daily)
CREATE TABLE IF NOT EXISTS dim_asset (
  asset_id      SERIAL PRIMARY KEY,
  ticker        TEXT NOT NULL UNIQUE,
  asset_name    TEXT,
  asset_class   TEXT,
  currency      TEXT,
  exchange      TEXT,
  created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dim_source (
  source_id     SERIAL PRIMARY KEY,
  source_name   TEXT NOT NULL,
  source_type   TEXT NOT NULL DEFAULT 'rss',
  base_url      TEXT,
  created_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE (source_name, source_type)
);

CREATE TABLE IF NOT EXISTS dim_date (
  d            DATE PRIMARY KEY,
  y            INT NOT NULL,
  m            INT NOT NULL,
  day          INT NOT NULL,
  dow          INT NOT NULL,
  is_weekend   BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_price_daily (
  asset_id     INT NOT NULL REFERENCES dim_asset(asset_id),
  d            DATE NOT NULL REFERENCES dim_date(d),
  open         NUMERIC,
  high         NUMERIC,
  low          NUMERIC,
  close        NUMERIC,
  adj_close    NUMERIC,
  volume       BIGINT,
  return_1d    NUMERIC,
  pct_change   NUMERIC,
  updated_at   TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (asset_id, d)
);

CREATE TABLE IF NOT EXISTS fact_news (
  news_id         BIGSERIAL PRIMARY KEY,
  asset_id        INT NOT NULL REFERENCES dim_asset(asset_id),
  source_id       INT NOT NULL REFERENCES dim_source(source_id),
  published_at    TIMESTAMPTZ NOT NULL,
  published_d     DATE NOT NULL REFERENCES dim_date(d),
  title           TEXT NOT NULL,
  url             TEXT,
  news_hash       TEXT NOT NULL UNIQUE,
  sentiment_score NUMERIC,
  sentiment_label TEXT,
  ingested_at     TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fact_news_asset_d ON fact_news(asset_id, published_d);
CREATE INDEX IF NOT EXISTS idx_fact_price_daily_d ON fact_price_daily(d);

CREATE TABLE IF NOT EXISTS fact_sentiment_daily (
  asset_id         INT NOT NULL REFERENCES dim_asset(asset_id),
  d                DATE NOT NULL REFERENCES dim_date(d),
  news_count       INT NOT NULL,
  sentiment_mean   NUMERIC,
  sentiment_median NUMERIC,
  pos_count        INT NOT NULL,
  neu_count        INT NOT NULL,
  neg_count        INT NOT NULL,
  updated_at       TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (asset_id, d)
);
