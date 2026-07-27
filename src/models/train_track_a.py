#!/usr/bin/env python3
"""
Track A (short-horizon, 1-21 trading days): does adding news sentiment to a
price/technical-indicator model improve directional accuracy?

Two experiments, kept honestly separate because they run on different amounts
of data:
  1. Technical-only baseline — all 30 tickers, full ~10-year price history.
     Large, robust sample; shows what pure price/technical momentum can do.
  2. Technical+sentiment — only the ~5 tickers with real sentiment coverage
     (>=30 days), restricted to the ~Dec 2025 onward window sentiment exists
     in. Small sample — treat these numbers as exploratory, not conclusive.

Both use a chronological (not random) train/test split — the whole point is
to see how the model does on dates it never trained on.

Usage:
    python -m src.models.train_track_a
"""
from __future__ import annotations
import warnings
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

from src.config import Settings
from src.common.db import get_engine
from src.models.dataset import (
    TECHNICAL_FEATURES, SENTIMENT_FEATURES,
    build_technical_dataset, build_sentiment_dataset, eligible_sentiment_tickers,
)

warnings.filterwarnings("ignore")

HORIZONS = [1, 5, 21]
TEST_FRACTION = 0.25

MODELS = {
    "logreg_balanced": lambda: Pipeline([
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ]),
    "gboost_balanced": lambda: HistGradientBoostingClassifier(
        max_iter=200, max_depth=4, class_weight="balanced", random_state=42
    ),
}


def _chronological_split(df: pd.DataFrame, test_fraction: float):
    dates = sorted(df["d"].unique())
    cutoff = dates[int(len(dates) * (1 - test_fraction))]
    train = df[df["d"] < cutoff]
    test = df[df["d"] >= cutoff]
    return train, test, cutoff


def _train_and_eval(df: pd.DataFrame, feature_cols: list[str], horizon: int, label: str, model_name: str):
    target_col = f"target_dir_{horizon}d"
    cols = feature_cols + [target_col, "d", "ticker"]
    clean = df[cols].dropna()

    if len(clean) < 60:
        print(f"  [{label}/{model_name}] h={horizon:>2}d  skipped — only {len(clean)} usable rows (need >=60)")
        return

    train, test, cutoff = _chronological_split(clean, TEST_FRACTION)
    if train.empty or test.empty or train[target_col].nunique() < 2:
        print(f"  [{label}/{model_name}] h={horizon:>2}d  skipped — not enough class variety after split")
        return

    X_train, y_train = train[feature_cols], train[target_col].astype(int)
    X_test, y_test = test[feature_cols], test[target_col].astype(int)

    model = MODELS[model_name]()
    model.fit(X_train, y_train)
    pred = model.predict(X_test)

    acc = accuracy_score(y_test, pred)
    prec, rec, f1, _ = precision_recall_fscore_support(y_test, pred, average="binary", zero_division=0)
    majority_baseline = max(y_test.mean(), 1 - y_test.mean())
    beats_majority = "YES" if acc > majority_baseline + 0.02 else ("no" if acc < majority_baseline - 0.02 else "~tie")

    print(
        f"  [{label:<22}/{model_name:<16}] h={horizon:>2}d  n_train={len(train):>5} n_test={len(test):>4}  "
        f"hit_rate={acc:.3f}  precision={prec:.3f}  recall={rec:.3f}  f1={f1:.3f}  "
        f"(majority_baseline={majority_baseline:.3f}, beats_majority={beats_majority})"
    )


def main() -> None:
    settings = Settings()
    engine = get_engine(settings)

    print("=== Experiment 1: technical-only baseline (30 tickers, ~10yr) ===")
    tech_df = build_technical_dataset(engine, list(settings.tickers), HORIZONS)
    print(f"Dataset: {len(tech_df)} rows, {tech_df['ticker'].nunique()} tickers, "
          f"{tech_df['d'].min()} -> {tech_df['d'].max()}")
    for h in HORIZONS:
        for model_name in MODELS:
            _train_and_eval(tech_df, TECHNICAL_FEATURES, h, "technical-only", model_name)

    print()
    print("=== Experiment 2: technical + sentiment (small sample, exploratory) ===")
    senti_tickers = eligible_sentiment_tickers(engine, min_days=30)
    if not senti_tickers:
        print("No ticker has enough sentiment history (>=30 days) yet — skipping.")
        return
    print(f"Eligible tickers (>=30 sentiment days): {senti_tickers}")

    senti_df = build_sentiment_dataset(engine, senti_tickers, HORIZONS)
    print(f"Dataset: {len(senti_df)} rows, {senti_df['ticker'].nunique()} tickers, "
          f"{senti_df['d'].min()} -> {senti_df['d'].max()}")

    print("\n-- technical features only, restricted to the same sentiment-era rows --")
    for h in HORIZONS:
        for model_name in MODELS:
            _train_and_eval(senti_df, TECHNICAL_FEATURES, h, "technical (senti-era)", model_name)

    print("\n-- technical + sentiment features --")
    for h in HORIZONS:
        for model_name in MODELS:
            _train_and_eval(senti_df, TECHNICAL_FEATURES + SENTIMENT_FEATURES, h, "technical+sentiment", model_name)


if __name__ == "__main__":
    main()
