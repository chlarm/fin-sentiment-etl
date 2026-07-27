"""Assembles notebooks/03_shap_interpretability.ipynb via nbformat. Regenerate
with: python3 _build_shap_interpretability.py (from the notebooks/ dir)."""
import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []

def md(text):
    cells.append(nbf.v4.new_markdown_cell(text))

def code(text):
    cells.append(nbf.v4.new_code_cell(text))

md("""# SHAP Interpretability — why did the technical-only model lose to baseline?

`02_hypothesis_testing.ipynb` found something specific and non-obvious under **H1**: the
technical-only gradient-boosting classifier's hit rate was **significantly *worse*** than the naive
majority-class baseline at every horizon (p < 1e-8), not just "no better." This notebook asks *why*,
using SHAP (SHapley Additive exPlanations) on the same model setup from `src/models/train_track_a.py`.

Two honestly different stories are possible here, and this notebook doesn't presuppose which one is
true:
1. The model found **no real per-feature signal at all** (SHAP values near zero, flat importances) —
   consistent with "there's nothing here to find."
2. The model **did** pick up some feature-driven pattern (non-trivial SHAP importances), but that
   pattern happens to be wrong more often than the trivial "always predict up" bet — a more
   interesting failure mode than "no signal."
""")

code("""import warnings
warnings.filterwarnings("ignore")

import os
os.environ.setdefault("POSTGRES_HOST", "localhost")
import sys
sys.path.insert(0, "..")

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import shap
from sklearn.ensemble import HistGradientBoostingClassifier

from src.config import Settings
from src.common.db import get_engine
from src.models.dataset import TECHNICAL_FEATURES, build_technical_dataset

settings = Settings()
engine = get_engine(settings)

HORIZON = 21  # the horizon with the strongest (most significant) H1 result
SAMPLE_SIZE = 3000  # rows to compute SHAP on -- TreeExplainer is fast enough for this comfortably
""")

md("## Reproduce the exact H1 model setup (horizon = 21d)")

code("""tech_df = build_technical_dataset(engine, list(settings.tickers), horizons=[HORIZON])
target_col = f"target_dir_{HORIZON}d"
clean = tech_df[TECHNICAL_FEATURES + [target_col, "d"]].dropna()

dates = sorted(clean["d"].unique())
cutoff = dates[int(len(dates) * 0.75)]
train = clean[clean["d"] < cutoff]
test = clean[clean["d"] >= cutoff]

X_train, y_train = train[TECHNICAL_FEATURES], train[target_col].astype(int)
X_test, y_test = test[TECHNICAL_FEATURES], test[target_col].astype(int)

model = HistGradientBoostingClassifier(max_iter=200, max_depth=4, class_weight="balanced", random_state=42)
model.fit(X_train, y_train)

pred = model.predict(X_test)
hit_rate = (pred == y_test).mean()
baseline = max(y_test.mean(), 1 - y_test.mean())
print(f"n_train={len(train)}  n_test={len(test)}")
print(f"hit_rate={hit_rate:.4f}   majority_baseline={baseline:.4f}   (matches 02_hypothesis_testing.ipynb's H1 row)")
""")

md("## SHAP values on a sample of the test set")

code("""rng = np.random.default_rng(42)
sample_idx = rng.choice(len(X_test), size=min(SAMPLE_SIZE, len(X_test)), replace=False)
X_sample = X_test.iloc[sample_idx]

explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_sample)

# HistGradientBoostingClassifier binary case: TreeExplainer returns values for the positive class
sv = shap_values[1] if isinstance(shap_values, list) else shap_values
print(f"SHAP values computed for {len(X_sample)} test rows x {len(TECHNICAL_FEATURES)} features")
print(f"Mean |SHAP value| across everything: {np.abs(sv).mean():.5f}")
""")

code("""shap.summary_plot(sv, X_sample, feature_names=TECHNICAL_FEATURES, show=False)
plt.title(f"SHAP beeswarm -- horizon={HORIZON}d technical-only model")
plt.tight_layout()
plt.show()
""")

code("""importance = pd.DataFrame({
    "feature": TECHNICAL_FEATURES,
    "mean_abs_shap": np.abs(sv).mean(axis=0),
}).sort_values("mean_abs_shap", ascending=False)

fig, ax = plt.subplots(figsize=(8, 4))
ax.barh(importance["feature"], importance["mean_abs_shap"], color="steelblue")
ax.invert_yaxis()
ax.set_xlabel("Mean |SHAP value| (impact on predicted log-odds)")
ax.set_title("Feature importance by mean absolute SHAP value")
plt.tight_layout()
plt.show()
importance
""")

md("## Does the model's confidence itself carry any information?")

code("""proba = model.predict_proba(X_sample)[:, 1]
fig, ax = plt.subplots(figsize=(9, 4.5))
ax.hist(proba, bins=40, color="darkorange", alpha=0.8)
ax.axvline(0.5, color="black", linestyle="--", label="50/50 (no confidence either way)")
ax.set_xlabel("Predicted probability of 'up'")
ax.set_title("Distribution of model confidence on the test sample")
ax.legend()
plt.show()

print(f"Predicted probability: min={proba.min():.3f}  max={proba.max():.3f}  std={proba.std():.4f}")
print(f"Share of predictions within +/-0.05 of a coin flip (0.45-0.55): {((proba > 0.45) & (proba < 0.55)).mean():.1%}")
""")

md("""## Interpretation

Read the actual numbers above (mean |SHAP|, the beeswarm spread, and the predicted-probability
histogram) before concluding anything — the two candidate stories from the intro predict different
patterns:

- **If SHAP importances are all small and predicted probabilities cluster tightly around 0.5**: the
  model essentially learned "I don't know," and its slightly-worse-than-baseline hit rate is just
  noise from occasionally betting against the market's historical upward drift when it shouldn't have.
  This is the "no real signal" story, and it strengthens H1's conclusion rather than just repeating it —
  now there's a mechanism, not just a rejected null hypothesis.
- **If SHAP shows one or two features with clearly larger, structured impact** (e.g. `rsi_14` or
  `momentum_63` visibly separating the beeswarm by color/direction) **and predicted probabilities do
  spread meaningfully away from 0.5**: the model isn't directionless, it's *confidently wrong* on a
  pattern that doesn't generalize to the test period — worth naming explicitly rather than folding into
  "no signal," since it points to a specific overfit relationship rather than pure noise.

(Fill in which of these actually matches the plots above once this notebook is run — that's the real
finding, not a template answer.)
""")

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3 (fin-sentiment-etl-2)", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.13"},
}

with open("03_shap_interpretability.ipynb", "w") as f:
    nbf.write(nb, f)

print("Wrote 03_shap_interpretability.ipynb")
