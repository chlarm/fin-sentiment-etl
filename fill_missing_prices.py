#!/usr/bin/env python3
"""
fill_missing_prices.py  (v3)
────────────────────────────
เติมราคาที่หายไปโดยใช้ข้อมูลจริงเท่านั้น:
  1. ดึงจาก Stooq (bulk, ไม่โดน rate limit)
  2. fallback Yahoo Finance สำหรับ ticker ที่ Stooq ไม่รองรับ
  3. วันที่ยังหาข้อมูลจริงไม่ได้ -> ข้าม (ไม่สร้างราคาปลอม)

Usage:
    python fill_missing_prices.py --start 2026-03-18 --end 2026-06-13
    python fill_missing_prices.py --start 2026-03-18 --end 2026-06-13 --dry-run
"""

import argparse
import io
import os
import time
from datetime import date, timedelta

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

# ── DB ─────────────────────────────────────────────────────────────────────────
engine = create_engine(
    f"postgresql+psycopg2://"
    f"{os.getenv('POSTGRES_USER','fin')}:{os.getenv('POSTGRES_PASSWORD','fin')}"
    f"@{os.getenv('POSTGRES_HOST','localhost')}:{os.getenv('POSTGRES_PORT','5432')}"
    f"/{os.getenv('POSTGRES_DB','fin_dw')}"
)

# Stooq symbol mapping
STOOQ_MAP = {
    "GC=F":     "xauusd",
    "BTC-USD":  "btcusd",
    "EURUSD=X": "eurusd",
    "THBUSD=X": None,   # Stooq ไม่มี THB/USD → ใช้ Yahoo
}


def stooq_symbol(ticker: str) -> str | None:
    t = ticker.upper()
    if t in STOOQ_MAP:
        return STOOQ_MAP[t]
    if "=X" in t:
        return None     # forex อื่น → ใช้ Yahoo
    return f"{t.lower()}.us"


def fetch_stooq(ticker: str, start: date, end: date) -> dict[date, dict]:
    sym = stooq_symbol(ticker)
    if not sym:
        return {}
    url = f"https://stooq.com/q/d/l/?s={sym}&d1={start.strftime('%Y%m%d')}&d2={end.strftime('%Y%m%d')}&i=d"
    try:
        r = requests.get(url, timeout=20)
        if r.status_code != 200 or "No data" in r.text or "Page not found" in r.text:
            return {}
        df = pd.read_csv(io.StringIO(r.text))
        if df.empty or "Close" not in df.columns:
            return {}
        df = df.rename(columns={"Date":"d","Open":"open","High":"high",
                                 "Low":"low","Close":"close","Volume":"volume"})
        df["d"] = pd.to_datetime(df["d"]).dt.date
        df["adj_close"] = df["close"]
        df["volume"] = df.get("volume", 0).fillna(0).astype(int)
        df = df.dropna(subset=["close"])
        # compute returns
        df = df.sort_values("d")
        df["return_1d"] = df["close"].pct_change()
        df["pct_change"] = df["return_1d"] * 100
        return {row["d"]: row.to_dict() for _, row in df.iterrows()}
    except Exception as ex:
        print(f"    ⚠️  Stooq error ({ticker}): {ex}")
        return {}


def fetch_yahoo(ticker: str, start: date, end: date) -> dict[date, dict]:
    try:
        dl = yf.download(
            tickers=ticker,
            start=(start - timedelta(days=5)).isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            interval="1d",
            auto_adjust=False,
            progress=False,
        )
        if dl.empty:
            return {}
        if isinstance(dl.columns, pd.MultiIndex):
            dl = dl[ticker] if ticker in dl.columns.get_level_values(0) else dl
        dl = dl.reset_index().rename(columns={
            "Date":"d","Open":"open","High":"high","Low":"low",
            "Close":"close","Adj Close":"adj_close","Volume":"volume"
        })
        dl["d"] = pd.to_datetime(dl["d"]).dt.date
        dl = dl.dropna(subset=["close"]).sort_values("d")
        dl["return_1d"] = dl["close"].pct_change()
        dl["pct_change"] = dl["return_1d"] * 100
        return {row["d"]: row.to_dict() for _, row in dl.iterrows()}
    except Exception as ex:
        print(f"    ⚠️  Yahoo error ({ticker}): {ex}")
        return {}


def ensure_dim_date(conn, d: date):
    conn.execute(text("""
        INSERT INTO dim_date(d,y,m,day,dow,is_weekend)
        VALUES(:d,:y,:m,:day,:dow,:iw)
        ON CONFLICT(d) DO NOTHING
    """), {"d":d,"y":d.year,"m":d.month,"day":d.day,
           "dow":d.isoweekday(),"iw":d.isoweekday()>=6})


def upsert(asset_id: int, d: date, row: dict, label: str, dry_run: bool):
    tag = f"[{label}]"
    if dry_run:
        print(f"    {tag} {d}  close={row['close']:.4f}")
        return
    with engine.begin() as conn:
        ensure_dim_date(conn, d)
        conn.execute(text("""
            INSERT INTO fact_price_daily
              (asset_id,d,open,high,low,close,adj_close,volume,return_1d,pct_change)
            VALUES(:aid,:d,:o,:h,:l,:c,:ac,:v,:r,:p)
            ON CONFLICT(asset_id,d) DO UPDATE SET
              open=EXCLUDED.open,high=EXCLUDED.high,low=EXCLUDED.low,
              close=EXCLUDED.close,adj_close=EXCLUDED.adj_close,
              volume=EXCLUDED.volume,return_1d=EXCLUDED.return_1d,
              pct_change=EXCLUDED.pct_change,updated_at=now()
        """), {"aid":asset_id,"d":d,
               "o":row["open"],"h":row["high"],"l":row["low"],
               "c":row["close"],"ac":row.get("adj_close",row["close"]),
               "v":int(row.get("volume",0) or 0),
               "r":row.get("return_1d"),"p":row.get("pct_change")})
    print(f"    ✅ {tag} {d}  close={row['close']:.4f}")


def get_asset_id(ticker: str) -> int:
    with engine.connect() as conn:
        r = conn.execute(text("SELECT asset_id FROM dim_asset WHERE ticker=:t"),
                         {"t": ticker}).fetchone()
    if not r:
        raise ValueError(f"Ticker {ticker} ไม่พบใน dim_asset")
    return r[0]


def get_existing_dates(ticker: str, start: date, end: date) -> set[date]:
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT p.d FROM fact_price_daily p
            JOIN dim_asset a ON a.asset_id=p.asset_id
            WHERE a.ticker=:t AND p.d>=:s AND p.d<=:e
        """), {"t":ticker,"s":start,"e":end}).fetchall()
    return {r[0] for r in rows}


def fill_ticker(ticker: str, start: date, end: date, dry_run: bool):
    print(f"\n{'─'*60}")
    print(f"📊  {ticker}")

    asset_id = get_asset_id(ticker)
    existing = get_existing_dates(ticker, start, end)
    all_bdays = list(pd.bdate_range(start, end).date)
    missing = sorted(d for d in all_bdays if d not in existing)

    if not missing:
        print("  ✔️  ไม่มีวันที่ขาด")
        return

    print(f"  🔍 ขาด {len(missing)} วัน ({missing[0]} → {missing[-1]})")

    # ── ดึงข้อมูลจริง ───────────────────────────────────────────────────────────
    print(f"  📥 ดึงจาก Stooq...")
    fetched = fetch_stooq(ticker, start - timedelta(days=5), end)
    print(f"     Stooq: {len(fetched)} วัน")

    if not fetched:
        print(f"  📥 Stooq ไม่มีข้อมูล → ลอง Yahoo Finance...")
        time.sleep(3)
        fetched = fetch_yahoo(ticker, start - timedelta(days=5), end)
        print(f"     Yahoo: {len(fetched)} วัน")

    n_real = n_skip = 0

    for d in missing:
        if d in fetched:
            upsert(asset_id, d, fetched[d], "real", dry_run)
            n_real += 1
        else:
            n_skip += 1

    print(f"\n  📈 สรุป {ticker}:")
    print(f"     จริง: {n_real} วัน")
    if n_skip:
        print(f"     ไม่มีข้อมูลจริง (ข้าม): {n_skip} วัน")
    if dry_run:
        print(f"     (dry-run — ยังไม่ได้ insert จริง)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start",   default="2026-03-18")
    parser.add_argument("--end",     default=str(date.today()))
    parser.add_argument("--tickers", default="AAPL,MSFT,TSLA,BTC-USD,EURUSD=X,THBUSD=X,GC=F")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    start   = date.fromisoformat(args.start)
    end     = date.fromisoformat(args.end)
    tickers = [t.strip() for t in args.tickers.split(",")]

    print(f"=== Fill Missing Prices v2: {start} → {end} ===")
    print(f"Tickers: {tickers}")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE INSERT'}\n")

    for ticker in tickers:
        fill_ticker(ticker, start, end, args.dry_run)
        time.sleep(2)

    print(f"\n{'═'*60}")
    print("=== เสร็จสิ้น! ===")


if __name__ == "__main__":
    main()
