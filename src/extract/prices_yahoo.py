from __future__ import annotations
from datetime import date, timedelta
import pandas as pd
import yfinance as yf

def fetch_daily_prices_yahoo(tickers: list[str], end_d: date, lookback_days: int = 14) -> pd.DataFrame:
    start_d = end_d - timedelta(days=lookback_days)
    df = yf.download(
        tickers=tickers,
        start=start_d.isoformat(),
        end=(end_d + timedelta(days=1)).isoformat(),
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        threads=True,
        progress=False,
    )

    rows = []
    if isinstance(df.columns, pd.MultiIndex):
        for t in tickers:
            if t not in df.columns.get_level_values(0):
                continue
            sub = df[t].copy()
            sub["ticker"] = t
            sub = sub.reset_index().rename(columns={"Date": "d"})
            rows.append(sub)
        out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    else:
        out = df.copy().reset_index().rename(columns={"Date": "d"})
        out["ticker"] = tickers[0] if tickers else None

    if out.empty:
        return out

    out = out.rename(columns={
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Adj Close": "adj_close",
        "Volume": "volume",
    })
    out["d"] = pd.to_datetime(out["d"]).dt.date
    out = out[["ticker", "d", "open", "high", "low", "close", "adj_close", "volume"]]
    return out.sort_values(["ticker", "d"])
