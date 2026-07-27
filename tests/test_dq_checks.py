"""
Integration tests for src/dq/checks.py against the real local Postgres.
Deliberately assert structural invariants (types, keys, PK-enforced
zero-counts) rather than exact values tied to today's data, since fact tables
grow every day the ETL runs — a test asserting an exact row count would be
stale by tomorrow. The one exception is the two checks that must always read
zero regardless of how much data accumulates: duplicate rows (blocked by a
primary key) and NULL return_1d on a non-first row (fixed at the source in
src/etl/run_daily.py — see src/scripts/backfill_price_returns.py for why this
one matters).
"""
from __future__ import annotations
import pandas as pd

from src.dq.checks import (
    ACCEPTED_ANOMALIES,
    run_basic_checks,
    run_price_anomaly_check,
    run_technical_gap_check,
    run_coverage_check,
    run_accepted_anomalies_report,
)

EXPECTED_BASIC_CHECK_KEYS = {
    "news_duplicates",
    "price_null_close",
    "sentiment_out_of_range",
    "synthetic_news_contamination",
    "duplicate_price_rows",
    "duplicate_sentiment_rows",
    "non_positive_close_price",
    "price_null_return_with_close",
}


def test_run_basic_checks_returns_all_expected_keys_as_non_negative_ints(engine):
    with engine.connect() as conn:
        result = run_basic_checks(conn)

    assert set(result.keys()) == EXPECTED_BASIC_CHECK_KEYS
    for name, value in result.items():
        assert isinstance(value, int), f"{name} should be an int, got {type(value)}"
        assert value >= 0, f"{name} should never be negative"


def test_duplicate_rows_are_always_zero_primary_key_enforced(engine):
    with engine.connect() as conn:
        result = run_basic_checks(conn)

    assert result["duplicate_price_rows"] == 0
    assert result["duplicate_sentiment_rows"] == 0


def test_return_1d_is_never_null_on_a_non_first_row(engine):
    """Regression guard for the bug fixed in src/etl/run_daily.py: every
    daily run used to null out the earliest row of its own lookback batch,
    silently overwriting an already-correct value. If this starts failing
    again, check that recompute_returns_from_db() is still being called
    after upsert_price_daily() in run_daily.py."""
    with engine.connect() as conn:
        result = run_basic_checks(conn)

    assert result["price_null_return_with_close"] == 0


def test_price_anomaly_check_returns_expected_columns(engine):
    with engine.connect() as conn:
        df = run_price_anomaly_check(conn, threshold_pct=40.0)

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["ticker", "d", "close", "pct_change"]
    if not df.empty:
        assert (df["pct_change"].abs() > 40.0).all()


def test_technical_gap_check_returns_expected_columns(engine):
    with engine.connect() as conn:
        df = run_technical_gap_check(conn, window_days=30)

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["ticker", "missing_technical_days"]
    if not df.empty:
        assert (df["missing_technical_days"] > 0).all()


def test_technical_gap_check_is_clean_after_run_daily_fix(engine):
    """Regression guard for the other half of the same incident: run_daily.py
    now computes technical indicators from the full DB history every run, so
    this should never show a gap for a ticker the pipeline is actively
    tracking (assuming the daily ETL has run at least once recently)."""
    with engine.connect() as conn:
        df = run_technical_gap_check(conn, window_days=30)

    assert df.empty, f"unexpected technical indicator gaps: {df.to_dict('records')}"


def test_all_basic_checks_pass(engine):
    """The report's overall PASS/FAIL is only useful if PASS is actually
    reachable. It sat on FAIL permanently until the one genuine anomaly
    (negative WTI close, 2020-04-20) was moved to ACCEPTED_ANOMALIES. If this
    fails, something real broke — read the failing key rather than adding a
    new entry to the allowlist to make it green again."""
    with engine.connect() as conn:
        result = run_basic_checks(conn)

    failing = {k: v for k, v in result.items() if v != 0}
    assert not failing, f"DQ checks failing: {failing}"


def test_accepted_anomaly_rows_still_exist(engine):
    """Guards against a stale allowlist. If an accepted row is no longer in
    the DB, the entry is excusing nothing and should be removed — otherwise
    it silently widens the exclusion for future data."""
    with engine.connect() as conn:
        df = run_accepted_anomalies_report(conn)

    assert len(df) == len(ACCEPTED_ANOMALIES)
    missing = df[df["close"].isna()]
    assert missing.empty, f"accepted anomalies no longer present in the DB: {missing.to_dict('records')}"


def test_accepted_anomaly_is_excluded_but_still_in_the_table(engine):
    """The allowlist must suppress the *count*, not delete the data — the
    negative close is real history and has to stay queryable."""
    with engine.connect() as conn:
        counted = run_basic_checks(conn)["non_positive_close_price"]
        raw = conn.exec_driver_sql(
            "SELECT COUNT(*) FROM fact_price_daily WHERE close IS NOT NULL AND close <= 0"
        ).scalar()

    assert counted == 0
    assert raw >= 1, "the accepted negative-close row should still exist in fact_price_daily"


def test_coverage_check_returns_expected_columns(engine):
    with engine.connect() as conn:
        df = run_coverage_check(conn, window_days=7)

    assert isinstance(df, pd.DataFrame)
    assert list(df.columns) == ["ticker", "trading_days", "zero_news_days"]
    if not df.empty:
        assert (df["zero_news_days"] <= df["trading_days"]).all()
