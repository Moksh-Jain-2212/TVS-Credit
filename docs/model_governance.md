# Model Governance

Every live underwriting result records governance metadata where available:

- underwriting engine version
- risk model version
- feature schema version
- decision policy version
- stress policy version
- repayment-envelope policy version
- behavioral-risk policy version
- evidence-confidence policy version
- evidence-ladder policy version
- timestamp
- evidence mode
- cash-flow forecast method and limitations

The historical repayment-risk model is served through `RiskModelService`, which:

- loads the joblib artifact once
- validates the artifact shape and feature schema
- exposes model metadata and health
- fails on incompatible feature inputs
- gracefully reports missing artifacts

Behavioral-risk probability currently has `POLICY_HEURISTIC` calibration status. It must not be presented as a statistically calibrated probability of default until validated against observed outcomes.

