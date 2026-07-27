"""Assembles notebooks/02_hypothesis_testing.ipynb via nbformat. Regenerate
with: python3 _build_hypothesis_testing.py (from the notebooks/ dir)."""
import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []

def md(text):
    cells.append(nbf.v4.new_markdown_cell(text))

def code(text):
    cells.append(nbf.v4.new_code_cell(text))

md("""# Formal Hypothesis Testing — Track A & Track B

This notebook reframes the exploratory results from `train_track_a.py` and `analyze_track_b.py`
as formal statistical hypothesis tests, each with an explicit H0/H1, a named test, and a decision
rule — rather than just reporting accuracy/correlation numbers on their own.

Three hypotheses, matching the two prediction tracks:

- **H1** (Track A, technical-only): do price/technical features alone predict direction better than
  chance/the naive baseline, on the full 10-year sample?
- **H2** (Track A, sentiment): does *adding* sentiment features change accuracy versus technical-only,
  on the identical sentiment-era test rows? (a **paired** comparison — same test cases, two models)
- **H3** (Track B, fundamentals): do any fundamental factors correlate with forward returns, once
  corrected for testing 18 factor/horizon combinations at once?
""")

code("""import warnings
warnings.filterwarnings("ignore")

import os
os.environ.setdefault("POSTGRES_HOST", "localhost")
import sys
sys.path.insert(0, "..")

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from statsmodels.stats.proportion import proportions_ztest
from statsmodels.stats.contingency_tables import mcnemar
from statsmodels.stats.multitest import multipletests
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.config import Settings
from src.common.db import get_engine
from src.models.dataset import (
    TECHNICAL_FEATURES, SENTIMENT_FEATURES,
    build_technical_dataset, build_sentiment_dataset, eligible_sentiment_tickers,
)
from src.models.dataset_fundamentals import FUNDAMENTAL_FEATURES, build_fundamentals_panel

settings = Settings()
engine = get_engine(settings)
ALPHA = 0.05
print(f"Significance level (alpha) used throughout: {ALPHA}")
""")

md("""## H1 — Technical-only model vs. the naive baseline (large sample, N ~ 19,000)

**H0:** the technical-only classifier's hit rate equals the majority-class baseline rate (i.e. the
model has no real skill beyond always guessing the more common direction).
**H1:** the hit rate differs from the majority-class baseline.

**Test:** one-sample proportion z-test — treats each test-set prediction as a Bernoulli trial
(correct/incorrect) and asks whether the observed correct-rate is statistically distinguishable
from the baseline rate, given the sample size.
""")

code("""def chronological_split(df, test_fraction=0.25):
    dates = sorted(df["d"].unique())
    cutoff = dates[int(len(dates) * (1 - test_fraction))]
    return df[df["d"] < cutoff], df[df["d"] >= cutoff]


tech_df = build_technical_dataset(engine, list(settings.tickers), horizons=[1, 5, 21])
h1_results = []

for h in [1, 5, 21]:
    target_col = f"target_dir_{h}d"
    clean = tech_df[TECHNICAL_FEATURES + [target_col, "d"]].dropna()
    train, test = chronological_split(clean)
    X_train, y_train = train[TECHNICAL_FEATURES], train[target_col].astype(int)
    X_test, y_test = test[TECHNICAL_FEATURES], test[target_col].astype(int)

    model = Pipeline([("scale", StandardScaler()),
                       ("clf", LogisticRegression(max_iter=1000, class_weight="balanced"))])
    model.fit(X_train, y_train)
    pred = model.predict(X_test)

    n_correct = int((pred == y_test).sum())
    n_test = len(y_test)
    baseline_p = max(y_test.mean(), 1 - y_test.mean())

    z_stat, p_value = proportions_ztest(count=n_correct, nobs=n_test, value=baseline_p)
    decision = "REJECT H0 (significant)" if p_value < ALPHA else "FAIL TO REJECT H0 (not significant)"

    h1_results.append({
        "horizon_days": h, "n_test": n_test, "hit_rate": n_correct / n_test,
        "baseline": baseline_p, "z_stat": z_stat, "p_value": p_value, "decision": decision,
    })

h1_df = pd.DataFrame(h1_results)
h1_df
""")

md("""**Reading this table:** a `p_value` here answers "how likely is this hit rate (or more extreme)
if the model truly had zero skill above baseline?" — it does *not* tell us whether the effect is big
enough to matter practically. With ~19,000 test rows, even a trivial 0.5 percentage-point edge can
reach statistical significance. So both columns matter: **is it significant, and is `hit_rate - baseline`
actually large enough to be useful?**""")

md("""## H2 — Does adding sentiment change accuracy? (paired comparison, same test rows)

**H0:** the technical-only and technical+sentiment classifiers make the same predictions equally
often correct/incorrect — i.e. sentiment features carry no additional information for this test set.
**H1:** the two models disagree in their correctness asymmetrically.

**Test:** McNemar's test — the correct test for comparing two classifiers on the *same* test cases
(unlike comparing two independent accuracy numbers, which ignores that the same rows were predicted
by both models and overstates the evidence). Only the rows where the two models *disagree* matter.
""")

code("""senti_tickers = eligible_sentiment_tickers(engine, min_days=30)
senti_df = build_sentiment_dataset(engine, senti_tickers, horizons=[1, 5, 21])
print(f"Sentiment-era dataset: {len(senti_df)} rows, tickers: {senti_tickers}")

h2_results = []

for h in [1, 5, 21]:
    target_col = f"target_dir_{h}d"
    cols_a = TECHNICAL_FEATURES
    cols_b = TECHNICAL_FEATURES + SENTIMENT_FEATURES
    clean = senti_df[cols_b + [target_col, "d"]].dropna()  # same rows for both models
    if len(clean) < 40:
        print(f"h={h}d: only {len(clean)} usable rows, skipping (too small for a meaningful test)")
        continue

    train, test = chronological_split(clean)
    y_train, y_test = train[target_col].astype(int), test[target_col].astype(int)

    model_a = Pipeline([("scale", StandardScaler()),
                         ("clf", LogisticRegression(max_iter=1000, class_weight="balanced"))])
    model_a.fit(train[cols_a], y_train)
    pred_a = model_a.predict(test[cols_a])

    model_b = Pipeline([("scale", StandardScaler()),
                         ("clf", LogisticRegression(max_iter=1000, class_weight="balanced"))])
    model_b.fit(train[cols_b], y_train)
    pred_b = model_b.predict(test[cols_b])

    correct_a = (pred_a == y_test.values)
    correct_b = (pred_b == y_test.values)

    # 2x2 contingency: [[both correct, A correct/B wrong], [A wrong/B correct, both wrong]]
    both_correct = int((correct_a & correct_b).sum())
    a_only = int((correct_a & ~correct_b).sum())
    b_only = int((~correct_a & correct_b).sum())
    both_wrong = int((~correct_a & ~correct_b).sum())
    table = [[both_correct, a_only], [b_only, both_wrong]]

    result = mcnemar(table, exact=(a_only + b_only) < 25, correction=True)
    decision = "REJECT H0 (sentiment changes predictions significantly)" if result.pvalue < ALPHA \\
        else "FAIL TO REJECT H0 (no significant difference)"

    h2_results.append({
        "horizon_days": h, "n_test": len(test),
        "hit_rate_technical_only": correct_a.mean(), "hit_rate_with_sentiment": correct_b.mean(),
        "n_disagree_A_right_B_wrong": a_only, "n_disagree_B_right_A_wrong": b_only,
        "mcnemar_stat": result.statistic, "p_value": result.pvalue, "decision": decision,
    })

h2_df = pd.DataFrame(h2_results)
h2_df
""")

md("""**Reading this table:** `n_disagree_*` columns are the actual evidence McNemar's test uses — if
sentiment were genuinely helping, we'd expect `n_disagree_B_right_A_wrong` (sentiment model fixes
technical-only's mistakes) to clearly outnumber `n_disagree_A_right_B_wrong` (sentiment model breaks
correct technical-only predictions). A p-value below 0.05 here is much stronger evidence of a real
sentiment effect than the earlier informal hit-rate comparison, precisely because it accounts for the
small sample properly instead of treating the two accuracy numbers as independent.""")

md("""## H3 — Do fundamental factors correlate with forward returns? (multiple-comparison corrected)

**H0:** a given fundamental factor has zero correlation with forward returns at a given horizon.
**H1:** the correlation is non-zero.

Testing 6 factors x 3 horizons = up to 18 hypotheses at once inflates the false-positive rate if each
is judged at the raw alpha=0.05 individually (expected ~0.9 false positives by chance alone). This
section applies the **Benjamini-Hochberg false discovery rate (FDR) correction** across all tests
simultaneously before drawing any conclusion — this is the step that was flagged as missing in the
original Track B analysis.
""")

code("""stock_tickers = pd.read_sql(
    "SELECT DISTINCT a.ticker FROM fact_fundamentals_quarterly f "
    "JOIN dim_asset a ON a.asset_id = f.asset_id", engine
)["ticker"].tolist()

panel = build_fundamentals_panel(engine, stock_tickers, horizons=[63, 126, 252])

h3_rows = []
for h in [63, 126, 252]:
    target_col = f"fwd_ret_{h}d"
    for feat in FUNDAMENTAL_FEATURES:
        sub = panel[[feat, target_col]].dropna()
        if len(sub) < 15:
            h3_rows.append({"horizon_days": h, "feature": feat, "n": len(sub), "r": np.nan, "p_raw": np.nan})
            continue
        r, p = scipy_stats.pearsonr(sub[feat], sub[target_col])
        h3_rows.append({"horizon_days": h, "feature": feat, "n": len(sub), "r": r, "p_raw": p})

h3_df = pd.DataFrame(h3_rows)

testable = h3_df.dropna(subset=["p_raw"]).copy()
reject, p_adj, _, _ = multipletests(testable["p_raw"], alpha=ALPHA, method="fdr_bh")
testable["p_fdr_adjusted"] = p_adj
testable["significant_after_correction"] = reject

h3_df = h3_df.merge(
    testable[["horizon_days", "feature", "p_fdr_adjusted", "significant_after_correction"]],
    on=["horizon_days", "feature"], how="left"
)
n_raw_sig = (h3_df["p_raw"] < ALPHA).sum()
n_fdr_sig = h3_df["significant_after_correction"].sum()
print(f"Significant at raw alpha=0.05: {n_raw_sig} / {len(testable)} testable combos")
print(f"Significant after Benjamini-Hochberg FDR correction: {n_fdr_sig} / {len(testable)}")
h3_df.sort_values("p_raw")
""")

md("""**Reading this table:** compare `n_raw_sig` (how many looked significant before correction) to
`n_fdr_sig` (how many survive once we account for running 18 tests at once). If a factor's finding
disappears after correction, that's the multiple-comparison problem in action — exactly why this
step matters for defending the Track B conclusion.""")

md("""## Summary: hypothesis test outcomes

| Hypothesis | Question | Outcome |
|---|---|---|
| H1 | Do technical indicators alone beat baseline? (N~19k, all 30 tickers) | See H1 table — decision per horizon |
| H2 | Does adding sentiment change predictions? (paired, N~30-40 per horizon) | See H2 table — decision per horizon |
| H3 | Do fundamentals correlate with forward returns? (FDR-corrected, 18 tests) | See H3 table — count surviving correction |

This notebook turns the earlier exploratory numbers into defensible statistical claims: every
conclusion here has a named test, an explicit null hypothesis, and — for H3 specifically — proper
correction for testing many things at once. The next natural step is model interpretability (e.g.
SHAP on the gradient-boosting model) to explain *why* the models that do show signal make the
predictions they do.
""")

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3 (fin-sentiment-etl-2)", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.13"},
}

with open("02_hypothesis_testing.ipynb", "w") as f:
    nbf.write(nb, f)

print("Wrote 02_hypothesis_testing.ipynb")
