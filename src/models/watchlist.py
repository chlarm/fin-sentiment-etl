"""
Watchlist: tickers the user asked the dashboard to monitor, plus a log of
every signal check so a flip (UP -> DOWN or vice versa) can be detected and
optionally emailed — turning the Signal tab from something you have to
remember to check into something that tells you when it changes.
"""
from __future__ import annotations
from sqlalchemy import text
from sqlalchemy.engine import Engine

from src.alerting import send_email_alert


def list_watchlist(engine: Engine) -> list[str]:
    sql = """
    SELECT a.ticker FROM dim_watchlist w
    JOIN dim_asset a ON a.asset_id = w.asset_id
    ORDER BY w.added_at DESC
    """
    with engine.connect() as conn:
        return [r[0] for r in conn.execute(text(sql))]


def add_to_watchlist(engine: Engine, ticker: str) -> None:
    sql = """
    INSERT INTO dim_watchlist (asset_id)
    SELECT asset_id FROM dim_asset WHERE ticker = :ticker
    ON CONFLICT (asset_id) DO NOTHING
    """
    with engine.begin() as conn:
        conn.execute(text(sql), {"ticker": ticker})


def remove_from_watchlist(engine: Engine, ticker: str) -> None:
    sql = """
    DELETE FROM dim_watchlist
    WHERE asset_id = (SELECT asset_id FROM dim_asset WHERE ticker = :ticker)
    """
    with engine.begin() as conn:
        conn.execute(text(sql), {"ticker": ticker})


def _last_logged_signal(engine: Engine, ticker: str) -> str | None:
    sql = """
    SELECT l.signal
    FROM fact_watchlist_signal_log l
    JOIN dim_asset a ON a.asset_id = l.asset_id
    WHERE a.ticker = :ticker
    ORDER BY l.checked_at DESC
    LIMIT 1
    """
    with engine.connect() as conn:
        row = conn.execute(text(sql), {"ticker": ticker}).fetchone()
    return row[0] if row else None


def _log_signal(engine: Engine, ticker: str, signal: str, confidence: float) -> None:
    sql = """
    INSERT INTO fact_watchlist_signal_log (asset_id, signal, confidence)
    SELECT asset_id, :signal, :confidence FROM dim_asset WHERE ticker = :ticker
    """
    with engine.begin() as conn:
        conn.execute(text(sql), {"ticker": ticker, "signal": signal, "confidence": confidence})


def check_signal_change(engine: Engine, ticker: str, prediction: dict) -> dict:
    """Compare today's signal against the last logged one for this ticker.
    Logs the current signal (so the next check has something to compare
    against) and emails an alert if it flipped. Returns the prediction dict
    augmented with `previous_signal` / `changed`."""
    signal = prediction["latest_signal"]
    confidence = prediction["latest_confidence"]
    previous = _last_logged_signal(engine, ticker)
    changed = previous is not None and previous != signal

    if previous is None or changed:
        _log_signal(engine, ticker, signal, confidence)

    if changed:
        send_email_alert(
            subject=f"[FinSentiment] {ticker} signal flipped to {signal}",
            body=(
                f"{ticker} model signal changed from {previous} to {signal} "
                f"({confidence:.0%} confidence) as of {prediction['latest_date']}."
            ),
        )

    return {**prediction, "previous_signal": previous, "changed": changed}
