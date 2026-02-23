import os
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape

load_dotenv()

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "fin_dw")
DB_USER = os.getenv("POSTGRES_USER", "fin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "fin")

engine = create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

app = FastAPI(title="Fin Sentiment Dashboard")
app.mount("/static", StaticFiles(directory="web/static"), name="static")

templates = Environment(
    loader=FileSystemLoader("web/templates"),
    autoescape=select_autoescape(["html", "xml"]),
)

def qdf(sql: str, **params) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, tab: str = "news", ticker: str = "ALL"):
    # --- counts ---
    counts = qdf("""
        SELECT
          (SELECT COUNT(*) FROM fact_price_daily) AS price_rows,
          (SELECT COUNT(*) FROM fact_news) AS news_rows,
          (SELECT COUNT(*) FROM fact_sentiment_daily) AS senti_rows;
    """).iloc[0].to_dict()

    # --- tickers for filter ---
    tickers = qdf("SELECT ticker FROM dim_asset ORDER BY ticker;")["ticker"].tolist()
    ticker_options = ["ALL"] + tickers
    if ticker not in ticker_options:
        ticker = "ALL"

    # --- latest news ---
    news_sql = """
    SELECT a.ticker, n.published_at, n.sentiment_label, n.sentiment_score, n.title, n.url
    FROM fact_news n
    JOIN dim_asset a ON a.asset_id=n.asset_id
    WHERE (:t = 'ALL' OR a.ticker = :t)
    ORDER BY n.published_at DESC
    LIMIT 50;
    """
    news = qdf(news_sql, t=ticker).to_dict(orient="records")

    # --- daily metrics from your view ---
    metrics_sql = """
    SELECT ticker, d, close, return_1d, sentiment_index, news_count
    FROM vw_daily_asset_metrics
    WHERE (:t = 'ALL' OR ticker = :t)
    ORDER BY d DESC, ticker
    LIMIT 120;
    """
    metrics = qdf(metrics_sql, t=ticker).to_dict(orient="records")

    # --- correlation & lags computed live ---
    corr_sql = """
    WITH x AS (
      SELECT
        ticker, d, return_1d, sentiment_index,
        lag(sentiment_index, 1) OVER (PARTITION BY ticker ORDER BY d) AS sentiment_lag1,
        lag(sentiment_index, 2) OVER (PARTITION BY ticker ORDER BY d) AS sentiment_lag2
      FROM vw_daily_asset_metrics
      WHERE (:t = 'ALL' OR ticker = :t)
    )
    SELECT
      ticker,
      corr(return_1d, sentiment_index) AS corr_t,
      corr(return_1d, sentiment_lag1)  AS corr_lag1,
      corr(return_1d, sentiment_lag2)  AS corr_lag2,
      COUNT(*) FILTER (WHERE return_1d IS NOT NULL AND sentiment_index IS NOT NULL) AS n_t,
      COUNT(*) FILTER (WHERE return_1d IS NOT NULL AND sentiment_lag1 IS NOT NULL)  AS n_lag1,
      COUNT(*) FILTER (WHERE return_1d IS NOT NULL AND sentiment_lag2 IS NOT NULL)  AS n_lag2
    FROM x
    GROUP BY ticker
    ORDER BY ticker;
    """
    corr = qdf(corr_sql, t=ticker).to_dict(orient="records")

    tpl = templates.get_template("dashboard.html")
    html = tpl.render(
        tab=tab,
        ticker=ticker,
        ticker_options=ticker_options,
        counts=counts,
        news=news,
        metrics=metrics,
        corr=corr,
    )
    return HTMLResponse(html)
