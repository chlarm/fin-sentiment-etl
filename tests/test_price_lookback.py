"""
Tests for how far back a run fetches prices.

The rule these cover exists because a fixed 14-day lookback made outages
permanent: when the machine was off 2026-08-12 to 2026-08-21, the next run's
window started after the hole, so it filled the recent days, reported success,
and left ten days that no future run would ever reach. The interior-gap case
is the one that matters — max(d) is perfectly current while the data has a
hole in the middle.
"""
from __future__ import annotations
from datetime import date

from src.etl.run_daily import (
    PRICE_LOOKBACK_CEILING_DAYS,
    PRICE_LOOKBACK_FLOOR_DAYS,
    choose_price_lookback,
)

RUN_D = date(2026, 9, 5)


def test_healthy_data_stays_at_the_floor():
    latest = [("AAPL", date(2026, 9, 4)), ("MSFT", date(2026, 9, 4))]
    lookback, reason = choose_price_lookback(RUN_D, latest, None, expected_tickers=2)
    assert lookback == PRICE_LOOKBACK_FLOOR_DAYS
    assert reason is None


def test_trailing_gap_widens_the_window():
    """Newest stored day is behind today."""
    latest = [("AAPL", date(2026, 9, 4)), ("MSFT", date(2026, 8, 1))]
    lookback, reason = choose_price_lookback(RUN_D, latest, None, expected_tickers=2)
    assert lookback == (RUN_D - date(2026, 8, 1)).days + 5
    assert "MSFT" in reason


def test_interior_gap_widens_the_window_even_when_nothing_is_stale():
    """The August 2026 case. Every ticker is current, so a staleness check
    alone reports no problem, yet ten days are missing in the middle."""
    latest = [("AAPL", RUN_D), ("MSFT", RUN_D)]
    lookback, reason = choose_price_lookback(
        RUN_D, latest, earliest_gap=date(2026, 8, 12), expected_tickers=2)
    assert lookback == (RUN_D - date(2026, 8, 12)).days + 5
    assert "2026-08-12" in reason


def test_the_larger_of_the_two_gaps_wins():
    latest = [("AAPL", date(2026, 9, 1))]          # 4 days stale
    lookback, reason = choose_price_lookback(
        RUN_D, latest, earliest_gap=date(2026, 7, 1), expected_tickers=1)
    assert lookback == (RUN_D - date(2026, 7, 1)).days + 5
    assert "2026-07-01" in reason


def test_a_ticker_with_no_history_pulls_the_full_window():
    """Newly added to TICKERS: it should get real history, not a fortnight."""
    latest = [("AAPL", RUN_D)]
    lookback, reason = choose_price_lookback(RUN_D, latest, None, expected_tickers=2)
    assert lookback == PRICE_LOOKBACK_CEILING_DAYS
    assert "no price history" in reason


def test_an_ancient_gap_is_capped_at_the_ceiling():
    """One run should not turn into an unbounded download."""
    latest = [("AAPL", RUN_D)]
    lookback, _ = choose_price_lookback(
        RUN_D, latest, earliest_gap=date(2015, 1, 1), expected_tickers=1)
    assert lookback == PRICE_LOOKBACK_CEILING_DAYS


def test_reason_is_reported_whenever_the_window_is_widened():
    """A silent widening would hide the very outage this is meant to surface."""
    latest = [("AAPL", date(2026, 8, 1))]
    lookback, reason = choose_price_lookback(RUN_D, latest, None, expected_tickers=1)
    assert lookback > PRICE_LOOKBACK_FLOOR_DAYS
    assert reason
