# TVS NADI - Adaptive Credit Path Engine

NADI is a hackathon MVP for alternative-data underwriting of new-to-credit and thin-file borrowers. It separates repayment risk, financial capacity, and evidence confidence so missing credit history is not treated as automatic high risk.

## Repository Layout

```text
backend/      FastAPI backend, tests, and Python dependencies
frontend/     Next.js borrower and admin interface
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

## Platform Underwriting

Borrowers can submit with either PKDD demo bank evidence or at least one consented alternative-data source. Supported alternative sources are GST/business, UPI, telecom recharge, utility bills, e-commerce settlements, and mobility/vehicle activity. Current connectors are local mock/manual adapters that normalize aggregate signals only; raw external payloads, raw counterparties, exact GPS, call logs, SMS, contacts, and protected traits are not persisted in underwriting views.

NADI keeps historical model risk separate from behavioral risk. `risk_probability` is the current combined risk used by the decision engine. Admin responses also expose `historical_model_risk_probability`, `behavioral_risk_probability`, behavioral data coverage, confidence, source component scores, and factor contributions.

Evidence confidence and the evidence ladder now account for alternative-data coverage. Missing alternative sources are treated as missing evidence, not adverse behavior.

## Email OTP Setup

TVS NADI supports real OTP delivery through backend-only SMTP settings. For Gmail SMTP, use environment variables like:

```text
OTP_DELIVERY_MODE=SMTP_EMAIL
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=<gmail-address>
SMTP_PASSWORD=<google-app-password>
SMTP_FROM_EMAIL=<gmail-address>
SMTP_FROM_NAME=TVS NADI
SMTP_USE_TLS=true
```

Gmail commonly requires a Google App Password instead of the normal Google account password. Do not put real SMTP passwords in source control or frontend environment files.

For automated tests or local fallback, set:

```text
OTP_DELIVERY_MODE=MOCK_CONSOLE
```

In `SMTP_EMAIL` mode the API never returns the OTP. The user receives it by email and enters it on `/verify-otp`.

## Grok Explainability

Admin users can request an optional structured Grok/xAI explanation for an application. The backend sends a de-identified underwriting payload only and caches responses by input hash. Local runs work without xAI credentials and return a deterministic fallback explanation.

```text
GROK_EXPLANATION_ENABLED=false
XAI_API_KEY=
XAI_MODEL=grok-4.6
XAI_BASE_URL=https://api.x.ai/v1
```

Keep xAI credentials backend-only. Do not place them in `NEXT_PUBLIC_*` variables.

## Data

Place the raw PKDD `.asc` files under:

```text
data/raw/pkdd/
```

Raw files are local inputs and should not be committed.

## Current Status

The project includes the FastAPI API, app database persistence, OTP login, borrower application flow, admin review flow, PKDD demo analysis, alternative-data behavioral underwriting, and optional Grok explainability.
