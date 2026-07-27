from __future__ import annotations
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Connection

# Data points that trip a check but are genuinely correct, so the overall
# PASS/FAIL stays meaningful instead of sitting on FAIL forever — a report
# that always says FAIL trains you to ignore it, which is worse than not
# having the check. These are excluded from the counts but still printed by
# main() so they can never quietly disappear.
#
# Adding an entry here is a claim that the data is RIGHT and the check is
# too strict for that row. It is not a way to silence a real problem.
ACCEPTED_ANOMALIES: tuple[dict[str, str], ...] = (
    {
        "check": "non_positive_close_price",
        "ticker": "CL=F",
        "d": "2020-04-20",
        "reason": (
            "WTI crude futures really did settle negative (-37.63) during the "
            "2020 storage glut. Real market event, not a vendor data error."
        ),
    },
)


def _accepted_pairs(check: str) -> tuple[list[str], list[str]]:
    """(tickers, dates) accepted for a given check, as parallel arrays for
    the pairwise anti-join below."""
    rows = [a for a in ACCEPTED_ANOMALIES if a["check"] == check]
    return [r["ticker"] for r in rows], [r["d"] for r in rows]


def run_basic_checks(conn: Connection) -> dict[str, int]:
    dup = conn.execute(text("SELECT COUNT(*) - COUNT(DISTINCT news_hash) FROM fact_news")).scalar()
    null_close = conn.execute(text("SELECT COUNT(*) FROM fact_price_daily WHERE close IS NULL")).scalar()
    out_of_range = conn.execute(text("""
        SELECT COUNT(*)
        FROM fact_news
        WHERE sentiment_score IS NOT NULL AND (sentiment_score < -1.0 OR sentiment_score > 1.0)
    """)).scalar()
    synthetic_contamination = conn.execute(text("""
        SELECT COUNT(*)
        FROM fact_news f
        JOIN dim_source s ON s.source_id = f.source_id
        WHERE s.source_type = 'synthetic'
    """)).scalar()
    # (asset_id, d) is the primary key on all three of these tables, so this
    # should always read 0 — kept as a cheap defensive check rather than a
    # blind trust in the schema, since it's exactly the kind of thing that
    # goes unnoticed until it invalidates a backtest number in the thesis.
    duplicate_price_rows = conn.execute(text("""
        SELECT COUNT(*) FROM (
            SELECT asset_id, d FROM fact_price_daily GROUP BY asset_id, d HAVING COUNT(*) > 1
        ) t
    """)).scalar()
    duplicate_sentiment_rows = conn.execute(text("""
        SELECT COUNT(*) FROM (
            SELECT asset_id, d FROM fact_sentiment_daily GROUP BY asset_id, d HAVING COUNT(*) > 1
        ) t
    """)).scalar()
    # Pairwise anti-join against ACCEPTED_ANOMALIES — matching on (ticker, d)
    # together, so accepting one ticker/date pair never accidentally excuses a
    # different ticker that happens to share the date.
    acc_tickers, acc_dates = _accepted_pairs("non_positive_close_price")
    non_positive_close = conn.execute(
        text("""
            SELECT COUNT(*)
            FROM fact_price_daily p
            JOIN dim_asset a ON a.asset_id = p.asset_id
            WHERE p.close IS NOT NULL AND p.close <= 0
              AND NOT EXISTS (
                  SELECT 1
                  FROM unnest(CAST(:acc_tickers AS text[]), CAST(:acc_dates AS date[]))
                       AS acc(ticker, d)
                  WHERE acc.ticker = a.ticker AND acc.d = p.d
              )
        """),
        {"acc_tickers": acc_tickers, "acc_dates": acc_dates},
    ).scalar()
    # A row can exist with a real close price but still have return_1d = NULL
    # (e.g. a partial-range ingest whose first row has no visible previous
    # close) — that silently breaks any rolling feature downstream, like
    # volatility_20 in src/transform/technical_indicators.py, for the next 20
    # rows after the gap. Excludes each ticker's very first row, which
    # legitimately has no prior close to diff against. Found the hard way:
    # see backfill_price_returns.py.
    null_return_with_close = conn.execute(text("""
        SELECT COUNT(*) FROM (
            SELECT asset_id, d, close, return_1d,
                   MIN(d) OVER (PARTITION BY asset_id) AS first_d
            FROM fact_price_daily
        ) t
        WHERE close IS NOT NULL AND return_1d IS NULL AND d <> first_d
    """)).scalar()
    return {
        "news_duplicates": int(dup or 0),
        "price_null_close": int(null_close or 0),
        "sentiment_out_of_range": int(out_of_range or 0),
        "synthetic_news_contamination": int(synthetic_contamination or 0),
        "duplicate_price_rows": int(duplicate_price_rows or 0),
        "duplicate_sentiment_rows": int(duplicate_sentiment_rows or 0),
        "non_positive_close_price": int(non_positive_close or 0),
        "price_null_return_with_close": int(null_return_with_close or 0),
    }


def run_accepted_anomalies_report(conn: Connection) -> pd.DataFrame:
    """The ACCEPTED_ANOMALIES rows as they currently exist in the DB, so the
    report can show what is being excused rather than hiding it. A row that
    no longer exists shows up with a null close, which is itself worth
    noticing — it means the underlying data changed and the entry may be
    stale."""
    if not ACCEPTED_ANOMALIES:
        return pd.DataFrame(columns=["check", "ticker", "d", "close", "reason"])

    frames = []
    for a in ACCEPTED_ANOMALIES:
        row = conn.execute(
            text("""
                SELECT p.close
                FROM fact_price_daily p
                JOIN dim_asset a ON a.asset_id = p.asset_id
                WHERE a.ticker = :ticker AND p.d = CAST(:d AS date)
            """),
            {"ticker": a["ticker"], "d": a["d"]},
        ).fetchone()
        frames.append({
            "check": a["check"],
            "ticker": a["ticker"],
            "d": a["d"],
            "close": float(row[0]) if row and row[0] is not None else None,
            "reason": a["reason"],
        })
    return pd.DataFrame(frames)


def run_price_anomaly_check(conn: Connection, threshold_pct: float = 40.0) -> pd.DataFrame:
    """Day-over-day price moves larger than `threshold_pct` (default 40%) —
    usually a vendor data error (bad tick, unadjusted split) rather than a
    real move, for anything other than the most volatile crypto pairs.
    Surfaced for manual review rather than auto-dropped, since occasionally
    it's real (a genuine earnings-day gap) and dropping it silently would be
    its own kind of data fabrication by omission."""
    return pd.read_sql(
        text("""
            SELECT a.ticker, p.d, p.close, p.pct_change
            FROM fact_price_daily p
            JOIN dim_asset a ON a.asset_id = p.asset_id
            WHERE p.pct_change IS NOT NULL AND ABS(p.pct_change) > :threshold_pct
            ORDER BY ABS(p.pct_change) DESC
        """),
        conn,
        params={"threshold_pct": threshold_pct},
    )


def run_technical_gap_check(conn: Connection, window_days: int = 30) -> pd.DataFrame:
    """Trading days with a price row but no matching fact_technical_daily row
    in the last `window_days` — signals the technical-indicator job silently
    fell behind the price ETL for that ticker. Matters because every model in
    src/models/predict.py depends on fact_technical_daily; a silent gap there
    quietly shrinks the usable training/backtest window without anyone
    noticing until the numbers look off."""
    return pd.read_sql(
        text("""
            SELECT a.ticker, COUNT(*) AS missing_technical_days
            FROM fact_price_daily p
            JOIN dim_asset a ON a.asset_id = p.asset_id
            LEFT JOIN fact_technical_daily t ON t.asset_id = p.asset_id AND t.d = p.d
            WHERE p.d >= (CURRENT_DATE - (:window_days || ' days')::interval)
              AND t.asset_id IS NULL
            GROUP BY a.ticker
            HAVING COUNT(*) > 0
            ORDER BY missing_technical_days DESC
        """),
        conn,
        params={"window_days": window_days},
    )


def run_coverage_check(conn: Connection, window_days: int = 7) -> pd.DataFrame:
    """Per-ticker count of trading days in the last `window_days` with zero real (rss) news.

    Surfaces how thin the real-news sample is per ticker — the ETL run summary
    should make this visible rather than let it hide inside a correlation p-value.
    """
    return pd.read_sql(
        text("""
            SELECT a.ticker,
                   COUNT(*) AS trading_days,
                   COUNT(*) FILTER (WHERE n.news_count IS NULL OR n.news_count = 0) AS zero_news_days
            FROM fact_price_daily p
            JOIN dim_asset a ON a.asset_id = p.asset_id
            LEFT JOIN (
                SELECT f.asset_id, f.published_d, COUNT(*) AS news_count
                FROM fact_news f
                JOIN dim_source s ON s.source_id = f.source_id
                WHERE s.source_type = 'rss'
                GROUP BY f.asset_id, f.published_d
            ) n ON n.asset_id = p.asset_id AND n.published_d = p.d
            WHERE p.d >= (CURRENT_DATE - (:window_days || ' days')::interval)
            GROUP BY a.ticker
            ORDER BY zero_news_days DESC
        """),
        conn,
        params={"window_days": window_days},
    )


def main() -> None:
    """On-demand full DQ report — run this before trusting any backtest/
    correlation number enough to write it into the thesis, not just after
    each daily ETL run.

    Usage:
        python -m src.dq.checks
    """
    from src.config import Settings
    from src.common.db import get_engine

    settings = Settings()
    engine = get_engine(settings)

    with engine.connect() as conn:
        basic = run_basic_checks(conn)
        accepted = run_accepted_anomalies_report(conn)
        price_anomalies = run_price_anomaly_check(conn)
        technical_gaps = run_technical_gap_check(conn)
        coverage = run_coverage_check(conn, window_days=7)

    print("=== Basic checks ===")
    all_zero = True
    for name, value in basic.items():
        status = "OK" if value == 0 else "FAIL"
        if value != 0:
            all_zero = False
        print(f"  {name:<28} {value:>6}  [{status}]")
    print(f"  overall: {'PASS' if all_zero else 'FAIL — investigate before trusting downstream numbers'}")

    if not accepted.empty:
        print("\n=== Accepted anomalies (excluded from the counts above) ===")
        for _, r in accepted.iterrows():
            close = "MISSING — entry may be stale" if r["close"] is None else f"close={r['close']}"
            print(f"  [{r['check']}] {r['ticker']} {r['d']}  {close}")
            print(f"      {r['reason']}")

    print("\n=== Price anomalies (|day-over-day change| > 40%) ===")
    if price_anomalies.empty:
        print("  none")
    else:
        print(price_anomalies.to_string(index=False))

    print("\n=== Technical indicator gaps (last 30 days) ===")
    if technical_gaps.empty:
        print("  none — fact_technical_daily is caught up with fact_price_daily")
    else:
        print(technical_gaps.to_string(index=False))

    print("\n=== News coverage (last 7 days) ===")
    thin = coverage[coverage["zero_news_days"] >= coverage["trading_days"]] if not coverage.empty else coverage
    if thin.empty:
        print("  every ticker had at least one real news day in the last 7 days")
    else:
        print(f"  {len(thin)} ticker(s) with ZERO real news in the last 7 days: {thin['ticker'].tolist()}")


if __name__ == "__main__":
    main()
