# TVS NADI - Adaptive Credit Path Engine

NADI is a hackathon MVP for alternative-data underwriting of new-to-credit and thin-file borrowers. It separates repayment risk, financial capacity, and evidence confidence so missing credit history is not treated as automatic high risk.

## Repository Layout

```text
backend/      FastAPI backend, tests, and Python dependencies
frontend/     Future Next.js frontend
data/         Raw and processed local data artifacts
models/       Future trained model artifacts
scripts/      Utility scripts for data and environment workflows
docs/         Project documentation
```

## Backend Setup

Use Python 3.11 or newer.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest
uvicorn app.main:app --reload
```

The backend exposes a basic health check at:

```text
GET /health
```

## Data

Place the raw PKDD `.asc` files under:

```text
data/raw/pkdd/
```

Raw files are local inputs and should not be committed.

## Phase Status

Phase 0 is repository foundation only. Data processing, database persistence, feature engineering, and ML training are intentionally not implemented yet.
