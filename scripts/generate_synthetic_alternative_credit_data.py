"""Generate a clearly-labelled, privacy-safe synthetic alternative-credit demo dataset.

This creates demo data only. It must never be described as lender performance
or used to make production credit decisions.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_OUTPUT = Path("data/demo/synthetic_alternative_credit_loans.csv")


def generate_dataset(rows: int, seed: int, profile: str = "standard") -> pd.DataFrame:
    if rows < 500:
        raise ValueError("Use at least 500 rows so every temporal split has meaningful demo coverage")
    rng = np.random.default_rng(seed)
    dates = pd.date_range("1993-01-01", "1997-12-31", freq="D")
    loan_date = rng.choice(dates, size=rows)
    segment = rng.choice(["gig_worker", "small_merchant", "informal_worker", "first_time_borrower"], size=rows, p=[0.30, 0.28, 0.24, 0.18])

    monthly_income = np.exp(rng.normal(np.log(28000), 0.48, rows)).clip(7000, 150000)
    requested_amount = (monthly_income * rng.uniform(0.6, 5.0, rows)).clip(5000, 300000)
    tenure = rng.choice([6, 9, 12, 18, 24, 36], size=rows, p=[0.08, 0.10, 0.30, 0.20, 0.22, 0.10])
    upi_stability = rng.beta(5, 2, rows)
    utility_on_time = rng.beta(7, 1.7, rows)
    telecom_regularity = rng.beta(6, 2, rows)
    gst_filing = np.where(segment == "small_merchant", rng.beta(7, 1.8, rows), rng.beta(2, 5, rows))
    ecommerce_stability = np.where(segment == "small_merchant", rng.beta(5, 3, rows), rng.beta(2, 5, rows))
    mobility_consistency = rng.beta(5, 2.5, rows)
    upi_inflow = (monthly_income * rng.uniform(0.55, 1.25, rows)).clip(1000, 180000)
    gst_turnover = np.where(segment == "small_merchant", monthly_income * rng.uniform(1.2, 4.5, rows), 0.0)
    ecommerce_settlement = np.where(segment == "small_merchant", monthly_income * rng.uniform(0.0, 1.5, rows), 0.0)
    missed_utilities = rng.poisson(np.clip((1 - utility_on_time) * 3.5, 0.02, 3.0))
    income_volatility = np.clip(1 - upi_stability + rng.normal(0, 0.07, rows), 0, 1)
    debt_burden = requested_amount / np.maximum(monthly_income * tenure, 1)

    # A deliberately simple synthetic data-generating relationship. It creates
    # plausible labels for an end-to-end demo without claiming causal truth.
    if profile == "showcase":
        # Clearer relationships are intentional for a transparent demo
        # benchmark. This is not representative of real-world performance.
        logit = (
            -3.80
            + 4.80 * debt_burden
            + 3.00 * income_volatility
            + 2.80 * (1 - utility_on_time)
            + 1.30 * (1 - telecom_regularity)
            + 1.60 * (1 - upi_stability)
            + 0.45 * missed_utilities
            + rng.normal(0, 0.22, rows)
        )
        provenance = "SYNTHETIC_SHOWCASE_ONLY"
    else:
        logit = (
            -2.25
            + 2.0 * debt_burden
            + 1.35 * income_volatility
            + 1.1 * (1 - utility_on_time)
            + 0.75 * (1 - telecom_regularity)
            + 0.70 * (1 - upi_stability)
            + 0.28 * missed_utilities
            + rng.normal(0, 0.45, rows)
        )
        provenance = "SYNTHETIC_DEMO_ONLY"
    # The showcase profile has intentionally lower unexplained label noise so
    # a demo can visibly validate feature-to-risk learning end to end.
    probability_scale = 2.5 if profile == "showcase" else 1.0
    default_probability = 1 / (1 + np.exp(-(logit * probability_scale)))
    default_target = rng.binomial(1, default_probability)

    return pd.DataFrame(
        {
            "loan_id": np.arange(9_000_001, 9_000_001 + rows),
            "loan_date": pd.to_datetime(loan_date).strftime("%Y-%m-%d"),
            "borrower_segment": segment,
            "requested_amount": requested_amount.round(2),
            "duration_months": tenure,
            "declared_monthly_income": monthly_income.round(2),
            "upi_30d_inflow": (upi_inflow / 3).round(2),
            "upi_90d_inflow": upi_inflow.round(2),
            "upi_transaction_count": rng.integers(12, 280, rows),
            "upi_stability_score": upi_stability.round(4),
            "utility_on_time_ratio": utility_on_time.round(4),
            "utility_missed_payment_count": missed_utilities,
            "telecom_recharge_regularity": telecom_regularity.round(4),
            "gst_turnover": gst_turnover.round(2),
            "gst_filing_regularity": gst_filing.round(4),
            "ecommerce_settlement_amount": ecommerce_settlement.round(2),
            "ecommerce_settlement_stability": ecommerce_stability.round(4),
            "mobility_usage_consistency": mobility_consistency.round(4),
            "income_volatility": income_volatility.round(4),
            "repayment_outcome_known": True,
            "repayment_default_target": default_target,
            "data_provenance": provenance,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--profile", choices=["standard", "showcase"], default="standard")
    args = parser.parse_args()
    frame = generate_dataset(args.rows, args.seed, args.profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)
    print(f"Wrote {args.output} with {len(frame)} synthetic demo loans.")
    print(f"Default rate: {frame['repayment_default_target'].mean():.2%}")
    print(f"PROVENANCE: {frame['data_provenance'].iloc[0]} - do not claim these are real borrower outcomes.")


if __name__ == "__main__":
    main()
