from __future__ import annotations
from datetime import date, timedelta
import io
import pandas as pd
import requests

def _to_stooq_symbol(ticker: str) -> str:
    t = ticker.strip().upper()
    if "." in t:
        return t
    # Mapping for common non-stock assets
    if t == "GC=F": return "XAUUSD"
    if t == "BTC-USD": return "BTCUSD"
    if t == "EURUSD=X": return "EURUSD"
    # Default to US stocks
    return f"{t}.US"

def fetch_daily_prices_stooq(tickers: list[str], end_d: date, lookback_days: int = 60) -> pd.DataFrame:
    rows = []
    start_d = end_d - timedelta(days=lookback_days)

    for t in tickers:
        sym = _to_stooq_symbol(t)
        url = f"https://stooq.com/q/d/l/?s={sym.lower()}&i=d"
        try:
            r = requests.get(url, timeout=20)
        except requests.exceptions.ConnectionError as e:
            print(f"[price][stooq] connection error for {sym}: {e}")
            continue
        except requests.exceptions.Timeout:
            print(f"[price][stooq] timeout for {sym}")
            continue
        # Handle cases where Stooq returns no data or an error page
        if r.status_code != 200 or not r.text.strip() or "Page not found" in r.text:
            print(f"[price][stooq] no data for {sym} (url={url})")
            continue

        if "Get your apikey" in r.text:
            print(f"[price][stooq] API key required by Stooq for {sym}. Please configure a Stooq API key or rely on Yahoo Finance.")
            continue

        try:
            df = pd.read_csv(io.StringIO(r.text))
        except Exception as e:
            print(f"[price][stooq] failed to parse CSV for {sym}: {e}")
            continue

        if df.empty:
            continue

        # Map existing columns and fill missing ones
        col_map = {
            "Date": "d",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        
        if "volume" not in df.columns:
            df["volume"] = 0
            
        df["d"] = pd.to_datetime(df["d"]).dt.date
        df = df[(df["d"] >= start_d) & (df["d"] <= end_d)].copy()
        if df.empty:
            continue

        df["ticker"] = t.upper()
        df["adj_close"] = None
        
        # Ensure all required columns exist
        final_cols = ["ticker", "d", "open", "high", "low", "close", "adj_close", "volume"]
        rows.append(df[final_cols])

    return pd.concat(rows, ignore_index=True).sort_values(["ticker", "d"]) if rows else pd.DataFrame()
