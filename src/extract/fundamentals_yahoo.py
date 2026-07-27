from __future__ import annotations
from datetime import date
import pandas as pd
import yfinance as yf


def _row_val(df: pd.DataFrame, row_name: str, col) -> float | None:
    if df.empty or row_name not in df.index or col not in df.columns:
        return None
    v = df.loc[row_name, col]
    return None if pd.isna(v) else float(v)


def _nearest_announced_date(period_end: date, earnings_dates: pd.DataFrame) -> date | None:
    """The earnings report for a fiscal quarter is announced shortly AFTER the
    period ends (usually 2-6 weeks later). Pick the earliest announcement date
    that falls after period_end, within a reasonable window, as the
    point-in-time anchor — this is when the numbers actually became public."""
    if earnings_dates is None or earnings_dates.empty:
        return None
    candidates = [
        d.date() for d in earnings_dates.index
        if d.date() >= period_end and (d.date() - period_end).days <= 90
    ]
    return min(candidates) if candidates else None


def fetch_quarterly_fundamentals(ticker: str) -> list[dict]:
    """Real quarterly fundamentals only — returns [] (not fabricated rows) for
    tickers yfinance has no statement data for (e.g. indices, forex, commodities,
    crypto don't file financial statements)."""
    tk = yf.Ticker(ticker)

    try:
        income = tk.quarterly_financials
        balance = tk.quarterly_balance_sheet
        cashflow = tk.quarterly_cashflow
    except Exception as e:
        print(f"[fundamentals][{ticker}] failed to fetch statements: {e}")
        return []

    if income is None or income.empty:
        return []

    try:
        earnings_dates = tk.get_earnings_dates(limit=40)
    except Exception:
        earnings_dates = None

    rows: list[dict] = []
    for col in income.columns:
        period_end = col.date() if hasattr(col, "date") else col

        revenue = _row_val(income, "Total Revenue", col)
        net_income = _row_val(income, "Net Income", col)
        eps_diluted = _row_val(income, "Diluted EPS", col)
        gross_profit = _row_val(income, "Gross Profit", col)
        gross_margin = (gross_profit / revenue) if (gross_profit is not None and revenue) else None
        net_margin = (net_income / revenue) if (net_income is not None and revenue) else None

        total_debt = _row_val(balance, "Total Debt", col)
        stockholders_equity = _row_val(balance, "Stockholders Equity", col)
        free_cash_flow = _row_val(cashflow, "Free Cash Flow", col)

        if revenue is None and net_income is None and eps_diluted is None:
            continue  # no real data for this period — skip, don't fake it

        rows.append({
            "ticker": ticker,
            "fiscal_period_end": period_end,
            "announced_d": _nearest_announced_date(period_end, earnings_dates),
            "revenue": revenue,
            "net_income": net_income,
            "eps_diluted": eps_diluted,
            "gross_margin": gross_margin,
            "net_margin": net_margin,
            "total_debt": total_debt,
            "stockholders_equity": stockholders_equity,
            "free_cash_flow": free_cash_flow,
        })

    return rows
