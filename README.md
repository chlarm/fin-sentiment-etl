# Finance News Sentiment ETL (Daily Batch)

ETL แบบ daily batch: ราคา + ข่าว RSS + sentiment (VADER) -> PostgreSQL (Star Schema)

## Quick Start

### 1) Start PostgreSQL
```bash
cp .env.example .env
docker compose --env-file .env up -d postgres
docker compose ps
```

### 2) Python venv
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
```

### 3) Run ETL
```bash
python -m src.etl.run_daily
# or
python -m src.etl.run_daily --date 2026-01-14
```

### 4) Verify (psql in container)
```bash
docker compose exec postgres psql -U fin -d fin_dw -P pager=off -c "\dt"
docker compose exec postgres psql -U fin -d fin_dw -P pager=off -c "SELECT COUNT(*) FROM fact_price_daily;"
docker compose exec postgres psql -U fin -d fin_dw -P pager=off -c "SELECT COUNT(*) FROM fact_news;"
docker compose exec postgres psql -U fin -d fin_dw -P pager=off -c "SELECT COUNT(*) FROM fact_sentiment_daily;"
```
