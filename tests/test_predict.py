"""
Unit tests for the pure-logic pieces of src/models/predict.py — the
train/test splitting, walk-forward folding, and SHAP explanation shape that
every number on the Signal tab depends on. Uses small synthetic feature
matrices purely to exercise the code paths; these are not real market data
and nothing here is meant to represent an actual ticker.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import HistGradientBoostingClassifier

from src.models.predict import (
    _chronological_split,
    _walk_forward_accuracies,
    _summarize_folds,
    _explain_prediction,
)


def _synthetic_df(n_days: int = 100, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    feat_a = rng.normal(size=n_days)
    feat_b = rng.normal(size=n_days)
    # Target correlated with feat_a so the classifier has something real to
    # learn, but noisy enough that it isn't perfectly separable.
    target = (feat_a + rng.normal(scale=0.5, size=n_days) > 0).astype(int)
    return pd.DataFrame({"d": dates, "feat_a": feat_a, "feat_b": feat_b, "target_dir": target})


class TestChronologicalSplit:
    def test_train_is_strictly_before_test(self):
        df = _synthetic_df(100)
        train, test = _chronological_split(df, test_fraction=0.25)
        assert train["d"].max() < test["d"].min()

    def test_split_sizes_roughly_match_fraction(self):
        df = _synthetic_df(100)
        train, test = _chronological_split(df, test_fraction=0.25)
        # split is by unique date count, not row count, but with one row per
        # day here they coincide
        assert len(test) == pytest.approx(25, abs=2)
        assert len(train) + len(test) == len(df)

    def test_no_rows_lost_or_duplicated(self):
        df = _synthetic_df(60)
        train, test = _chronological_split(df, test_fraction=0.3)
        combined = pd.concat([train, test]).sort_values("d").reset_index(drop=True)
        expected = df.sort_values("d").reset_index(drop=True)
        pd.testing.assert_series_equal(combined["d"], expected["d"])


class TestWalkForwardAccuracies:
    def test_returns_expected_number_of_folds(self):
        df = _synthetic_df(300)
        folds = _walk_forward_accuracies(df, ["feat_a", "feat_b"], "target_dir", n_folds=5)
        assert 1 <= len(folds) <= 5

    def test_folds_are_chronologically_ordered_and_non_overlapping(self):
        df = _synthetic_df(300)
        folds = _walk_forward_accuracies(df, ["feat_a", "feat_b"], "target_dir", n_folds=5)
        for prev, cur in zip(folds, folds[1:]):
            assert prev["test_end"] < cur["test_start"]

    def test_each_fold_has_valid_accuracy_range(self):
        df = _synthetic_df(300)
        folds = _walk_forward_accuracies(df, ["feat_a", "feat_b"], "target_dir", n_folds=5)
        for f in folds:
            assert 0.0 <= f["accuracy"] <= 1.0
            assert 0.0 <= f["baseline"] <= 1.0
            assert f["n_test"] > 0

    def test_too_little_data_returns_fewer_or_no_folds(self):
        df = _synthetic_df(15)
        folds = _walk_forward_accuracies(df, ["feat_a", "feat_b"], "target_dir", n_folds=5, min_fold_test_days=10)
        assert folds == []


class TestSummarizeFolds:
    def test_empty_input_returns_none(self):
        assert _summarize_folds([]) is None

    def test_aggregates_match_manual_computation(self):
        fold_results = [
            {"accuracy": 0.4, "beats_baseline": False},
            {"accuracy": 0.6, "beats_baseline": True},
            {"accuracy": 0.5, "beats_baseline": False},
        ]
        summary = _summarize_folds(fold_results)
        assert summary["n_folds"] == 3
        assert summary["accuracy_min"] == 0.4
        assert summary["accuracy_max"] == 0.6
        assert summary["accuracy_mean"] == pytest.approx(0.5)
        assert summary["folds_beating_baseline"] == 1


class TestExplainPrediction:
    def test_returns_one_row_per_feature_sorted_by_abs_shap(self):
        df = _synthetic_df(150)
        feature_cols = ["feat_a", "feat_b"]
        model = HistGradientBoostingClassifier(max_iter=50, max_depth=3, random_state=0)
        model.fit(df[feature_cols], df["target_dir"])

        latest_X = df[feature_cols].iloc[[-1]]
        rows = _explain_prediction(model, latest_X, feature_cols)

        assert {r["feature"] for r in rows} == set(feature_cols)
        abs_shaps = [abs(r["shap"]) for r in rows]
        assert abs_shaps == sorted(abs_shaps, reverse=True)
