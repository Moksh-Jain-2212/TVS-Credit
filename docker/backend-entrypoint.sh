#!/bin/sh
set -eu

# Raw datasets are intentionally excluded from the image. On a first run,
# create the reproducible fixture used by the demo and integration tests.
if [ ! -f /app/data/processed/nadi_features.csv ] || [ ! -f /app/models/repayment_risk_model.joblib ]; then
  echo "No generated feature artifact found; bootstrapping deterministic demo data..."
  python /app/scripts/bootstrap_demo.py
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
