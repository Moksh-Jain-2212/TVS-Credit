# Phase 23 Demo Cases

Generated from the actual processed PKDD-derived feature dataset:

```text
data/processed/nadi_features.csv
```

No model thresholds or borrower profiles were changed for this search.

## Current Decision Coverage

| Decision state | Row count | Demo status |
| --- | ---: | --- |
| APPROVE | 0 | No exact current case |
| SAFE_TO_LEARN | 7 | Exact case available |
| EVIDENCE_NEEDED | 0 | No exact current case |
| NOT_CURRENTLY_AFFORDABLE | 675 | Exact case available |

## Recommended Demo Cases

| Demo need | Loan ID | Account ID | Current decision | Why this case is useful |
| --- | ---: | ---: | --- | --- |
| APPROVE-adjacent | 6819 | 9031 | SAFE_TO_LEARN | Closest current profile to approval: requested INR 50,112 and maximum safe exposure is INR 50,000, with low risk probability 0.002 and stress probability 0.000. Use this to show the strict envelope boundary without claiming it is an approved case. |
| SAFE_TO_LEARN | 5161 | 1012 | SAFE_TO_LEARN | Cleanest starter-credit story: requested INR 98,184, starter exposure INR 50,000, high confidence score 75, low risk probability 0.002, and three simulated repayment observations for the adaptive path view. |
| EVIDENCE_NEEDED-adjacent | 5063 | 442 | NOT_CURRENTLY_AFFORDABLE | Lowest confidence score found in the current processed dataset: 56, with only 4 months of history and transaction density 0.5. The evidence ladder recommends additional bank history with expected confidence improvement 29.16, but the current policy still classifies it as not currently affordable because risk is high and safe exposure is zero. |
| NOT_CURRENTLY_AFFORDABLE | 6097 | 5362 | NOT_CURRENTLY_AFFORDABLE | Strong capacity-failure example with sufficient evidence: confidence score 94, low risk probability 0.001, requested INR 202,848, maximum safe exposure INR 0, stress probability 1.000, and conservative cash-flow forecast INR -20,756. |

## Demo Notes

- Use loan `5161` for the main SAFE_TO_LEARN adaptive-path walkthrough.
- Use loan `6819` when a judge asks what an approval-like borrower looks like under the current envelope policy.
- Use loan `5063` to explain additional-evidence behavior, while clearly saying it is not an exact EVIDENCE_NEEDED decision in this snapshot.
- Use loan `6097` to show that NADI separates risk and capacity: evidence and model risk can look strong while stress-adjusted affordability still fails.
