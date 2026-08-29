# Underwriting Pipeline

NADI keeps three concepts separate:

- Repayment risk: model or behavioral estimate of repayment difficulty.
- Financial capacity: cash flow, stress survival, and safe exposure.
- Evidence confidence: how complete and reliable the evidence is.

Live evidence modes:

- `PKDD_DEMO`: historical bank-derived feature snapshot plus historical model risk.
- `DECLARED_PLUS_ALTERNATIVE_DATA`: declared income/expenses plus normalized alternative evidence.

Cash-flow methods:

- `HISTORICAL_BANK_FORECAST`: historical PKDD forecast.
- `DECLARED_PLUS_ALTERNATIVE_ESTIMATE`: policy heuristic using declared and alternative aggregates.
- `INSUFFICIENT_EVIDENCE`: not enough evidence to estimate responsibly.

Four decision states remain:

- `APPROVE`
- `SAFE_TO_LEARN`
- `EVIDENCE_NEEDED`
- `NOT_CURRENTLY_AFFORDABLE`

`SAFE_TO_LEARN` offers a smaller starter path when the full requested amount is not yet supportable.

