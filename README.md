VeriStaff Analytics
An end-to-end assignment integrity audit system for service businesses.
VeriStaff quantifies the hidden cost of skill mismatch and favoritism in task assignments — then predicts which open assignments are most likely to fail before they do.
Built as a portfolio project targeting Data Analyst / BI Developer roles. Stack: Python, SQL (SQLite), scikit-learn, Power BI.
---
What It Does
Service businesses lose 15–30% of client lifetime value to poor people-to-task decisions driven by favoritism, opaque competency data, and false milestone reporting. VeriStaff surfaces that risk with a number attached.
Output:
Predicted failure probability per assignment (AUC 0.91 on demo data)
Manager accountability scorecard with favoritism index
Dollar-quantified revenue at risk and favoritism cost
Full override + outcome audit trail
Power BI dashboard (4 pages + tooltip) + DAX measures
Plug-in pipeline for real client data
---
Project Structure
```
veristaff/
├── 01_generate_data.py          # Phase 1: Synthetic data with embedded bias patterns
├── 02_pipeline_features.py      # Phase 2: ETL → SQLite + feature engineering
├── 03_model.py                  # Phase 3: Logistic Regression + Gradient Boosting + SHAP
├── 06_client_pipeline.py        # Phase 6: Automated pipeline for real client data
│
├── sql/
│   └── 04_analytics_views.sql   # Phase 4: 7 SQL views for Power BI consumption
│
├── docs/
│   ├── 05_powerbi_dax_spec.md   # Phase 5: Full DAX measures + page-by-page spec
│   ├── client_data_template.xlsx# Phase 6: Formatted Excel template for clients
│   └── executive_summary_template.txt  # McKinsey-style 1-page findings brief
│
├── data/
│   ├── raw/                     # Generated CSVs (git-ignored after first run)
│   └── processed/               # SQLite DB + master_flat.csv + SHAP CSV
│
├── models/                      # Serialized model files (gb_model.pkl, lr_pipeline.pkl)
├── requirements.txt
└── README.md
```
---
Quickstart
1. Install dependencies
```bash
pip install -r requirements.txt
```
2. Generate demo data
```bash
python 01_generate_data.py
```
Generates 752 assignments across 120 employees, 8 managers, 45 clients — with hidden favoritism patterns embedded (Mgr_005, Emp_023).
3. Run the feature pipeline
```bash
python 02_pipeline_features.py
```
Creates `data/processed/veristaff.db` with normalized tables + engineered features.
4. Train the model
```bash
python 03_model.py
```
Trains Logistic Regression + Gradient Boosting (time-split). Writes predicted failure probabilities back to SQLite. Prints SHAP top drivers.
Demo results:
Model	AUC-ROC	Avg Precision
Logistic Regression	0.8822	0.7413
Gradient Boosting	0.9097	0.8127
Top 3 failure drivers (SHAP): `early_warning_quality` → `manager_override_ratio_6m` → `skill_gap`
5. Build the Power BI dashboard
Open Power BI Desktop
Get Data → ODBC → SQLite → point to `data/processed/veristaff.db`
Import all `v_*` views + `fact_predictions`
Paste DAX measures from `docs/05_powerbi_dax_spec.md`
Follow the page-by-page design spec in the same file
6. Real client engagement
Give the client `docs/client_data_template.xlsx`. Once filled:
```bash
python 06_client_pipeline.py --input client_filled_template.xlsx --output client_veristaff.db
```
Point the Power BI template at the new `.db` file. Done.
---
Hidden Patterns in Demo Data
The synthetic data embeds specific patterns to validate the system works:
Pattern	Detail	Detectable?
Mgr_005 favoritism	Assigns Emp_023 (verified score 35/100) to high-stakes presentations 90% of the time, always overriding system flags	✅ `v_FavoritismImpact`
Emp_007 suppression	Top performer (ability 0.93) routed to low-stakes tasks by Mgr_002	✅ `v_ManagerScorecard`
False "On Track" reports	Low-quality assignments reported on-track at 50% milestone → 100% churn in demo	✅ `v_FalseOnTrackAudit`
Self-assessment inflation	Mgr_005's team self-inflates by avg 20.6 pts vs 9.9 pts for others	✅ `self_assessment_bias` feature
---
Engineered Features
Feature	Definition
`skill_gap`	`verified_score – required_score` (negative = below threshold)
`self_assessment_bias`	`self_assessed – verified` (positive = over-rated)
`manager_override_ratio_6m`	% of that manager's assignments with override flag in rolling 180 days
`employee_hist_failure_rate`	Employee's past failure rate on the same skill type
`early_warning_quality`	Checkpoint status encoded: 0=OnTrack, 1=AtRisk, 2=Delayed
`unverified_flag`	1 if no verified skill score on file — treated as max risk
`complexity_normalized`	Project complexity index 0–1
`client_value_encoded`	Client tier: Low=1, Medium=2, High=3
---
SQL Views (Power BI Data Sources)
View	Purpose
`v_AssignmentIntelligenceReport`	Master report: all fields + risk tier + revenue at risk
`v_ManagerScorecard`	Per-manager KPIs: override rate, churn rate, favoritism score
`v_FavoritismImpact`	Direct cost of override + mismatch assignments
`v_WhatIfScenarios`	Simulated savings from skill-compliant assignments
`v_EmployeeCompetencePassport`	Tooltip page: per-employee skill radar + performance KPIs
`v_FalseOnTrackAudit`	Audit trail of false milestone reports + outcomes
`v_ExecutiveSummaryKPIs`	Single-row KPI row for dashboard header cards
---
Tech Stack
Python 3.9+ — pandas, numpy, scikit-learn, shap, openpyxl, joblib
SQLite — local portable database (no server required)
Power BI Desktop — dashboard + DAX (free download from Microsoft)
No web dev. No paid services. Fully portable.
---
Use as a Client-Facing Service
Deliver `docs/client_data_template.xlsx` with instructions
Client exports from their HRMS/project tool into the template
Run `06_client_pipeline.py --input their_file.xlsx`
Open Power BI, switch data source, refresh — done in under 10 minutes
Deliver Power BI report + `docs/executive_summary_template.txt` as PDF cover
---
Skills Demonstrated
`Python` `Pandas` `scikit-learn` `SHAP` `SQLite` `SQL Views` `Feature Engineering` `Classification Modeling` `AUC/PR Evaluation` `Power BI` `DAX` `Excel Automation` `openpyxl` `ETL Pipeline Design` `Business Analytics` `Data Storytelling`
---
Author
Siratal Mustakim Ador
LinkedIn · GitHub
