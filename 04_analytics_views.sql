-- ============================================================
-- VeriStaff Analytics — Phase 4: SQL Analytics Layer
-- ============================================================
-- Run these in SQLite (or adapt for any RDBMS).
-- Power BI should connect to veristaff.db and import these views.
--
-- VIEWS PROVIDED:
--   v_AssignmentIntelligenceReport
--   v_ManagerScorecard
--   v_FavoritismImpact
--   v_WhatIfScenarios
--   v_EmployeeCompetencePassport
--   v_FalseOnTrackAudit
-- ============================================================


-- ──────────────────────────────────────────────────────────────────────────────
-- VIEW 1: Assignment Intelligence Report
-- Master report combining all relevant fields + risk segmentation.
-- This is the primary table Power BI Page 1 & 3 draw from.
-- ──────────────────────────────────────────────────────────────────────────────
DROP VIEW IF EXISTS v_AssignmentIntelligenceReport;
CREATE VIEW v_AssignmentIntelligenceReport AS
SELECT
    fp.assignment_id,
    fp.project_id,
    dp.project_name,
    dp.project_type,
    dp.stakes_level                                         AS project_stakes,
    fp.task_stakes_level,
    fp.employee_id,
    de.employee_name,
    de.role                                                 AS employee_role,
    de.department,
    de.tenure_years,
    fp.manager_id,
    dm.manager_name,
    fp.client_id,
    dc.client_name,
    dc.client_value_tier,
    dc.annual_revenue_usd                                   AS client_annual_value,

    -- Skill assessment
    fp.required_skill_id,
    ds.skill_name,
    fp.required_skill_score,
    fp.skill_gap,
    fp.self_assessment_bias,
    fp.mismatch_flag,
    fp.unverified_flag,

    -- Override behaviour
    fp.override_flag,
    fa.override_justification,
    fp.manager_override_ratio_6m,

    -- Historical performance
    fp.employee_hist_failure_rate,
    fp.early_warning_quality,
    CASE fp.early_warning_quality
        WHEN 0 THEN 'On Track'
        WHEN 1 THEN 'At Risk'
        WHEN 2 THEN 'Delayed'
        ELSE 'Unknown'
    END                                                     AS checkpoint_label,

    -- Outcomes
    fp.quality_score,
    fp.rework_pct,
    fp.client_status,
    fp.actual_revenue_usd,
    fp.expected_revenue_usd,
    fp.lost_revenue_usd,
    fp.target_failure                                       AS actual_failure,

    -- ML predictions
    fp.predicted_failure_prob,
    fp.risk_tier,
    CASE
        WHEN fp.predicted_failure_prob >= 0.70 THEN 'High'
        WHEN fp.predicted_failure_prob >= 0.40 THEN 'Medium'
        ELSE 'Low'
    END                                                     AS risk_category,

    -- Revenue at risk per assignment
    ROUND(fp.expected_revenue_usd * fp.predicted_failure_prob, 2) AS revenue_at_risk_usd,

    -- False on-track flag
    CASE
        WHEN fp.early_warning_quality = 0 AND fp.quality_score < 4.0 THEN 1
        ELSE 0
    END                                                     AS false_ontrack_flag,

    fp.assigned_date,
    dp.start_date                                           AS project_start,
    dp.end_date                                             AS project_end,
    dp.budget_usd                                           AS project_budget,
    dp.complexity_score

FROM fact_predictions fp
LEFT JOIN dim_employees  de ON fp.employee_id  = de.employee_id
LEFT JOIN dim_managers   dm ON fp.manager_id   = dm.manager_id
LEFT JOIN dim_clients    dc ON fp.client_id    = dc.client_id
LEFT JOIN dim_projects   dp ON fp.project_id   = dp.project_id
LEFT JOIN dim_skills     ds ON fp.required_skill_id = ds.skill_id
LEFT JOIN fact_assignments fa ON fp.assignment_id = fa.assignment_id;


-- ──────────────────────────────────────────────────────────────────────────────
-- VIEW 2: Manager Scorecard
-- Per-manager KPIs: override behaviour, churn attribution, revenue at risk.
-- Powers Page 2 (Manager Accountability).
-- ──────────────────────────────────────────────────────────────────────────────
DROP VIEW IF EXISTS v_ManagerScorecard;
CREATE VIEW v_ManagerScorecard AS
WITH base AS (
    SELECT
        fp.manager_id,
        dm.manager_name,
        dm.department,
        COUNT(fp.assignment_id)                             AS total_assignments,
        SUM(fp.override_flag)                               AS total_overrides,
        ROUND(AVG(fp.override_flag), 4)                     AS override_rate,
        ROUND(AVG(fp.mismatch_flag), 4)                     AS mismatch_rate,
        ROUND(AVG(fp.skill_gap), 2)                         AS avg_skill_gap,
        ROUND(AVG(fp.predicted_failure_prob), 4)            AS avg_failure_prob,

        -- Churn: only assignments with known outcomes
        SUM(CASE WHEN fp.client_status = 'Churned' THEN 1 ELSE 0 END) AS churned_clients,
        COUNT(CASE WHEN fp.client_status IS NOT NULL THEN 1 END)       AS assignments_with_outcome,

        -- Revenue
        ROUND(SUM(fp.lost_revenue_usd), 2)                 AS total_lost_revenue,
        ROUND(SUM(fp.expected_revenue_usd * fp.predicted_failure_prob), 2) AS forecasted_revenue_at_risk,

        -- Quality
        ROUND(AVG(fp.quality_score), 2)                    AS avg_quality_score,

        -- False on-track reports
        SUM(CASE
            WHEN fp.early_warning_quality = 0 AND fp.quality_score < 4.0 THEN 1
            ELSE 0
        END)                                                AS false_ontrack_count,

        -- High-risk assignments made
        SUM(CASE WHEN fp.predicted_failure_prob >= 0.70 THEN 1 ELSE 0 END) AS high_risk_count

    FROM fact_predictions fp
    LEFT JOIN dim_managers dm ON fp.manager_id = dm.manager_id
    GROUP BY fp.manager_id, dm.manager_name, dm.department
),
scored AS (
    SELECT *,
        ROUND(
            CAST(churned_clients AS FLOAT) /
            NULLIF(assignments_with_outcome, 0), 4
        )                                                   AS churn_rate,

        -- Favoritism Score: weighted index (0–100, higher = more biased)
        ROUND(
            (override_rate * 40)
            + (mismatch_rate * 30)
            + (CASE WHEN avg_skill_gap < -10 THEN 20 ELSE 0 END)
            + (CAST(false_ontrack_count AS FLOAT) / NULLIF(total_assignments, 0) * 10),
        2)                                                  AS favoritism_score

    FROM base
)
SELECT
    manager_id,
    manager_name,
    department,
    total_assignments,
    total_overrides,
    ROUND(override_rate * 100, 1)                           AS override_rate_pct,
    ROUND(mismatch_rate * 100, 1)                           AS mismatch_rate_pct,
    avg_skill_gap,
    avg_failure_prob,
    churned_clients,
    ROUND(churn_rate * 100, 1)                              AS churn_rate_pct,
    total_lost_revenue,
    forecasted_revenue_at_risk,
    avg_quality_score,
    false_ontrack_count,
    high_risk_count,
    favoritism_score,
    -- Label for conditional formatting
    CASE
        WHEN favoritism_score >= 40 THEN 'Critical'
        WHEN favoritism_score >= 20 THEN 'Elevated'
        ELSE 'Normal'
    END                                                     AS bias_risk_label
FROM scored
ORDER BY favoritism_score DESC;


-- ──────────────────────────────────────────────────────────────────────────────
-- VIEW 3: Favoritism Impact
-- Calculates direct financial cost of override + mismatch combinations.
-- Surfaces the specific dollar amount attributable to systematic bias.
-- Powers the "Favoritism Cost" KPI card and Page 2 waterfall.
-- ──────────────────────────────────────────────────────────────────────────────
DROP VIEW IF EXISTS v_FavoritismImpact;
CREATE VIEW v_FavoritismImpact AS
WITH mgr_flags AS (
    -- Mark managers whose override rate > 30%
    SELECT manager_id,
           ROUND(AVG(override_flag), 4) AS mgr_override_rate
    FROM fact_predictions
    GROUP BY manager_id
    HAVING mgr_override_rate > 0.30
),
biased_assignments AS (
    SELECT
        fp.assignment_id,
        fp.project_id,
        fp.employee_id,
        de.employee_name,
        fp.manager_id,
        dm.manager_name,
        dm.department,
        fp.client_id,
        dc.client_name,
        fp.override_flag,
        fp.mismatch_flag,
        fp.skill_gap,
        fp.predicted_failure_prob,
        fp.quality_score,
        fp.client_status,
        fp.expected_revenue_usd,
        fp.actual_revenue_usd,
        fp.lost_revenue_usd,
        fp.rework_pct,
        ROUND(fp.rework_pct * dp.budget_usd, 2)            AS rework_cost_usd,
        fp.assigned_date,
        fa.override_justification,
        mf.mgr_override_rate
    FROM fact_predictions fp
    INNER JOIN mgr_flags mf ON fp.manager_id = mf.manager_id
    LEFT JOIN dim_employees  de ON fp.employee_id  = de.employee_id
    LEFT JOIN dim_managers   dm ON fp.manager_id   = dm.manager_id
    LEFT JOIN dim_clients    dc ON fp.client_id    = dc.client_id
    LEFT JOIN dim_projects   dp ON fp.project_id   = dp.project_id
    LEFT JOIN fact_assignments fa ON fp.assignment_id = fa.assignment_id
    WHERE fp.mismatch_flag = 1    -- mismatch present
      AND fp.override_flag = 1    -- manager overrode the flag
)
SELECT
    *,
    ROUND(lost_revenue_usd + rework_cost_usd, 2)           AS total_financial_impact_usd,
    CASE
        WHEN client_status = 'Churned' THEN 'Revenue Lost'
        WHEN quality_score < 4.0      THEN 'Quality Failure'
        ELSE 'Elevated Risk'
    END                                                     AS impact_type
FROM biased_assignments
ORDER BY total_financial_impact_usd DESC;


-- ──────────────────────────────────────────────────────────────────────────────
-- VIEW 4: What-If Scenarios
-- Simulates: "What if all assignments respected skill thresholds?"
-- Shows estimated savings from skill-compliant assignments.
-- Powers the simulation bookmark on Page 3.
-- ──────────────────────────────────────────────────────────────────────────────
DROP VIEW IF EXISTS v_WhatIfScenarios;
CREATE VIEW v_WhatIfScenarios AS
WITH actual AS (
    SELECT
        manager_id,
        COUNT(*)                                                    AS total_assignments,
        SUM(CASE WHEN mismatch_flag = 1 THEN 1 ELSE 0 END)         AS mismatched_assignments,
        ROUND(SUM(lost_revenue_usd), 2)                             AS actual_lost_revenue,
        ROUND(SUM(expected_revenue_usd * predicted_failure_prob), 2) AS actual_revenue_at_risk,
        ROUND(AVG(quality_score), 2)                                AS actual_avg_quality,
        ROUND(SUM(expected_revenue_usd), 2)                         AS total_expected_revenue
    FROM fact_predictions
    GROUP BY manager_id
),
simulated AS (
    -- Assume: compliant assignments reduce failure prob to base rate (~15%)
    -- and eliminate override-related risk premium
    SELECT
        manager_id,
        ROUND(SUM(
            CASE
                WHEN mismatch_flag = 1 OR override_flag = 1
                -- Replace biased assignments with baseline risk
                THEN expected_revenue_usd * 0.12
                ELSE expected_revenue_usd * predicted_failure_prob
            END
        ), 2)                                                       AS simulated_revenue_at_risk,
        ROUND(SUM(
            CASE
                WHEN mismatch_flag = 1 OR override_flag = 1 THEN 0
                ELSE lost_revenue_usd
            END
        ), 2)                                                       AS simulated_lost_revenue,
        ROUND(AVG(
            CASE
                WHEN mismatch_flag = 1 THEN LEAST(quality_score + 2.5, 10.0)
                ELSE quality_score
            END
        ), 2)                                                       AS simulated_avg_quality
    FROM fact_predictions
    GROUP BY manager_id
)
SELECT
    a.manager_id,
    dm.manager_name,
    dm.department,
    a.total_assignments,
    a.mismatched_assignments,
    ROUND(CAST(a.mismatched_assignments AS FLOAT) / NULLIF(a.total_assignments,0) * 100, 1) AS mismatch_pct,
    a.total_expected_revenue,

    -- Actual state
    a.actual_lost_revenue,
    a.actual_revenue_at_risk,
    a.actual_avg_quality,

    -- Simulated (skill-compliant) state
    s.simulated_lost_revenue,
    s.simulated_revenue_at_risk,
    s.simulated_avg_quality,

    -- Delta (the potential gain from compliance)
    ROUND(a.actual_revenue_at_risk - s.simulated_revenue_at_risk, 2) AS recoverable_revenue_usd,
    ROUND(a.actual_lost_revenue    - s.simulated_lost_revenue,    2) AS avoided_loss_usd,
    ROUND(s.simulated_avg_quality  - a.actual_avg_quality,        2) AS quality_improvement

FROM actual a
INNER JOIN simulated s  ON a.manager_id = s.manager_id
LEFT JOIN  dim_managers dm ON a.manager_id = dm.manager_id
ORDER BY recoverable_revenue_usd DESC;


-- ──────────────────────────────────────────────────────────────────────────────
-- VIEW 5: Employee Competence Passport
-- Used in the Power BI Tooltip Page: per-employee skill profile.
-- ──────────────────────────────────────────────────────────────────────────────
DROP VIEW IF EXISTS v_EmployeeCompetencePassport;
CREATE VIEW v_EmployeeCompetencePassport AS
WITH latest_skills AS (
    -- Most recent verified score per employee-skill pair
    SELECT
        es.employee_id,
        es.skill_id,
        ds.skill_name,
        es.verified_score,
        es.self_assessed_score,
        ROUND(CAST(es.self_assessed_score AS FLOAT) - es.verified_score, 1) AS bias,
        es.audit_date,
        ROW_NUMBER() OVER (
            PARTITION BY es.employee_id, es.skill_id
            ORDER BY es.audit_date DESC
        )                                                   AS rn
    FROM fact_employee_skills es
    LEFT JOIN dim_skills ds ON es.skill_id = ds.skill_id
),
emp_perf AS (
    SELECT
        employee_id,
        COUNT(assignment_id)                                AS total_assignments,
        ROUND(AVG(predicted_failure_prob), 4)               AS avg_failure_prob,
        ROUND(AVG(quality_score), 2)                        AS avg_quality_score,
        SUM(CASE WHEN client_status = 'Churned' THEN 1 ELSE 0 END) AS churned_count,
        ROUND(AVG(CAST(target_failure AS FLOAT)), 4)        AS historical_failure_rate,
        ROUND(AVG(mismatch_flag), 4)                        AS mismatch_rate,
        SUM(lost_revenue_usd)                               AS total_revenue_impact
    FROM fact_predictions
    GROUP BY employee_id
)
SELECT
    de.employee_id,
    de.employee_name,
    de.role,
    de.department,
    de.tenure_years,
    de.manager_id,

    -- Latest skill records
    ls.skill_id,
    ls.skill_name,
    ls.verified_score,
    ls.self_assessed_score,
    ls.bias                                                 AS self_assessment_bias,
    ls.audit_date                                           AS last_audit_date,

    -- Performance KPIs
    ep.total_assignments,
    ROUND(ep.historical_failure_rate * 100, 1)              AS failure_rate_pct,
    ep.avg_quality_score,
    ROUND(ep.mismatch_rate * 100, 1)                        AS mismatch_rate_pct,
    ep.churned_count,
    ep.avg_failure_prob,
    ep.total_revenue_impact

FROM latest_skills ls
INNER JOIN dim_employees de ON ls.employee_id = de.employee_id
LEFT JOIN  emp_perf ep      ON ls.employee_id = ep.employee_id
WHERE ls.rn = 1
ORDER BY de.employee_id, ls.skill_name;


-- ──────────────────────────────────────────────────────────────────────────────
-- VIEW 6: Full Audit Trail — False On-Track Incidents
-- Powers Page 4. Surfaces every case where a project was reported
-- "On Track" at the 50% milestone but ended with quality < 4.0.
-- ──────────────────────────────────────────────────────────────────────────────
DROP VIEW IF EXISTS v_FalseOnTrackAudit;
CREATE VIEW v_FalseOnTrackAudit AS
SELECT
    fp.assignment_id,
    fp.project_id,
    dp.project_name,
    dp.project_type,
    fp.employee_id,
    de.employee_name,
    de.role,
    fp.manager_id,
    dm.manager_name,
    fp.client_id,
    dc.client_name,
    dc.client_value_tier,

    -- The false report
    'On Track'                                              AS reported_at_50pct,
    ROUND(fp.quality_score, 2)                              AS final_quality_score,
    fp.client_status,
    ROUND(fp.rework_pct * 100, 1)                           AS rework_pct,
    fp.override_flag,
    fa.override_justification,

    -- Financial impact
    fp.expected_revenue_usd,
    fp.lost_revenue_usd,
    fp.predicted_failure_prob,

    -- Audit narrative
    CASE
        WHEN fp.client_status = 'Churned' AND fp.override_flag = 1
        THEN 'CRITICAL: Override + false report + churn — full audit required.'
        WHEN fp.client_status = 'Churned'
        THEN 'HIGH: False on-track report preceded client churn.'
        WHEN fp.quality_score < 3.0
        THEN 'HIGH: Severe quality failure masked by false milestone report.'
        ELSE 'MEDIUM: Quality below threshold despite on-track report.'
    END                                                     AS audit_finding,

    fp.assigned_date

FROM fact_predictions fp
LEFT JOIN dim_employees  de ON fp.employee_id  = de.employee_id
LEFT JOIN dim_managers   dm ON fp.manager_id   = dm.manager_id
LEFT JOIN dim_clients    dc ON fp.client_id    = dc.client_id
LEFT JOIN dim_projects   dp ON fp.project_id   = dp.project_id
LEFT JOIN fact_assignments fa ON fp.assignment_id = fa.assignment_id

-- The key filter: on-track reported but quality failed
WHERE fp.early_warning_quality = 0   -- reported "On Track"
  AND fp.quality_score < 4.0         -- but actually failed

ORDER BY fp.lost_revenue_usd DESC;


-- ──────────────────────────────────────────────────────────────────────────────
-- HELPER: Total Summary Stats (single-row KPI source for Power BI cards)
-- ──────────────────────────────────────────────────────────────────────────────
DROP VIEW IF EXISTS v_ExecutiveSummaryKPIs;
CREATE VIEW v_ExecutiveSummaryKPIs AS
SELECT
    COUNT(DISTINCT project_id)                                  AS total_projects,
    COUNT(assignment_id)                                        AS total_assignments,
    ROUND(SUM(CASE WHEN risk_tier = 'High' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS pct_high_risk,
    ROUND(SUM(CASE WHEN predicted_failure_prob >= 0.70 THEN expected_revenue_usd * predicted_failure_prob ELSE 0 END), 0) AS total_revenue_at_risk,
    ROUND(SUM(lost_revenue_usd), 0)                             AS total_lost_revenue,
    COUNT(DISTINCT employee_id)                                 AS total_employees_assigned,
    SUM(CASE WHEN override_flag = 1 THEN 1 ELSE 0 END)         AS total_overrides,
    ROUND(AVG(quality_score), 2)                                AS avg_quality_score,
    SUM(CASE WHEN client_status = 'Churned' THEN 1 ELSE 0 END) AS total_churned_clients,
    -- Favoritism cost: override + mismatch + churned
    ROUND(SUM(
        CASE WHEN override_flag = 1 AND mismatch_flag = 1 AND client_status = 'Churned'
        THEN lost_revenue_usd ELSE 0 END
    ), 0)                                                       AS favoritism_direct_cost,
    -- Assignment Health Score: 0-100
    ROUND((1 - AVG(predicted_failure_prob)) * 100, 1)           AS assignment_health_score
FROM fact_predictions;
