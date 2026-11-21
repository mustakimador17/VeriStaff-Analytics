# VeriStaff Analytics — Phase 5: Power BI Dashboard Specification
# ================================================================
# Complete DAX measures + page-by-page design blueprint.
# Build this in Power BI Desktop pointed at: data/processed/veristaff.db
#
# DATA SOURCE SETUP
# -----------------
# Home → Get Data → ODBC → SQLite (or use Python connector)
# Import ALL views (v_*) and fact_predictions as the model base.
# Set assigned_date as Date type. Create a Date table (see DAX below).
# Relationships:
#   fact_predictions[manager_id]  → dim_managers[manager_id]
#   fact_predictions[employee_id] → dim_employees[employee_id]
#   fact_predictions[client_id]   → dim_clients[client_id]
#   fact_predictions[project_id]  → dim_projects[project_id]
#   fact_predictions[assigned_date] → DateTable[Date]


# ════════════════════════════════════════════════════════════════════
# SECTION 1 — DATE TABLE (paste into DAX → New Table)
# ════════════════════════════════════════════════════════════════════

DateTable =
VAR MinDate = MIN(fact_predictions[assigned_date])
VAR MaxDate = MAX(fact_predictions[assigned_date])
RETURN
ADDCOLUMNS(
    CALENDAR(MinDate, MaxDate),
    "Year",         YEAR([Date]),
    "Month",        MONTH([Date]),
    "MonthName",    FORMAT([Date], "MMM"),
    "Quarter",      "Q" & QUARTER([Date]),
    "YearMonth",    FORMAT([Date], "YYYY-MM"),
    "WeekNum",      WEEKNUM([Date]),
    "IsWeekend",    IF(WEEKDAY([Date], 2) >= 6, TRUE, FALSE)
)


# ════════════════════════════════════════════════════════════════════
# SECTION 2 — CORE MEASURES (New Measure for each block)
# ════════════════════════════════════════════════════════════════════

# ── KPI CARDS ────────────────────────────────────────────────────────

[Total Assignments] =
COUNTROWS(fact_predictions)

[Total Active Projects] =
DISTINCTCOUNT(fact_predictions[project_id])

[High Risk Assignment Count] =
CALCULATE(
    COUNTROWS(fact_predictions),
    fact_predictions[predicted_failure_prob] >= 0.70
)

[% High Risk Assignments] =
DIVIDE([High Risk Assignment Count], [Total Assignments], 0)

[Total Revenue At Risk] =
SUMX(
    FILTER(fact_predictions, fact_predictions[predicted_failure_prob] >= 0.70),
    fact_predictions[expected_revenue_usd] * fact_predictions[predicted_failure_prob]
)

[Total Lost Revenue] =
SUM(fact_predictions[lost_revenue_usd])

[Favoritism Cost] =
CALCULATE(
    SUM(fact_predictions[lost_revenue_usd]),
    FILTER(
        fact_predictions,
        fact_predictions[override_flag] = 1
        && fact_predictions[mismatch_flag] = 1
        && fact_predictions[client_status] = "Churned"
    )
)

[Assignment Health Score] =
VAR AvgRisk = AVERAGE(fact_predictions[predicted_failure_prob])
RETURN ROUND((1 - AvgRisk) * 100, 1)
-- Displays 0–100; format as "0.0" with no % sign. Target > 75.

[Total Overrides] =
SUM(fact_predictions[override_flag])

[Override Rate %] =
DIVIDE([Total Overrides], [Total Assignments], 0)

[Avg Quality Score] =
AVERAGE(fact_predictions[quality_score])

[Total Churned Clients] =
CALCULATE(
    DISTINCTCOUNT(fact_predictions[client_id]),
    fact_predictions[client_status] = "Churned"
)

[Churn Rate %] =
DIVIDE(
    CALCULATE(COUNTROWS(fact_predictions), fact_predictions[client_status] = "Churned"),
    [Total Assignments],
    0
)

[Mismatch Rate %] =
DIVIDE(
    CALCULATE(COUNTROWS(fact_predictions), fact_predictions[mismatch_flag] = 1),
    [Total Assignments],
    0
)


# ── RISK SEGMENTATION ────────────────────────────────────────────────

[Risk Category] =
-- Calculated Column on fact_predictions
IF(
    fact_predictions[predicted_failure_prob] >= 0.70, "High",
    IF(fact_predictions[predicted_failure_prob] >= 0.40, "Medium", "Low")
)

[High Risk Revenue] =
CALCULATE(
    SUMX(fact_predictions, fact_predictions[expected_revenue_usd] * fact_predictions[predicted_failure_prob]),
    fact_predictions[predicted_failure_prob] >= 0.70
)

[Medium Risk Revenue] =
CALCULATE(
    SUMX(fact_predictions, fact_predictions[expected_revenue_usd] * fact_predictions[predicted_failure_prob]),
    fact_predictions[predicted_failure_prob] >= 0.40,
    fact_predictions[predicted_failure_prob] < 0.70
)


# ── MANAGER ACCOUNTABILITY ────────────────────────────────────────────

[Manager Override Rate] =
DIVIDE(
    CALCULATE(SUM(fact_predictions[override_flag])),
    CALCULATE(COUNTROWS(fact_predictions)),
    0
)

[Manager Churn Rate] =
DIVIDE(
    CALCULATE(COUNTROWS(fact_predictions), fact_predictions[client_status] = "Churned"),
    CALCULATE(COUNTROWS(fact_predictions)),
    0
)

[Manager Revenue Lost] =
CALCULATE(SUM(fact_predictions[lost_revenue_usd]))

[Manager Avg Skill Gap] =
AVERAGE(fact_predictions[skill_gap])

[Manager Mismatch Count] =
CALCULATE(COUNTROWS(fact_predictions), fact_predictions[mismatch_flag] = 1)

[Favoritism Score] =
-- Index 0–100: higher = more evidence of systematic bias
VAR OverrideR  = [Manager Override Rate]
VAR MismatchR  = [Mismatch Rate %]
VAR AvgGap     = [Manager Avg Skill Gap]
VAR FalseOT    = CALCULATE(
                    COUNTROWS(fact_predictions),
                    fact_predictions[early_warning_quality] = 0,
                    fact_predictions[quality_score] < 4
                 )
VAR TotalAsgn  = [Total Assignments]
RETURN
ROUND(
    (OverrideR * 40) +
    (MismatchR * 30) +
    (IF(AvgGap < -10, 20, 0)) +
    (DIVIDE(FalseOT, TotalAsgn, 0) * 10),
2)

[Recoverable Revenue (Simulation)] =
-- Simulates gain if all mismatched/override assignments used compliant staff
SUMX(
    fact_predictions,
    IF(
        fact_predictions[mismatch_flag] = 1 || fact_predictions[override_flag] = 1,
        fact_predictions[expected_revenue_usd] * (fact_predictions[predicted_failure_prob] - 0.12),
        0
    )
)


# ── TREND MEASURES ────────────────────────────────────────────────────

[Monthly Risk % Trend] =
-- Use this in a Line chart with DateTable[YearMonth] on X axis
DIVIDE(
    CALCULATE(
        COUNTROWS(fact_predictions),
        fact_predictions[predicted_failure_prob] >= 0.70
    ),
    CALCULATE(COUNTROWS(fact_predictions)),
    0
)

[Rolling 3M Override Rate] =
VAR CurrentDate = MAX(DateTable[Date])
VAR StartDate   = CurrentDate - 90
RETURN
CALCULATE(
    DIVIDE(SUM(fact_predictions[override_flag]), COUNTROWS(fact_predictions), 0),
    fact_predictions[assigned_date] >= StartDate,
    fact_predictions[assigned_date] <= CurrentDate
)


# ── PREDICTIVE / SIMULATION ───────────────────────────────────────────

[Open High-Risk Assignments] =
-- Assignments still active (no outcome yet) with high failure prob
CALCULATE(
    COUNTROWS(fact_predictions),
    fact_predictions[predicted_failure_prob] >= 0.70,
    fact_predictions[client_status] = "Active"
)

[Predicted Churn Revenue Exposure] =
CALCULATE(
    SUMX(fact_predictions, fact_predictions[expected_revenue_usd] * fact_predictions[predicted_failure_prob]),
    fact_predictions[client_status] = "Active"
)

# What-If Parameter (create via Modeling → New Parameter in Power BI)
# Name: Skill Gap Adjustment
# Min: -50, Max: 50, Increment: 1, Default: 0
# This creates a slicer users drag to simulate "what if we raised/lowered skill gap"

[Simulated Failure Prob] =
-- Uses What-If parameter to show dynamic failure prob change
VAR BaseProb   = AVERAGE(fact_predictions[predicted_failure_prob])
VAR GapAdjust  = 'Skill Gap Adjustment'[Skill Gap Adjustment Value]
-- Approx: every +10 skill gap points reduces failure prob by ~8%
VAR Adjustment = (GapAdjust / 10) * -0.08
RETURN ROUND(MAX(0, MIN(1, BaseProb + Adjustment)), 3)

[Simulated Revenue Saved] =
VAR BaseRisk   = [Total Revenue At Risk]
VAR SimRisk    = [Simulated Failure Prob] * SUM(fact_predictions[expected_revenue_usd])
RETURN MAX(0, BaseRisk - SimRisk)


# ── DYNAMIC TEXT (use in Text Box with field insert or Card visual) ────

[Top Offending Manager Text] =
-- Returns a summary string for the annotation card on Page 2
VAR TopMgr = TOPN(1, v_ManagerScorecard, v_ManagerScorecard[total_lost_revenue], DESC)
VAR MgrName = MAXX(TopMgr, v_ManagerScorecard[manager_name])
VAR LostRev = MAXX(TopMgr, v_ManagerScorecard[total_lost_revenue])
VAR RecovR  = MAXX(TopMgr, v_ManagerScorecard[forecasted_revenue_at_risk])
RETURN
"⚠ " & MgrName & " attributed $" & FORMAT(LostRev, "#,##0") &
" in lost revenue. Redirecting 2 high-stakes tasks to compliant staff " &
"could recover $" & FORMAT(RecovR * 0.4, "#,##0") & "."


# ════════════════════════════════════════════════════════════════════
# SECTION 3 — PAGE-BY-PAGE DESIGN SPECIFICATION
# ════════════════════════════════════════════════════════════════════

# ── PAGE 1: Executive Risk Overview ──────────────────────────────────
#
# Canvas: 1920×1080, background #0F1923 (dark navy)
# Accent colors: Red=#E84040, Amber=#F5A623, Green=#27AE60, White=#F0F0F0
# Font: Segoe UI throughout
#
# Row 1 — KPI Cards (6 cards across top, equal width)
#   [1] Total Active Projects        → value, no trend
#   [2] % High-Risk Assignments      → % format, red if >25%
#   [3] Total Revenue at Risk        → $M format, conditional red
#   [4] Favoritism Cost              → $M, always red
#   [5] Avg Quality Score            → 0–10, green if >6.5, red if <5
#   [6] Assignment Health Score      → gauge, 0–100
#
# Row 2 Left (60%) — Gauge Chart
#   Visual: Gauge
#   Value: [Assignment Health Score]
#   Min: 0, Max: 100
#   Target line: 75
#   Colors: Red zone 0–49, Amber 50–74, Green 75–100
#   Title: "Overall Assignment Health"
#
# Row 2 Right (40%) — Monthly Risk Trend Line
#   Visual: Line chart
#   X: DateTable[YearMonth]
#   Y: [Monthly Risk % Trend]
#   Y2: [Override Rate %] (secondary axis, dashed)
#   Title: "Assignment Risk Trend (24 Months)"
#   Annotations: Mark any month where override rate spiked >15%
#
# Row 3 — Top Risky Projects Table (full width)
#   Visual: Table
#   Columns: project_name, client_name, client_value_tier,
#            predicted_failure_prob, risk_category, revenue_at_risk_usd,
#            manager_name, assigned_date
#   Sort: revenue_at_risk_usd DESC
#   Filter: predicted_failure_prob >= 0.70
#   Conditional formatting: risk_category cell background
#     High=Red, Medium=Amber, Low=Green
#   Drill-through: right-click row → Page 4 (Assignment Detail)
#   Title: "High-Risk Assignments Requiring Immediate Attention"
#
# Slicers (top right panel): Department, Stakes Level, Date Range
#
# ── PAGE 2: Manager Accountability & Bias Detection ──────────────────
#
# Canvas: Same specs as Page 1
#
# Row 1 Left (50%) — Scatter Chart
#   Visual: Scatter
#   X: v_ManagerScorecard[override_rate_pct]    "Override Rate %"
#   Y: v_ManagerScorecard[churn_rate_pct]       "Client Churn Rate %"
#   Size: v_ManagerScorecard[total_lost_revenue] "Revenue Lost"
#   Color: department (4 colors)
#   Data labels: manager_name
#   Reference lines: X=30 (override threshold), Y=25 (churn threshold)
#   Quadrant annotation:
#     Top-Right = "HIGH RISK: High override + High churn"
#     Bottom-Left = "HEALTHY: Low override + Low churn"
#   Title: "Manager Override Rate vs Client Churn Rate"
#
# Row 1 Right (50%) — Waterfall Chart
#   Visual: Waterfall
#   Category: manager_name
#   Y: v_WhatIfScenarios[recoverable_revenue_usd]
#   Breakdown: shows each manager's contribution to recoverable revenue
#   Total bar color: Green
#   Title: "Revenue Recoverable via Skill-Compliant Assignments"
#
# Row 2 Full Width — Manager Matrix Table
#   Visual: Matrix
#   Rows: manager_name
#   Columns (values):
#     total_assignments, override_rate_pct, mismatch_rate_pct,
#     false_ontrack_count, avg_quality_score, favoritism_score, bias_risk_label
#   Conditional formatting:
#     override_rate_pct  → data bars, red gradient
#     avg_quality_score  → background: green if >6.5, red if <5
#     favoritism_score   → background: red if >40, amber if >20
#     bias_risk_label    → font color: Critical=Red, Elevated=Amber, Normal=Green
#   Title: "Manager Performance & Integrity Scorecard"
#
# Dynamic Annotation Card (bottom right)
#   Visual: Card with [Top Offending Manager Text] measure
#   Background: Dark red #3D0000, white text
#   Border: 2px solid #E84040
#
# ── PAGE 3: Predictive Risk & Early Warning ───────────────────────────
#
# Row 1 Left (40%) — Failure Probability Histogram
#   Visual: Clustered bar chart
#   X: predicted_failure_prob binned (0–0.2, 0.2–0.4, 0.4–0.6, 0.6–0.8, 0.8–1.0)
#   Y: Count of assignments
#   Color split: actual_failure (0=Blue pass, 1=Red fail)
#   Title: "Distribution of Predicted Failure Probability"
#   Annotation: "Assignments right of 0.70 line = High Risk zone"
#
# Row 1 Right (60%) — Open High-Risk Assignments Table
#   Visual: Table
#   Filter: client_status = "Active" AND predicted_failure_prob >= 0.75
#   Columns: assignment_id, employee_name, project_name, skill_name,
#            skill_gap, early_warning_quality (as label), predicted_failure_prob,
#            revenue_at_stake, assigned_date
#   Conditional format: early_warning_quality → red if "At Risk" or "Delayed"
#   Title: "Active Assignments: Intervention Required"
#
# Row 2 Left (50%) — Key Influencers Visual
#   Visual: Key Influencers (built-in Power BI AI visual)
#   Analyze: target_failure
#   Explain by: skill_gap, manager_override_ratio_6m, early_warning_quality,
#               employee_hist_failure_rate, override_flag, mismatch_flag,
#               self_assessment_bias, complexity_score
#   Title: "What Drives Assignment Failure?"
#
# Row 2 Right (50%) — Simulation Mode (Bookmark toggle)
#   Two bookmark states:
#     State A (default): Shows v_WhatIfScenarios bar chart by manager
#     State B (sim mode): Shows [Simulated Failure Prob] card + [Simulated Revenue Saved] card
#                         + What-If slicer "Skill Gap Adjustment" (-50 to +50)
#   Toggle button: "Switch to Simulation Mode" / "Back to Overview"
#   Title: "What-If: Skill Compliance Impact"
#
# ── PAGE 4: Full Audit Trail & Narrative ─────────────────────────────
#
# Row 1 — Audit Findings Banner
#   Visual: Multi-row card
#   Fields: audit_finding (from v_FalseOnTrackAudit), count of assignments,
#           total lost revenue
#   Background: #1A0000 (dark red wash)
#
# Row 2 Full Width — Full Audit Table
#   Data: v_FalseOnTrackAudit
#   Columns: assignment_id, project_name, employee_name, manager_name,
#            client_name, reported_at_50pct, final_quality_score,
#            client_status, override_justification, expected_revenue_usd,
#            lost_revenue_usd, audit_finding
#   Conditional format: audit_finding background color
#     CRITICAL = #8B0000, HIGH = #C0392B, MEDIUM = #E67E22
#   Filter panel: manager_name, department, client_value_tier, date range
#   Title: "Complete Assignment Override & Outcome Audit Log"
#
# Story Card — Emp_023 Spotlight (floating text box, bottom right)
#   Content:
#     "CASE STUDY — EMP_023 & MGR_005
#      Emp_023 (verified Client Presentation score: 35/100) was assigned
#      to 11 high-stakes client presentations by MGR_005, overriding
#      system flags each time. Justifications cited 'client rapport' and
#      'scheduling conflicts.' Outcome: 81.8% churn rate on these
#      assignments, estimated $X in direct revenue loss.
#      This pattern is detectable 6 weeks before churn using the
#      early-warning checkpoint model."
#   Style: white text, dark background, left red border accent
#
# Export Button: "Export Audit to Excel"
#   Action: Export visual data → underlying data → Excel
#
# ── TOOLTIP PAGE: Employee Competence Passport ────────────────────────
#
# Page size: 320×280 px (tooltip size)
# Enable as tooltip: Page settings → Allow use as tooltip = ON
#
# Visuals:
#   [1] Radar/Spider Chart (use custom visual "Radar Chart" from AppSource)
#       Data: v_EmployeeCompetencePassport filtered to hovered employee
#       Values: verified_score per skill
#       Second series: self_assessed_score (show gap visually)
#       Title: employee_name
#
#   [2] KPI mini-cards (horizontal stack)
#       - failure_rate_pct   label: "Fail Rate"
#       - avg_quality_score  label: "Avg Quality"
#       - self_assessment_bias label: "SA Bias"
#
#   [3] Trend sparkline (Last 6 assignments)
#       X: assigned_date, Y: predicted_failure_prob
#       Tiny line chart, no axes labels
#
# Trigger: Set any Employee Name field in any table visual
#          → Format → Tooltip → Type: Report Page → Page: Tooltip Page


# ════════════════════════════════════════════════════════════════════
# SECTION 4 — ADDITIONAL DAX UTILITY MEASURES
# ════════════════════════════════════════════════════════════════════

[Emp 023 Churn Rate] =
CALCULATE(
    DIVIDE(
        COUNTROWS(FILTER(fact_predictions, fact_predictions[client_status] = "Churned")),
        COUNTROWS(fact_predictions),
        0
    ),
    fact_predictions[employee_id] = "EMP_023"
)

[False OnTrack Count] =
CALCULATE(
    COUNTROWS(fact_predictions),
    fact_predictions[early_warning_quality] = 0,
    fact_predictions[quality_score] < 4
)

[Unverified Skill Risk Count] =
CALCULATE(
    COUNTROWS(fact_predictions),
    fact_predictions[unverified_flag] = 1,
    fact_predictions[predicted_failure_prob] >= 0.70
)

[YoY Risk Change %] =
VAR CurrentYearRisk =
    CALCULATE([% High Risk Assignments], YEAR(fact_predictions[assigned_date]) = 2024)
VAR PriorYearRisk =
    CALCULATE([% High Risk Assignments], YEAR(fact_predictions[assigned_date]) = 2023)
RETURN DIVIDE(CurrentYearRisk - PriorYearRisk, PriorYearRisk, 0)

[Assignments Above Threshold] =
CALCULATE(
    COUNTROWS(fact_predictions),
    fact_predictions[skill_gap] >= 0
)

[Skill Compliance Rate] =
DIVIDE([Assignments Above Threshold], [Total Assignments], 0)
