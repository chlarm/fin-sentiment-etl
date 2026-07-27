import os
import time
from pathlib import Path
import numpy as np
import requests as _requests
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime, timedelta, timezone
from scipy import stats as scipy_stats

from src.models.predict import signal_and_backtest, sentiment_signal
from src.models.case_studies import find_case_studies
from src.models.watchlist import (
    list_watchlist, add_to_watchlist, remove_from_watchlist, check_signal_change,
)
from fastapi import Form
from fastapi.responses import RedirectResponse

BASE_DIR = Path(__file__).resolve().parent

def _static_version() -> str:
    try:
        return str(int((BASE_DIR / "static" / "style.css").stat().st_mtime))
    except OSError:
        return "0"

STATIC_VERSION = _static_version()

_translate_cache: dict = {}

def translate_to_thai(text_en: str) -> str:
    """Translate English text to Thai using free Google Translate endpoint."""
    if not text_en or not text_en.strip():
        return text_en
    key = text_en[:120]  # cache key truncated
    if key in _translate_cache:
        return _translate_cache[key]
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx", "sl": "en", "tl": "th",
            "dt": "t", "q": text_en[:500]
        }
        resp = _requests.get(url, params=params, timeout=5)
        parts = resp.json()[0]
        translated = "".join(p[0] for p in parts if p[0])
        _translate_cache[key] = translated
        return translated
    except Exception:
        return text_en  # fallback to original if translation fails

def _fisher_ci(r: float | None, n: int | None, alpha: float = 0.05) -> tuple[float | None, float | None]:
    """95% CI for a Pearson r via the Fisher z-transform (standard closed-form approach)."""
    if r is None or not n or n < 4:
        return None, None
    r_clamped = max(min(r, 0.999999), -0.999999)
    z = np.arctanh(r_clamped)
    se = 1 / np.sqrt(n - 3)
    z_crit = scipy_stats.norm.ppf(1 - alpha / 2)
    lo, hi = np.tanh(z - z_crit * se), np.tanh(z + z_crit * se)
    return round(float(lo), 4), round(float(hi), 4)


def _pooled_fe_ols(df: pd.DataFrame) -> dict:
    """Pooled return_1d ~ sentiment_lag1 with ticker fixed effects (within/demeaning
    estimator) and cluster-robust (by ticker) SE. One adequately-powered estimate,
    since each ticker's own real-news sample is individually too thin to trust alone.
    """
    d = df.dropna(subset=["return_1d", "sentiment_lag1"]).copy()
    n_tickers = d["ticker"].nunique()
    if len(d) < 10 or n_tickers < 2:
        return {"n": len(d), "n_tickers": n_tickers, "slope": None, "se": None, "t": None, "p": None}

    d["y"] = d["return_1d"] - d.groupby("ticker")["return_1d"].transform("mean")
    d["x"] = d["sentiment_lag1"] - d.groupby("ticker")["sentiment_lag1"].transform("mean")

    x = d["x"].values
    y = d["y"].values
    xtx = float((x * x).sum())
    if xtx == 0:
        return {"n": len(d), "n_tickers": n_tickers, "slope": None, "se": None, "t": None, "p": None}
    xtx_inv = 1.0 / xtx
    beta = xtx_inv * float((x * y).sum())

    resid = y - x * beta
    d["resid"] = resid
    meat = 0.0
    for _, g in d.groupby("ticker"):
        s = float((g["x"].values * g["resid"].values).sum())
        meat += s * s
    var_beta = (xtx_inv ** 2) * meat
    se = float(np.sqrt(var_beta)) if var_beta > 0 else None

    if not se:
        return {"n": len(d), "n_tickers": n_tickers, "slope": round(beta, 6), "se": None, "t": None, "p": None}

    t_stat = beta / se
    dof = max(n_tickers - 1, 1)
    p_val = float(2 * scipy_stats.t.sf(abs(t_stat), dof))

    return {
        "n": len(d),
        "n_tickers": n_tickers,
        "slope": round(beta, 6),
        "se": round(se, 6),
        "t": round(t_stat, 3),
        "p": round(p_val, 4),
    }


load_dotenv()

DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "fin_dw")
DB_USER = os.getenv("POSTGRES_USER", "fin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "fin")

if DB_HOST.startswith("/cloudsql"):
    db_url = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@/{DB_NAME}?host={DB_HOST}"
else:
    db_url = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(db_url)

app = FastAPI(title="Fin Sentiment Dashboard")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

templates = Environment(
    loader=FileSystemLoader(str(BASE_DIR / "templates")),
    autoescape=select_autoescape(["html", "xml"]),
)

# Human-readable display names for cryptic ticker symbols
TICKER_DISPLAY_NAMES: dict[str, str] = {
    "GC=F":     "Gold",
    "CL=F":     "Crude Oil",
    "EURUSD=X": "EUR/USD",
    "THBUSD=X": "THB/USD",
    "BTC-USD":  "Bitcoin",
    "ETH-USD":  "Ethereum",
    "^GSPC":    "S&P 500",
    "^DJI":     "Dow Jones",
    "^IXIC":    "NASDAQ",
    "NVDA":     "Nvidia",
    "GOOGL":    "Google",
    "AMZN":     "Amazon",
    "NFLX":     "Netflix",
    "AMD":      "AMD",
    "ORCL":     "Oracle",
    "MSFT":     "Microsoft",
    "AAPL":     "Apple",
    "META":     "Meta",
    "TSLA":     "Tesla",
}

VALID_TABS = frozenset({"home", "predict", "watchlist", "news", "metrics", "corr"})

# Simple in-memory cache for live sentiment (refreshed by /api/live-sentiment)
_live_sentiment_cache: dict = {"data": [], "updated_at": None}

# Prediction/backtest is a real model fit (not a cheap query) — cache per
# ticker for the life of the process so switching tabs doesn't retrain.
_predict_cache: dict = {}
_sentiment_signal_cache: dict = {"computed": False, "result": None}
_case_studies_cache: dict = {"computed": False, "result": None}


def qdf(sql: str, **params) -> pd.DataFrame:
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def _get_prediction(ticker_symbol: str) -> dict | None:
    if ticker_symbol not in _predict_cache:
        _predict_cache[ticker_symbol] = signal_and_backtest(engine, ticker_symbol)
    return _predict_cache[ticker_symbol]


def _get_sentiment_signal() -> dict | None:
    if not _sentiment_signal_cache["computed"]:
        _sentiment_signal_cache["result"] = sentiment_signal(engine)
        _sentiment_signal_cache["computed"] = True
    return _sentiment_signal_cache["result"]


def _get_case_studies() -> list:
    if not _case_studies_cache["computed"]:
        _case_studies_cache["result"] = find_case_studies(engine)
        _case_studies_cache["computed"] = True
    return _case_studies_cache["result"]


@app.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    tab: str = 'home',
    ticker: str = 'AAPL',
    start_d: str = None,
    end_d: str = None,
    q: str = None,
):
    """
    Main dashboard view.
    - tab: 'home', 'predict', 'watchlist', 'news', 'metrics', or 'corr'
    - ticker: active ticker to show
    - start_d/end_d: date range for filtering
    - q: free-text search — matches a ticker/company name directly, or
      falls back to a news-title search on the News tab
    """
    # An unrecognised tab used to fall through the template's final {% else %}
    # and silently render Correlations, which meant a typo'd or stale URL
    # landed on the one view the committee singled out as not being a usable
    # result. Unknown tabs now go to Home instead.
    if tab not in VALID_TABS:
        tab = 'home'

    if not start_d:
        start_date = datetime.now() - timedelta(days=90)
    else:
        start_date = datetime.strptime(start_d, '%Y-%m-%d')

    if not end_d:
        end_date = datetime.now()
    else:
        end_date = datetime.strptime(end_d, '%Y-%m-%d')

    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    # --- counts ---
    counts = qdf("""
        SELECT
          (SELECT COUNT(*) FROM fact_price_daily WHERE d >= :sd AND d <= :ed) AS price_rows,
          (SELECT COUNT(*) FROM fact_news WHERE published_d >= :sd AND published_d <= :ed) AS news_rows,
          (SELECT COUNT(*) FROM fact_sentiment_daily WHERE d >= :sd AND d <= :ed) AS senti_rows;
    """, sd=start_date_str, ed=end_date_str).iloc[0].to_dict()

    # --- tickers for filter ---
    tickers_list = qdf("SELECT ticker FROM dim_asset ORDER BY ticker;")["ticker"].tolist()
    ticker_options = ["ALL"] + tickers_list

    if ticker not in ticker_options:
        ticker = "ALL"
    # Pagination logic
    page = int(request.query_params.get('page', 1))
    limit = 15
    offset = (max(1, page) - 1) * limit

    # --- search: exact ticker/company match jumps straight to that asset;
    # otherwise fall back to a news-title search on the News tab ---
    search_query = (q or "").strip()
    search_ticker_match = None
    if search_query:
        q_upper = search_query.upper()
        for t in tickers_list:
            if t.upper() == q_upper or TICKER_DISPLAY_NAMES.get(t, t).upper() == q_upper:
                search_ticker_match = t
                break
        if search_ticker_match:
            ticker = search_ticker_match
            tab = 'news'  # News tab actually filters by ticker; Home's feed doesn't
            page = 1
            offset = 0
            search_query = ""  # matched a ticker — no free-text search needed
        else:
            tab = 'news'
            ticker = 'ALL'
            page = 1
            offset = 0

    # --- news with pagination ---
    # First, get total count for this filter
    total_news_sql = """
    SELECT COUNT(*) as total
    FROM fact_news n
    JOIN dim_asset a ON a.asset_id=n.asset_id
    WHERE (:t = 'ALL' OR a.ticker = :t)
      AND n.published_d >= :sd AND n.published_d <= :ed
      AND (:q = '' OR n.title ILIKE :qlike)
    """
    total_news = qdf(total_news_sql, t=ticker, sd=start_date_str, ed=end_date_str, q=search_query, qlike=f"%{search_query}%").iloc[0]["total"]
    total_pages = (total_news + limit - 1) // limit

    news_sql = """
    SELECT a.ticker, n.published_at, n.sentiment_label, n.sentiment_score, n.title, n.url
    FROM fact_news n
    JOIN dim_asset a ON a.asset_id=n.asset_id
    WHERE (:t = 'ALL' OR a.ticker = :t)
      AND n.published_d >= :sd AND n.published_d <= :ed
      AND (:q = '' OR n.title ILIKE :qlike)
    ORDER BY n.published_at DESC
    LIMIT :limit OFFSET :offset;
    """
    news_df = qdf(news_sql, t=ticker, sd=start_date_str, ed=end_date_str, limit=limit, offset=offset, q=search_query, qlike=f"%{search_query}%")
    if not news_df.empty:
        news_df['date_str'] = news_df['published_at'].dt.strftime('%a %b %d')
        news_df['time_str'] = news_df['published_at'].dt.strftime('%I:%M%p').str.lower()
        news_df['published_at'] = news_df['published_at'].astype(str)
    news = news_df.to_dict(orient="records")

    # --- sentiment donut data — query ALL news count (not just 15-row page) ---
    senti_sql = """
    SELECT n.sentiment_label, COUNT(*) AS cnt
    FROM fact_news n
    JOIN dim_asset a ON a.asset_id = n.asset_id
    WHERE (:t = 'ALL' OR a.ticker = :t)
      AND n.published_d >= :sd AND n.published_d <= :ed
      AND n.sentiment_label IS NOT NULL
    GROUP BY n.sentiment_label;
    """
    senti_df = qdf(senti_sql, t=ticker, sd=start_date_str, ed=end_date_str)
    senti_dist = dict(zip(senti_df["sentiment_label"], senti_df["cnt"])) if not senti_df.empty else {}

    # --- daily metrics table ---
    metrics_sql = """
    SELECT
        v.ticker,
        v.d,
        p.open,
        v.close,
        v.pct_change,
        v.sentiment_index,
        v.news_count
    FROM vw_daily_asset_metrics v
    JOIN fact_price_daily p ON p.d = v.d
    JOIN dim_asset a ON a.asset_id = p.asset_id AND a.ticker = v.ticker
    WHERE (:t = 'ALL' OR v.ticker = :t)
      AND v.d >= :sd AND v.d <= :ed
    ORDER BY v.d DESC, v.ticker
    LIMIT 100;
    """
    raw_metrics = qdf(metrics_sql, t=ticker, sd=start_date_str, ed=end_date_str)

    # Format for display
    def _fmt_rows(df):
        import pandas as pd
        rows = []
        for _, r in df.iterrows():
            pct = r.get('pct_change')
            senti = r.get('sentiment_index')
            d_val = r.get('d')
            # Format date to string here so template can just use {{ r.d }}
            if hasattr(d_val, 'strftime'):
                d_str = d_val.strftime('%a %b %d')
            else:
                d_str = str(d_val)
            # pct_change is ALREADY in percent (e.g. -2.21 not -0.0221)
            pct_fmt = f"{float(pct):+.2f}%" if pct is not None and not pd.isna(pct) else 'N/A'
            senti_fmt = round(float(senti), 3) if senti is not None and not pd.isna(senti) else 'N/A'
            rows.append({
                'ticker': r.get('ticker'),
                'd': d_str,
                'open': round(float(r['open']), 2) if r.get('open') is not None and not pd.isna(r['open']) else None,
                'close': round(float(r['close']), 2) if r.get('close') is not None and not pd.isna(r['close']) else None,
                'return_1d': pct_fmt,
                'sentiment_index': senti_fmt,
                'news_count': int(r['news_count']) if r.get('news_count') is not None and not pd.isna(r['news_count']) else 0,
            })
        return rows

    metrics = _fmt_rows(raw_metrics) if not raw_metrics.empty else []

    # --- correlation (predictive analysis) ---
    # Step 1: Pull raw data for Python-side statistical computation
    corr_raw_sql = """
    WITH x AS (
      SELECT
        ticker, d, return_1d, sentiment_index,
        lag(sentiment_index, 1) OVER (PARTITION BY ticker ORDER BY d) AS sentiment_lag1,
        lag(sentiment_index, 2) OVER (PARTITION BY ticker ORDER BY d) AS sentiment_lag2
      FROM vw_daily_asset_metrics
      WHERE (:t = 'ALL' OR ticker = :t)
        AND d >= :sd AND d <= :ed
    )
    SELECT ticker, d, return_1d, sentiment_index, sentiment_lag1, sentiment_lag2
    FROM x
    ORDER BY ticker, d;
    """
    corr_raw_df = qdf(corr_raw_sql, t=ticker, sd=start_date_str, ed=end_date_str)

    def _pearson(a, b):
        """Return (r, p, n) or (None, None, 0) if insufficient data."""
        mask = a.notna() & b.notna()
        a2, b2 = a[mask].values, b[mask].values
        n = len(a2)
        if n < 5:
            return None, None, n
        try:
            r, p = scipy_stats.pearsonr(a2, b2)
            return round(float(r), 4), round(float(p), 4), n
        except Exception:
            return None, None, n

    def _stars(p):
        if p is None:
            return "ns"
        if p < 0.01:
            return "***"
        if p < 0.05:
            return "**"
        if p < 0.10:
            return "*"
        return "ns"

    def _hit_rate(ret, senti_lag):
        """Directional accuracy: % of times sign(return) == sign(senti_lag)."""
        mask = ret.notna() & senti_lag.notna() & (senti_lag != 0)
        r2, s2 = ret[mask], senti_lag[mask]
        n = len(r2)
        if n < 5:
            return None, n
        hits = ((r2 > 0) == (s2 > 0)).sum()
        return round(float(hits / n) * 100, 1), n

    corr = []
    rolling_corr_data = {}  # ticker -> [{d, rolling_r}]
    conditional_return_data = {}  # ticker -> {pos, neu, neg}

    for tkr, grp in corr_raw_df.groupby("ticker"):
        grp = grp.dropna(subset=["return_1d"]).copy()

        r_t, p_t, n_t = _pearson(grp["return_1d"], grp["sentiment_index"])
        r_l1, p_l1, n_l1 = _pearson(grp["return_1d"], grp["sentiment_lag1"])
        r_l2, p_l2, n_l2 = _pearson(grp["return_1d"], grp["sentiment_lag2"])
        hit_rate, hit_n = _hit_rate(grp["return_1d"], grp["sentiment_lag1"])
        ci_lo, ci_hi = _fisher_ci(r_l1, n_l1)

        corr.append({
            "ticker": tkr,
            "display_name": TICKER_DISPLAY_NAMES.get(tkr, tkr),
            # Correlation values
            "corr_t": r_t, "p_t": p_t, "sig_t": _stars(p_t), "n_t": n_t,
            "corr_lag1": r_l1, "p_lag1": p_l1, "sig_lag1": _stars(p_l1), "n_lag1": n_l1,
            "corr_lag2": r_l2, "p_lag2": p_l2, "sig_lag2": _stars(p_l2), "n_lag2": n_l2,
            # Fisher-z 95% CI on the lag-1 correlation (the one the hit-rate/prediction framing uses)
            "ci_lo": ci_lo, "ci_hi": ci_hi,
            # Flag rows whose lag-1 N is too thin to trust with the same visual weight as a well-powered one
            "n_flag": "low" if (n_l1 or 0) < 30 else "ok",
            # Prediction metrics
            "hit_rate": hit_rate,
            "hit_n": hit_n,
            # Best lag (highest abs corr that is significant)
            "best_lag": (
                "Lag 1" if abs(r_l1 or 0) >= abs(r_l2 or 0) else "Lag 2"
            ) if (r_l1 or r_l2) else "N/A",
        })

        # --- Rolling 30-day correlation (Lag 1) ---
        roll_mask = grp["return_1d"].notna() & grp["sentiment_lag1"].notna()
        roll_grp = grp[roll_mask][["d", "return_1d", "sentiment_lag1"]].copy()
        if len(roll_grp) >= 30:
            roll_r = (
                roll_grp[["return_1d", "sentiment_lag1"]]
                .rolling(30)
                .corr()
                .unstack()["return_1d"]["sentiment_lag1"]
                .round(4)
            )
            rolling_corr_data[tkr] = [
                {"d": str(d), "r": float(r) if pd.notna(r) else None}
                for d, r in zip(roll_grp["d"], roll_r)
                if pd.notna(r)
            ]

        # --- Conditional Returns by Sentiment Group ---
        cond_mask = grp["sentiment_lag1"].notna() & grp["return_1d"].notna()
        cond_df = grp[cond_mask].copy()
        if not cond_df.empty:
            cond_df["senti_group"] = pd.cut(
                cond_df["sentiment_lag1"],
                bins=[-float("inf"), -0.15, 0.15, float("inf")],
                labels=["Negative", "Neutral", "Positive"]
            )
            cond_means = cond_df.groupby("senti_group", observed=True)["return_1d"].agg(
                ["mean", "count"]
            ).round(6)
            conditional_return_data[tkr] = {
                grp_name: {
                    "avg_return": round(float(row["mean"]) * 100, 3),
                    "count": int(row["count"])
                }
                for grp_name, row in cond_means.iterrows()
            }

    # Benjamini-Hochberg FDR correction on lag-1 p-values — testing every ticker
    # independently means ~1-2 "significant" hits are expected by chance alone
    # out of 30; this flags which ones actually survive correcting for that.
    p_idx = [i for i, c in enumerate(corr) if c["p_lag1"] is not None]
    for c in corr:
        c["q_lag1"] = None
        c["sig_lag1_fdr"] = None
    if p_idx:
        pvals = np.array([corr[i]["p_lag1"] for i in p_idx])
        qvals = scipy_stats.false_discovery_control(pvals, method="bh")
        for i, q in zip(p_idx, qvals):
            corr[i]["q_lag1"] = round(float(q), 4)
            corr[i]["sig_lag1_fdr"] = _stars(float(q))

    # Sort by significance of lag-1 correlation
    corr.sort(key=lambda x: abs(x["corr_lag1"] or 0), reverse=True)

    # Pooled panel estimate (ticker fixed effects) — one adequately-powered
    # number instead of 30 individually thin-N per-ticker tests.
    pooled = _pooled_fe_ols(corr_raw_df)

    # Summary stats for the cards at top of tab
    corr_summary = {}
    if corr:
        best_ticker = corr[0]["ticker"]
        corr_summary = {
            "best_ticker": best_ticker,
            "best_r": corr[0]["corr_lag1"],
            "best_sig": corr[0]["sig_lag1"],
            "avg_hit_rate": round(
                sum(c["hit_rate"] for c in corr if c["hit_rate"] is not None)
                / max(1, sum(1 for c in corr if c["hit_rate"] is not None)),
                1
            ),
        }
    corr_summary["pooled"] = pooled

    # --- source credibility ---
    sources_sql = """
    SELECT s.source_name, MAX(s.credibility_score) as credibility_score
    FROM fact_news n
    JOIN dim_source s ON n.source_id = s.source_id
    WHERE n.published_d >= :sd AND n.published_d <= :ed
    GROUP BY s.source_name
    ORDER BY credibility_score DESC, s.source_name ASC
    LIMIT 10;
    """
    sources_rating = qdf(sources_sql, sd=start_date_str, ed=end_date_str).to_dict(orient="records")

    # --- sparkline data ---
    # fact_price_daily does not have 'ticker', we must join with dim_asset
    spark_sql = """
    SELECT a.ticker, p.d, p.open, p.high, p.low, p.close
    FROM fact_price_daily p
    JOIN dim_asset a ON p.asset_id = a.asset_id
    WHERE p.d >= (CURRENT_DATE - INTERVAL '30 days')
    ORDER BY a.ticker, p.d ASC;
    """
    spark_df = qdf(spark_sql)
    if not spark_df.empty:
        spark_df = spark_df.dropna(subset=["close"])
        spark_df['d'] = spark_df['d'].astype(str)
    spark_data = {}
    for t in spark_df['ticker'].unique():
        spark_data[t] = spark_df[spark_df['ticker'] == t].to_dict(orient="records")
    
    # Correcting common SQL errors in ticker views if any (just in case they were broken)
    # The subagent noted 500 errors on specific tickers too.

    # --- ticker strip (top-of-page bar): each asset's own most recent priced day ---
    # (not a single global MAX(d) — on weekends/holidays most assets have no close
    # for "today" while e.g. crypto does, which would blank out the whole strip)
    live_sql = """
    SELECT DISTINCT ON (ticker) ticker, close, return_1d, sentiment_index, news_count, d
    FROM vw_daily_asset_metrics
    WHERE close IS NOT NULL
    ORDER BY ticker, d DESC;
    """
    live_df = qdf(live_sql)
    live_df = live_df.astype(object).where(live_df.notna(), None) if not live_df.empty else live_df
    live_sentiment_data = live_df.to_dict(orient="records") if not live_df.empty else []
    for row in live_sentiment_data:
        row["display_name"] = TICKER_DISPLAY_NAMES.get(row["ticker"], row["ticker"])

    # --- homepage-only data: news feed + trending/gainers/losers rails ---
    home_news = []
    trending = []
    gainers = []
    losers = []
    if tab == 'home':
        home_news_sql = """
        SELECT a.ticker, n.published_at, n.sentiment_label, n.sentiment_score, n.title, n.url, s.source_name
        FROM fact_news n
        JOIN dim_asset a ON a.asset_id = n.asset_id
        LEFT JOIN dim_source s ON s.source_id = n.source_id
        ORDER BY n.published_at DESC
        LIMIT 13;
        """
        home_news_df = qdf(home_news_sql)
        if not home_news_df.empty:
            home_news_df['display_name'] = home_news_df['ticker'].map(lambda t: TICKER_DISPLAY_NAMES.get(t, t))
            home_news_df['date_str'] = home_news_df['published_at'].dt.strftime('%a %b %d')
            home_news_df['time_str'] = home_news_df['published_at'].dt.strftime('%I:%M%p').str.lower()
            home_news = home_news_df.to_dict(orient="records")

        ranked_by_news = sorted(live_sentiment_data, key=lambda r: r.get("news_count") or 0, reverse=True)
        trending = ranked_by_news[:6]

        with_return = [r for r in live_sentiment_data if r.get("return_1d") is not None]
        gainers = sorted(with_return, key=lambda r: r["return_1d"], reverse=True)[:5]
        losers = sorted(with_return, key=lambda r: r["return_1d"])[:5]

    # --- prediction/backtest (per-ticker signal, only computed when viewed) ---
    predict_result = None
    predict_ticker = ticker
    sentiment_result = None
    sentiment_ticker_result = None
    case_studies = []
    if tab == 'predict':
        predict_ticker = ticker if ticker != 'ALL' else (tickers_list[0] if tickers_list else 'AAPL')
        predict_result = _get_prediction(predict_ticker)
        sentiment_result = _get_sentiment_signal()
        if sentiment_result and predict_ticker in sentiment_result["per_ticker"]:
            sentiment_ticker_result = sentiment_result["per_ticker"][predict_ticker]
        case_studies = _get_case_studies()

    # --- watchlist: check each watched ticker's signal for a flip since last view ---
    watchlist_tickers = []
    watchlist_rows = []
    if tab == 'watchlist':
        watchlist_tickers = list_watchlist(engine)
        for t in watchlist_tickers:
            pred = _get_prediction(t)
            if pred is None:
                watchlist_rows.append({"ticker": t, "insufficient": True})
                continue
            checked = check_signal_change(engine, t, pred)
            checked["ticker"] = t
            checked["display_name"] = TICKER_DISPLAY_NAMES.get(t, t)
            watchlist_rows.append(checked)

    tpl = templates.get_template("dashboard.html")
    html = tpl.render(
        tab=tab,
        ticker=ticker,
        predict_ticker=predict_ticker,
        predict_result=predict_result,
        sentiment_result=sentiment_result,
        sentiment_ticker_result=sentiment_ticker_result,
        case_studies=case_studies,
        watchlist_rows=watchlist_rows,
        watchlist_tickers=watchlist_tickers,
        start_date=start_date_str,
        end_date=end_date_str,
        ticker_options=ticker_options,
        ticker_display_names=TICKER_DISPLAY_NAMES,
        counts=counts,
        news=news,
        current_page=page,
        total_pages=total_pages,
        total_news=int(total_news),
        metrics=metrics,
        corr=corr,
        corr_summary=corr_summary,
        rolling_corr_data=rolling_corr_data,
        conditional_return_data=conditional_return_data,
        senti_dist=senti_dist,
        sources_rating=sources_rating,
        spark_data=spark_data,
        live_sentiment_data=live_sentiment_data,
        home_news=home_news,
        trending=trending,
        gainers=gainers,
        losers=losers,
        asset_v=STATIC_VERSION,
        search_query=search_query,
        now=datetime.now(timezone.utc),
        timedelta=timedelta
    )
    return HTMLResponse(html)


@app.post("/watchlist/add")
def watchlist_add(ticker: str = Form(...)):
    add_to_watchlist(engine, ticker)
    return RedirectResponse(url="/?tab=watchlist", status_code=303)


@app.post("/watchlist/remove")
def watchlist_remove(ticker: str = Form(...)):
    remove_from_watchlist(engine, ticker)
    return RedirectResponse(url="/?tab=watchlist", status_code=303)


@app.get("/api/live-sentiment")
def api_live_sentiment():
    """
    Return latest sentiment snapshot per ticker.
    Used by dashboard auto-refresh (every 60s) and live ticker bar.
    """
    live_sql = """
    SELECT ticker, sentiment_index, news_count, d
    FROM vw_daily_asset_metrics
    WHERE d = (SELECT MAX(d) FROM vw_daily_asset_metrics)
    ORDER BY ticker;
    """
    try:
        df = qdf(live_sql)
        if df.empty:
            return JSONResponse({"updated_at": None, "items": []})
        records = []
        for _, row in df.iterrows():
            records.append({
                "ticker": row["ticker"],
                "display_name": TICKER_DISPLAY_NAMES.get(row["ticker"], row["ticker"]),
                "sentiment_index": float(row["sentiment_index"]) if pd.notna(row["sentiment_index"]) else None,
                "news_count": int(row["news_count"]) if pd.notna(row["news_count"]) else 0,
                "date": str(row["d"]),
            })
        return JSONResponse({
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "items": records
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/latest-price/{ticker_symbol}")
def api_latest_price(ticker_symbol: str):
    """
    Return the most recent price for a ticker from the DB (updated daily by ETL).
    Optionally enriched with quasi-realtime data from yfinance when available.
    """
    sql = """
    SELECT p.close, p.d, a.ticker
    FROM fact_price_daily p
    JOIN dim_asset a ON a.asset_id = p.asset_id
    WHERE a.ticker = :t
    ORDER BY p.d DESC
    LIMIT 1;
    """
    try:
        df = qdf(sql, t=ticker_symbol)
        if df.empty:
            return JSONResponse({"error": f"No price data for {ticker_symbol}"}, status_code=404)
        row = df.iloc[0]
        result = {
            "ticker": ticker_symbol,
            "display_name": TICKER_DISPLAY_NAMES.get(ticker_symbol, ticker_symbol),
            "close": float(row["close"]) if pd.notna(row["close"]) else None,
            "date": str(row["d"]),
            "source": "db_eod",
        }
        # Try yfinance quasi-realtime (15-min delayed) — fail gracefully
        try:
            import yfinance as yf
            info = yf.Ticker(ticker_symbol).fast_info
            last_price = getattr(info, "last_price", None)
            if last_price and last_price > 0:
                result["live_price"] = round(float(last_price), 4)
                result["source"] = "yfinance_live"
        except Exception:
            pass  # Fall back to DB price
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


def _infer_asset_class(ticker: str) -> str:
    """Derive asset class from ticker pattern since dim_asset.asset_class is NULL."""
    t = ticker.upper()
    if t in ('BTC-USD', 'ETH-USD', 'BNB-USD', 'SOL-USD', 'XRP-USD'):
        return 'Crypto'
    if t in ('GC=F', 'CL=F', 'SI=F', 'NG=F', 'NQ=F', 'ES=F', 'ZC=F', 'ZW=F'):
        return 'Futures'
    if '=X' in t or t in ('XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY'):
        return 'Forex'
    if t in ('SPY', 'QQQ', 'DIA', 'IWM', 'GLD', 'SLV', 'VTI'):
        return 'Funds'
    if '^' in t:
        return 'Indices'
    return 'Stocks'


@app.get("/daily", response_class=HTMLResponse)
def daily_summary(
    request: Request,
    date_d: str = None,
    asset_class: str = 'All',
    ticker: str = 'ALL',
    lang: str = 'en',
):
    """Daily news summary page grouped by date and asset."""
    if not date_d:
        date_d = datetime.now().strftime('%Y-%m-%d')

    tickers_list = qdf("SELECT ticker FROM dim_asset ORDER BY ticker;")["ticker"].tolist()

    # Get date range that has news data
    date_range_df = qdf("""
        SELECT MIN(published_d::date) AS min_d, MAX(published_d::date) AS max_d
        FROM fact_news;
    """)
    min_date = date_range_df['min_d'].iloc[0].strftime('%Y-%m-%d') if not date_range_df.empty else '2020-01-01'
    max_date = date_range_df['max_d'].iloc[0].strftime('%Y-%m-%d') if not date_range_df.empty else datetime.now().strftime('%Y-%m-%d')

    # Clamp date to available range
    if date_d < min_date:
        date_d = max_date
    if date_d > max_date:
        date_d = max_date

    # Get news for chosen date
    news_df = qdf("""
        SELECT
            n.published_at,
            n.title,
            n.url,
            n.sentiment_score,
            n.sentiment_label,
            a.ticker
        FROM fact_news n
        JOIN dim_asset a ON a.asset_id = n.asset_id
        WHERE n.published_d = :d
        ORDER BY a.ticker, n.published_at DESC;
    """, d=date_d)

    if not news_df.empty:
        news_df['asset_class'] = news_df['ticker'].map(lambda t: _infer_asset_class(t))
        news_df['published_at_str'] = pd.to_datetime(news_df['published_at']).dt.strftime('%H:%M')
        news_df['sentiment_score'] = news_df['sentiment_score'].fillna(0.0)

    # Filter by asset class
    if asset_class != 'All' and not news_df.empty:
        news_df = news_df[news_df['asset_class'] == asset_class]

    # Filter by ticker
    if ticker != 'ALL' and not news_df.empty:
        news_df = news_df[news_df['ticker'] == ticker]

    # Available filter classes for the selected date
    all_news_df = qdf("""
        SELECT DISTINCT a.ticker
        FROM fact_news n
        JOIN dim_asset a ON a.asset_id = n.asset_id
        WHERE n.published_d = :d;
    """, d=date_d)
    available_classes = ['All']
    if not all_news_df.empty:
        classes_on_date = sorted(set(all_news_df['ticker'].map(lambda t: _infer_asset_class(t))))
        available_classes += classes_on_date

    # Group news by ticker into summaries
    summaries = []
    if not news_df.empty:
        for tkr, grp in news_df.groupby('ticker', sort=True):
            avg_score = grp['sentiment_score'].mean()
            pos = (grp['sentiment_score'] > 0.1).sum()
            neg = (grp['sentiment_score'] < -0.1).sum()
            neu = len(grp) - pos - neg
            sentiment_label = 'POSITIVE' if avg_score > 0.1 else ('NEGATIVE' if avg_score < -0.1 else 'NEUTRAL')

            headlines = []
            for _, row in grp.iterrows():
                title_en = row['title'] or ''
                title_display = translate_to_thai(title_en) if lang == 'th' else title_en
                headlines.append({
                    'time': row['published_at_str'],
                    'title': title_display,
                    'title_en': title_en,
                    'url': row['url'],
                    'score': round(float(row['sentiment_score']), 3),
                    'label': row['sentiment_label'] or 'NEUTRAL'
                })

            summaries.append({
                'ticker': tkr,
                'asset_class': _infer_asset_class(tkr),
                'count': len(grp),
                'avg_score': round(float(avg_score), 3),
                'sentiment_label': sentiment_label,
                'pos': int(pos), 'neg': int(neg), 'neu': int(neu),
                'headlines': headlines
            })

    tmpl = templates.get_template('daily_summary.html')
    html = tmpl.render(
        asset_v=STATIC_VERSION,
        date_d=date_d,
        min_date=min_date,
        max_date=max_date,
        available_classes=available_classes,
        asset_class=asset_class,
        ticker=ticker,
        ticker_options=['ALL'] + tickers_list,
        ticker_display_names=TICKER_DISPLAY_NAMES,
        lang=lang,
        summaries=summaries,
        now=datetime.now(timezone.utc),
    )
    return HTMLResponse(html)



