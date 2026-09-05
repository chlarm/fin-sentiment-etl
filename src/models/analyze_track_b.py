#!/usr/bin/env python3
"""
Track B (medium/long horizon, 1 quarter - 1 year): does a stock's fundamentals
(growth, margins, leverage, valuation) at the time its earnings were announced
correlate with its subsequent return?

Still deliberately a correlation/regression study, not a classifier like
Track A — see DATA_DECISIONS.md on why Q4 derivation was rejected; a chunk of
this panel's "quarters" are genuinely as-filed and clean, but treating a
6-feature linear fit as if it deserved SHAP-level interpretability would
overstate what a panel this size supports. That said, the panel itself is no
longer the ~106-row set this reasoning was originally written against — SEC
EDGAR brought it to 1,134 fundamentals rows and ~700-1,050 usable (ticker,
quarter) observations per horizon after joining to price history. The
multi-feature regression below is fit on real data now, which is exactly why
it needed the same discipline Track A already has: a chronological
train/test split and a baseline to beat, not an in-sample R^2 computed on
the same rows it was fit to (what this script reported until 2026-07-29,
labeled "indicative only" because it was — R^2 on training data always looks
better than the model actually generalizes, and doesn't say by how much).

Usage:
    python -m src.models.analyze_track_b
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

from src.config import Settings
from src.common.db import get_engine
from src.models.dataset_fundamentals import FUNDAMENTAL_FEATURES, build_fundamentals_panel

warnings.filterwarnings("ignore")

HORIZONS = [63, 126, 252]  # ~1 quarter, ~6 months, ~1 year (trading days)
MIN_N_FOR_STATS = 15

# Same convention as predict.py's TEST_FRACTION, for the same reason: fit only
# on the past, score only on the future.
TEST_FRACTION = 0.25
WF_N_FOLDS = 5
WF_MIN_FOLD_TEST = 20


def _sig_stars(p: float) -> str:
    if p < 0.01:
        return "***"
    if p < 0.05:
        return "**"
    if p < 0.10:
        return "*"
    return "ns"


def _chronological_split(df: pd.DataFrame, date_col: str, test_fraction: float):
    dates = sorted(df[date_col].unique())
    cutoff = dates[int(len(dates) * (1 - test_fraction))]
    return df[df[date_col] < cutoff], df[df[date_col] >= cutoff]


# Ratio features here are arithmetically correct and statistically
# pathological: dividing by a near-zero denominator produces values that are
# real but meaningless. Observed in this panel — P/E of 10,545 (AMZN 2023Q1,
# price 105 over trailing EPS of about a cent), EPS growth of -144, debt/equity
# of 133 (AMD 2015, near-zero book equity). Untreated, a single such row in a
# test split drove OLS to R^2 = -34, and Pearson r is nearly as fragile.
WINSOR_LIMITS = (0.01, 0.99)


def _winsorize_to(train: pd.DataFrame, frames: list[pd.DataFrame], cols: list[str]) -> list[pd.DataFrame]:
    """Clip `cols` to the TRAINING set's 1st/99th percentiles.

    Bounds come from train only. Taking them from the full panel would let the
    test period influence its own preprocessing — a mild leak, but the whole
    point of the chronological split is that nothing after the cutoff informs
    what happens before it.
    """
    lo = train[cols].quantile(WINSOR_LIMITS[0])
    hi = train[cols].quantile(WINSOR_LIMITS[1])
    out = []
    for f in frames:
        g = f.copy()
        g[cols] = g[cols].clip(lower=lo, upper=hi, axis=1)
        out.append(g)
    return out


def _baseline_r2(y_train: pd.Series, y_test: pd.Series) -> float:
    """R^2 of the simplest honest forecast: predict the training mean for
    every test row. Not zero in general — sklearn's R^2 always compares
    against the mean of whatever set is being scored, so this baseline only
    lands near 0 when the train and test means agree, and can go negative
    when they don't (which is itself informative: fundamentals-driven returns
    are not stationary across the panel's 2008-2026 span)."""
    baseline_pred = np.full(len(y_test), float(y_train.mean()))
    return float(r2_score(y_test, baseline_pred))


def _out_of_sample_ols(full: pd.DataFrame, target_col: str) -> dict | None:
    """Chronological train/test split for the multi-feature regression —
    replaces the old in-sample-only R^2 with the number that actually says
    whether the fit generalizes."""
    train, test = _chronological_split(full, "anchor_date", TEST_FRACTION)
    if len(train) < MIN_N_FOR_STATS or len(test) < MIN_N_FOR_STATS:
        return None

    train, test = _winsorize_to(train, [train, test], FUNDAMENTAL_FEATURES)
    X_train, y_train = train[FUNDAMENTAL_FEATURES], train[target_col]
    X_test, y_test = test[FUNDAMENTAL_FEATURES], test[target_col]

    model = LinearRegression().fit(X_train, y_train)
    train_r2 = float(model.score(X_train, y_train))
    test_r2 = float(r2_score(y_test, model.predict(X_test)))
    baseline_r2 = _baseline_r2(y_train, y_test)

    return {
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "train_r2": round(train_r2, 3),
        "test_r2": round(test_r2, 3),
        "baseline_r2": round(baseline_r2, 3),
        "beats_baseline": test_r2 > baseline_r2,
        "coefficients": {
            feat: round(float(coef), 4)
            for feat, coef in zip(FUNDAMENTAL_FEATURES, model.coef_)
        },
    }


def _walk_forward_r2(
    full: pd.DataFrame, target_col: str,
    n_folds: int = WF_N_FOLDS, min_fold_test: int = WF_MIN_FOLD_TEST,
) -> list[dict]:
    """Expanding-window folds, same construction as predict.py's
    _walk_forward_accuracies: fold i trains on everything up to a cutoff and
    tests on the next chronological slice. One 75/25 split can be a lucky or
    unlucky draw from a panel spanning three recessions and a pandemic; this
    is what shows whether the fit holds up across different stretches of it."""
    dates = sorted(full["anchor_date"].unique())
    n = len(dates)
    max_folds = max(1, (n // min_fold_test) - 1)
    n_folds = min(n_folds, max_folds)
    if n_folds < 1:
        return []

    segment = n // (n_folds + 1)
    results = []
    for i in range(1, n_folds + 1):
        train_end = dates[i * segment - 1]
        test_start_idx = i * segment
        test_end_idx = (i + 1) * segment if i < n_folds else n
        test_start = dates[test_start_idx]
        test_end = dates[test_end_idx - 1]

        train = full[full["anchor_date"] <= train_end]
        test = full[(full["anchor_date"] >= test_start) & (full["anchor_date"] <= test_end)]
        if len(train) < MIN_N_FOR_STATS or len(test) < min_fold_test:
            continue

        train, test = _winsorize_to(train, [train, test], FUNDAMENTAL_FEATURES)
        model = LinearRegression().fit(train[FUNDAMENTAL_FEATURES], train[target_col])
        test_r2 = float(r2_score(test[target_col], model.predict(test[FUNDAMENTAL_FEATURES])))
        baseline_r2 = _baseline_r2(train[target_col], test[target_col])
        results.append({
            "test_start": str(test_start),
            "test_end": str(test_end),
            "n_test": int(len(test)),
            "test_r2": round(test_r2, 3),
            "baseline_r2": round(baseline_r2, 3),
            "beats_baseline": test_r2 > baseline_r2,
        })
    return results


def _correlation_table(panel: pd.DataFrame, horizon: int):
    target_col = f"fwd_ret_{horizon}d"
    print(f"\n--- horizon = {horizon}d (~{horizon/21:.1f} months) ---")

    # Spearman leads because it ranks rather than measures: one P/E of 10,545
    # moves Pearson r substantially and moves a rank correlation by one place.
    # Pearson is printed alongside precisely so the gap is visible — where the
    # two disagree, the Pearson figure is being driven by a handful of rows.
    print(f"  {'feature':<20} {'n':>5} {'spearman':>9} {'p':>7}      {'pearson':>8} {'p':>7}")
    for feat in FUNDAMENTAL_FEATURES:
        sub = panel[[feat, target_col]].dropna()
        n = len(sub)
        if n < MIN_N_FOR_STATS:
            print(f"  {feat:<20} {n:>5}  (too small to test — need >= {MIN_N_FOR_STATS})")
            continue
        rho, p_rho = scipy_stats.spearmanr(sub[feat], sub[target_col])
        r, p_r = scipy_stats.pearsonr(sub[feat], sub[target_col])
        print(f"  {feat:<20} {n:>5} {rho:>+9.3f} {p_rho:>7.3f} {_sig_stars(p_rho):<4} "
              f"{r:>+8.3f} {p_r:>7.3f} {_sig_stars(p_r)}")

    # multi-feature linear regression, chronologically held out — see
    # _out_of_sample_ols for why this is no longer an in-sample number.
    full = panel[FUNDAMENTAL_FEATURES + [target_col, "anchor_date"]].dropna()
    oos = _out_of_sample_ols(full, target_col) if len(full) >= MIN_N_FOR_STATS * 2 else None

    if oos is None:
        need = MIN_N_FOR_STATS * 2
        print(f"  [multi-feature OLS] skipped — only {len(full)} rows with every feature present "
              f"(need >= {need} to hold out a chronological test split)")
        return

    beat = "beats" if oos["beats_baseline"] else "does not beat"
    print(f"  [multi-feature OLS] n_train={oos['n_train']} n_test={oos['n_test']}  "
          f"train_R^2={oos['train_r2']:.3f}  test_R^2={oos['test_r2']:.3f}  "
          f"baseline_R^2={oos['baseline_r2']:.3f}  ({beat} the train-mean baseline)")
    for feat, coef in oos["coefficients"].items():
        print(f"      {feat:<20} coef={coef:+.4f}")

    wf = _walk_forward_r2(full, target_col)
    if wf:
        r2s = [f["test_r2"] for f in wf]
        beating = sum(1 for f in wf if f["beats_baseline"])
        print(f"  [walk-forward, {len(wf)} folds] test_R^2 range {min(r2s):+.3f} to {max(r2s):+.3f} "
              f"(mean {np.mean(r2s):+.3f}) — {beating}/{len(wf)} folds beat their own baseline")
        for f in wf:
            print(f"      {f['test_start']} -> {f['test_end']}  n={f['n_test']:>4}  "
                  f"test_R^2={f['test_r2']:+.3f}  baseline={f['baseline_r2']:+.3f}  "
                  f"{'beats' if f['beats_baseline'] else 'does not beat'}")
    else:
        print(f"  [walk-forward] skipped — not enough chronological spread for "
              f"{WF_N_FOLDS} folds of >= {WF_MIN_FOLD_TEST} rows each")


def main() -> None:
    settings = Settings()
    engine = get_engine(settings)

    # only tickers that actually have fundamentals (stocks, not indices/forex/crypto/commodities)
    from sqlalchemy import text
    with engine.connect() as conn:
        stock_tickers = pd.read_sql(
            text("""
                SELECT DISTINCT a.ticker FROM fact_fundamentals_quarterly f
                JOIN dim_asset a ON a.asset_id = f.asset_id
            """), conn
        )["ticker"].tolist()

    print(f"Building fundamentals panel for {len(stock_tickers)} stocks: {stock_tickers}")
    panel = build_fundamentals_panel(engine, stock_tickers, HORIZONS)

    if panel.empty:
        print("No usable (fundamentals + price) rows found.")
        return

    print(f"Panel: {len(panel)} (ticker, quarter) rows, "
          f"{panel['fiscal_period_end'].min()} -> {panel['fiscal_period_end'].max()}")
    print(f"NOTE: this is a cross-sectional panel across {panel['ticker'].nunique()} stocks, "
          f"NOT a long per-ticker time series — treat every result below as exploratory.")

    for h in HORIZONS:
        _correlation_table(panel, h)


if __name__ == "__main__":
    main()
