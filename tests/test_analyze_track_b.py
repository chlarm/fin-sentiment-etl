"""
Unit tests for the out-of-sample validation added to Track B's multi-feature
regression. Uses small synthetic panels purely to exercise the splitting and
scoring logic — not real fundamentals data.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

from src.models.analyze_track_b import (
    _baseline_r2,
    _chronological_split,
    _out_of_sample_ols,
    _walk_forward_r2,
)
from src.models.dataset_fundamentals import FUNDAMENTAL_FEATURES


def _synthetic_panel(n: int = 300, seed: int = 0, signal: float = 0.0) -> pd.DataFrame:
    """`signal` controls how much the target actually depends on the features
    (0 = pure noise, matching the honest null result Track B measures on real
    data; >0 lets a test assert the machinery CAN detect a real relationship
    when one exists, so a "does not beat baseline" result elsewhere can't be
    mistaken for a bug in the scoring code)."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2015-01-01", periods=n, freq="7D")
    data = {"anchor_date": dates}
    for feat in FUNDAMENTAL_FEATURES:
        data[feat] = rng.normal(size=n)
    target = signal * data[FUNDAMENTAL_FEATURES[0]] + rng.normal(scale=1.0, size=n)
    data["fwd_ret_63d"] = target
    return pd.DataFrame(data)


class TestChronologicalSplit:
    def test_train_strictly_before_test(self):
        df = _synthetic_panel(200)
        train, test = _chronological_split(df, "anchor_date", 0.25)
        assert train["anchor_date"].max() < test["anchor_date"].min()

    def test_no_rows_lost(self):
        df = _synthetic_panel(150)
        train, test = _chronological_split(df, "anchor_date", 0.3)
        assert len(train) + len(test) == len(df)


class TestBaselineR2:
    def test_perfect_agreement_between_train_and_test_means_is_near_zero(self):
        y_train = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        y_test = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        assert abs(_baseline_r2(y_train, y_test)) < 1e-9

    def test_shifted_test_mean_gives_negative_baseline(self):
        """If the test period's average return genuinely differs from the
        training period's, predicting the training mean should score BELOW
        zero on test — that's real non-stationarity, not a bug."""
        y_train = pd.Series([0.0] * 20)
        y_test = pd.Series([1.0] * 20)  # constant but shifted -> nonzero SS_tot needs variance
        y_test_varied = pd.Series(np.linspace(0.5, 1.5, 20))
        r2 = _baseline_r2(y_train, y_test_varied)
        assert r2 < 0


class TestOutOfSampleOls:
    def test_returns_none_below_minimum_size(self):
        df = _synthetic_panel(10)
        assert _out_of_sample_ols(df, "fwd_ret_63d") is None

    def test_pure_noise_does_not_reliably_beat_baseline(self):
        """The honest null result: with no real relationship, the fitted
        model's test R^2 should not systematically exceed the baseline by a
        wide margin. Regression to noise can occasionally edge out the
        baseline by chance, so this checks direction/magnitude, not a strict
        inequality on every seed."""
        df = _synthetic_panel(400, seed=1, signal=0.0)
        result = _out_of_sample_ols(df, "fwd_ret_63d")
        assert result is not None
        assert result["test_r2"] < 0.10  # nowhere near a real predictive fit

    def test_a_real_relationship_is_detectable(self):
        """Sanity check that the scoring machinery isn't broken: give the
        target an actual dependence on one feature and confirm test R^2
        comes back positive and beats the baseline."""
        df = _synthetic_panel(400, seed=2, signal=3.0)
        result = _out_of_sample_ols(df, "fwd_ret_63d")
        assert result is not None
        assert result["test_r2"] > 0.2
        assert result["beats_baseline"]

    def test_output_shape(self):
        df = _synthetic_panel(300, seed=3, signal=1.0)
        result = _out_of_sample_ols(df, "fwd_ret_63d")
        assert set(result["coefficients"]) == set(FUNDAMENTAL_FEATURES)
        assert result["n_train"] + result["n_test"] == len(df)


class TestWalkForwardR2:
    def test_folds_are_chronologically_ordered_and_non_overlapping(self):
        df = _synthetic_panel(500, seed=4)
        folds = _walk_forward_r2(df, "fwd_ret_63d", n_folds=5, min_fold_test=20)
        for prev, cur in zip(folds, folds[1:]):
            assert prev["test_end"] < cur["test_start"]

    def test_too_little_data_returns_fewer_or_no_folds(self):
        df = _synthetic_panel(30, seed=5)
        folds = _walk_forward_r2(df, "fwd_ret_63d", n_folds=5, min_fold_test=20)
        assert len(folds) <= 1

    def test_each_fold_reports_a_baseline_and_comparison(self):
        df = _synthetic_panel(500, seed=6)
        folds = _walk_forward_r2(df, "fwd_ret_63d", n_folds=5, min_fold_test=20)
        assert len(folds) >= 1
        for f in folds:
            assert f["n_test"] > 0
            assert isinstance(f["beats_baseline"], bool)


class TestWinsorize:
    """Ratio features here can be arithmetically correct and statistically
    ruinous — a P/E of 10,545 arises from dividing by a cent of trailing EPS.
    One such row in a test split drove OLS to R^2 = -34."""

    def _frames(self):
        train = pd.DataFrame({f: np.linspace(0, 100, 101) for f in FUNDAMENTAL_FEATURES})
        test = pd.DataFrame({f: [-500.0, 50.0, 10_545.0] for f in FUNDAMENTAL_FEATURES})
        return train, test

    def test_extreme_test_values_are_clipped_to_train_bounds(self):
        from src.models.analyze_track_b import _winsorize_to
        train, test = self._frames()
        _, clipped = _winsorize_to(train, [train, test], FUNDAMENTAL_FEATURES)
        f = FUNDAMENTAL_FEATURES[0]
        assert clipped[f].max() <= train[f].quantile(0.99)
        assert clipped[f].min() >= train[f].quantile(0.01)
        assert clipped[f].iloc[1] == 50.0  # an in-range value is untouched

    def test_bounds_come_from_train_only(self):
        """Using full-panel percentiles would let the test period influence its
        own preprocessing, defeating the chronological split."""
        from src.models.analyze_track_b import _winsorize_to
        train, test = self._frames()
        wide = pd.concat([train, test], ignore_index=True)
        _, from_train = _winsorize_to(train, [train, test], FUNDAMENTAL_FEATURES)
        _, from_all = _winsorize_to(wide, [train, test], FUNDAMENTAL_FEATURES)
        f = FUNDAMENTAL_FEATURES[0]
        assert from_train[f].max() < from_all[f].max()

    def test_regression_no_longer_explodes_on_an_outlier(self):
        from sklearn.linear_model import LinearRegression
        from sklearn.metrics import r2_score
        from src.models.analyze_track_b import _winsorize_to
        rng = np.random.default_rng(0)
        n = 300
        tr = pd.DataFrame({f: rng.normal(size=n) for f in FUNDAMENTAL_FEATURES})
        tr["y"] = rng.normal(size=n)
        te = pd.DataFrame({f: rng.normal(size=40) for f in FUNDAMENTAL_FEATURES})
        te["y"] = rng.normal(size=40)
        te.loc[0, FUNDAMENTAL_FEATURES[0]] = 10_545.0   # the AMZN P/E case

        m = LinearRegression().fit(tr[FUNDAMENTAL_FEATURES], tr["y"])
        raw = r2_score(te["y"], m.predict(te[FUNDAMENTAL_FEATURES]))
        tr_w, te_w = _winsorize_to(tr, [tr, te], FUNDAMENTAL_FEATURES)
        m2 = LinearRegression().fit(tr_w[FUNDAMENTAL_FEATURES], tr_w["y"])
        fixed = r2_score(te_w["y"], m2.predict(te_w[FUNDAMENTAL_FEATURES]))
        assert raw < -1.0        # untreated: catastrophic
        assert fixed > -0.5      # treated: merely unhelpful, which is the truth
