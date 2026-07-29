"""
Unit tests for the EDGAR parsing rules. No network: each test hands the
functions a hand-built `companyfacts` fragment, so what is being checked is
the rule itself, not SEC's current data.

The cases here are the real ones that broke during development, kept as tests
because every one of them was silent — the extractor produced plausible
numbers and nothing raised.
"""
from __future__ import annotations
from datetime import date

from src.extract.fundamentals_edgar import (
    _dedupe_near_period_ends,
    _drop_mistagged_quarters,
    _first_reported,
    _series_by_priority,
)


def _fact(start: str, end: str, val: float, filed: str) -> dict:
    return {"start": start, "end": end, "val": val, "filed": filed}


def test_earliest_filing_wins_for_dollar_amounts():
    """Point-in-time: a later restatement must not overwrite what was known."""
    rows = [
        _fact("2012-01-01", "2012-03-31", 13_185, "2012-04-27"),
        _fact("2012-01-01", "2012-03-31", 9_857, "2013-01-30"),
    ]
    out = _first_reported(rows, "quarter")
    assert out[date(2012, 3, 31)][0] == 13_185
    assert out[date(2012, 3, 31)][1] == date(2012, 4, 27)


def test_latest_filing_wins_for_per_share_amounts():
    """Apple's 7:1 split: 14.50 pre-split and 2.07 after, same quarter.

    Taking the earliest would splice pre- and post-split values into one
    series. The announced date must still be the original filing.
    """
    rows = [
        _fact("2013-09-29", "2013-12-28", 14.50, "2014-01-28"),
        _fact("2013-09-29", "2013-12-28", 2.07, "2014-10-27"),
    ]
    out = _first_reported(rows, "quarter", prefer="latest")
    assert out[date(2013, 12, 28)][0] == 2.07
    assert out[date(2013, 12, 28)][1] == date(2014, 1, 28)


def test_latest_preference_ignores_payload_ordering():
    """The chosen value must follow the filing date, not the list order.

    Tracking one date for both "when was this first known" and "which filing
    won" made prefer='latest' silently pick whichever fact came last in the
    payload, which is not the same thing and was wrong roughly half the time.
    """
    rows = [
        _fact("2013-09-29", "2013-12-28", 2.07, "2014-10-27"),
        _fact("2013-09-29", "2013-12-28", 14.50, "2014-01-28"),
    ]
    assert _first_reported(rows, "quarter", prefer="latest")[date(2013, 12, 28)][0] == 2.07


def test_ytd_durations_are_excluded():
    """10-Qs tag year-to-date alongside three-month figures."""
    rows = [
        _fact("2012-01-01", "2012-09-30", 39_825, "2012-10-26"),  # 273d YTD
        _fact("2012-07-01", "2012-09-30", 13_806, "2012-10-26"),  # 91d quarter
    ]
    out = _first_reported(rows, "quarter")
    assert out == {date(2012, 9, 30): (13_806, date(2012, 10, 26), date(2012, 7, 1))}


def test_candidate_tags_fill_gaps_in_priority_order():
    """Apple's ASC 606 changeover: one line, two tag names over time."""
    facts = {
        "RevenueFromContractWithCustomerExcludingAssessedTax": {
            "units": {"USD": [_fact("2019-01-01", "2019-03-31", 200, "2019-04-01")]}
        },
        "SalesRevenueNet": {
            "units": {"USD": [_fact("2016-01-01", "2016-03-31", 100, "2016-04-01")]}
        },
    }
    series, used = _series_by_priority(
        facts, ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
        "USD", span="quarter")
    assert series[date(2016, 3, 31)][0] == 100
    assert series[date(2019, 3, 31)][0] == 200
    assert used == ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"]


def test_higher_priority_tag_is_not_overwritten_by_a_later_one():
    """JPMorgan reports both Revenues and RevenuesNetOfInterestExpense for the
    same quarter, and they are different measures. The preferred tag must win
    outright — filling from the other would splice two definitions."""
    facts = {
        "RevenuesNetOfInterestExpense": {
            "units": {"USD": [_fact("2020-01-01", "2020-03-31", 29_000, "2020-04-14")]}
        },
        "Revenues": {
            "units": {"USD": [_fact("2020-01-01", "2020-03-31", 33_000, "2020-04-14")]}
        },
    }
    series, used = _series_by_priority(
        facts, ["RevenuesNetOfInterestExpense", "Revenues"], "USD", span="quarter")
    assert series[date(2020, 3, 31)][0] == 29_000
    assert used == ["RevenuesNetOfInterestExpense"]


def test_quarter_equal_to_its_fiscal_year_is_dropped():
    """Oracle tags the full-year figure with a valid 91-day quarter span."""
    quarterly = {date(2020, 5, 31): (39_068.0, date(2020, 6, 22), date(2020, 3, 1))}
    annual = {date(2020, 5, 31): (39_068.0, date(2020, 6, 22), date(2019, 6, 1))}
    assert _drop_mistagged_quarters("ORCL", quarterly, annual) == 1
    assert quarterly == {}


def test_a_genuinely_dominant_quarter_is_kept():
    """Tesla's Model S ramp really did put 74% of FY2012 revenue in Q4. The
    guard exists to catch quarters that EQUAL their year, not large ones."""
    quarterly = {date(2012, 12, 31): (306_332.0, date(2013, 3, 7), date(2012, 10, 1))}
    annual = {date(2012, 12, 31): (413_256.0, date(2013, 3, 7), date(2012, 1, 1))}
    assert _drop_mistagged_quarters("TSLA", quarterly, annual) == 0
    assert date(2012, 12, 31) in quarterly


def test_one_quarter_filed_under_two_dates_is_collapsed():
    """NVIDIA's quarter ending 2010-08-01 is re-dated 2010-07-31 by a 2012
    filing, with identical figures. Two rows would double-count it."""
    rows = [
        {"fiscal_period_end": date(2010, 8, 1), "announced_d": date(2010, 8, 30), "revenue": 811_208},
        {"fiscal_period_end": date(2010, 7, 31), "announced_d": date(2012, 3, 13), "revenue": 811_208},
        {"fiscal_period_end": date(2010, 10, 31), "announced_d": date(2010, 12, 7), "revenue": 843_912},
    ]
    out = _dedupe_near_period_ends("NVDA", rows)
    assert [r["fiscal_period_end"] for r in out] == [date(2010, 8, 1), date(2010, 10, 31)]


def test_adjacent_real_quarters_are_left_alone():
    """Quarters are ~91 days apart; the guard must not touch them."""
    rows = [
        {"fiscal_period_end": date(2020, 3, 31), "announced_d": date(2020, 4, 30), "revenue": 1},
        {"fiscal_period_end": date(2020, 6, 30), "announced_d": date(2020, 7, 30), "revenue": 2},
    ]
    assert len(_dedupe_near_period_ends("X", rows)) == 2


def test_a_sub_line_does_not_beat_the_real_top_line():
    """Oracle tags SalesRevenueNet with one product line (458m) for the quarter
    ending 2010-02-28 while stating total revenue of 6,404m under Revenues,
    which ranks lower. Priority order alone cannot fix this: for Apple and
    Amazon, SalesRevenueNet *is* the total."""
    facts = {
        "SalesRevenueNet": {
            "units": {"USD": [_fact("2009-12-01", "2010-02-28", 458_000_000, "2010-03-29")]}
        },
        "Revenues": {
            "units": {"USD": [_fact("2009-12-01", "2010-02-28", 6_404_000_000, "2010-03-29")]}
        },
    }
    series, _ = _series_by_priority(
        facts, ["SalesRevenueNet", "Revenues"], "USD", span="quarter",
        promote_much_larger=True)
    assert series[date(2010, 2, 28)][0] == 6_404_000_000


def test_a_definitional_difference_keeps_the_preferred_tag():
    """JPMorgan's Revenues exceeds RevenuesNetOfInterestExpense by 14%, and the
    bank measure must still win. Only multiples indicate a sub-line."""
    facts = {
        "RevenuesNetOfInterestExpense": {
            "units": {"USD": [_fact("2020-01-01", "2020-03-31", 29_000, "2020-04-14")]}
        },
        "Revenues": {
            "units": {"USD": [_fact("2020-01-01", "2020-03-31", 33_000, "2020-04-14")]}
        },
    }
    series, _ = _series_by_priority(
        facts, ["RevenuesNetOfInterestExpense", "Revenues"], "USD", span="quarter",
        promote_much_larger=True)
    assert series[date(2020, 3, 31)][0] == 29_000


def test_zero_revenue_falls_through_to_the_next_tag():
    """A tag present but zero means the company does not report that line."""
    facts = {
        "SalesRevenueNet": {
            "units": {"USD": [_fact("2008-12-01", "2009-02-28", 0, "2010-03-29")]}
        },
        "Revenues": {
            "units": {"USD": [_fact("2008-12-01", "2009-02-28", 5_453_000_000, "2010-03-29")]}
        },
    }
    series, _ = _series_by_priority(
        facts, ["SalesRevenueNet", "Revenues"], "USD", span="quarter", skip_zero=True)
    assert series[date(2009, 2, 28)][0] == 5_453_000_000


def test_a_wrong_annual_figure_cannot_delete_a_good_quarter():
    """Oracle's FY2010 total is tagged 2.29bn, the wrong line. The quarter of
    5.86bn is correct and must survive: the guard looks for a quarter that
    EQUALS its year, not one that merely exceeds it."""
    quarterly = {date(2009, 11, 30): (5_858_000_000.0, date(2009, 12, 22), date(2009, 9, 1))}
    annual = {date(2010, 5, 31): (2_290_000_000.0, date(2010, 7, 1), date(2009, 6, 1))}
    assert _drop_mistagged_quarters("ORCL", quarterly, annual) == 0
    assert date(2009, 11, 30) in quarterly
