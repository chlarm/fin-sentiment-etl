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
  credibility_score NUMERIC(3,1) DEFAULT 5.0,
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

-- Technical indicators derived purely from fact_price_daily (Phase 1: prediction-model feature base)
CREATE TABLE IF NOT EXISTS fact_technical_daily (
  asset_id       INT NOT NULL REFERENCES dim_asset(asset_id),
  d              DATE NOT NULL REFERENCES dim_date(d),
  sma_20         NUMERIC,
  sma_50         NUMERIC,
  sma_200        NUMERIC,
  ema_12         NUMERIC,
  ema_26         NUMERIC,
  macd           NUMERIC,
  macd_signal    NUMERIC,
  macd_hist      NUMERIC,
  rsi_14         NUMERIC,
  volatility_20  NUMERIC,  -- rolling 20d stdev of daily returns
  momentum_5     NUMERIC,  -- 5-trading-day return
  momentum_21    NUMERIC,  -- ~1 month return
  momentum_63    NUMERIC,  -- ~1 quarter return
  updated_at     TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (asset_id, d)
);

-- Quarterly company fundamentals (Phase 1: long-horizon prediction feature base).
-- announced_d is the point-in-time anchor (earnings announcement date) — use this,
-- never fiscal_period_end, when joining against price/sentiment to avoid lookahead bias.
CREATE TABLE IF NOT EXISTS fact_fundamentals_quarterly (
  asset_id             INT NOT NULL REFERENCES dim_asset(asset_id),
  fiscal_period_end    DATE NOT NULL,
  announced_d          DATE,
  revenue              NUMERIC,
  net_income           NUMERIC,
  eps_diluted          NUMERIC,
  gross_margin         NUMERIC,
  net_margin           NUMERIC,
  total_debt           NUMERIC,
  stockholders_equity  NUMERIC,
  free_cash_flow       NUMERIC,
  -- Where the row came from, so a mixed table stays auditable and one
  -- provider can be swapped out without guessing which rows are whose:
  --   'yfinance'      quarterly statements via yfinance (5-7 quarters/ticker,
  --                   period ends rounded to month end)
  --   'edgar'         as-filed XBRL facts from SEC companyfacts
  --   'edgar_derived' Q4 computed as FY minus Q1+Q2+Q3, because a 10-K
  --                   reports the full year and most filers never tag a
  --                   standalone Q4. Arithmetic on reported figures, but
  --                   separated so it can be excluded from analysis.
  source               TEXT,
  updated_at           TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (asset_id, fiscal_period_end)
);
ALTER TABLE fact_fundamentals_quarterly ADD COLUMN IF NOT EXISTS source TEXT;
CREATE INDEX IF NOT EXISTS idx_fact_fundamentals_announced_d ON fact_fundamentals_quarterly(announced_d);

-- User's watchlist: tickers to monitor for signal flips on the web dashboard.
CREATE TABLE IF NOT EXISTS dim_watchlist (
  asset_id     INT PRIMARY KEY REFERENCES dim_asset(asset_id),
  added_at     TIMESTAMPTZ DEFAULT now()
);

-- One row per time a watched ticker's model signal was checked, so the web
-- app can detect "the signal just flipped" instead of just showing the
-- current value every time. Appended to by the /watchlist page itself.
CREATE TABLE IF NOT EXISTS fact_watchlist_signal_log (
  log_id       BIGSERIAL PRIMARY KEY,
  asset_id     INT NOT NULL REFERENCES dim_asset(asset_id),
  checked_at   TIMESTAMPTZ DEFAULT now(),
  signal       TEXT NOT NULL,
  confidence   NUMERIC
);
CREATE INDEX IF NOT EXISTS idx_watchlist_log_asset_time ON fact_watchlist_signal_log(asset_id, checked_at DESC);

-- Joined view of price + sentiment used by the dashboard and correlation analysis
CREATE OR REPLACE VIEW vw_daily_asset_metrics AS
SELECT
  a.ticker,
  p.d,
  p.close,
  p.return_1d,
  p.pct_change,
  s.news_count,
  s.sentiment_mean AS sentiment_index,
  s.sentiment_median,
  s.pos_count,
  s.neu_count,
  s.neg_count
FROM fact_price_daily p
JOIN dim_asset a ON a.asset_id = p.asset_id
LEFT JOIN fact_sentiment_daily s ON s.asset_id = p.asset_id AND s.d = p.d;

-- Registrant profile and business narrative from SEC EDGAR. One row per asset
-- that actually files with the SEC; indices, forex, commodities and crypto
-- have no row at all, which is a property of the asset rather than missing
-- data. Every field is traceable to a filing: latest_10k_url points at the
-- exact document the business description was read from.
CREATE TABLE IF NOT EXISTS dim_company_profile (
  asset_id               INT PRIMARY KEY REFERENCES dim_asset(asset_id),
  cik                    TEXT,
  legal_name             TEXT,
  sic                    TEXT,
  sic_description        TEXT,   -- SEC's own industry classification
  entity_type            TEXT,
  state_of_incorporation TEXT,
  fiscal_year_end        TEXT,   -- MMDD, e.g. 0926 for the last Saturday of Sept
  exchanges              TEXT,
  ein                    TEXT,
  filer_category         TEXT,
  phone                  TEXT,
  hq_street              TEXT,
  hq_city                TEXT,
  hq_state               TEXT,
  former_names           TEXT,
  -- Item 1 "Business" from the most recent 10-K. NULL when the filing does
  -- not use a locatable Item 1 heading (see company_profile_edgar.py) — the
  -- profile and the filing link are still useful, and a wrong description
  -- would be worse than none.
  business_description   TEXT,
  latest_10k_filed       DATE,
  latest_10k_accession   TEXT,
  latest_10k_url         TEXT,
  recent_filings         JSONB,  -- [{form, filed, accession, url}, ...]
  fetched_at             TIMESTAMPTZ DEFAULT now()
);
