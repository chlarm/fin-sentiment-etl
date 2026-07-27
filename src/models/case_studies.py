"""
Finds real historical days where the pooled sentiment-augmented model
(src/models/predict.py) was both confident and correct, AND where sentiment
features (not just technicals) did most of the work — candidate case studies
for the thesis, grounded in what the model actually did on that specific date
rather than hand-picked anecdotes chosen to fit a preferred narrative.

Usage:
    python -m src.models.case_studies
"""
from __future__ import annotations
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.models.dataset import (
    TECHNICAL_FEATURES, SENTIMENT_FEATURES,
    build_sentiment_dataset, eligible_sentiment_tickers,
)
from src.models.predict import _chronological_split, _explain_prediction, HORIZON, TEST_FRACTION

MIN_USABLE_ROWS = 60
MIN_CONFIDENCE = 0.65


def _sentiment_share(explanation: list[dict], sentiment_features: list[str]) -> float:
    """What fraction of a prediction's total |SHAP| weight came from
    sentiment features vs technical ones — how this module ranks which
    correct, confident predictions are actually sentiment-driven rather than
    technicals that happened to also have sentiment data attached."""
    total = sum(abs(e["shap"]) for e in explanation) or 1e-9
    senti = sum(abs(e["shap"]) for e in explanation if e["feature"] in sentiment_features)
    return senti / total


def find_case_studies(
    engine: Engine, horizon: int = HORIZON, top_n: int = 3, min_days: int = 30
) -> list[dict]:
    """Returns up to top_n real test-period predictions, ranked by how much of
    the model's (correct, confident) call is attributable to sentiment
    features via SHAP. Empty list if there isn't enough real sentiment history
    to do this honestly yet."""
    tickers = eligible_sentiment_tickers(engine, min_days=min_days)
    if not tickers:
        return []

    df = build_sentiment_dataset(engine, tickers, [horizon])
    if df.empty:
        return []

    target_col = f"target_dir_{horizon}d"
    ret_col = f"target_ret_{horizon}d"
    feature_cols = TECHNICAL_FEATURES + SENTIMENT_FEATURES

    usable = df.dropna(subset=feature_cols + [target_col, ret_col]).copy()
    if len(usable) < MIN_USABLE_ROWS:
        return []

    train, test = _chronological_split(usable, TEST_FRACTION)
    if train.empty or test.empty or train[target_col].nunique() < 2:
        return []

    model = HistGradientBoostingClassifier(
        max_iter=200, max_depth=4, class_weight="balanced", random_state=42
    )
    model.fit(train[feature_cols], train[target_col].astype(int))

    test = test.copy()
    test["pred"] = model.predict(test[feature_cols])
    test["proba_up"] = model.predict_proba(test[feature_cols])[:, 1]
    test["correct"] = test["pred"] == test[target_col].astype(int)

    candidates = []
    for _, row in test.iterrows():
        confidence = row["proba_up"] if row["pred"] == 1 else 1 - row["proba_up"]
        if not row["correct"] or confidence < MIN_CONFIDENCE:
            continue

        X_row = row[feature_cols].to_frame().T
        expl = _explain_prediction(model, X_row, feature_cols)
        senti_share = _sentiment_share(expl, SENTIMENT_FEATURES)

        candidates.append({
            "ticker": row["ticker"],
            "date": str(row["d"]),
            "signal": "UP" if row["pred"] == 1 else "DOWN",
            "confidence": round(float(confidence), 3),
            "realized_return_pct": round(float(row[ret_col]) * 100, 2),
            "sentiment_index": round(float(row["sentiment_index"]), 3) if pd.notna(row["sentiment_index"]) else None,
            "sentiment_share_of_signal": round(float(senti_share), 3),
            "explanation": expl,
        })

    if not candidates:
        return []

    candidates.sort(key=lambda c: c["sentiment_share_of_signal"], reverse=True)
    top = candidates[:top_n]

    # Attach a real headline from that ticker/day for narrative grounding —
    # never fabricated, and left absent if no matching row exists.
    with engine.connect() as conn:
        for c in top:
            row = conn.execute(
                text("""
                    SELECT n.title FROM fact_news n
                    JOIN dim_asset a ON a.asset_id = n.asset_id
                    WHERE a.ticker = :ticker AND n.published_d = :d
                    ORDER BY n.published_at LIMIT 1
                """),
                {"ticker": c["ticker"], "d": c["date"]},
            ).fetchone()
            c["sample_headline"] = row[0] if row else None

    return top


def main() -> None:
    from src.config import Settings
    from src.common.db import get_engine

    settings = Settings()
    engine = get_engine(settings)
    cases = find_case_studies(engine)

    if not cases:
        print("No case studies yet — not enough confident+correct sentiment-driven predictions in the test window.")
        return

    for c in cases:
        print(f"\n{c['ticker']} — {c['date']}")
        print(f"  Signal: {c['signal']} ({c['confidence']:.0%} confidence), realized return: {c['realized_return_pct']:+.2f}%")
        print(f"  Sentiment index that day: {c['sentiment_index']}, sentiment's share of the SHAP signal: {c['sentiment_share_of_signal']:.0%}")
        if c["sample_headline"]:
            print(f"  Headline: {c['sample_headline']}")
        print("  Top feature contributions:")
        for e in c["explanation"][:4]:
            print(f"    {e['feature']:<20} value={e['value']:<10} shap={e['shap']}")


if __name__ == "__main__":
    main()
