"""
Train جدير's cash-flow credit model.
Generates a realistic synthetic dataset of the 5 signals -> default outcome,
trains XGBoost, and saves a portable model that scores ANY uploaded statement.

Run:  python train_model.py
Output: credit_model.json (used automatically by the app), + prints Accuracy/AUC.
Note: synthetic data stands in for proprietary Saudi cash-flow data; in production
we retrain on real repayment outcomes.
"""
import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score

FEATURES = ["net_cashflow", "stability_cv", "growth_pct", "min_balance", "red_flags"]
np.random.seed(42)
N = 4000

# --- sample realistic companies across the whole risk spectrum ---
net_cashflow = np.random.normal(2000, 8000, N)          # monthly operating surplus/deficit
stability_cv = np.clip(np.random.gamma(2, 0.18, N), 0.03, 1.4)
growth_pct   = np.random.normal(-5, 25, N)              # revenue trend %
min_balance  = np.random.normal(20000, 35000, N)        # lowest balance in the year
red_flags    = np.random.poisson(2, N)                  # bounced/overdraft/late events

# --- realistic default probability (higher when the business is weak) ---
z = (-1.4
     - net_cashflow / 9000                # surplus lowers risk
     + stability_cv * 1.6                 # volatility raises risk
     - growth_pct / 60                    # decline raises risk
     - min_balance / 40000                # negative balances raise risk
     + red_flags * 0.28)                  # each red flag raises risk
p_default = 1 / (1 + np.exp(-z))
default = (np.random.rand(N) < p_default).astype(int)

df = pd.DataFrame({"net_cashflow": net_cashflow, "stability_cv": stability_cv,
                   "growth_pct": growth_pct, "min_balance": min_balance,
                   "red_flags": red_flags, "default": default})

X, y = df[FEATURES], df["default"]
Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

model = XGBClassifier(n_estimators=200, max_depth=4, learning_rate=0.1, eval_metric="logloss")
model.fit(Xtr, ytr)

pred = model.predict(Xte)
proba = model.predict_proba(Xte)[:, 1]
print(f"training rows: {len(df):,}  |  default rate: {y.mean():.0%}")
print(f"Accuracy: {accuracy_score(yte, pred):.3f}")
print(f"AUC:      {roc_auc_score(yte, proba):.3f}")

model.save_model("credit_model.json")   # portable across machines/versions
print("saved: credit_model.json")
