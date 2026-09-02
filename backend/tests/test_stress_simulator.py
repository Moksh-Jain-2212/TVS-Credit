import json
from pathlib import Path

import pandas as pd

from app.services.stress_simulator import StressPolicy, StressScenario, simulate_borrower_stress
from scripts.add_stress_simulation import add_stress_simulation


def borrower_row() -> pd.Series:
    return pd.Series(
        {
            "loan_id": 1,
            "duration_months": 3,
            "scheduled_payment": 500.0,
            "pre_loan_latest_balance": 2000.0,
            "mean_monthly_inflow": 3000.0,
            "cash_flow_forecast_p10": 200.0,
            "cash_flow_forecast_p50": 1000.0,
            "cash_flow_forecast_p90": 1500.0,
        }
    )


def test_simulate_borrower_stress_returns_required_fields() -> None:
    policy = StressPolicy(
        survival_buffer_floor=0.0,
        scenarios=[
            StressScenario("normal", 1.0, 0.0, "p50"),
            StressScenario("income_minus_30", 0.7, 0.0, "p50"),
            StressScenario("combined_income_expense_shock", 0.8, 1000.0, "p10", 1),
        ],
    )

    result = simulate_borrower_stress(borrower_row(), policy)

    assert result["scenario_survival"]["normal"] is True
    assert 0 <= result["stress_probability"] <= 1
    assert result["worst_scenario"] == "combined_income_expense_shock"
    assert result["worst_projected_period"] >= 1
    assert result["minimum_remaining_cash_buffer"] < 2000.0


def test_temporary_income_shock_recovers_after_configured_months() -> None:
    row = borrower_row()
    row["duration_months"] = 12
    scenario = StressScenario("temporary", 0.5, 0.0, "p50", income_shock_months=2)
    result = simulate_borrower_stress(row, StressPolicy(0.0, [scenario]))

    assert result["scenario_results"][0]["monthly_cash_flow_after_stress"] == -500.0
    # The recurring forecast resumes after month two; the shock is not applied
    # for every month of the loan tenure.
    assert result["minimum_remaining_cash_buffer"] == 0.0


def test_add_stress_simulation_appends_columns_and_is_rerunnable(tmp_path: Path) -> None:
    features_path = tmp_path / "nadi_features.csv"
    policy_path = tmp_path / "stress_scenarios.json"
    pd.DataFrame([borrower_row().to_dict()]).to_csv(features_path, index=False)
    policy_path.write_text(
        json.dumps(
            {
                "survival_buffer_floor": 0,
                "scenarios": [
                    {"name": "normal", "income_multiplier": 1.0, "expense_shock": 0, "cash_flow_quantile": "p50"},
                    {"name": "low_income_period", "income_multiplier": 1.0, "expense_shock": 0, "cash_flow_quantile": "p10"},
                ],
            }
        ),
        encoding="utf-8",
    )

    first = add_stress_simulation(features_path, features_path, policy_path)
    second = add_stress_simulation(features_path, features_path, policy_path)

    assert len(first) == 1
    assert len(second) == 1
    assert "stress_probability" in second.columns
    assert second.loc[0, "stress_probability"] >= 0
    assert not any(column.endswith("_x") or column.endswith("_y") for column in second.columns)
