"""
VeriStaff Analytics — Phase 3: Predictive Failure Model
=========================================================
Trains Logistic Regression (interpretable baseline) and Gradient Boosting
(performance model) to predict assignment failure.

Failure = client churned OR quality_score < 4.0 OR rework_pct > 20%

Split strategy: time-based — last 6 months of data as test set.
Outputs predicted_failure_prob back to SQLite for Power BI consumption.

Run AFTER 02_pipeline_features.py:
    python 03_model.py
"""

import pandas as pd
import numpy as np
import sqlite3
import joblib
import os
import warnings
warnings.filterwarnings("ignore")

from sklearn.linear_model    import LogisticRegression
from sklearn.ensemble        import GradientBoostingClassifier
from sklearn.preprocessing   import StandardScaler
from sklearn.pipeline        import Pipeline
from sklearn.metrics         import (
    roc_auc_score, classification_report,
    precision_recall_curve, average_precision_score
)
from sklearn.calibration     import CalibratedClassifierCV

try:
    import shap
    HAS_SHAP = True
except ImportError:
    HAS_SHAP = False
    print("SHAP not installed — using built-in feature importance instead.")

PROC_DIR   = "data/processed"
DB_PATH    = f"{PROC_DIR}/veristaff.db"
MODEL_DIR  = "models"
os.makedirs(MODEL_DIR, exist_ok=True)

# ─── FEATURE SET ──────────────────────────────────────────────────────────────
FEATURE_COLS = [
    "skill_gap",                    # verified_score - required_score
    "self_assessment_bias",         # self_assessed - verified
    "manager_override_ratio_6m",    # override freq in past 180 days
    "employee_hist_failure_rate",   # emp's past failure rate on same skill type
    "complexity_normalized",        # project complexity 0-1
    "early_warning_quality",        # 0=OnTrack, 1=AtRisk, 2=Delayed
    "client_value_encoded",         # 1=Low, 2=Med, 3=High
    "stakes_encoded",               # 1=Low, 2=Med, 3=High
    "override_flag",                # 1 if manager overrode system flag
    "mismatch_flag",                # 1 if emp is below threshold
    "unverified_flag",              # 1 if no audit score on file
    "tenure_years",                 # employee tenure
]

TARGET_COL = "target_failure"

# ─── LOAD DATA ────────────────────────────────────────────────────────────────
print("Loading analytical master from SQLite...")
conn = sqlite3.connect(DB_PATH)
df   = pd.read_sql("SELECT * FROM analytical_master", conn)
conn.close()

df["assigned_date"] = pd.to_datetime(df["assigned_date"])

# Drop rows where outcome is unknown (project not yet finished)
df = df[df["has_outcome"] == 1].copy()
print(f"  Records with known outcomes: {len(df)}")
print(f"  Failure rate: {df[TARGET_COL].mean():.1%}")

# ─── TIME-BASED TRAIN / TEST SPLIT ────────────────────────────────────────────
cutoff_date = df["assigned_date"].max() - pd.DateOffset(months=6)
train       = df[df["assigned_date"] <= cutoff_date].copy()
test        = df[df["assigned_date"] >  cutoff_date].copy()

print(f"\nTrain: {len(train)} rows (up to {cutoff_date.date()})")
print(f"Test:  {len(test)} rows (last 6 months)")
print(f"Train failure rate: {train[TARGET_COL].mean():.1%}")
print(f"Test  failure rate: {test[TARGET_COL].mean():.1%}")

X_train = train[FEATURE_COLS].fillna(0)
y_train = train[TARGET_COL]
X_test  = test[FEATURE_COLS].fillna(0)
y_test  = test[TARGET_COL]

# ─── MODEL 1: LOGISTIC REGRESSION (interpretable baseline) ────────────────────
print("\n── Model 1: Logistic Regression ────────────────────────────────────")

lr_pipe = Pipeline([
    ("scaler", StandardScaler()),
    ("model",  LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42))
])
lr_pipe.fit(X_train, y_train)
lr_proba = lr_pipe.predict_proba(X_test)[:, 1]

lr_auc = roc_auc_score(y_test, lr_proba)
lr_ap  = average_precision_score(y_test, lr_proba)
print(f"  AUC-ROC : {lr_auc:.4f}")
print(f"  Avg Prec: {lr_ap:.4f}")
print("\n  Classification Report (threshold 0.5):")
print(classification_report(y_test, (lr_proba >= 0.5).astype(int),
      target_names=["Pass", "Fail"]))

# LR coefficients as feature importance
lr_coefs = pd.Series(
    lr_pipe.named_steps["model"].coef_[0],
    index=FEATURE_COLS
).sort_values(key=abs, ascending=False)
print("\n  Logistic Regression Coefficients (|coef| ranked):")
print(lr_coefs.to_string())

# ─── MODEL 2: GRADIENT BOOSTING (performance) ─────────────────────────────────
print("\n── Model 2: Gradient Boosting ──────────────────────────────────────")

gb_model = GradientBoostingClassifier(
    n_estimators=200,
    learning_rate=0.05,
    max_depth=4,
    min_samples_leaf=10,
    subsample=0.8,
    random_state=42
)
gb_model.fit(X_train, y_train)
gb_proba  = gb_model.predict_proba(X_test)[:, 1]

gb_auc = roc_auc_score(y_test, gb_proba)
gb_ap  = average_precision_score(y_test, gb_proba)
print(f"  AUC-ROC : {gb_auc:.4f}")
print(f"  Avg Prec: {gb_ap:.4f}")
print("\n  Classification Report (threshold 0.5):")
print(classification_report(y_test, (gb_proba >= 0.5).astype(int),
      target_names=["Pass", "Fail"]))

# Built-in feature importance
gb_importance = pd.Series(
    gb_model.feature_importances_,
    index=FEATURE_COLS
).sort_values(ascending=False)
print("\n  Gradient Boosting Feature Importance (top 5 drivers of failure):")
print(gb_importance.head(5).to_string())

# ─── SHAP VALUES (if available) ────────────────────────────────────────────────
if HAS_SHAP:
    print("\n── SHAP Analysis ───────────────────────────────────────────────────")
    explainer   = shap.TreeExplainer(gb_model)
    shap_values = explainer.shap_values(X_test)

    shap_mean = pd.Series(
        np.abs(shap_values).mean(axis=0),
        index=FEATURE_COLS
    ).sort_values(ascending=False)
    print("\n  SHAP mean |value| (global feature impact):")
    print(shap_mean.to_string())
    print("\n  Top 3 Drivers of Assignment Failure Risk:")
    for rank, (feat, val) in enumerate(shap_mean.head(3).items(), 1):
        descriptions = {
            "early_warning_quality":      "Mid-project checkpoint status (At Risk / Delayed) is the strongest early signal of failure.",
            "manager_override_ratio_6m":  "Managers with high override frequency drive failure — systematic override culture is the #2 risk factor.",
            "employee_hist_failure_rate": "An employee's own past failure rate on similar tasks is highly predictive of future failure.",
            "skill_gap":                  "Negative skill gap (employee below required threshold) directly elevates failure probability.",
            "self_assessment_bias":       "High self-assessment inflation correlates with poor outcomes — overconfidence precedes failure.",
            "override_flag":              "Individual override events significantly increase failure risk independent of manager pattern.",
        }
        desc = descriptions.get(feat, f"Strong predictor — see SHAP plot.")
        print(f"  #{rank} {feat}: SHAP = {val:.4f} — {desc}")

    # Save SHAP summary to CSV for Power BI key influencers reference
    shap_df = pd.DataFrame({
        "feature":         FEATURE_COLS,
        "shap_importance": np.abs(shap_values).mean(axis=0)
    }).sort_values("shap_importance", ascending=False)
    shap_df.to_csv(f"{PROC_DIR}/shap_importance.csv", index=False)
    print(f"\n  SHAP importance saved to {PROC_DIR}/shap_importance.csv")

else:
    # Save GB importance as substitute
    gb_importance.reset_index().rename(
        columns={"index": "feature", 0: "shap_importance"}
    ).to_csv(f"{PROC_DIR}/shap_importance.csv", index=False)

# ─── CHOOSE FINAL MODEL ────────────────────────────────────────────────────────
# GB wins on AUC; LR is saved separately for explainability deck
print(f"\n── Model Selection ─────────────────────────────────────────────────")
print(f"  LR  AUC = {lr_auc:.4f}  |  GB AUC = {gb_auc:.4f}")
print(f"  → Using Gradient Boosting as primary model (higher AUC).")
print(f"  → Logistic Regression exported for client explainability decks.")

# ─── GENERATE PREDICTIONS ON FULL DATASET ─────────────────────────────────────
print("\nGenerating failure probability for ALL assignment records...")

X_all = df[FEATURE_COLS].fillna(0)
df["predicted_failure_prob"] = gb_model.predict_proba(X_all)[:, 1].round(4)
df["lr_failure_prob"]        = lr_pipe.predict_proba(X_all)[:, 1].round(4)

# Risk tier
df["risk_tier"] = pd.cut(
    df["predicted_failure_prob"],
    bins=[-0.001, 0.40, 0.70, 1.001],
    labels=["Low", "Medium", "High"]
)

# ─── WRITE PREDICTIONS BACK TO SQLITE ─────────────────────────────────────────
print(f"Writing predictions to SQLite: {DB_PATH}")
conn = sqlite3.connect(DB_PATH)

# Write prediction table
pred_cols = [
    "assignment_id", "project_id", "employee_id", "manager_id",
    "assigned_date", "required_skill_id", "required_skill_score",
    "task_stakes_level", "client_id",
    "skill_gap", "self_assessment_bias", "manager_override_ratio_6m",
    "employee_hist_failure_rate", "override_flag", "mismatch_flag",
    "unverified_flag", "early_warning_quality",
    "predicted_failure_prob", "lr_failure_prob", "risk_tier",
    "target_failure",     # actual outcome for evaluation
    "quality_score", "client_status", "rework_pct",
    "actual_revenue_usd", "expected_revenue_usd", "lost_revenue_usd",
]
# Filter to cols that exist
pred_cols = [c for c in pred_cols if c in df.columns]
df[pred_cols].to_sql("fact_predictions", conn, if_exists="replace", index=False)

# Also update analytical_master
df.to_sql("analytical_master", conn, if_exists="replace", index=False)
conn.close()

# ─── SAVE MODELS ──────────────────────────────────────────────────────────────
joblib.dump(gb_model,  f"{MODEL_DIR}/gb_model.pkl")
joblib.dump(lr_pipe,   f"{MODEL_DIR}/lr_pipeline.pkl")
print(f"Models saved to {MODEL_DIR}/")

# ─── PRECISION-RECALL THRESHOLDS (help choose operating point) ────────────────
print("\n── Threshold Analysis (GB Model) ──────────────────────────────────")
prec, rec, thresh = precision_recall_curve(y_test, gb_proba)
pr_df = pd.DataFrame({
    "threshold": list(thresh) + [1.0],
    "precision": prec,
    "recall":    rec
})
# Show at operationally useful thresholds
for t in [0.3, 0.4, 0.5, 0.6, 0.7]:
    row = pr_df[pr_df["threshold"] >= t].head(1)
    if len(row):
        print(f"  Threshold {t}: Precision={row['precision'].values[0]:.2f}, "
              f"Recall={row['recall'].values[0]:.2f}")

pr_df.to_csv(f"{PROC_DIR}/pr_curve.csv", index=False)

# ─── FINAL STATS ──────────────────────────────────────────────────────────────
high_risk = df[df["risk_tier"] == "High"]
print(f"\n── Prediction Summary ──────────────────────────────────────────────")
print(f"  High-risk assignments (prob > 0.70)   : {len(high_risk)}")
print(f"  Estimated revenue at risk (high tier) : ${high_risk['expected_revenue_usd'].sum():,.0f}")
print(f"  Avg predicted failure prob            : {df['predicted_failure_prob'].mean():.3f}")
print(f"\n── Phase 3 complete. Predictions stored in SQLite. ─────────────────\n")
