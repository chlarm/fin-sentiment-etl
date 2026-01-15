from __future__ import annotations
from datetime import date, timedelta
from sqlalchemy import text
from sqlalchemy.engine import Connection

def ensure_assets(conn: Connection, tickers: list[str]) -> dict[str, int]:
    if not tickers:
        return {}

    conn.execute(
        text("""
        INSERT INTO dim_asset (ticker)
        VALUES (:ticker)
        ON CONFLICT (ticker) DO NOTHING
        """),
        [{"ticker": t} for t in tickers],
    )

    rows = conn.execute(
        text("SELECT asset_id, ticker FROM dim_asset WHERE ticker = ANY(:t)"),
        {"t": tickers},
    ).fetchall()

    return {r.ticker: int(r.asset_id) for r in rows}

def ensure_source(conn: Connection, source_name: str, source_type: str, base_url: str | None) -> int:
    conn.execute(
        text("""
        INSERT INTO dim_source (source_name, source_type, base_url)
        VALUES (:n, :t, :u)
        ON CONFLICT (source_name, source_type) DO NOTHING
        """),
        {"n": source_name, "t": source_type, "u": base_url},
    )
    row = conn.execute(
        text("SELECT source_id FROM dim_source WHERE source_name=:n AND source_type=:t"),
        {"n": source_name, "t": source_type},
    ).fetchone()
    if not row:
        raise RuntimeError("ensure_source failed")
    return int(row.source_id)

def ensure_dim_dates(conn: Connection, start_d: date, end_d: date) -> None:
    days = []
    d = start_d
    while d <= end_d:
        dow = d.isoweekday()
        days.append({
            "d": d,
            "y": d.year,
            "m": d.month,
            "day": d.day,
            "dow": dow,
            "is_weekend": dow in (6, 7),
        })
        d += timedelta(days=1)

    if not days:
        return

    conn.execute(
        text("""
        INSERT INTO dim_date (d, y, m, day, dow, is_weekend)
        VALUES (:d, :y, :m, :day, :dow, :is_weekend)
        ON CONFLICT (d) DO NOTHING
        """),
        days,
    )
