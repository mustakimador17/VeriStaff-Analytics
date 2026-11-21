"""
VeriStaff Analytics — Phase 1: Realistic Data Simulation
=========================================================
Generates synthetic but structurally realistic CSVs for a mid-sized
event marketing agency (120 employees, 8 managers, 2-year window).

Hidden patterns embedded (tune via CONFIG block):
  • Mgr_5 systematically assigns Emp_023 to high-stakes presentations
    despite a verified skill score of 35/100, always overriding system flags.
    Emp_023's projects carry ~60% client churn.
  • Mgr_2 suppresses Emp_007 (top performer) onto low-stakes tasks only.
  • Projects falsely reported "on_track" at 50% milestone but ending with
    quality < 4.0 have 90% churn probability.
  • Favorites group has self-assessment inflated 20-30 pts above verified.

Run:
    python 01_generate_data.py
Output:
    data/raw/employees.csv
    data/raw/skills.csv
    data/raw/employee_skills.csv
    data/raw/clients.csv
    data/raw/projects.csv
    data/raw/tasks.csv
    data/raw/assignments.csv
    data/raw/outcomes.csv
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
import os

# ─── CONFIG ───────────────────────────────────────────────────────────────────
SEED = 42
N_EMPLOYEES        = 120
N_MANAGERS         = 8
N_PROJECTS         = 240        # ~10/month over 24 months
N_CLIENTS          = 45
START_DATE         = datetime(2023, 1, 1)
END_DATE           = datetime(2024, 12, 31)
OUTPUT_DIR         = "data/raw"

# Pattern strength (0 = no bias, 1 = always biased)
MGR5_BIAS_STRENGTH     = 0.90
MGR2_SUPPRESS_STRENGTH = 0.85
SELF_ASSESS_BASE_INFLATION  = 12   # avg pts for normal employees
SELF_ASSESS_FAVE_INFLATION  = 25   # avg pts for Mgr_5 favorites

# Special entity IDs (these are the story protagonists)
PROTAGONIST_EMP   = "EMP_023"   # Mgr_5's unqualified protégé
BURIED_EMP        = "EMP_007"   # Mgr_2's suppressed top performer
BIAS_MANAGER      = "MGR_005"
SUPPRESS_MANAGER  = "MGR_002"

# ─── SEED ─────────────────────────────────────────────────────────────────────
np.random.seed(SEED)
random.seed(SEED)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── REFERENCE DATA ───────────────────────────────────────────────────────────
DEPARTMENTS = ["Events", "Marketing", "Logistics", "Finance"]
ROLES = {
    "Events":    ["Event Coordinator", "Senior Event Manager", "AV Specialist", "Client Liaison"],
    "Marketing": ["Campaign Manager", "Brand Strategist", "Content Producer", "Media Buyer"],
    "Logistics": ["Logistics Coordinator", "Vendor Manager", "Fleet Supervisor", "Supply Chain Analyst"],
    "Finance":   ["Budget Analyst", "Financial Controller", "Billing Specialist", "Cost Estimator"],
}
SKILL_DEFS = [
    ("SKL_001", "Client Presentation",  True),   # (id, name, is_high_stakes)
    ("SKL_002", "Technical Setup",      False),
    ("SKL_003", "Crisis Management",    True),
    ("SKL_004", "Budget Handling",      True),
    ("SKL_005", "Vendor Coordination",  False),
    ("SKL_006", "Team Leadership",      True),
    ("SKL_007", "Data Reporting",       False),
    ("SKL_008", "Logistics Planning",   False),
]
PROJECT_TYPES = [
    "Product Launch", "Annual Conference", "Trade Show", "Corporate Gala",
    "Brand Activation", "Sponsorship Event", "Investor Summit", "Award Ceremony",
    "Sales Kickoff", "PR Campaign", "Regional Roadshow", "Team Offsite",
]
CLIENT_NAMES = [
    "Apex Ventures", "BlueWave Corp", "Chromex Ltd", "DeltaForce Media",
    "Echo Systems", "Frontier Analytics", "GlobalNex", "Horizon Brands",
    "IronPath Retail", "JetStream Partners", "KaleidoGroup", "LunaMedia",
    "MavenTech", "NorthStar Events", "Orion Holdings", "PeakPulse",
    "QuestCo", "RedSail Agency", "Solaris Inc", "TerraNova",
    "Umbra Digital", "Vertex Corp", "WillowBridge", "Xenith Labs",
    "Yukon Dynamics", "ZenithPro", "Arco Brands", "Bluebell Group",
    "Cascade Retail", "Denova Media", "EastBay Ventures", "FusionPoint",
    "Grantfield Co", "HarborView", "IntelliMedia", "JoveBrand",
    "Kairos Group", "Lumina Partners", "Mira Holdings", "Novex Retail",
    "Onyx Events", "Prism Media", "Quantum Brands", "Riviera Corp",
    "Summit Analytics",
]

# ─── 1. MANAGERS ──────────────────────────────────────────────────────────────
print("Generating managers...")
manager_rows = []
mgr_dept_map = {}
for i in range(1, N_MANAGERS + 1):
    mgr_id   = f"MGR_{i:03d}"
    dept     = DEPARTMENTS[(i - 1) % len(DEPARTMENTS)]  # 2 managers per dept
    mgr_dept_map[mgr_id] = dept
    manager_rows.append({
        "manager_id":  mgr_id,
        "manager_name": f"Manager_{i}",
        "department":   dept,
        "hire_date":   (START_DATE - timedelta(days=np.random.randint(365, 2000))).strftime("%Y-%m-%d"),
    })
df_managers = pd.DataFrame(manager_rows)

# ─── 2. EMPLOYEES ─────────────────────────────────────────────────────────────
print("Generating employees...")
# Map employees to managers (15 per manager on average)
emp_rows = []
emp_perf_base = {}   # true underlying performance ability 0-1

for i in range(1, N_EMPLOYEES + 1):
    emp_id    = f"EMP_{i:03d}"
    mgr_idx   = (i - 1) % N_MANAGERS + 1
    mgr_id    = f"MGR_{mgr_idx:03d}"
    dept      = mgr_dept_map[mgr_id]
    role      = random.choice(ROLES[dept])
    tenure    = round(np.random.exponential(2.5) + 0.5, 1)  # years, skewed
    tenure    = min(tenure, 12.0)

    # True ability: normally distributed but Emp_007 is top, Emp_023 is weak
    if emp_id == PROTAGONIST_EMP:
        true_ability = np.random.uniform(0.20, 0.35)  # weak
    elif emp_id == BURIED_EMP:
        true_ability = np.random.uniform(0.88, 0.98)  # top performer
    else:
        true_ability = np.clip(np.random.normal(0.65, 0.18), 0.15, 0.99)

    emp_perf_base[emp_id] = true_ability

    emp_rows.append({
        "employee_id":    emp_id,
        "employee_name":  f"Employee_{i}",
        "role":           role,
        "department":     dept,
        "manager_id":     mgr_id,
        "tenure_years":   tenure,
        "hire_date":      (START_DATE - timedelta(days=int(tenure * 365))).strftime("%Y-%m-%d"),
        "true_ability":   round(true_ability, 4),   # hidden ground truth for simulation
    })

df_employees = pd.DataFrame(emp_rows)

# ─── 3. SKILLS TABLE ──────────────────────────────────────────────────────────
print("Generating skills...")
skill_rows = [{"skill_id": s[0], "skill_name": s[1], "is_high_stakes": s[2]} for s in SKILL_DEFS]
df_skills = pd.DataFrame(skill_rows)

# ─── 4. EMPLOYEE SKILLS ───────────────────────────────────────────────────────
# Each employee has 4-6 skills audited at irregular intervals
print("Generating employee skills (audit + self-assessment)...")
es_rows = []

# Identify Mgr_5's full team (protégé + teammates)
mgr5_team = df_employees[df_employees["manager_id"] == BIAS_MANAGER]["employee_id"].tolist()

for _, emp in df_employees.iterrows():
    emp_id   = emp["employee_id"]
    ability  = emp["true_ability"]
    n_skills = random.randint(4, 7)
    emp_skills = random.sample(SKILL_DEFS, n_skills)

    for skill in emp_skills:
        skl_id = skill[0]
        is_hs  = skill[2]

        # Verified score: correlated with true ability; Emp_023 is fixed weak in Client Presentation
        if emp_id == PROTAGONIST_EMP and skl_id == "SKL_001":
            verified = int(np.random.normal(35, 5))          # deliberately weak
        elif emp_id == BURIED_EMP:
            verified = int(np.random.normal(ability * 100, 4))  # accurately high
        else:
            base     = ability * 100
            noise    = np.random.normal(0, 8)
            verified = int(np.clip(base + noise, 10, 100))

        # Self-assessed: inflated, more so for Mgr_5 favorites
        if emp_id in mgr5_team:
            inflation = int(np.random.normal(SELF_ASSESS_FAVE_INFLATION, 5))
        elif emp_id == BURIED_EMP:
            inflation = int(np.random.normal(3, 3))          # accurate, humble
        else:
            inflation = int(np.random.normal(SELF_ASSESS_BASE_INFLATION, 6))

        self_assessed = int(np.clip(verified + inflation, 10, 100))

        # Audit date: random within 2023-2024, one entry per 6-12 months
        audit_months = sorted(random.sample(range(0, 24), random.choice([1, 2])))
        for month_offset in audit_months:
            audit_dt = (START_DATE + timedelta(days=month_offset * 30)).strftime("%Y-%m-%d")
            # Slight drift in verified score over time (improvement)
            drift     = int(np.random.normal(1.5 * (month_offset / 12), 2))
            v_drifted = int(np.clip(verified + drift, 10, 100))
            sa_drifted= int(np.clip(self_assessed + drift * 0.5, 10, 100))

            es_rows.append({
                "employee_id":      emp_id,
                "skill_id":         skl_id,
                "verified_score":   v_drifted,
                "self_assessed_score": sa_drifted,
                "audit_date":       audit_dt,
                "audited_by":       f"MGR_{random.randint(1, N_MANAGERS):03d}",
            })

df_employee_skills = pd.DataFrame(es_rows)

# ─── 5. CLIENTS ───────────────────────────────────────────────────────────────
print("Generating clients...")
client_rows = []
for i, name in enumerate(CLIENT_NAMES[:N_CLIENTS]):
    tier     = random.choices(["High", "Medium", "Low"], weights=[0.25, 0.45, 0.30])[0]
    base_rev = {"High": (80000, 300000), "Medium": (20000, 79999), "Low": (5000, 19999)}[tier]
    client_rows.append({
        "client_id":          f"CLI_{i+1:03d}",
        "client_name":        name,
        "client_value_tier":  tier,
        "annual_revenue_usd": int(np.random.uniform(*base_rev)),
        "relationship_start": (START_DATE - timedelta(days=np.random.randint(180, 1500))).strftime("%Y-%m-%d"),
    })
df_clients = pd.DataFrame(client_rows)

# ─── 6. PROJECTS ──────────────────────────────────────────────────────────────
print("Generating projects...")
date_range_days = (END_DATE - START_DATE).days

project_rows = []
for i in range(1, N_PROJECTS + 1):
    proj_id     = f"PRJ_{i:04d}"
    proj_type   = random.choice(PROJECT_TYPES)
    client      = df_clients.sample(1).iloc[0]
    stakes      = random.choices(["High", "Medium", "Low"], weights=[0.30, 0.45, 0.25])[0]
    budget      = int(np.random.uniform(15000, 250000))
    revenue_mult= np.random.uniform(1.15, 1.55)  # margin on top of budget
    revenue     = int(budget * revenue_mult)
    duration_d  = int(np.random.uniform(14, 120))

    # Spread projects across the 2-year window
    offset_days = np.random.randint(0, date_range_days - duration_d)
    start_dt    = START_DATE + timedelta(days=offset_days)
    end_dt      = start_dt + timedelta(days=duration_d)

    # Required skills: 2-4 skills with thresholds
    n_req_skills  = random.randint(2, 4)
    req_skills    = random.sample([s[0] for s in SKILL_DEFS], n_req_skills)
    thresholds    = {s: int(np.random.uniform(55, 85)) for s in req_skills}
    complexity    = round(n_req_skills * 0.2 + budget / 250000 * 0.5 + (1 if stakes == "High" else 0) * 0.3, 3)

    project_rows.append({
        "project_id":          proj_id,
        "project_name":        f"{proj_type} — {client['client_name']}",
        "project_type":        proj_type,
        "client_id":           client["client_id"],
        "stakes_level":        stakes,
        "budget_usd":          budget,
        "expected_revenue_usd":revenue,
        "start_date":          start_dt.strftime("%Y-%m-%d"),
        "end_date":            end_dt.strftime("%Y-%m-%d"),
        "required_skills":     ",".join(req_skills),      # denormalized for readability
        "skill_thresholds":    str(thresholds),
        "complexity_score":    complexity,
        "n_required_skills":   n_req_skills,
    })

df_projects = pd.DataFrame(project_rows)

# ─── 7. TASKS ─────────────────────────────────────────────────────────────────
print("Generating tasks...")
TASK_TEMPLATES = {
    "SKL_001": ("Client Kick-off Presentation",   "High"),
    "SKL_002": ("AV & Technical Setup",           "Low"),
    "SKL_003": ("On-site Crisis Response",        "High"),
    "SKL_004": ("Budget Reconciliation",          "Medium"),
    "SKL_005": ("Vendor Negotiation",             "Medium"),
    "SKL_006": ("Team Briefing & Leadership",     "High"),
    "SKL_007": ("Post-event Data Report",         "Low"),
    "SKL_008": ("Logistics Coordination",         "Low"),
}

task_rows = []
task_id_counter = 1

for _, proj in df_projects.iterrows():
    req_skills = proj["required_skills"].split(",")
    thresholds = eval(proj["skill_thresholds"])  # safe: we generated it

    for skl in req_skills:
        task_id   = f"TSK_{task_id_counter:05d}"
        tname, default_stakes = TASK_TEMPLATES.get(skl, ("General Task", "Medium"))
        # Override stakes if project is high-stakes
        final_stakes = proj["stakes_level"] if proj["stakes_level"] == "High" else default_stakes

        task_rows.append({
            "task_id":             task_id,
            "project_id":          proj["project_id"],
            "task_name":           tname,
            "required_skill_id":   skl,
            "required_skill_score":thresholds[skl],
            "task_stakes_level":   final_stakes,
            "client_id":           proj["client_id"],
            "task_revenue_share_usd": int(proj["expected_revenue_usd"] / len(req_skills)),
        })
        task_id_counter += 1

df_tasks = pd.DataFrame(task_rows)

# ─── 8. ASSIGNMENTS ───────────────────────────────────────────────────────────
print("Generating assignments (embedding bias patterns)...")

# Build lookup: latest verified score per (employee, skill)
# Keep most recent audit per employee-skill
df_latest_skills = (
    df_employee_skills
    .sort_values("audit_date")
    .groupby(["employee_id", "skill_id"])
    .last()
    .reset_index()[["employee_id", "skill_id", "verified_score"]]
)

def get_verified(emp_id, skl_id):
    row = df_latest_skills[
        (df_latest_skills["employee_id"] == emp_id) &
        (df_latest_skills["skill_id"] == skl_id)
    ]
    return row["verified_score"].values[0] if len(row) > 0 else None

# Pool employees by manager
mgr_to_emps = df_employees.groupby("manager_id")["employee_id"].apply(list).to_dict()
emp_to_mgr  = df_employees.set_index("employee_id")["manager_id"].to_dict()

assignment_rows = []
asgn_id_counter = 1

for _, task in df_tasks.iterrows():
    proj_id   = task["project_id"]
    proj_row  = df_projects[df_projects["project_id"] == proj_id].iloc[0]
    skl_id    = task["required_skill_id"]
    req_score = task["required_skill_score"]
    stakes    = task["task_stakes_level"]
    client_id = task["client_id"]

    # Determine which manager owns this project (random, but consistent per project)
    proj_mgr_seed = int(proj_id.split("_")[1]) % N_MANAGERS + 1
    mgr_id = f"MGR_{proj_mgr_seed:03d}"

    pool = mgr_to_emps.get(mgr_id, [])
    if not pool:
        pool = df_employees["employee_id"].tolist()

    # ── BIAS PATTERN 1: Mgr_5 assigns Emp_023 to high-stakes presentations ──
    chosen_emp   = None
    override_flag = False
    override_just = ""

    is_presentation_task = (skl_id == "SKL_001" and stakes == "High")

    if mgr_id == BIAS_MANAGER and is_presentation_task:
        if random.random() < MGR5_BIAS_STRENGTH:
            chosen_emp    = PROTAGONIST_EMP
            override_flag = True
            override_just = random.choice([
                "Emp_023 has strong client rapport despite lower audit score.",
                "Previous client requested Emp_023 personally.",
                "Scheduling conflict with qualified staff; Emp_023 is available.",
                "Manager discretion — Emp_023 is being developed for this role.",
                "Client relationship takes precedence over skill metric.",
            ])

    # ── BIAS PATTERN 2: Mgr_2 suppresses Emp_007 into low-stakes tasks ──
    if mgr_id == SUPPRESS_MANAGER and stakes == "High" and BURIED_EMP in pool:
        if random.random() < MGR2_SUPPRESS_STRENGTH:
            # Actively avoid assigning Emp_007 to high-stakes
            pool_filtered = [e for e in pool if e != BURIED_EMP]
            if pool_filtered:
                pool = pool_filtered

    # Default: pick best-qualified available employee
    if chosen_emp is None:
        # Score candidates by verified skill vs required
        best_score = -9999
        for emp_id in pool:
            v = get_verified(emp_id, skl_id)
            if v is None:
                continue
            gap   = v - req_score
            score = gap + emp_perf_base.get(emp_id, 0.5) * 20  # weight ability
            if score > best_score:
                best_score   = score
                chosen_emp   = emp_id

        # If no verified match, fall back to random from pool
        if chosen_emp is None:
            chosen_emp = random.choice(pool)

        # Check if chosen employee meets threshold; flag if not
        v_chosen = get_verified(chosen_emp, skl_id)
        if v_chosen is not None and v_chosen < req_score:
            override_flag = True   # system flagged but manager proceeded
            override_just = "No fully qualified candidate available in team."

    # Assignment date = project start + random day offset
    proj_start = datetime.strptime(proj_row["start_date"], "%Y-%m-%d")
    asgn_date  = proj_start + timedelta(days=random.randint(0, 5))

    assignment_rows.append({
        "assignment_id":        f"ASN_{asgn_id_counter:05d}",
        "task_id":              task["task_id"],
        "project_id":           proj_id,
        "employee_id":          chosen_emp,
        "manager_id":           mgr_id,
        "assigned_date":        asgn_date.strftime("%Y-%m-%d"),
        "override_flag":        int(override_flag),
        "override_justification": override_just,
        "client_id":            client_id,
        "task_stakes_level":    stakes,
        "required_skill_id":    skl_id,
        "required_skill_score": req_score,
    })
    asgn_id_counter += 1

df_assignments = pd.DataFrame(assignment_rows)

# ─── 9. OUTCOMES ──────────────────────────────────────────────────────────────
print("Generating outcomes (embedding churn and false-report patterns)...")

outcome_rows = []

for _, asgn in df_assignments.iterrows():
    asgn_id   = asgn["assignment_id"]
    emp_id    = asgn["employee_id"]
    mgr_id    = asgn["manager_id"]
    skl_id    = asgn["required_skill_id"]
    req_score = asgn["required_skill_score"]
    stakes    = asgn["task_stakes_level"]
    proj_id   = asgn["project_id"]
    override  = asgn["override_flag"]

    # Get verified skill score for this assignment
    v_score   = get_verified(emp_id, skl_id)
    skill_gap = (v_score - req_score) if v_score is not None else -30  # penalize unknown

    # Base quality: correlated with ability and skill gap
    ability   = emp_perf_base.get(emp_id, 0.65)
    base_qual = (ability * 6.0) + (skill_gap / 100.0) * 3.0  # scale to 0-10
    noise     = np.random.normal(0, 0.8)
    quality   = float(np.clip(base_qual + noise, 0.5, 10.0))

    # ── PATTERN: Emp_023 in high-stakes Client Presentation → degraded quality ──
    if emp_id == PROTAGONIST_EMP and skl_id == "SKL_001" and stakes == "High":
        quality = float(np.clip(np.random.normal(2.8, 0.9), 0.5, 5.0))

    # Rework hours: inversely related to quality
    rework_pct = max(0, (10 - quality) / 10 * 0.35)  # up to 35% of budget as rework
    rework_pct += np.random.uniform(0, 0.05)          # random noise
    rework_pct = round(rework_pct, 4)

    proj_budget = df_projects[df_projects["project_id"] == proj_id]["budget_usd"].values[0]
    rework_hours= int(rework_pct * proj_budget / 75)  # assume $75/hr labour

    # Cost overrun (%)
    cost_overrun_pct = round(max(0, rework_pct * 1.5 + np.random.uniform(-0.02, 0.08)), 4)

    # Mid-checkpoint status (50% milestone report)
    # False on-track pattern: some low-quality assignments are falsely reported OK
    truly_on_track = quality >= 5.0
    false_report_chance = 0.30 if (mgr_id == BIAS_MANAGER and not truly_on_track) else 0.10
    if truly_on_track:
        mid_status = "On Track"
    elif random.random() < false_report_chance:
        mid_status = "On Track"   # <-- FALSE REPORT (the pattern we want to detect)
    else:
        mid_status = random.choice(["At Risk", "Delayed"])

    # ── PATTERN: False "on_track" + quality < 4 → 90% churn probability ──
    # Churn model
    churn_prob = 0.0
    if quality < 4.0:
        churn_prob += 0.55
        if mid_status == "On Track":    # falsely reported
            churn_prob += 0.35          # → ~90% total
    if emp_id == PROTAGONIST_EMP and stakes == "High":
        churn_prob += 0.25
    if skill_gap < -20:
        churn_prob += 0.15
    if override == 1 and stakes == "High":
        churn_prob += 0.10
    churn_prob = min(churn_prob + np.random.uniform(-0.05, 0.05), 1.0)

    churned    = int(random.random() < churn_prob)
    cl_status  = "Churned" if churned else random.choices(
        ["Renewed", "Active"], weights=[0.65, 0.35]
    )[0]

    proj_rev   = df_projects[df_projects["project_id"] == proj_id]["expected_revenue_usd"].values[0]
    actual_rev = int(proj_rev * (1 - cost_overrun_pct) * (0.0 if churned else 1.0))
    lost_rev   = int(proj_rev - actual_rev)

    outcome_rows.append({
        "assignment_id":       asgn_id,
        "project_id":          proj_id,
        "quality_score":       round(quality, 2),
        "rework_pct":          rework_pct,
        "rework_hours":        rework_hours,
        "cost_overrun_pct":    cost_overrun_pct,
        "mid_checkpoint_status": mid_status,
        "client_status":       cl_status,
        "actual_revenue_usd":  actual_rev,
        "expected_revenue_usd":proj_rev,
        "lost_revenue_usd":    lost_rev,
        "churn_probability_true": round(churn_prob, 4),  # ground truth (hidden from model)
    })

df_outcomes = pd.DataFrame(outcome_rows)

# ─── WRITE CSVs ───────────────────────────────────────────────────────────────
print("\nWriting CSVs to", OUTPUT_DIR)
df_managers.to_csv(f"{OUTPUT_DIR}/managers.csv",         index=False)
df_employees.to_csv(f"{OUTPUT_DIR}/employees.csv",       index=False)
df_skills.to_csv(f"{OUTPUT_DIR}/skills.csv",             index=False)
df_employee_skills.to_csv(f"{OUTPUT_DIR}/employee_skills.csv", index=False)
df_clients.to_csv(f"{OUTPUT_DIR}/clients.csv",           index=False)
df_projects.to_csv(f"{OUTPUT_DIR}/projects.csv",         index=False)
df_tasks.to_csv(f"{OUTPUT_DIR}/tasks.csv",               index=False)
df_assignments.to_csv(f"{OUTPUT_DIR}/assignments.csv",   index=False)
df_outcomes.to_csv(f"{OUTPUT_DIR}/outcomes.csv",         index=False)

# ─── SUMMARY ──────────────────────────────────────────────────────────────────
print("\n── Data Generation Summary ──────────────────────────────────────────")
print(f"  Managers       : {len(df_managers)}")
print(f"  Employees      : {len(df_employees)}")
print(f"  Skill records  : {len(df_employee_skills)}")
print(f"  Clients        : {len(df_clients)}")
print(f"  Projects       : {len(df_projects)}")
print(f"  Tasks          : {len(df_tasks)}")
print(f"  Assignments    : {len(df_assignments)}")
print(f"  Outcomes       : {len(df_outcomes)}")
print()
print("── Pattern Verification ─────────────────────────────────────────────")

# Verify Emp_023 pattern
emp23_asgns = df_assignments[df_assignments["employee_id"] == PROTAGONIST_EMP]
emp23_hs    = emp23_asgns[(emp23_asgns["required_skill_id"] == "SKL_001") &
                           (emp23_asgns["task_stakes_level"] == "High")]
print(f"  Emp_023 high-stakes presentation assignments : {len(emp23_hs)}")

emp23_outcomes = df_outcomes[df_outcomes["assignment_id"].isin(emp23_asgns["assignment_id"])]
churn_rate_23  = (emp23_outcomes["client_status"] == "Churned").mean()
print(f"  Emp_023 churn rate                          : {churn_rate_23:.1%}  (target ~60%)")

# Verify Emp_007 suppression
emp07_asgns = df_assignments[df_assignments["employee_id"] == BURIED_EMP]
emp07_hs_pct = (emp07_asgns["task_stakes_level"] == "High").mean()
print(f"  Emp_007 high-stakes assignment rate         : {emp07_hs_pct:.1%}  (should be LOW)")

# Verify false-report churn pattern
false_ot = df_outcomes[
    (df_outcomes["quality_score"] < 4.0) &
    (df_outcomes["mid_checkpoint_status"] == "On Track")
]
false_ot_churn = (false_ot["client_status"] == "Churned").mean()
print(f"  False 'On Track' + low quality churn rate  : {false_ot_churn:.1%}  (target ~90%)")

# Self-assessment inflation
mgr5_team_ids = df_employees[df_employees["manager_id"] == BIAS_MANAGER]["employee_id"].tolist()
skl_mgr5 = df_employee_skills[df_employee_skills["employee_id"].isin(mgr5_team_ids)].copy()
skl_other = df_employee_skills[~df_employee_skills["employee_id"].isin(mgr5_team_ids)].copy()
for df_s, label in [(skl_mgr5, "Mgr_5 team"), (skl_other, "Others")]:
    df_s["bias"] = df_s["self_assessed_score"] - df_s["verified_score"]
    print(f"  Avg self-assessment bias ({label:12s})    : {df_s['bias'].mean():.1f} pts")

print("\n── Done. Data ready for pipeline. ───────────────────────────────────\n")
