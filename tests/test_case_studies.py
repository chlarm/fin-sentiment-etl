"""
Unit tests for src/models/case_studies.py's pure ranking logic. The DB-backed
find_case_studies() itself is exercised as an integration check in
tests/test_dq_checks.py's spirit (skipped when the local Postgres isn't up) —
this file covers the part that decides which candidate is "sentiment-driven"
without needing a database.
"""
from __future__ import annotations
from src.models.case_studies import _sentiment_share


SENTIMENT_FEATURES = ["sentiment_lag1", "sentiment_lag2"]


def test_all_weight_on_sentiment_features_gives_share_of_one():
    explanation = [
        {"feature": "sentiment_lag1", "value": 0.1, "shap": 0.8},
        {"feature": "sentiment_lag2", "value": 0.1, "shap": 0.2},
    ]
    assert _sentiment_share(explanation, SENTIMENT_FEATURES) == 1.0


def test_all_weight_on_technical_features_gives_share_of_zero():
    explanation = [
        {"feature": "rsi_14", "value": 50.0, "shap": 0.5},
        {"feature": "macd_hist", "value": 0.1, "shap": -0.3},
    ]
    assert _sentiment_share(explanation, SENTIMENT_FEATURES) == 0.0


def test_mixed_contribution_uses_absolute_value_not_signed():
    explanation = [
        {"feature": "sentiment_lag1", "value": 0.1, "shap": -0.4},  # negative shap still counts
        {"feature": "rsi_14", "value": 50.0, "shap": 0.4},
    ]
    assert _sentiment_share(explanation, SENTIMENT_FEATURES) == 0.5


def test_empty_explanation_does_not_divide_by_zero():
    assert _sentiment_share([], SENTIMENT_FEATURES) == 0.0
