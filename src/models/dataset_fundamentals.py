from __future__ import annotations
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

FUNDAMENTAL_FEATURES = [
    "revenue_growth_qoq", "eps_growth_qoq", "net_margin", "margin_delta_qoq",
    "debt_to_equity", "pe_ratio",
]


def _nearest_price_on_or_after(price_series: pd.Series, target_date) -> tuple:
    """price_series: index=date, values=close, sorted ascending, for one ticker.
    Returns (date_used, close) for the first trading day >= target_date, or
    (None, None) if there isn't one yet (e.g. announcement is too recent)."""
    idx = price_series.index.searchsorted(target_date)
    if idx >= len(price_series):
        return None, None
    return price_series.index[idx], price_series.iloc[idx]


def _price_n_trading_days_after(price_series: pd.Series, anchor_date, n: int) -> float | None:
    idx = price_series.index.searchsorted(anchor_date)
    target_idx = idx + n
    if target_idx >= len(price_series):
        return None
    return price_series.iloc[target_idx]


def build_fundamentals_panel(engine: Engine, tickers: list[str], horizons: list[int]) -> pd.DataFrame:
    """One row per (ticker, fiscal_period_end) with growth/valuation features and
    forward-return targets at each horizon, anchored at the real announcement
    date (announced_d) — never fiscal_period_end — to avoid lookahead bias."""
    with engine.connect() as conn:
        fund = pd.read_sql(
            text("""
                SELECT a.ticker, f.fiscal_period_end, f.announced_d, f.revenue, f.net_income,
                       f.eps_diluted, f.gross_margin, f.net_margin, f.total_debt,
                       f.stockholders_equity, f.free_cash_flow
                FROM fact_fundamentals_quarterly f
                JOIN dim_asset a ON a.asset_id = f.asset_id
                WHERE a.ticker = ANY(:tickers) AND f.announced_d IS NOT NULL
                ORDER BY a.ticker, f.fiscal_period_end
            """),
            conn, params={"tickers": tickers},
        )
        price = pd.read_sql(
            text("""
                SELECT a.ticker, p.d, p.close
                FROM fact_price_daily p
                JOIN dim_asset a ON a.asset_id = p.asset_id
                WHERE a.ticker = ANY(:tickers) AND p.close IS NOT NULL
                ORDER BY a.ticker, p.d
            """),
            conn, params={"tickers": tickers},
        )

    if fund.empty or price.empty:
        return pd.DataFrame()

    fund = fund.sort_values(["ticker", "fiscal_period_end"]).copy()
    fund["revenue_growth_qoq"] = fund.groupby("ticker")["revenue"].pct_change()
    fund["eps_growth_qoq"] = fund.groupby("ticker")["eps_diluted"].pct_change()
    fund["margin_delta_qoq"] = fund.groupby("ticker")["net_margin"].diff()
    fund["debt_to_equity"] = fund["total_debt"] / fund["stockholders_equity"]

    # trailing-4Q EPS (or however many quarters we actually have) for a point-in-time P/E
    fund["eps_ttm"] = fund.groupby("ticker")["eps_diluted"].transform(
        lambda s: s.rolling(4, min_periods=2).sum()
    )

    price_by_ticker = {t: g.set_index("d")["close"] for t, g in price.groupby("ticker")}

    rows = []
    for r in fund.itertuples(index=False):
        pser = price_by_ticker.get(r.ticker)
        if pser is None or pser.empty:
            continue
        anchor_date, anchor_price = _nearest_price_on_or_after(pser, r.announced_d)
        if anchor_date is None:
            continue

        pe_ratio = (anchor_price / r.eps_ttm) if (r.eps_ttm and r.eps_ttm > 0) else None

        row = {
            "ticker": r.ticker,
            "fiscal_period_end": r.fiscal_period_end,
            "announced_d": r.announced_d,
            "anchor_date": anchor_date,
            "anchor_price": anchor_price,
            "revenue_growth_qoq": r.revenue_growth_qoq,
            "eps_growth_qoq": r.eps_growth_qoq,
            "net_margin": r.net_margin,
            "margin_delta_qoq": r.margin_delta_qoq,
            "debt_to_equity": r.debt_to_equity,
            "pe_ratio": pe_ratio,
        }
        for h in horizons:
            future_price = _price_n_trading_days_after(pser, anchor_date, h)
            row[f"fwd_ret_{h}d"] = (future_price / anchor_price - 1) if future_price is not None else None
        rows.append(row)

    return pd.DataFrame(rows)
