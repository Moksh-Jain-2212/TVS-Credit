from __future__ import annotations

import pandas as pd

from app.models import AlternativeDataSnapshot, AlternativeSourceType, BorrowerSegment, LoanApplication
from app.services.segment_analysis import apply_segment_analysis, calculate_segment_analysis
from app.services.stress_simulator import simulate_borrower_stress, StressPolicy


def base_row() -> pd.Series:
    return pd.Series(
        {
            "requested_amount": 100000.0,
            "duration_months": 12,
            "scheduled_payment": 9200.0,
            "pre_loan_latest_balance": 70000.0,
            "mean_monthly_inflow": 55000.0,
            "median_monthly_inflow": 52000.0,
            "p10_monthly_inflow": 42000.0,
            "mean_monthly_outflow": 26000.0,
            "mean_monthly_net_cash_flow": 29000.0,
            "positive_cash_flow_month_ratio": 0.83,
            "income_volatility": 0.18,
            "average_balance": 48000.0,
            "minimum_balance": 14000.0,
            "months_of_history": 6,
            "cash_flow_forecast_p10": 24000.0,
            "cash_flow_forecast_p50": 29000.0,
            "cash_flow_forecast_p90": 34000.0,
            "risk_model_probability": 0.31,
        }
    )


def snapshot(source_type: AlternativeSourceType, features: dict) -> AlternativeDataSnapshot:
    return AlternativeDataSnapshot(
        source_type=source_type,
        normalized_features_json=features,
        data_quality_json={"quality_score": 1.0},
        provenance_json={},
    )


def application(segment: BorrowerSegment) -> LoanApplication:
    return LoanApplication(
        requested_amount=100000,
        requested_tenure=12,
        loan_purpose="Two wheeler purchase",
        employment_type=segment.value.lower(),
        borrower_segment=segment,
        declared_monthly_income=55000,
        declared_monthly_expenses=26000,
        existing_monthly_emi=7000,
    )


def test_salaried_segment_uses_conservative_salary_without_direct_risk_change() -> None:
    row = base_row()
    analysis = calculate_segment_analysis(
        application(BorrowerSegment.SALARIED),
        row,
        [
            snapshot(
                AlternativeSourceType.UPI,
                {
                    "monthly_inflow": 50250,
                    "monthly_outflow": 26000,
                    "monthly_net_inflow": 17250,
                    "inflow_stability": 0.97,
                    "recurring_income_indicators": 1,
                },
            )
        ],
    )
    enriched = apply_segment_analysis(row, analysis)

    assert analysis["borrower_segment"] == "SALARIED"
    assert analysis["segment_specific_features"]["p10_salary"] <= analysis["segment_specific_features"]["average_salary"]
    assert enriched["cash_flow_forecast_p10"] == analysis["sustainable_monthly_surplus"]
    assert enriched["risk_model_probability"] == row["risk_model_probability"]


def test_gig_worker_segment_uses_p10_monthly_earnings_and_mobility_support() -> None:
    row = base_row()
    analysis = calculate_segment_analysis(
        application(BorrowerSegment.GIG_WORKER),
        row,
        [
            snapshot(
                AlternativeSourceType.UPI,
                {
                    "monthly_inflow": 42000,
                    "monthly_outflow": 18000,
                    "monthly_net_inflow": 24000,
                    "transactions_per_month": 23,
                    "inflow_stability": 0.76,
                    "concentration": 0.45,
                },
            ),
            snapshot(
                AlternativeSourceType.MOBILITY,
                {
                    "trips_per_month": 86,
                    "distance_per_month": 1185,
                    "vehicle_active_month_ratio": 1.0,
                    "usage_consistency": 0.88,
                },
            ),
        ],
    )

    assert analysis["borrower_segment"] == "GIG_WORKER"
    assert analysis["segment_specific_features"]["p10_monthly_income"] <= analysis["segment_specific_features"]["average_monthly_income"]
    assert analysis["segment_specific_features"]["trips_per_month"] == 86
    assert "MOBILITY" in analysis["connected_relevant_evidence"]


def test_small_merchant_segment_uses_business_surplus_not_turnover() -> None:
    row = base_row()
    analysis = calculate_segment_analysis(
        application(BorrowerSegment.SMALL_MERCHANT),
        row,
        [
            snapshot(
                AlternativeSourceType.GST,
                {
                    "median_monthly_turnover": 220000,
                    "turnover_volatility": 0.16,
                    "turnover_trend": 0.05,
                    "business_inflow_consistency": 0.84,
                },
            ),
            snapshot(
                AlternativeSourceType.UPI,
                {
                    "monthly_inflow": 220000,
                    "monthly_outflow": 175000,
                    "monthly_net_inflow": 45000,
                    "inflow_stability": 0.81,
                },
            ),
        ],
    )

    assert analysis["borrower_segment"] == "SMALL_MERCHANT"
    assert analysis["segment_specific_features"]["monthly_turnover"] == 220000
    assert analysis["segment_specific_features"]["business_surplus"] == 45000
    assert analysis["conservative_income"] < analysis["segment_specific_features"]["monthly_turnover"]


def test_informal_worker_segment_uses_observed_cash_flow_and_utility_confidence() -> None:
    row = base_row()
    analysis = calculate_segment_analysis(
        application(BorrowerSegment.INFORMAL_WORKER),
        row,
        [
            snapshot(
                AlternativeSourceType.UPI,
                {
                    "monthly_inflow": 32000,
                    "monthly_outflow": 18000,
                    "monthly_net_inflow": 14000,
                    "transactions_per_month": 18,
                    "inflow_stability": 0.72,
                    "recurring_income_indicators": 3,
                    "transaction_frequency_stability": 0.78,
                },
            ),
            snapshot(AlternativeSourceType.UTILITIES, {"on_time_payment_ratio": 0.9}),
        ],
    )

    assert analysis["borrower_segment"] == "INFORMAL_WORKER"
    assert analysis["segment_specific_features"]["recurring_credit_patterns"] == 3
    assert analysis["segment_specific_features"]["utility_payment_regularity"] == 0.9
    assert analysis["income_interpretation"].startswith("NADI uses observed cash-flow")


def test_stress_scenarios_are_segment_aware() -> None:
    policy = StressPolicy(survival_buffer_floor=0.0, scenarios=[])
    expected = {
        BorrowerSegment.SALARIED: "salary_minus_20",
        BorrowerSegment.GIG_WORKER: "low_demand_month",
        BorrowerSegment.SMALL_MERCHANT: "business_expenses_plus_15",
        BorrowerSegment.INFORMAL_WORKER: "two_weak_earning_periods",
    }

    for segment, scenario_name in expected.items():
        analysis = calculate_segment_analysis(application(segment), base_row(), [])
        result = simulate_borrower_stress(apply_segment_analysis(base_row(), analysis), policy)

        assert scenario_name in result["scenario_survival"]
