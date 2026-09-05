"""
Tests for how a fundamentals row is anchored to a price.

The bug these lock down was silent and cost 39% of the Track B panel:
`searchsorted` returns the first stored day for any target that predates the
price history, so every announcement before 2016-07-14 anchored to that one
date. 445 of 1,134 rows paired 2007-2016 fundamentals with the forward return
measured from July 2016, all sharing a handful of return values. Nothing
raised, and the panel looked full.
"""
from __future__ import annotations
from datetime import date, timedelta

import pandas as pd

from src.models.dataset_fundamentals import (
    MAX_ANCHOR_GAP_DAYS,
    _nearest_price_on_or_after,
    _price_n_trading_days_after,
)


def _series(dates: list[date], closes: list[float]) -> pd.Series:
    return pd.Series(closes, index=pd.Index(dates)).sort_index()


TRADING_DAYS = _series(
    [date(2020, 1, 2), date(2020, 1, 3), date(2020, 1, 6), date(2020, 1, 7)],
    [100.0, 101.0, 102.0, 103.0],
)


class TestAnchoring:
    def test_exact_trading_day_is_used(self):
        d, px = _nearest_price_on_or_after(TRADING_DAYS, date(2020, 1, 3))
        assert (d, px) == (date(2020, 1, 3), 101.0)

    def test_weekend_announcement_rolls_to_the_next_trading_day(self):
        """2020-01-04 was a Saturday; the next close is Monday the 6th."""
        d, px = _nearest_price_on_or_after(TRADING_DAYS, date(2020, 1, 4))
        assert (d, px) == (date(2020, 1, 6), 102.0)

    def test_announcement_before_all_price_history_is_rejected(self):
        """The regression. Without the gap check this silently returned the
        first stored day, pairing a 2007 filing with a 2020 price."""
        assert _nearest_price_on_or_after(TRADING_DAYS, date(2007, 9, 30)) == (None, None)

    def test_announcement_after_all_price_history_is_rejected(self):
        assert _nearest_price_on_or_after(TRADING_DAYS, date(2026, 1, 1)) == (None, None)

    def test_gap_just_inside_the_limit_is_accepted(self):
        target = date(2020, 1, 2) - timedelta(days=MAX_ANCHOR_GAP_DAYS)
        d, _ = _nearest_price_on_or_after(TRADING_DAYS, target)
        assert d == date(2020, 1, 2)

    def test_gap_just_outside_the_limit_is_rejected(self):
        target = date(2020, 1, 2) - timedelta(days=MAX_ANCHOR_GAP_DAYS + 1)
        assert _nearest_price_on_or_after(TRADING_DAYS, target) == (None, None)


class TestForwardPrice:
    def test_returns_the_close_n_trading_days_later(self):
        assert _price_n_trading_days_after(TRADING_DAYS, date(2020, 1, 2), 2) == 102.0

    def test_returns_none_when_the_future_is_not_in_the_data(self):
        assert _price_n_trading_days_after(TRADING_DAYS, date(2020, 1, 2), 99) is None
