"""
VeriStaff Analytics — Phase 2: Data Pipeline & Feature Engineering
===================================================================
Loads raw CSVs → merges into analytical star schema → engineers advanced
features → writes normalized tables to SQLite for Power BI consumption.

Run AFTER 01_generate_data.py:
    python 02_pipeline_features.py

Output:
    data/processed/veristaff.db   (SQLite — point Power BI here)
    data/processed/master_flat.csv (flat analytical table for ML)
"""

import pandas as pd
import numpy as np
import sqlite3
import os
from datetime import datetime, timedelta

RAW_DIR   = "data/raw"
os.makedirs(RAW_DIR, exist_ok=True)
PROC_DIR  = "data/processed"
DB_PATH   = f"{PROC_DIR}/veristaff.db"

os.makedirs(PROC_DIR, exist_ok=True)

# ─── LOAD RAW CSVs ────────────────────────────────────────────────────────────
print("Loading raw CSVs...")
managers       = pd.read_csv(f"{RAW_DIR}/managers.csv")
employees      = pd.read_csv(f"{RAW_DIR}/employees.csv")
skills         = pd.read_csv(f"{RAW_DIR}/skills.csv")
employee_skills= pd.read_csv(f"{RAW_DIR}/employee_skills.csv")
clients        = pd.read_csv(f"{RAW_DIR}/clients.csv")
projects       = pd.read_csv(f"{RAW_DIR}/projects.csv")
tasks          = pd.read_csv(f"{RAW_DIR}/tasks.csv")
assignments    = pd.read_csv(f"{RAW_DIR}/assignments.csv")
outcomes       = pd.read_csv(f"{RAW_DIR}/outcomes.csv")

# ─── DATE PARSING ─────────────────────────────────────────────────────────────
for df, cols in [
    (employees,       ["hire_date"]),
    (employee_skills, ["audit_date"]),
    (projects,        ["start_date", "end_date"]),
    (assignments,     ["assigned_date"]),
    (managers,        ["hire_date"]),
]:
    for c in cols:
        df[c] = pd.to_datetime(df[c])

# ─── STEP 1: LATEST VERIFIED SKILL PER EMPLOYEE-SKILL ────────────────────────
# We want the most recent verified score at the time of each assignment
# (snapshot join — important for time-correct modeling)
print("Building skill snapshots...")

employee_skills_sorted = employee_skills.sort_values("audit_date")

def get_skill_score_at_date(emp_id: str, skl_id: str, as_of: pd.Timestamp) -> dict:
    """Return the verified and self-assessed scores most recent to 'as_of'."""
    rows = employee_skills_sorted[
        (employee_skills_sorted["employee_id"] == emp_id) &
        (employee_skills_sorted["skill_id"]    == skl_id) &
        (employee_skills_sorted["audit_date"]  <= as_of)
    ]
    if rows.empty:
        return {"verified_score": None, "self_assessed_score": None, "unverified_flag": 1}
    last = rows.iloc[-1]
    return {
        "verified_score":      last["verified_score"],
        "self_assessed_score": last["self_assessed_score"],
        "unverified_flag":     0,
    }

# Build the core analytical record per assignment
print("Joining assignment → task → skill scores (snapshot join, may take ~30s)...")

records = []
for _, asgn in assignments.iterrows():
    snap = get_skill_score_at_date(
        asgn["employee_id"],
        asgn["required_skill_id"],
        asgn["assigned_date"]
    )
    records.append({**asgn.to_dict(), **snap})

master = pd.DataFrame(records)

# ─── STEP 2: JOIN REMAINING TABLES ───────────────────────────────────────────
print("Joining all dimensions...")

master = master.merge(outcomes,  on=["assignment_id", "project_id"], how="left", suffixes=("", "_out"))
master = master.merge(
    employees[["employee_id", "employee_name", "role", "department",
               "tenure_years", "true_ability"]],
    on="employee_id", how="left"
)
master = master.merge(
    managers[["manager_id", "manager_name", "department"]].rename(
        columns={"department": "manager_dept"}
    ),
    on="manager_id", how="left"
)
master = master.merge(
    projects[["project_id", "project_type", "stakes_level", "budget_usd",
               "expected_revenue_usd", "complexity_score", "n_required_skills"]],
    on="project_id", how="left", suffixes=("","_proj")
)
master = master.merge(
    clients[["client_id", "client_name", "client_value_tier", "annual_revenue_usd"]],
    on="client_id", how="left"
)
master = master.merge(
    skills[["skill_id", "skill_name", "is_high_stakes"]].rename(
        columns={"skill_id": "required_skill_id"}
    ),
    on="required_skill_id", how="left"
)

# ─── STEP 3: FEATURE ENGINEERING ─────────────────────────────────────────────
print("Engineering features...")

# 3.1 Skill gap (negative = employee is BELOW the threshold — bad)
#     If no verified score, flag unverified and assign worst-case gap
master["skill_gap"] = np.where(
    master["unverified_flag"] == 1,
    -40,   # max risk penalty for unverified employees
    master["verified_score"] - master["required_skill_score"]
)

# 3.2 Self-assessment bias (positive = they over-rate themselves)
master["self_assessment_bias"] = np.where(
    master["unverified_flag"] == 1,
    np.nan,
    master["self_assessed_score"] - master["verified_score"]
)

# 3.3 Mismatch flag — assigned below required threshold
master["mismatch_flag"] = (master["skill_gap"] < 0).astype(int)

# 3.4 Manager override ratio — rolling 6-month window per manager
#     How frequently does this manager assign overrides in past 180 days?
master_sorted = master.sort_values("assigned_date").copy()

def compute_rolling_override_ratio(df: pd.DataFrame, window_days: int = 180) -> pd.Series:
    ratios = []
    for i, row in df.iterrows():
        cutoff = row["assigned_date"] - pd.Timedelta(days=window_days)
        hist   = df[
            (df["manager_id"]    == row["manager_id"]) &
            (df["assigned_date"] >= cutoff) &
            (df["assigned_date"] <  row["assigned_date"])
        ]
        if len(hist) == 0:
            ratios.append(0.0)
        else:
            ratios.append(hist["override_flag"].mean())
    return pd.Series(ratios, index=df.index)

print("  Computing rolling override ratios (this loops — ~45s)...")
master_sorted["manager_override_ratio_6m"] = compute_rolling_override_ratio(master_sorted)
master = master_sorted  # keep sorted order

# 3.5 Employee historical failure rate on SIMILAR tasks
#     "Failure" = quality < 4.0 or churned
master["assignment_failed"] = (
    (master["quality_score"] < 4.0) |
    (master["client_status"] == "Churned")
).astype(int)

def compute_emp_hist_failure_rate(df: pd.DataFrame) -> pd.Series:
    rates = []
    for i, row in df.iterrows():
        hist = df[
            (df["employee_id"]    == row["employee_id"]) &
            (df["required_skill_id"] == row["required_skill_id"]) &
            (df["assigned_date"]  <  row["assigned_date"])
        ]
        if len(hist) == 0:
            rates.append(0.5)   # prior: assume 50% uncertain
        else:
            rates.append(hist["assignment_failed"].mean())
    return pd.Series(rates, index=df.index)

print("  Computing employee historical failure rates...")
master["employee_hist_failure_rate"] = compute_emp_hist_failure_rate(master)

# 3.6 Early warning quality signal
#     mid_checkpoint_status encoded numerically
CHECKPOINT_MAP = {"On Track": 0, "At Risk": 1, "Delayed": 2}
master["early_warning_quality"] = master["mid_checkpoint_status"].map(CHECKPOINT_MAP).fillna(1)

# 3.7 Project complexity score (already in projects, but normalize 0-1)
max_complexity = master["complexity_score"].max()
master["complexity_normalized"] = master["complexity_score"] / max_complexity

# 3.8 Client value tier encoded
TIER_MAP = {"High": 3, "Medium": 2, "Low": 1}
master["client_value_encoded"] = master["client_value_tier"].map(TIER_MAP).fillna(1)

# 3.9 Stakes encoded
STAKES_MAP = {"High": 3, "Medium": 2, "Low": 1}
master["stakes_encoded"] = master["task_stakes_level"].map(STAKES_MAP).fillna(1)

# 3.10 Tenure bucket
master["tenure_bucket"] = pd.cut(
    master["tenure_years"],
    bins=[0, 1, 3, 6, 99],
    labels=["Junior", "Mid", "Senior", "Veteran"]
)

# 3.11 False on-track flag (detected pattern)
master["false_ontrack_flag"] = (
    (master["mid_checkpoint_status"] == "On Track") &
    (master["quality_score"] < 4.0)
).astype(int)

# 3.12 Revenue at stake per assignment
master["revenue_at_stake"] = (
    master["expected_revenue_usd_proj"] / master["n_required_skills"]
).round(2)

# 3.13 Binary target label for ML
master["target_failure"] = (
    (master["client_status"] == "Churned") |
    (master["quality_score"] < 4.0) |
    (master["rework_pct"] > 0.20)
).astype(int)

# ─── STEP 4: DATA QUALITY FLAGS ──────────────────────────────────────────────
print("Running data quality checks...")

# Flag missing outcomes (projects not yet finished may lack outcomes)
master["has_outcome"] = master["quality_score"].notna().astype(int)

# Impute missing outcome fields with conservative estimates
master["quality_score"]  = master["quality_score"].fillna(5.0)
master["rework_pct"]     = master["rework_pct"].fillna(master["rework_pct"].median())
master["client_status"]  = master["client_status"].fillna("Active")

# Fill self_assessment_bias NaN (unverified) with median for modeling
bias_median = master["self_assessment_bias"].median()
master["self_assessment_bias"] = master["self_assessment_bias"].fillna(bias_median)

# ─── STEP 5: WRITE TO SQLite ──────────────────────────────────────────────────
print(f"Writing normalized tables to SQLite: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)

# Dimension tables (reference)
managers.to_sql("dim_managers",       conn, if_exists="replace", index=False)
employees.to_sql("dim_employees",     conn, if_exists="replace", index=False)
skills.to_sql("dim_skills",           conn, if_exists="replace", index=False)
clients.to_sql("dim_clients",         conn, if_exists="replace", index=False)

# Fact table: assignments with features
assignments.to_sql("fact_assignments",conn, if_exists="replace", index=False)
outcomes.to_sql("fact_outcomes",      conn, if_exists="replace", index=False)
tasks.to_sql("dim_tasks",             conn, if_exists="replace", index=False)
projects.to_sql("dim_projects",       conn, if_exists="replace", index=False)
employee_skills.to_sql("fact_employee_skills", conn, if_exists="replace", index=False)

# Master analytical table (denormalized for Power BI and ML)
master.to_sql("analytical_master",   conn, if_exists="replace", index=False)

conn.close()
print("  SQLite write complete.")

# Also export master flat file for ML (Phase 3)
master.to_csv(f"{PROC_DIR}/master_flat.csv", index=False)
print("  master_flat.csv exported.\n")

# ─── SUMMARY ─────────────────────────────────────────────────────────────────
print("── Feature Engineering Summary ─────────────────────────────────────")
print(f"  Total assignment records  : {len(master)}")
print(f"  Mismatch rate             : {master['mismatch_flag'].mean():.1%}")
print(f"  Override rate (all)       : {master['override_flag'].mean():.1%}")
print(f"  Target failure rate       : {master['target_failure'].mean():.1%}")
print(f"  False on-track incidents  : {master['false_ontrack_flag'].sum()}")
print(f"  Unverified skill assigns  : {master['unverified_flag'].sum()}")
print()
print("── Top Features by Correlation with Failure ─────────────────────────")
feature_cols = [
    "skill_gap", "self_assessment_bias", "manager_override_ratio_6m",
    "employee_hist_failure_rate", "complexity_normalized",
    "early_warning_quality", "client_value_encoded", "stakes_encoded",
    "override_flag", "mismatch_flag"
]
corrs = master[feature_cols + ["target_failure"]].corr()["target_failure"].drop("target_failure")
print(corrs.sort_values(key=abs, ascending=False).to_string())
print("\n── Done. Ready for Phase 3 (model training). ───────────────────────\n")
