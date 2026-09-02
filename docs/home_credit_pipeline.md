# Home Credit Risk Benchmark

NADI can build an offline, reproducible default-risk benchmark from the Home
Credit Default Risk dataset. It does not mix this dataset with PKDD records and
does not silently use unavailable bureau features during live underwriting.

## Build features

```powershell
python scripts/build_home_credit_features.py `
  --raw-dir data\raw\home_credit
```

This combines the labelled application table with borrower-level aggregates
from `bureau.csv`, `bureau_balance.csv`, and `previous_application.csv`.
It creates debt, overdue, active-credit, recent-application, affordability,
and bureau-repayment-status features. Add `--include-installments` to create
chunked payment-history features from `installments_payments.csv`: late counts,
late-payment ratios, average/max days late, payment shortfalls, coverage, recent
60/90/180/365-day windows, and last 2/3/5 payment summaries.

## Train the benchmark

```powershell
python scripts/train_home_credit_risk_model.py
```

Artifacts include Logistic Regression and HistGradientBoosting comparison,
calibration deciles, and auditable Logistic Regression feature importance. The
highest PR-AUC model is selected and written to `models/home_credit_risk_model.joblib`;
metrics are saved in `models/home_credit_risk_metrics.json`.

## Governance boundary

This artifact is an offline benchmark. Its fields include external-bureau and
historical-loan data that a new NADI applicant may not provide. It must not be
used to score a live application until each input has a consented, documented
source and an equivalent NADI feature mapping. PKDD remains the live demo's
transaction and cash-flow evidence source.
