**An end-to-end assignment integrity audit system for service businesses.**

VeriStaff quantifies the hidden cost of skill mismatch and favoritism in task assignments - then predicts which open assignments are most likely to fail before they do.

Built as a portfolio project targeting Data Analyst / BI Developer roles. Stack: Python, SQL (SQLite), scikit-learn, Power BI.

---

## What It Does

Service businesses lose 15-30% of client lifetime value to poor people-to-task decisions driven by favoritism, opaque competency data, and false milestone reporting. VeriStaff surfaces that risk with a number attached.

**Output:**
- Predicted failure probability per assignment (AUC 0.91 on demo data)
- Manager accountability scorecard with favoritism index
- Dollar-quantified revenue at risk and favoritism cost
- Full override + outcome audit trail
- Power BI dashboard (4 pages + tooltip) + DAX measures
- Plug-in pipeline for real client data

---

## Why This Project Exists

In most service organizations, the decision of *who works on what* is made informally - by manager intuition, availability, or relationship. It is rarely audited, and almost never quantified.

VeriStaff demonstrates that this decision layer can be made measurable. By combining verified skill audits, manager override logs, and project outcome records, the project shows how to:

1. **Detect** systematic favoritism and skill mismatch in assignment patterns
2. **Quantify** the financial cost of those patterns in lost revenue and rework
3. **Predict** which in-flight assignments are likely to fail before they do
4. **Simulate** the impact of enforcing skill-compliance rules

The dataset is synthetic but structurally realistic - it embeds four known "hidden patterns" (documented in `01_generate_data.py`) so that every downstream component can be verified against ground truth. The pipeline then rediscovers these patterns without being told where to look, mirroring how a real audit would work.

---

## Project Structure

```
veristaff/
│
├── 01_generate_data.py              <- Synthetic data generator with embedded patterns
├── 02_pipeline_features.py          <- Feature engineering + SQLite star schema
├── 03_model.py                      <- Failure prediction model (LR + GBM + SHAP)
├── 04_analytics_views.sql           <- Six analytical SQL views for BI layer
├── 05_powerbi_dax_spec.md           <- Complete Power BI spec: DAX + page layouts
├── 06_client_pipeline.py            <- Drop-in pipeline for real client Excel data
├── client_data_template.xlsx        <- Excel template for client data intake
├── executive_summary_template.txt   <- One-page McKinsey-style findings brief
├── README.md                        <- You are here
│
├── data/
│   ├── raw/                         <- Generated CSVs (9 source tables)
│   └── processed/
│       ├── veristaff.db             <- SQLite DB (Power BI source)
│       ├── master_flat.csv          <- Denormalized analytical table for ML
│       ├── shap_importance.csv      <- SHAP global feature importance
│       └── pr_curve.csv             <- Precision-recall curve for threshold tuning
│
└── models/
    ├── gb_model.pkl                 <- Gradient Boosting (primary)
    └── lr_pipeline.pkl              <- Logistic Regression (explainability)
```

---

## The Pipeline - Six Phases

### Phase 1 - Data Simulation (`01_generate_data.py`)

Generates a structurally realistic dataset for a 120-person, 8-manager event marketing agency over a two-year window (2023-2024). Produces nine interrelated CSVs at `data/raw/`.

**Embedded hidden patterns (tunable via CONFIG block):**

| Pattern | Description |
|---|---|
| **Mgr_5 protege bias** | Mgr_5 systematically assigns `EMP_023` to high-stakes client presentations despite a verified score of 35/100. ~90% override rate on these tasks. |
| **Mgr_2 suppression** | Mgr_2 actively avoids assigning `EMP_007` (a top performer) to high-stakes tasks. |
| **False on-track reporting** | Projects reported "On Track" at the 50% milestone but ending with quality < 4.0 have ~90% churn probability. |
| **Self-assessment inflation** | Mgr_5's team self-rates 20-30 points above verified scores. Others inflate ~12 points. |

Deterministic seed (`SEED = 42`) means every run produces identical data.

### Phase 2 - Feature Engineering (`02_pipeline_features.py`)

Loads raw CSVs, performs **time-correct snapshot joins** (verified score as of assignment date, not latest), and engineers 13 analytical features:

- `skill_gap` - verified score minus required threshold
- `self_assessment_bias` - self-assessed minus verified
- `manager_override_ratio_6m` - rolling 180-day override frequency
- `employee_hist_failure_rate` - prior failure rate on same skill type
- `early_warning_quality` - encoded checkpoint status
- `false_ontrack_flag` - detected false report
- `target_failure` - binary outcome label

Writes normalized star schema + denormalized `analytical_master` to SQLite.

### Phase 3 - Predictive Modeling (`03_model.py`)

Trains two models on a **time-based split** (last 6 months as holdout):

| Model | Purpose | Test AUC |
|---|---|---|
| Logistic Regression | Interpretable baseline; exported for explainability decks | 0.8822 |
| Gradient Boosting | Primary model; best predictive performance | 0.9097 |

Uses SHAP (if installed) to rank global feature importance and generate plain-language interpretations of the top drivers of failure. Writes predictions back to `fact_predictions` in SQLite with risk tiers (Low / Medium / High).

### Phase 4 - SQL Analytics Layer (`04_analytics_views.sql`)

Seven pre-built views that Power BI imports directly:

| View | Purpose |
|---|---|
| `v_AssignmentIntelligenceReport` | Master report joining all dimensions; base for Pages 1 & 3 |
| `v_ManagerScorecard` | Per-manager KPIs + favoritism index; base for Page 2 |
| `v_FavoritismImpact` | Isolates assignments where override + mismatch caused churn; dollar cost |
| `v_WhatIfScenarios` | Simulates recovery if all assignments respected skill thresholds |
| `v_EmployeeCompetencePassport` | Per-employee skill profile for tooltip page |
| `v_FalseOnTrackAudit` | Full audit trail of false milestone reports |
| `v_ExecutiveSummaryKPIs` | Single-row KPI source for Power BI cards |

### Phase 5 - Power BI Dashboard (`05_powerbi_dax_spec.md`)

Complete specification for a four-page Power BI dashboard plus a tooltip page:

- **Page 1 - Executive Risk Overview**: Six KPI cards, assignment health gauge, monthly risk trend, high-risk project table
- **Page 2 - Manager Accountability & Bias Detection**: Override-vs-churn scatter, recoverable revenue waterfall, manager matrix with favoritism score, dynamic annotation card
- **Page 3 - Predictive Risk & Early Warning**: Failure probability histogram, active high-risk assignments table, key influencers visual, what-if simulation mode
- **Page 4 - Full Audit Trail & Narrative**: False on-track audit log, Emp_023 case study spotlight, export button
- **Tooltip Page - Employee Competence Passport**: Skill radar chart, mini KPI cards, trend sparkline

The spec includes 60+ DAX measures covering KPI cards, risk segmentation, manager accountability, trend measures, simulation parameters, and dynamic text.

### Phase 6 - Client Pipeline (`06_client_pipeline.py`)

A drop-in script for real client engagements:

1. Validates the client Excel template (schema + data quality checks)
2. Runs all feature engineering
3. Trains the failure model on the client's historical data
4. Writes a SQLite database ready for the Power BI template
5. Prints an executive summary of findings with three recommended actions

Usage:
```bash
python 06_client_pipeline.py --input client_filled_template.xlsx --output client_veristaff.db
```

---

## Getting Started

### Prerequisites
- Python 3.9+
- SQLite (built into Python - no install needed)
- Power BI Desktop (for dashboard)

### Installation

```bash
# 1. Clone repository
git clone https://github.com/yourusername/veristaff-analytics.git
cd veristaff-analytics

# 2. Install dependencies
pip install pandas numpy scikit-learn joblib shap

# 3. Run the full pipeline in order
python 01_generate_data.py         # Generate synthetic data
python 02_pipeline_features.py     # Engineer features + write SQLite
python 03_model.py                 # Train models + write predictions
```

### Power BI Setup

1. Open Power BI Desktop
2. Get Data -> ODBC -> SQLite -> point to `data/processed/veristaff.db`
3. Import all `v_*` views and `fact_predictions`
4. Follow the layout spec in `05_powerbi_dax_spec.md`
5. Copy the DAX measures from the spec into your model

### Client Data Mode

1. Fill out `client_data_template.xlsx` with real data
2. Run:
```bash
python 06_client_pipeline.py --input your_filled_template.xlsx --output client_veristaff.db
```
3. Point the Power BI template at `client_veristaff.db`

---

## Model Results

**Test set:** last 6 months of assignments (time-based holdout)

| Model | AUC-ROC | Avg Precision | Purpose |
|---|---|---|---|
| Logistic Regression | 0.8822 | 0.7413 | Explainability, client decks |
| Gradient Boosting | 0.9097 | 0.8127 | Primary production model |

**Top failure drivers (SHAP):**

1. `early_warning_quality` - checkpoint status at 50% milestone
2. `manager_override_ratio_6m` - rolling override frequency
3. `skill_gap` - verified score below threshold
4. `employee_hist_failure_rate` - prior failure rate on similar tasks
5. `self_assessment_bias` - overconfidence precedes failure

---

## Executive Summary (Demo Data)

| Metric | Value |
|---|---|
| Total assignments analyzed | 752 |
| High-risk assignments (prob > 0.70) | 187 |
| Estimated revenue at risk | $2.4M |
| Direct favoritism cost (override + mismatch + churn) | $412K |
| Assignment health score | 68.4 / 100 |
| Emp_023 churn rate on biased assignments | 81.8% |

**Top three recommendations from the audit:**

1. **Enforce skill gates** on high-stakes assignments - requires secondary approval when verified score is >15 points below threshold
2. **Audit managers** with override rate > 30% - three targeted conversations recover majority of favoritism cost
3. **72-hour escalation protocol** on "At Risk" checkpoints - can reduce final churn by 40-60%

---

## Design Notes

- **Deterministic seeding** - every data generation run produces identical rows, making results fully reproducible
- **Time-correct joins** - skill snapshots use `as_of_date` at assignment time, not the latest audit, to prevent leakage
- **Class-balanced training** - Logistic Regression uses `class_weight='balanced'`; GBM uses `subsample=0.8` to avoid overfitting on the minority class
- **Threshold tuning** - precision-recall curve exported to `pr_curve.csv` for operational threshold selection
- **Explainability** - SHAP values exported to `shap_importance.csv` and translated into plain-language descriptions for non-technical stakeholders
- **Fully portable** - no servers, no paid services, no cloud dependencies. Everything runs on a laptop.

---

## Technologies

| Layer | Tools |
|---|---|
| Data generation | Python, numpy, pandas |
| Feature engineering | pandas, numpy |
| Storage | SQLite (via sqlite3) |
| Modeling | scikit-learn (LR, GBM), joblib, SHAP |
| SQL analytics | SQLite views |
| BI layer | Power BI, DAX |
| Automation | openpyxl, argparse |

---

## License

This project is provided for **educational and portfolio use**. Feel free to fork, extend, and adapt it for your own learning or teaching.

---

## Author

**Siratal Mustakim Ador**
[LinkedIn](https://linkedin.com/in/siratal-mustakim-ador-0717b9314) | [GitHub](https://github.com/mustakimador17)

