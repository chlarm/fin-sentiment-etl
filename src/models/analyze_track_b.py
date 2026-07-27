#!/usr/bin/env python3
"""
Track B (medium/long horizon, 1 quarter - 1 year): does a stock's fundamentals
(growth, margins, leverage, valuation) at the time its earnings were announced
correlate with its subsequent return?

Deliberately NOT a black-box classifier: with only ~100 (ticker, quarter) rows
total, any ML model would be fitting noise, not signal — see the small n
warnings printed for every result below. Correlation + regression with
explicit p-values and sample sizes is the honest way to look at a panel this
small; a classifier's 70% "accuracy" on n=20 would be meaningless and
misleading in a way a plain r/p-value table is not.

Usage:
    python -m src.models.analyze_track_b
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from sklearn.linear_model import LinearRegression

from src.config import Settings
from src.common.db import get_engine
from src.models.dataset_fundamentals import FUNDAMENTAL_FEATURES, build_fundamentals_panel

warnings.filterwarnings("ignore")

HORIZONS = [63, 126, 252]  # ~1 quarter, ~6 months, ~1 year (trading days)
MIN_N_FOR_STATS = 15


def _sig_stars(p: float) -> str:
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return "ns"


def _correlation_table(panel: pd.DataFrame, horizon: int):
    target_col = f"fwd_ret_{horizon}d"
    print(f"\n--- horizon = {horizon}d (~{horizon/21:.1f} months) ---")

    for feat in FUNDAMENTAL_FEATURES:
        sub = panel[[feat, target_col]].dropna()
        n = len(sub)
        if n < MIN_N_FOR_STATS:
            print(f"  {feat:<20} n={n:>3}  (too small to test — need >= {MIN_N_FOR_STATS})")
            continue
        r, p = scipy_stats.pearsonr(sub[feat], sub[target_col])
        print(f"  {feat:<20} n={n:>3}  r={r:+.3f}  p={p:.3f}  {_sig_stars(p)}")

    # multi-feature linear regression, only if enough complete rows exist
    full = panel[FUNDAMENTAL_FEATURES + [target_col]].dropna()
    if len(full) >= MIN_N_FOR_STATS + len(FUNDAMENTAL_FEATURES):
        X, y = full[FUNDAMENTAL_FEATURES], full[target_col]
        model = LinearRegression().fit(X, y)
        r2 = model.score(X, y)
        print(f"  [multi-feature OLS] n={len(full)}  R^2={r2:.3f}  (in-sample fit, not out-of-sample — indicative only)")
        for feat, coef in zip(FUNDAMENTAL_FEATURES, model.coef_):
            print(f"      {feat:<20} coef={coef:+.4f}")
    else:
        print(f"  [multi-feature OLS] skipped — only {len(full)} rows with every feature present "
              f"(need >= {MIN_N_FOR_STATS + len(FUNDAMENTAL_FEATURES)})")


def main() -> None:
    settings = Settings()
    engine = get_engine(settings)

    # only tickers that actually have fundamentals (stocks, not indices/forex/crypto/commodities)
    from sqlalchemy import text
    with engine.connect() as conn:
        stock_tickers = pd.read_sql(
            text("""
                SELECT DISTINCT a.ticker FROM fact_fundamentals_quarterly f
                JOIN dim_asset a ON a.asset_id = f.asset_id
            """), conn
        )["ticker"].tolist()

    print(f"Building fundamentals panel for {len(stock_tickers)} stocks: {stock_tickers}")
    panel = build_fundamentals_panel(engine, stock_tickers, HORIZONS)

    if panel.empty:
        print("No usable (fundamentals + price) rows found.")
        return

    print(f"Panel: {len(panel)} (ticker, quarter) rows, "
          f"{panel['fiscal_period_end'].min()} -> {panel['fiscal_period_end'].max()}")
    print(f"NOTE: this is a cross-sectional panel across {panel['ticker'].nunique()} stocks, "
          f"NOT a long per-ticker time series — treat every result below as exploratory.")

    for h in HORIZONS:
        _correlation_table(panel, h)


if __name__ == "__main__":
    main()
