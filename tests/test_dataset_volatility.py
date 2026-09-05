"""
Tests for the volatility target and features.

The dangerous failure here is look-ahead: a forward-volatility window that
accidentally includes the current day produces a model that looks excellent
and is worthless. That mistake would not raise, and the resulting R^2 would be
higher, not lower — so it would read as success. Most of these tests exist to
make it impossible to reintroduce quietly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.dataset_volatility import VOLATILITY_FEATURES, build_volatility_dataset


def _forward_vol(returns: pd.Series, h: int) -> pd.Series:
    """The expression under test, isolated from the database."""
    return returns.shift(-1).rolling(h).std().shift(-(h - 1))


class TestForwardWindow:
    def test_window_is_exactly_the_next_h_days(self):
        rng = np.random.default_rng(0)
        r = pd.Series(rng.normal(size=40))
        h = 5
        fwd = _forward_vol(r, h)
        for i in range(len(r) - h):
            assert fwd.iloc[i] == pytest.approx(r.iloc[i + 1 : i + 1 + h].std())

    def test_today_is_excluded_from_its_own_target(self):
        """A spike on day 6 must not appear in day 6's own forward window —
        only in the windows of the days before it."""
        r = pd.Series([0.0] * 6 + [99.0] + [0.0] * 6)
        fwd = _forward_vol(r, 5)
        assert np.isnan(fwd.iloc[6]) or fwd.iloc[6] == pytest.approx(0.0)
        # the five days before it do see the spike
        assert all(fwd.iloc[i] > 1 for i in range(1, 6))

    def test_tail_rows_have_no_target(self):
        """The last h days cannot know their own future and must stay NaN
        rather than being filled with a partial window."""
        r = pd.Series(np.random.default_rng(1).normal(size=20))
        fwd = _forward_vol(r, 5)
        assert fwd.iloc[-5:].isna().all()


class TestDatasetShape:
    """Integration checks against the real database. Skipped when it is down."""

    @pytest.fixture(scope="class")
    @classmethod
    def panel(cls, engine):
        return build_volatility_dataset(engine, ["AAPL", "MSFT"], [5, 21])

    def test_has_expected_columns(self, panel):
        for c in VOLATILITY_FEATURES:
            assert c in panel.columns
        for h in (5, 21):
            assert f"target_logvol_{h}d" in panel.columns
            assert f"persistence_{h}d" in panel.columns

    def test_targets_are_finite_where_present(self, panel):
        for h in (5, 21):
            v = panel[f"target_logvol_{h}d"].dropna()
            assert len(v) > 0
            assert np.isfinite(v).all()

    def test_no_infinities_leak_into_features(self, panel):
        """Ratio features divide by volatility, which can be near zero."""
        assert not np.isinf(panel[VOLATILITY_FEATURES].to_numpy(dtype=float)).any()

    def test_horizons_do_not_cross_ticker_boundaries(self, panel):
        """Each ticker's last rows must be NaN for the target; if the rolling
        window ran across the concatenation, the earlier ticker would have a
        target computed from the later ticker's returns."""
        for _, g in panel.groupby("ticker"):
            g = g.sort_values("d")
            assert g["target_logvol_21d"].iloc[-21:].isna().all()

    def test_persistence_is_the_current_20d_reading(self, panel):
        """The baseline must be today's information only — if it ever picked
        up the target, the comparison it anchors would be meaningless."""
        sub = panel.dropna(subset=["log_vol_20", "persistence_5d"])
        assert (sub["persistence_5d"] == sub["log_vol_20"]).all()
