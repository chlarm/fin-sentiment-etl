#!/usr/bin/env python3
"""
Volatility forecasting — the counterpart to Track A's null result.

Track A asked whether the direction of the next move is predictable and found
that it is not. This asks whether the SIZE of the next moves is predictable,
which the same data says is a different question: lag-1 autocorrelation of
returns averages -0.053 across the 30 assets, while 20-day realised volatility
autocorrelates at +0.901 over a 5-day lag.

The number that matters here is not R^2. Predicting volatility from volatility
scores well by construction, and a headline R^2 of 0.8 would say nothing. The
test is whether the model beats **persistence** — the free forecast that next
period's volatility equals the current 20-day reading. A practitioner gets
persistence for nothing, so anything that fails to beat it has no value, no
matter how high its R^2 looks in isolation.

Reported for every horizon:
  train R^2      in-sample, shown only to expose overfitting against test R^2
  test R^2       chronological hold-out, log space
  persistence    the same metric for the free forecast, on identical rows
  skill          1 - MSE(model)/MSE(persistence); >0 means it adds something
  MAE ratio      median |error| in real volatility units, model vs persistence

Usage:
    python -m src.models.forecast_volatility
"""
from __future__ import annotations
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import r2_score
from sqlalchemy import text

from src.common.db import get_engine
from src.config import Settings
from src.models.dataset_volatility import VOLATILITY_FEATURES, build_volatility_dataset

warnings.filterwarnings("ignore")

HORIZONS = [5, 21]
TEST_FRACTION = 0.25
WF_FOLDS = 5
MIN_ROWS = 500


def _chronological_split(df: pd.DataFrame, test_fraction: float):
    dates = sorted(df["d"].unique())
    cutoff = dates[int(len(dates) * (1 - test_fraction))]
    return df[df["d"] < cutoff], df[df["d"] >= cutoff]


def _fit_predict(train: pd.DataFrame, test: pd.DataFrame, target: str):
    model = HistGradientBoostingRegressor(
        max_iter=300, max_depth=5, learning_rate=0.05, random_state=42
    )
    model.fit(train[VOLATILITY_FEATURES], train[target])
    return model, model.predict(test[VOLATILITY_FEATURES])


def _score(y_true, y_model, y_persist) -> dict:
    """Model and persistence scored on exactly the same rows."""
    mse_m = float(np.mean((y_true - y_model) ** 2))
    mse_p = float(np.mean((y_true - y_persist) ** 2))
    # Errors in real volatility units (annualised %) rather than logs, since
    # a log-space R^2 is hard to interpret as "how wrong is it in practice".
    ann = np.sqrt(252) * 100
    mae_m = float(np.median(np.abs(np.exp(y_true) - np.exp(y_model))) * ann)
    mae_p = float(np.median(np.abs(np.exp(y_true) - np.exp(y_persist))) * ann)
    return {
        "test_r2": r2_score(y_true, y_model),
        "persist_r2": r2_score(y_true, y_persist),
        "skill": 1 - mse_m / mse_p if mse_p > 0 else float("nan"),
        "mae_model_annpct": mae_m,
        "mae_persist_annpct": mae_p,
    }


def _walk_forward(df: pd.DataFrame, target: str, persist_col: str, n_folds=WF_FOLDS):
    dates = sorted(df["d"].unique())
    n = len(dates)
    seg = n // (n_folds + 1)
    results = []
    for i in range(1, n_folds + 1):
        train_end = dates[i * seg - 1]
        t_start, t_end = dates[i * seg], dates[min((i + 1) * seg, n) - 1]
        tr = df[df["d"] <= train_end]
        te = df[(df["d"] >= t_start) & (df["d"] <= t_end)]
        if len(tr) < MIN_ROWS or len(te) < 100:
            continue
        _, pred = _fit_predict(tr, te, target)
        s = _score(te[target].to_numpy(), pred, te[persist_col].to_numpy())
        s.update({"test_start": str(t_start), "test_end": str(t_end), "n_test": len(te)})
        results.append(s)
    return results


def main() -> None:
    settings = Settings()
    engine = get_engine(settings)
    with engine.connect() as conn:
        tickers = pd.read_sql(text("SELECT ticker FROM dim_asset ORDER BY ticker"), conn)["ticker"].tolist()

    print(f"Building volatility dataset for {len(tickers)} assets...")
    panel = build_volatility_dataset(engine, tickers, HORIZONS)
    if panel.empty:
        print("No data."); return
    print(f"Panel: {len(panel):,} rows, {panel['ticker'].nunique()} assets, "
          f"{panel['d'].min()} -> {panel['d'].max()}")

    for h in HORIZONS:
        target, persist = f"target_logvol_{h}d", f"persistence_{h}d"
        cols = VOLATILITY_FEATURES + [target, persist, "d", "ticker"]
        df = panel[cols].replace([np.inf, -np.inf], np.nan).dropna()
        print(f"\n{'='*74}\nhorizon = {h} trading days   ({len(df):,} usable rows)")

        train, test = _chronological_split(df, TEST_FRACTION)
        if len(train) < MIN_ROWS or len(test) < MIN_ROWS:
            print("  not enough rows"); continue

        model, pred = _fit_predict(train, test, target)
        train_r2 = r2_score(train[target], model.predict(train[VOLATILITY_FEATURES]))
        s = _score(test[target].to_numpy(), pred, test[persist].to_numpy())

        print(f"  train {train['d'].min()} -> {train['d'].max()}  n={len(train):,}")
        print(f"  test  {test['d'].min()} -> {test['d'].max()}  n={len(test):,}")
        print(f"\n  {'':22s} {'model':>9s} {'persistence':>12s}")
        print(f"  {'R^2 (log space)':22s} {s['test_r2']:>9.3f} {s['persist_r2']:>12.3f}")
        print(f"  {'median error (ann %)':22s} {s['mae_model_annpct']:>9.2f} {s['mae_persist_annpct']:>12.2f}")
        print(f"  in-sample R^2 = {train_r2:.3f}  (gap to test R^2 shows overfitting)")
        verdict = "beats persistence" if s["skill"] > 0 else "DOES NOT beat persistence"
        print(f"\n  skill vs persistence = {s['skill']:+.3f}   -> {verdict}")

        wf = _walk_forward(df, target, persist)
        if wf:
            sk = [f["skill"] for f in wf]
            beat = sum(1 for x in sk if x > 0)
            print(f"\n  [walk-forward, {len(wf)} folds] skill {min(sk):+.3f} to {max(sk):+.3f} "
                  f"(mean {np.mean(sk):+.3f}) — {beat}/{len(wf)} folds beat persistence")
            for f in wf:
                print(f"     {f['test_start']} -> {f['test_end']}  n={f['n_test']:>6,}  "
                      f"R^2={f['test_r2']:+.3f}  persist={f['persist_r2']:+.3f}  "
                      f"skill={f['skill']:+.3f}")


if __name__ == "__main__":
    main()
