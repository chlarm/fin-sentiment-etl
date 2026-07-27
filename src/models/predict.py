"""
Per-ticker directional signal + backtest, built from the same technical-only
dataset/split logic as Track A (see train_track_a.py). This is the "usable
tool" counterpart to the correlation tables in web/main.py's corr tab: instead
of reporting a correlation coefficient, it trains a model, holds out a
chronological test window, and reports how following its signal would
actually have done vs buy-and-hold — plus today's live signal.

Deliberately technical-only (no sentiment features) so it works for every
ticker with price history, not just the ~5 with sentiment coverage. A
sentiment-augmented variant can reuse eligible_sentiment_tickers() +
build_sentiment_dataset() the same way train_track_a.py does, once sentiment
history is deep enough to backtest honestly.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import HistGradientBoostingClassifier
from sqlalchemy.engine import Engine

from src.models.dataset import (
    TECHNICAL_FEATURES, SENTIMENT_FEATURES,
    build_technical_dataset, build_sentiment_dataset, eligible_sentiment_tickers,
)

HORIZON = 5
TEST_FRACTION = 0.25
MIN_USABLE_ROWS = 120
# Sentiment history only goes back to ~Dec 2025 across ~5 tickers, so the
# pooled sentiment model necessarily has far less data than the per-ticker
# technical-only one — the lower bar here is deliberate, not an oversight.
MIN_USABLE_ROWS_SENTIMENT = 60


def _chronological_split(df: pd.DataFrame, test_fraction: float):
    dates = sorted(df["d"].unique())
    cutoff = dates[int(len(dates) * (1 - test_fraction))]
    return df[df["d"] < cutoff], df[df["d"] >= cutoff]


def _walk_forward_accuracies(
    df: pd.DataFrame, feature_cols: list[str], target_col: str,
    n_folds: int = 5, min_fold_test_days: int = 10,
) -> list[dict]:
    """Expanding-window chronological folds: fold i trains on everything before
    a cutoff and tests on the next chronological slice. This is what answers
    "how stable is this accuracy number across different time windows" instead
    of reporting one lucky (or unlucky) 75/25 split. Folds with too few distinct
    days to be meaningful are dropped rather than padded with more folds than
    the data can actually support."""
    dates = sorted(df["d"].unique())
    n = len(dates)
    max_folds = max(1, (n // min_fold_test_days) - 1)
    n_folds = min(n_folds, max_folds)
    if n_folds < 1:
        return []

    segment = n // (n_folds + 1)
    results = []
    for i in range(1, n_folds + 1):
        train_end = dates[i * segment - 1]
        test_start_idx = i * segment
        test_end_idx = (i + 1) * segment if i < n_folds else n
        test_start = dates[test_start_idx]
        test_end = dates[test_end_idx - 1]

        train = df[df["d"] <= train_end]
        test = df[(df["d"] >= test_start) & (df["d"] <= test_end)]
        if train.empty or len(test) < min_fold_test_days or train[target_col].nunique() < 2:
            continue

        model = HistGradientBoostingClassifier(
            max_iter=200, max_depth=4, class_weight="balanced", random_state=42
        )
        model.fit(train[feature_cols], train[target_col].astype(int))
        pred = model.predict(test[feature_cols])
        y_test = test[target_col].astype(int)
        acc = float((pred == y_test).mean())
        baseline = float(max(y_test.mean(), 1 - y_test.mean()))
        results.append({
            "test_start": str(test_start),
            "test_end": str(test_end),
            "n_test": int(len(test)),
            "accuracy": round(acc, 3),
            "baseline": round(baseline, 3),
            "beats_baseline": acc > baseline + 0.02,
        })
    return results


def _summarize_folds(fold_results: list[dict]) -> dict | None:
    if not fold_results:
        return None
    accs = [f["accuracy"] for f in fold_results]
    return {
        "n_folds": len(fold_results),
        "folds": fold_results,
        "accuracy_mean": round(float(np.mean(accs)), 3),
        "accuracy_min": round(float(np.min(accs)), 3),
        "accuracy_max": round(float(np.max(accs)), 3),
        "folds_beating_baseline": sum(1 for f in fold_results if f["beats_baseline"]),
    }


def _explain_prediction(model, latest_X: pd.DataFrame, feature_cols: list[str]) -> list[dict]:
    """SHAP contribution of each feature to today's single prediction — how
    much each indicator pushed the model toward UP vs DOWN, not just "the
    model thinks X" with no reason given."""
    explainer = shap.TreeExplainer(model)
    sv = explainer.shap_values(latest_X)
    # Some sklearn/shap version combos return a list per class; normalize to
    # the single row of per-feature contributions for the positive ("up") class.
    if isinstance(sv, list):
        sv = sv[1] if len(sv) > 1 else sv[0]
    sv = np.asarray(sv).reshape(-1)
    rows = [
        {"feature": f, "value": round(float(latest_X.iloc[0][f]), 4), "shap": round(float(s), 4)}
        for f, s in zip(feature_cols, sv)
    ]
    rows.sort(key=lambda r: abs(r["shap"]), reverse=True)
    return rows


def signal_and_backtest(engine: Engine, ticker: str, horizon: int = HORIZON) -> dict | None:
    """Train a technical-only direction classifier for one ticker on a
    chronological train/test split. Returns today's signal plus a backtest of
    following that signal on the held-out test period vs buy-and-hold.
    Returns None if there isn't enough real data to train/evaluate honestly."""
    df = build_technical_dataset(engine, [ticker], [horizon])
    if df.empty:
        return None

    target_col = f"target_dir_{horizon}d"
    ret_col = f"target_ret_{horizon}d"
    feature_cols = TECHNICAL_FEATURES

    usable = df.dropna(subset=feature_cols + [target_col])
    if len(usable) < MIN_USABLE_ROWS:
        return None

    train, test = _chronological_split(usable, TEST_FRACTION)
    if train.empty or test.empty or train[target_col].nunique() < 2:
        return None

    model = HistGradientBoostingClassifier(
        max_iter=200, max_depth=4, class_weight="balanced", random_state=42
    )
    model.fit(train[feature_cols], train[target_col].astype(int))

    test = test.sort_values("d").copy()
    test["pred"] = model.predict(test[feature_cols])
    test["proba_up"] = model.predict_proba(test[feature_cols])[:, 1]

    y_test = test[target_col].astype(int)
    acc = float((test["pred"] == y_test).mean())
    majority_baseline = float(max(y_test.mean(), 1 - y_test.mean()))

    # Backtest: hold the position when the model says UP, sit in cash otherwise;
    # compare cumulative growth to plain buy-and-hold over the same window.
    strat_ret = test[ret_col].where(test["pred"] == 1, 0.0).fillna(0.0)
    hold_ret = test[ret_col].fillna(0.0)
    equity_strat = (1 + strat_ret).cumprod()
    equity_hold = (1 + hold_ret).cumprod()

    # Latest available row (most recent day with usable features) — this is
    # today's actionable signal, separate from the backtest window above.
    latest_row = df.dropna(subset=feature_cols).sort_values("d").iloc[-1]
    latest_X = latest_row[feature_cols].to_frame().T
    latest_proba = float(model.predict_proba(latest_X)[:, 1][0])

    walk_forward = _summarize_folds(
        _walk_forward_accuracies(usable, feature_cols, target_col)
    )

    return {
        "explanation": _explain_prediction(model, latest_X, feature_cols),
        "walk_forward": walk_forward,
        "ticker": ticker,
        "horizon": horizon,
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "test_accuracy": round(acc, 3),
        "majority_baseline": round(majority_baseline, 3),
        "beats_baseline": acc > majority_baseline + 0.02,
        "latest_date": str(latest_row["d"]),
        "latest_signal": "UP" if latest_proba >= 0.5 else "DOWN",
        "latest_confidence": round(latest_proba if latest_proba >= 0.5 else 1 - latest_proba, 3),
        "final_return_strategy": round(float(equity_strat.iloc[-1] - 1), 4),
        "final_return_buy_hold": round(float(equity_hold.iloc[-1] - 1), 4),
        "equity_curve": [
            {"d": str(d), "strategy": round(float(s), 4), "buy_hold": round(float(h), 4)}
            for d, s, h in zip(test["d"], equity_strat, equity_hold)
        ],
    }


def sentiment_signal(engine: Engine, horizon: int = HORIZON, min_days: int = 30) -> dict | None:
    """Pooled technical+sentiment model across every ticker with real sentiment
    coverage (see eligible_sentiment_tickers) — same pooling choice as Track A's
    Experiment 2, because any single ticker's sentiment history alone (~Dec 2025
    onward) is too thin to train and honestly backtest per-ticker. Explicitly
    exploratory: treat the accuracy number as directional, not conclusive.
    Returns None if no ticker currently has enough sentiment history."""
    tickers = eligible_sentiment_tickers(engine, min_days=min_days)
    if not tickers:
        return None

    df = build_sentiment_dataset(engine, tickers, [horizon])
    if df.empty:
        return None

    target_col = f"target_dir_{horizon}d"
    feature_cols = TECHNICAL_FEATURES + SENTIMENT_FEATURES

    usable = df.dropna(subset=feature_cols + [target_col])
    if len(usable) < MIN_USABLE_ROWS_SENTIMENT:
        return None

    train, test = _chronological_split(usable, TEST_FRACTION)
    if train.empty or test.empty or train[target_col].nunique() < 2:
        return None

    model = HistGradientBoostingClassifier(
        max_iter=200, max_depth=4, class_weight="balanced", random_state=42
    )
    model.fit(train[feature_cols], train[target_col].astype(int))

    pred = model.predict(test[feature_cols])
    y_test = test[target_col].astype(int)
    acc = float((pred == y_test).mean())
    majority_baseline = float(max(y_test.mean(), 1 - y_test.mean()))

    per_ticker = {}
    for t in tickers:
        sub = df[df["ticker"] == t].dropna(subset=feature_cols).sort_values("d")
        if sub.empty:
            continue
        latest_row = sub.iloc[-1]
        latest_X = latest_row[feature_cols].to_frame().T
        proba = float(model.predict_proba(latest_X)[:, 1][0])
        per_ticker[t] = {
            "latest_date": str(latest_row["d"]),
            "latest_signal": "UP" if proba >= 0.5 else "DOWN",
            "latest_confidence": round(proba if proba >= 0.5 else 1 - proba, 3),
            "explanation": _explain_prediction(model, latest_X, feature_cols),
        }

    # Sentiment history is thin (~5 tickers since ~Dec 2025), so fewer folds
    # with a lower per-fold minimum than the technical-only model — still
    # honest about it via n_folds/n_test in the returned summary.
    walk_forward = _summarize_folds(
        _walk_forward_accuracies(usable, feature_cols, target_col, n_folds=3, min_fold_test_days=5)
    )

    return {
        "tickers": tickers,
        "horizon": horizon,
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "test_accuracy": round(acc, 3),
        "majority_baseline": round(majority_baseline, 3),
        "beats_baseline": acc > majority_baseline + 0.02,
        "walk_forward": walk_forward,
        "per_ticker": per_ticker,
    }
