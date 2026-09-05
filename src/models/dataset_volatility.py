"""
Dataset for forecasting realised volatility rather than return direction.

Why this target and not direction. Measured across all 30 assets over
2006-2026, the lag-1 autocorrelation of daily returns averages -0.053 — no
usable signal, which is what Track A's null result reflects. Over the same
data, the autocorrelation of 20-day realised volatility is +0.901 at a 5-day
lag and +0.504 at 20 days, and the weakest asset still scores +0.821 at 5
days. Volatility clusters; direction does not. Asking the model for the
predictable quantity is not a lowered bar, it is the difference between a
question the data can answer and one it cannot.

The honest test is NOT "is R^2 high" — predicting volatility from volatility
is trivially high. It is whether the model beats the persistence forecast
("next period's volatility equals the current reading"), which is free, needs
no model, and is what any practitioner would use as a default. That
comparison is built into the target below by keeping `persistence` alongside
the target so the evaluator can score both on identical rows.

Targets are log volatility. Realised volatility is positive and right-skewed;
in logs the errors are closer to symmetric, a proportional miss counts the
same whether the level is high or low, and the model cannot predict a
negative volatility.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

# Realised-volatility features. Deliberately all derived from price: this
# model does not use sentiment, and Track A already established why.
VOLATILITY_FEATURES = [
    "log_vol_5",        # short-window realised vol
    "log_vol_20",       # the persistence anchor
    "log_vol_60",       # slower regime level
    "vol_ratio_5_20",   # is short-term vol above or below its own trend
    "vol_ratio_20_60",
    "abs_ret_1",        # yesterday's absolute move
    "abs_ret_5_mean",
    "range_20",         # high-low range, an efficient vol estimator
    "neg_ret_share_20", # downside share — vol rises more after falls
    # The two market-wide features below were measured and add nothing:
    # dropping both moves the 21-day test R^2 from 0.739 to 0.740. They are
    # kept because they cost nothing at prediction time and are the natural
    # place to look when extending this to crisis periods, but nobody should
    # cite them as contributing. Measured 2026-09-05.
    "log_market_vol_20",  # cross-sectional: the whole market's volatility
    "rel_vol_to_market",  # this asset's vol relative to the market's
]

MIN_VOL = 1e-6  # floor before taking logs, for a stretch of identical closes


def _realised_vol(returns: pd.Series, window: int) -> pd.Series:
    return returns.rolling(window).std()


def build_volatility_dataset(
    engine: Engine, tickers: list[str], horizons: list[int]
) -> pd.DataFrame:
    """One row per (ticker, day) with volatility features and forward
    realised-volatility targets.

    For each horizon h, three columns are produced:
      target_logvol_{h}d   log realised vol over the NEXT h trading days
      persistence_{h}d     log of today's 20-day vol — the free forecast
      target_vol_{h}d      the un-logged target, for reporting in real units

    Every feature uses only information available on day d. The forward
    window starts at d+1, so no row can see its own target.
    """
    with engine.connect() as conn:
        df = pd.read_sql(
            text("""
                SELECT a.ticker, p.d, p.close, p.high, p.low, p.return_1d
                FROM fact_price_daily p
                JOIN dim_asset a ON a.asset_id = p.asset_id
                WHERE a.ticker = ANY(:tickers) AND p.close IS NOT NULL
                ORDER BY a.ticker, p.d
            """),
            conn, params={"tickers": tickers},
        )
    if df.empty:
        return df

    for c in ("close", "high", "low", "return_1d"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.sort_values(["ticker", "d"]).copy()

    # --- market-wide volatility, built before per-ticker features so every
    # asset sees the same market state on a given day. This is the equivalent
    # of a VIX reading and is why an asset can be told "the whole market is
    # calm" rather than only knowing its own history.
    daily_mkt = (
        df.groupby("d")["return_1d"].mean().rename("market_ret").to_frame()
    )
    daily_mkt["market_vol_20"] = daily_mkt["market_ret"].rolling(20).std()
    df = df.merge(daily_mkt[["market_vol_20"]], left_on="d", right_index=True, how="left")

    out = []
    for ticker, g in df.groupby("ticker", sort=False):
        g = g.sort_values("d").copy()
        r = g["return_1d"]

        v5, v20, v60 = (_realised_vol(r, w) for w in (5, 20, 60))
        g["log_vol_5"] = np.log(v5.clip(lower=MIN_VOL))
        g["log_vol_20"] = np.log(v20.clip(lower=MIN_VOL))
        g["log_vol_60"] = np.log(v60.clip(lower=MIN_VOL))
        g["vol_ratio_5_20"] = v5 / v20
        g["vol_ratio_20_60"] = v20 / v60

        g["abs_ret_1"] = r.abs()
        g["abs_ret_5_mean"] = r.abs().rolling(5).mean()
        # Parkinson-style range: uses the day's high and low, so it extracts
        # more information from one day than close-to-close alone.
        with np.errstate(divide="ignore", invalid="ignore"):
            hl = np.log(g["high"] / g["low"])
        g["range_20"] = pd.Series(hl, index=g.index).rolling(20).mean()
        g["neg_ret_share_20"] = (r < 0).rolling(20).mean()

        g["log_market_vol_20"] = np.log(g["market_vol_20"].clip(lower=MIN_VOL))
        g["rel_vol_to_market"] = v20 / g["market_vol_20"]

        for h in horizons:
            # Forward window strictly after d: shift(-1) first, then roll
            # forward h days. Getting this wrong is how a volatility model
            # accidentally reads the present.
            fwd = r.shift(-1).rolling(h).std().shift(-(h - 1))
            g[f"target_vol_{h}d"] = fwd
            g[f"target_logvol_{h}d"] = np.log(fwd.clip(lower=MIN_VOL))
            g[f"persistence_{h}d"] = g["log_vol_20"]

        out.append(g)

    res = pd.concat(out, ignore_index=True)
    res[VOLATILITY_FEATURES] = res[VOLATILITY_FEATURES].replace([np.inf, -np.inf], np.nan)
    return res
