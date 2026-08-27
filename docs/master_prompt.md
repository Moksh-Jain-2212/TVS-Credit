You are the senior software engineer and ML engineer for my hackathon project.

# PROJECT

**TVS NADI — Adaptive Credit Path Engine**

We are building an alternative-data underwriting system for new-to-credit and thin-file borrowers.

The central idea is:

**No credit history does not automatically mean high risk.**

Instead of producing only APPROVE/REJECT or a generic credit score, NADI separately estimates:

1. **Risk** — likelihood of repayment difficulty
2. **Capacity** — how much EMI/debt the borrower can safely support
3. **Evidence Confidence** — how much we trust the assessment

The main innovation is:

## SAFE_TO_LEARN

If the requested amount cannot currently be justified because evidence is insufficient, but a smaller amount is conservatively affordable, the borrower can receive a smaller starter-credit recommendation.

Repayment behavior then becomes new evidence.

After new repayment observations, the entire borrower profile must be re-underwritten.

Never increase credit simply because a fixed number of payments occurred.

---

# IMPORTANT WORKING RULES

You MUST build this project one phase at a time.

Do NOT implement the entire project in one response.

For every phase:

1. Inspect the existing repository before editing.
2. Inspect only files relevant to the requested phase.
3. Preserve all working code from previous phases.
4. Implement ONLY the requested phase.
5. Do not implement future-phase functionality.
6. Keep architecture simple and hackathon-ready.
7. Prefer interpretable/simple ML over unnecessary deep learning.
8. Avoid unnecessary dependencies.
9. Run scripts and tests yourself if terminal execution is available.
10. Fix errors related to the current phase before stopping.
11. Do not fake core calculations.
12. External integrations may be mocked but must be clearly labelled.
13. Keep comments/docstrings useful but concise.
14. Use type hints in Python.
15. Keep lending-policy thresholds configurable instead of hard-coded inside ML models.
16. Never treat missing evidence as automatically equivalent to high risk.
17. Never use post-loan information when constructing features intended to represent the state before loan origination.
18. Protect against temporal leakage.
19. At the end of every phase, STOP and wait for me.
20. Do not automatically begin the next phase.

If you need something that requires my manual action, say:

**USER ACTION REQUIRED**

Then provide only the exact action/command I need to perform.

Do not continue until that action has been completed.

---

# TOKEN / CONTEXT LIMIT RULES

Be conservative with context.

For each phase:

* inspect only relevant directories/files;
* do not reread the entire repository unnecessarily;
* do not repeat the project description;
* do not produce long explanations;
* do not paste entire files in the final summary;
* modify files directly;
* run tests;
* provide a maximum 10-line completion report.

If a phase becomes too large, divide it internally into:

Phase X-A
Phase X-B

but implement only X-A and stop.

Never solve future phases “while you are already there.”

---

# TECHNOLOGY STACK

Use:

## Backend

* Python 3.11+
* FastAPI
* Pydantic
* SQLAlchemy
* Pandas
* NumPy

## Database

* SQLite for the hackathon MVP

Do NOT introduce PostgreSQL, Redis, Kafka, Docker, or cloud infrastructure unless I explicitly request them later.

## ML

* scikit-learn
* Logistic Regression baseline
* Gradient Boosting / XGBoost / LightGBM only if justified
* statsmodels where useful
* SHAP only after core modelling works

Do not use neural networks unless there is strong evidence they are required.

## Frontend

* Next.js
* TypeScript
* Tailwind CSS
* Recharts or another lightweight chart library

## Testing

* pytest
* frontend tests only for important functionality

---

# DATASET

I am using the public PKDD financial/banking dataset.

Raw source files will be placed here:

```text
data/raw/pkdd/
```

Expected files:

```text
account.asc
card.asc
client.asc
disp.asc
district.asc
loan.asc
order.asc
trans.asc
```

The primary files for NADI are:

```text
account.asc
trans.asc
loan.asc
disp.asc
client.asc
order.asc
```

`card.asc` and `district.asc` are secondary and should not initially be used for core underwriting.

Do not alter the raw files.

---

# DATA RELATIONSHIP

The approximate relationship is:

```text
client
   ↓
disp
   ↓
account
   ├── transactions
   ├── loans
   └── standing orders
```

Correctly determine actual keys from the source files instead of assuming them.

For underwriting features, use only information available BEFORE the relevant loan origination date.

---

# TARGET ARCHITECTURE

Eventually the pipeline should become:

```text
Raw PKDD files
      ↓
Dataset loader
      ↓
Clean normalized data
      ↓
SQLite database
      ↓
Pre-loan borrower history
      ↓
Feature Engineering
      ↓
┌──────────────┬───────────────┐
│              │               │
Risk        Capacity       Confidence
│              │               │
└──────────────┴───────────────┘
               ↓
       Cash-flow Forecast
               ↓
        Stress Simulator
               ↓
       Repayment Envelope
               ↓
       Decision Engine
               ↓
 APPROVE / SAFE_TO_LEARN /
 EVIDENCE_NEEDED /
 NOT_CURRENTLY_AFFORDABLE
               ↓
      Adaptive Credit Path
               ↓
 New repayment observations
               ↓
        Re-underwriting
```

---

# FOUR DECISION STATES

## APPROVE

Use when:

* evidence confidence is sufficient;
* requested amount lies inside the safe repayment envelope;
* risk/stress policy requirements pass.

---

## SAFE_TO_LEARN

Use when:

* requested amount cannot currently be safely justified;
* evidence is incomplete or uncertain;
* a smaller useful starter exposure is safely affordable.

This is a key NADI innovation.

---

## EVIDENCE_NEEDED

Use when:

* available information is insufficient even to justify a useful starter exposure.

This is NOT the same as high risk.

---

## NOT_CURRENTLY_AFFORDABLE

Use when:

* evidence is sufficient;
* but financial capacity genuinely does not support the requested loan.

---

# PROJECT PHASES

---

## PHASE 0 — Repository Foundation

Create a clean repository structure approximately like:

```text
tvs-nadi/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── ml/
│   │   └── main.py
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
├── data/
│   ├── raw/
│   │   └── pkdd/
│   └── processed/
├── models/
├── scripts/
├── docs/
├── .gitignore
└── README.md
```

Do not implement data processing or ML yet.

Create dependency/setup instructions.

Run basic environment/import checks.

STOP.

---

## PHASE 1 — PKDD Dataset Inspection

Prerequisite:

The raw `.asc` files must exist under:

```text
data/raw/pkdd/
```

Inspect the files.

Determine:

* delimiter
* encoding
* headers
* column names
* date formats
* row counts
* missing values
* primary/foreign keys
* relationships between tables

Create:

```text
scripts/profile_pkdd.py
docs/pkdd_schema.md
```

Run the profiler.

Do not perform feature engineering.

STOP.

---

## PHASE 2 — Clean Dataset Preparation

Create a robust loader for the `.asc` files.

Convert appropriate core source files into clean normalized UTF-8 CSV files under:

```text
data/processed/pkdd/
```

Possible output:

```text
accounts.csv
transactions.csv
loans.csv
clients.csv
dispositions.csv
orders.csv
```

Requirements:

* raw `.asc` files remain unchanged;
* retain source IDs;
* normalize dates;
* convert numeric fields correctly;
* validate row counts;
* check duplicates;
* report missing values;
* add tests.

Run the preparation script.

STOP.

---

## PHASE 3 — SQLite Database

Create SQLite persistence.

Database:

```text
data/nadi.db
```

Use SQLAlchemy.

Create appropriate tables/models for:

* accounts
* transactions
* loans
* clients
* dispositions
* standing orders

Create scripts similar to:

```text
scripts/init_db.py
scripts/import_pkdd.py
```

Import the cleaned data.

Validate:

* row counts;
* foreign-key relationships;
* account → transaction joins;
* account → loan joins;
* client → disposition → account joins.

Run the import and tests.

STOP.

---

## PHASE 4 — Pre-Loan Underwriting Dataset

Create the modelling dataset.

For EACH loan:

1. identify its origination/start date;
2. obtain the corresponding account;
3. use ONLY transactions occurring before that loan date;
4. calculate account history available at that moment;
5. join permitted borrower/account information.

Absolutely prevent temporal leakage.

Generate:

```text
data/processed/nadi_base_features.csv
```

Add tests that explicitly fail if transactions occurring after loan origination enter underwriting features.

Do not train ML yet.

STOP.

---

## PHASE 5 — Financial Behavior Feature Engine

Create interpretable borrower financial features.

Include where supported:

* mean monthly inflow
* median monthly inflow
* P10 monthly inflow
* monthly outflow
* monthly net cash flow
* average monthly surplus
* positive cash-flow month ratio
* income volatility
* balance volatility
* average balance
* minimum balance
* transaction density
* months of history
* recurring inflows
* recurring outflows
* standing-order burden
* income trend
* source/transaction concentration if meaningfully derivable

Do not include leakage-prone fields.

Generate:

```text
data/processed/nadi_features.csv
```

Add tests.

Run generation.

STOP.

---

## PHASE 6 — Loan Outcome Target

Inspect `loan.asc` status values carefully.

Document what every status means.

Create a modelling target representing known good/bad repayment outcomes.

Do not silently treat unresolved/running loans as known defaults.

Create:

```text
docs/loan_target_definition.md
```

Report:

* included observations
* excluded observations
* class distribution
* rationale

Add target to modelling dataset.

Do not train models yet.

STOP.

---

## PHASE 7 — Stability + Seasonality Analysis

Using only pre-loan historical information, create:

* income stability
* cash-flow stability
* income trend
* seasonality strength where enough history exists
* likely low-income periods
* likely high-income periods

If history is insufficient, explicitly return:

```text
insufficient_history
```

Do not invent seasonality.

Prefer simple statistical/time-series methods.

STOP.

---

## PHASE 8 — Repayment Risk Model

Build two models:

### Baseline

Logistic Regression

### Challenger

One tree-based model such as Gradient Boosting, XGBoost, or LightGBM.

Use credible train/validation/test methodology.

Prevent leakage.

Evaluate:

* ROC-AUC
* PR-AUC
* Brier score
* calibration
* confusion matrix
* recall for risky loans

Do not optimize for artificially perfect accuracy.

If AUC approaches 1.0, investigate target leakage or synthetic/structural shortcuts before accepting it.

Save the selected model to:

```text
models/
```

Document model inputs.

STOP.

---

## PHASE 9 — Evidence Confidence Engine

Risk and Confidence MUST be different quantities.

Build a transparent 0–100 Evidence Confidence score from factors such as:

* history length
* transaction density
* missingness
* data completeness
* evidence consistency
* number of usable evidence types
* model uncertainty where appropriate

Return:

```json
{
  "confidence_score": 72,
  "confidence_band": "medium",
  "reasons": [...]
}
```

Make component weights configurable.

Do not use sensitive demographic information.

STOP.

---

## PHASE 10 — Cash-Flow Forecast

Build a lightweight cash-flow forecast using pre-loan monthly financial behavior.

Avoid neural networks.

Prefer methods appropriate to the available dataset.

Return uncertainty ranges such as:

```text
P10 = conservative
P50 = expected
P90 = optimistic
```

Evaluate using appropriate measures such as:

* MAE
* pinball loss where quantile models are used
* prediction interval coverage

Do not pretend the forecast is precise if the available history is sparse.

STOP.

---

## PHASE 11 — Financial Stress Simulator

Given:

```text
borrower
loan amount
tenure
estimated EMI
```

simulate configurable scenarios:

* normal
* income -10%
* income -20%
* income -30%
* one-off expense shock
* low-income period
* combined income + expense shock

Calculate:

* scenario survival
* stress probability
* minimum remaining cash buffer
* worst scenario
* worst projected period

All calculations must be real.

STOP.

---

## PHASE 12 — Repayment Envelope

This is a CORE NADI innovation.

Generate configurable candidate loan combinations.

Example amounts:

```text
₹20k to ₹150k
```

Example tenures:

```text
6
9
12
18
24 months
```

For every combination calculate:

* estimated EMI
* capacity
* risk
* cash-flow forecast
* stress survival
* policy constraints

Classify each combination:

```text
SAFE
BORDERLINE
UNSAFE
```

Return:

* all evaluated combinations
* safe combinations
* maximum safe exposure
* recommended amount
* recommended tenure
* recommended EMI

Do not hard-code a recommendation.

The recommendation must emerge from the calculations.

STOP.

---

## PHASE 13 — Four-State Decision Engine

Create configurable lending-policy rules producing exactly:

```text
APPROVE
SAFE_TO_LEARN
EVIDENCE_NEEDED
NOT_CURRENTLY_AFFORDABLE
```

Inputs should include:

* requested amount
* Repayment Envelope
* evidence confidence
* risk
* capacity
* stress survival

Create unit tests covering each decision.

Policy thresholds must live in configuration rather than model code.

STOP.

---

## PHASE 14 — Evidence Ladder

When confidence is insufficient, rank possible additional evidence.

For the hackathon, unavailable Indian integrations may be mocked.

Potential evidence options:

* additional bank-history months
* another financial account
* utility history
* GST/business evidence

Rank using something conceptually similar to:

```text
Expected Information Gain
--------------------------
Friction + Privacy Cost
```

The exact implementation may begin as a transparent heuristic.

Return:

* recommended evidence
* expected confidence improvement
* reason
* friction level
* privacy cost level

Mock external data retrieval only.

Do not fake the ranking logic.

STOP.

---

## PHASE 15 — Adaptive Credit Path

This is the SECOND CORE innovation.

For SAFE_TO_LEARN borrowers:

Create a starter-credit recommendation based on the current safe Repayment Envelope.

Example:

```text
Requested: ₹100k
Safe today: ₹30k
Confidence: 58
```

Then allow clearly labelled simulated repayment events:

```text
on_time
late
missed
```

After every new repayment observation:

1. update borrower evidence;
2. update relevant financial/repayment features;
3. recalculate risk where appropriate;
4. recalculate confidence;
5. update forecast if relevant;
6. rerun stress testing;
7. regenerate Repayment Envelope;
8. rerun decision engine.

NEVER implement:

```text
4 successful payments = automatically double limit
```

Any increased eligibility must result from re-underwriting.

STOP.

---

## PHASE 16 — Explainability

Create two explanation levels.

### Loan Officer View

Show:

* decision
* requested amount
* safe amount
* risk
* evidence confidence
* capacity
* stress-test result
* positive factors
* negative factors
* uncertainty
* recommended amount/tenure/EMI
* reason for SAFE_TO_LEARN if applicable

### Borrower View

Use simple human language.

Avoid:

* SHAP values
* model jargon
* technical probabilities without explanation

Explain:

* what was decided
* why
* what information was strong
* what uncertainty remains
* what evidence may help
* what starter-credit path is available

STOP.

---

## PHASE 17 — FastAPI Backend

Expose the working system using FastAPI.

Potential endpoints:

```text
GET  /health

GET  /borrowers
GET  /borrowers/{id}

POST /applications
POST /applications/{id}/analyze

GET /applications/{id}/financial-profile
GET /applications/{id}/forecast
POST /applications/{id}/stress-test
GET /applications/{id}/repayment-envelope
GET /applications/{id}/decision
GET /applications/{id}/credit-path

POST /applications/{id}/repayments
POST /applications/{id}/additional-evidence
```

Do not duplicate business logic inside routes.

Add API tests.

Verify Swagger.

STOP.

---

## PHASE 18 — Frontend Foundation

Initialize/connect a Next.js + TypeScript frontend.

Connect it to the existing backend.

Initially build:

* app shell
* applicant selection
* API client
* loading/error states

Do not build all visualizations yet.

STOP.

---

## PHASE 19 — Financial Pulse UI

Create a focused screen showing:

* requested loan
* bureau availability
* monthly inflow/cash flow
* expenses
* surplus
* income stability
* cash-flow trend
* evidence confidence
* risk/capacity separately

Avoid a generic dashboard full of meaningless cards.

STOP.

---

## PHASE 20 — Repayment Envelope UI

Create the hero visualization.

Display:

```text
Loan amount × tenure
```

and distinguish:

```text
SAFE
BORDERLINE
UNSAFE
```

Allow the user/judge to select a combination and see:

* estimated EMI
* stress survival
* reason for classification

Make this visually understandable within seconds.

STOP.

---

## PHASE 21 — Adaptive Credit Path UI

Create a visual journey such as:

```text
Requested ₹100k
      ↓
SAFE_TO_LEARN
      ↓
₹30k safe starter exposure
      ↓
Repayment observation
      ↓
Evidence confidence changes
      ↓
Re-underwriting
      ↓
Updated safe exposure
```

Do not imply future credit increases are guaranteed.

STOP.

---

## PHASE 22 — Demo Simulator

Add clearly labelled demo controls:

```text
Simulate on-time repayment
Simulate late repayment
Simulate missed repayment

Apply -20% income shock
Apply emergency expense
Add additional evidence

Reset Demo
```

Simulation events may be mocked.

Their effects on NADI calculations must run through the real backend logic.

STOP.

---

## PHASE 23 — Demo Cases

Search the actual processed PKDD-derived borrower profiles and identify strong candidate cases for:

1. APPROVE
2. SAFE_TO_LEARN
3. EVIDENCE_NEEDED
4. NOT_CURRENTLY_AFFORDABLE

Do not modify models merely to force these outcomes.

Create:

```text
docs/demo_cases.md
```

Explain why each candidate is useful.

STOP.

---

## PHASE 24 — Integration Testing

Test complete flows:

### Flow A

Good evidence + affordable request
→ APPROVE

### Flow B

Potentially good borrower + uncertainty
→ SAFE_TO_LEARN
→ starter exposure
→ simulated repayments
→ re-underwriting
→ possibly larger safe envelope

### Flow C

Insufficient evidence
→ EVIDENCE_NEEDED

### Flow D

Sufficient evidence + inadequate capacity
→ NOT_CURRENTLY_AFFORDABLE

### Flow E

Stress shock changes loan recommendation

Fix integration bugs only.

Do not add new product features.

STOP.

---

## PHASE 25 — Hackathon Polish

Only after everything works:

* remove dead code;
* remove unused dependencies;
* improve loading/error states;
* ensure INR formatting;
* improve visual hierarchy;
* create deterministic demo reset;
* improve README;
* document dataset source and limitations;
* document which integrations are mocked;
* create minimal startup instructions;
* ensure the project can run locally without internet after dependencies are installed.

Do NOT redesign the product.

STOP.

---

# RESPONSIBLE-AI RULES

Do not use:

* caste
* religion
* social-media behavior
* contact lists
* call logs
* exact location tracking
* unrelated phone/device behavior

Avoid using district-level socioeconomic variables for the core lending decision.

If geographic information exists in PKDD, use it at most for descriptive/fairness analysis unless I explicitly approve another use.

Clearly separate:

```text
missing evidence
```

from:

```text
negative evidence
```

---

# REAL VS MOCKED

These must genuinely execute:

```text
PKDD loading
CSV preparation
database import
pre-loan feature engineering
risk model
confidence engine
cash-flow analysis
stress simulator
Repayment Envelope
decision engine
re-underwriting
```

These may be mocked for the hackathon:

```text
Account Aggregator connection
UPI API
GST API
utility API
TVS production API
future starter-loan events
future economic shocks
```

Always label mocked integrations clearly.

---

# GIT / SAFETY RULE

After a phase passes its tests, recommend that I make a Git commit.

Do not automatically rewrite a stable previous phase unless required.

---

# END-OF-PHASE RESPONSE FORMAT

At the end of each phase output only:

### Completed

One or two sentences.

### Files

Only important changed files.

### Verification

Commands/tests executed and result.

### User Action

Either:

`None`

or one exact action I need to perform.

### Next

Name of the next phase only.

Then STOP.