# TVS NADI - Adaptive Credit Path Engine

TVS NADI is a production-oriented underwriting prototype for new-to-credit and thin-file borrowers. Its core principle is simple: missing credit history is uncertainty, not automatically high risk.

NADI separates:

- repayment risk
- financial capacity
- evidence confidence

The decision engine keeps four states:

- `APPROVE`
- `SAFE_TO_LEARN`
- `EVIDENCE_NEEDED`
- `NOT_CURRENTLY_AFFORDABLE`

`SAFE_TO_LEARN` is the starter-credit path: when the full request is not safely supportable, NADI can recommend a smaller exposure that may grow with successful repayment behavior.

## Architecture

```text
backend/      FastAPI, SQLAlchemy, SQLite, underwriting services, tests
frontend/     Next.js borrower and admin portals
data/         Local raw/processed artifacts, ignored where sensitive
models/       Trained model artifacts
scripts/      Reproducible bootstrap, data, model, and policy scripts
docs/         Architecture, security, governance, and evaluation notes
```

See:

- `docs/architecture.md`
- `docs/underwriting_pipeline.md`
- `docs/security.md`
- `docs/model_governance.md`
- `docs/policy_evaluation.md`

## Local Setup

Use Python 3.11+ and Node 22+.

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
npm --prefix frontend install
make bootstrap
```

Run the app:

```bash
cd backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm run dev
```

URLs:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:3000`
- Health: `GET /health`
- Readiness: `GET /ready`

## Demo Bootstrap

`make bootstrap` runs `scripts/bootstrap_demo.py`.

It initializes databases, detects local PKDD raw files, prepares/imports data, generates features, trains the historical model, scores confidence, forecasts cash flow, runs stress tests, builds repayment envelopes, creates NADI decisions, prepares explainability, writes policy evaluation docs, and creates a demo admin if configured.

If raw PKDD files are unavailable, the bootstrap creates a small deterministic fixture so tests and CI can still run without distributing raw data.

Default demo admin:

```text
admin@example.com
admin-pass-1
```

Override with:

```text
BOOTSTRAP_ADMIN_EMAIL=
BOOTSTRAP_ADMIN_PASSWORD=
BOOTSTRAP_CREATE_ADMIN=false
```

## Alternative Data

Borrowers can submit with PKDD demo bank evidence or at least one consented alternative-data source:

- GST / business
- UPI
- telecom recharge
- utility bills
- e-commerce settlements
- mobility / vehicle activity

NADI stores normalized aggregate signals, not unnecessary raw sensitive data. It does not persist SMS content, call logs, contacts, exact GPS trails, raw UPI counterparties, protected traits, or unrelated shopping preference inference.

Missing alternative sources are treated as missing evidence, not negative behavior.

## ML Model

The historical repayment-risk model is trained by `scripts/train_risk_model.py` and served by `RiskModelService`.

Model serving:

- loads the artifact once
- validates the feature schema
- exposes metadata and health
- records model/schema versions in underwriting results
- fails loudly on incompatible features
- gracefully handles a missing artifact

Behavioral risk is separate. Its current probability field is marked `POLICY_HEURISTIC` until calibrated against observed outcomes.

## Underwriting Pipeline

Live underwriting builds a typed context from one of two evidence modes:

- `PKDD_DEMO`
- `DECLARED_PLUS_ALTERNATIVE_DATA`

Then NADI runs:

```text
Evidence Provider -> Underwriting Context -> Risk + Capacity + Confidence
-> Stress -> Repayment Envelope -> Decision -> Explanation
```

Cash-flow outputs distinguish:

- `HISTORICAL_BANK_FORECAST`
- `DECLARED_PLUS_ALTERNATIVE_ESTIMATE`
- `INSUFFICIENT_EVIDENCE`

## Grok Explainability

Grok/xAI is optional and explanation-only. It never makes credit decisions.

```text
GROK_EXPLANATION_ENABLED=false
XAI_API_KEY=
XAI_MODEL=grok-4.6
XAI_BASE_URL=https://api.x.ai/v1
```

The backend sends a de-identified underwriting payload and caches responses by input hash. Without credentials, the API returns a deterministic fallback explanation.

## Security

Implemented:

- email normalization and password strength validation
- PBKDF2 password hashing
- short-lived access tokens
- rotating refresh tokens
- backend logout with refresh-session revocation
- OTP expiry, retry limits, resend cooldown
- basic auth route rate limits
- configurable CORS
- request IDs and security headers
- standardized error envelopes

Production guidance:

- use backend-only secrets
- prefer secure HttpOnly cookies for browser token transport
- use Redis or another shared store for rate limits
- run Alembic migrations against a managed database
- do not log passwords, OTPs, bearer tokens, refresh tokens, or raw financial payloads

## Database

Local development uses SQLite. Production-oriented migration scaffolding is under:

```text
backend/alembic.ini
backend/alembic/
```

Use `APP_DATABASE_URL` for managed database URLs or `APP_DATABASE_PATH` for SQLite.

## Testing

```bash
make test
make build
```

CI runs backend tests and the frontend production build with deterministic settings.
