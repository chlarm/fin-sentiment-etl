from __future__ import annotations
from datetime import date, timedelta
import io
import pandas as pd
import requests

def _to_stooq_symbol(ticker: str) -> str:
    t = ticker.strip().upper()
    if "." in t:
        return t
    return f"{t}.US"

def fetch_daily_prices_stooq(tickers: list[str], end_d: date, lookback_days: int = 60) -> pd.DataFrame:
    rows = []
    start_d = end_d - timedelta(days=lookback_days)

    for t in tickers:
        sym = _to_stooq_symbol(t)
        url = f"https://stooq.com/q/d/l/?s={sym.lower()}&i=d"
        r = requests.get(url, timeout=20)
        r.raise_for_status()

        df = pd.read_csv(io.StringIO(r.text))
        if df.empty:
            continue

        df = df.rename(columns={
            "Date": "d",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })
        df["d"] = pd.to_datetime(df["d"]).dt.date
        df = df[(df["d"] >= start_d) & (df["d"] <= end_d)].copy()
        if df.empty:
            continue

        df["ticker"] = t.upper()
        df["adj_close"] = None
        rows.append(df[["ticker", "d", "open", "high", "low", "close", "adj_close", "volume"]])

    return pd.concat(rows, ignore_index=True).sort_values(["ticker", "d"]) if rows else pd.DataFrame()
